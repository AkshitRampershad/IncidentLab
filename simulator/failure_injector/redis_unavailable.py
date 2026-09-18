from datetime import datetime, timedelta

from simulator.models import Deployment, GroundTruth, IncidentDraft, LogEvent, MetricPoint

from .base import FailureInjector

SCENARIO_ID = "redis_unavailable"
AFFECTED_SERVICE = "checkout"
UNRELATED_SERVICE = "search"

# Number of "redis connection refused" error log lines the outage produces.
_ERROR_LOG_COUNT = 10


class RedisUnavailableInjector(FailureInjector):
    """Scenario 2 (spec §23): Redis becomes unreachable. Per
    knowledge/architecture/checkout-service.md, checkout is designed to
    fall through to Postgres on any cache miss — so this degrades latency
    without spiking the error rate, and must NOT trigger the
    "connection pool exhaustion" pattern at all (no "pool exhausted" or
    "connection timeout" wording anywhere here). This is the scenario that
    actually tests whether the system can tell two different root causes
    apart, rather than always landing on the one hypothesis a single
    scenario happens to favor.

    Ground truth: redis_unavailable / redis / dependency_outage.
    """

    scenario_id = SCENARIO_ID

    def generate(self, anchor_time: datetime) -> IncidentDraft:
        start_time = anchor_time - timedelta(minutes=15)
        end_time = anchor_time

        logs: list[LogEvent] = []
        metrics: list[MetricPoint] = []
        deployments: list[Deployment] = []

        # --- Distractor: unrelated deployment to a different service.
        deployments.append(
            Deployment(
                service=UNRELATED_SERVICE,
                timestamp=start_time - timedelta(minutes=12),
                version="v2.3.0",
                commit_sha="7c4e1fa",
                description="Add typo-tolerant search ranking",
                is_distractor=True,
            )
        )

        # --- Baseline: everything healthy — cache hits, low DB load.
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time,
                metric_name="cache_hit_rate",
                value=0.85,
            )
        )
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time,
                metric_name="db_connections_active",
                value=2,
                is_distractor=True,  # healthy reading — offered as a red herring, not a finding
            )
        )

        # --- Redis becomes unreachable.
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=2),
                metric_name="cache_hit_rate",
                value=0.05,
            )
        )
        for i in range(_ERROR_LOG_COUNT):
            logs.append(
                LogEvent(
                    service=AFFECTED_SERVICE,
                    timestamp=start_time + timedelta(minutes=2, seconds=6 * i),
                    level="error",
                    message=(
                        f"redis connection refused: falling through to primary datastore "
                        f"request_id=req-{i:05d}"
                    ),
                )
            )

        # --- Impact: latency rises (extra Postgres round-trips replacing
        # cache hits), but error rate stays low — checkout keeps working,
        # just slower. This is the signal that should stop the system from
        # mistaking this for a connection-pool incident.
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=3),
                metric_name="latency_p99_ms",
                value=650,
            )
        )
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=3),
                metric_name="error_rate",
                value=0.02,
                is_distractor=True,  # confirmed-normal reading, not a finding
            )
        )

        # --- Distractor: a normal, healthy log line among the errors.
        logs.append(
            LogEvent(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=5),
                level="info",
                message="checkout order confirmed for cart:5127",
                is_distractor=True,
            )
        )

        return IncidentDraft(
            service=AFFECTED_SERVICE,
            severity="warning",
            description="Checkout API latency elevated, cache hit rate collapsed",
            start_time=start_time,
            end_time=end_time,
            ground_truth=GroundTruth(
                scenario_id=SCENARIO_ID,
                root_cause="redis_unavailable",
                affected_component="redis",
                trigger="dependency_outage",
            ),
            logs=logs,
            metrics=metrics,
            deployments=deployments,
        )
