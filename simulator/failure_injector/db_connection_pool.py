from datetime import datetime, timedelta

from simulator.models import Deployment, GroundTruth, IncidentDraft, LogEvent, MetricPoint

from .base import FailureInjector

SCENARIO_ID = "db_connection_pool"
AFFECTED_SERVICE = "checkout"
UNRELATED_SERVICE = "auth"

# Number of "connection timeout" error log lines the exhausted pool produces.
_ERROR_LOG_COUNT = 12


class DbConnectionPoolInjector(FailureInjector):
    """Scenario 1 (spec §23): a deploy shrinks checkout's DB connection pool
    from 50 to 5, which saturates within minutes and starts rejecting
    checkout requests.

    Ground truth: database_connection_pool_exhaustion / postgres / deployment.
    """

    scenario_id = SCENARIO_ID

    def generate(self, anchor_time: datetime) -> IncidentDraft:
        start_time = anchor_time - timedelta(minutes=15)
        end_time = anchor_time

        logs: list[LogEvent] = []
        metrics: list[MetricPoint] = []
        deployments: list[Deployment] = []

        # --- Distractor: unrelated deployment to a different service, well
        # before the incident window, per spec §24 ("unrelated deployment").
        deployments.append(
            Deployment(
                service=UNRELATED_SERVICE,
                timestamp=start_time - timedelta(minutes=10),
                version="v4.12.0",
                commit_sha="9f1c2ab",
                description="Extend auth token expiry from 12h to 24h",
                is_distractor=True,
            )
        )

        # --- The actual trigger: the connection-pool deploy, ~1 minute
        # before the incident starts (spec §13's "60 seconds before").
        deployments.append(
            Deployment(
                service=AFFECTED_SERVICE,
                timestamp=start_time - timedelta(minutes=1),
                version="v1.842.0",
                commit_sha="a1b2c3d",
                description="Reduce checkout-db connection pool size from 50 to 5",
            )
        )

        # --- Baseline: pool already shrunk, a few connections in use, still
        # under capacity.
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time,
                metric_name="db_connection_pool_size",
                value=5,
            )
        )
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time,
                metric_name="db_connections_active",
                value=4,
            )
        )

        # --- Distractor: a routine Redis warning, unrelated to Postgres.
        logs.append(
            LogEvent(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=1),
                level="warning",
                message="redis cache eviction warning: memory usage at 85%",
                is_distractor=True,
            )
        )

        # --- Pool saturates.
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=2),
                metric_name="db_connections_active",
                value=5,
            )
        )
        for i in range(_ERROR_LOG_COUNT):
            logs.append(
                LogEvent(
                    service=AFFECTED_SERVICE,
                    timestamp=start_time + timedelta(minutes=2, seconds=5 * i),
                    level="error",
                    message=(
                        f"database connection timeout after 30000ms "
                        f"(pool exhausted, active=5/5) request_id=req-{i:05d}"
                    ),
                )
            )

        # --- Customer-visible impact.
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=3),
                metric_name="error_rate",
                value=0.42,
            )
        )
        metrics.append(
            MetricPoint(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=3),
                metric_name="latency_p99_ms",
                value=3200,
            )
        )

        # --- Distractor: a CPU blip on a completely unrelated service.
        metrics.append(
            MetricPoint(
                service=UNRELATED_SERVICE,
                timestamp=start_time + timedelta(minutes=4),
                metric_name="cpu_usage_percent",
                value=78,
                is_distractor=True,
            )
        )

        # --- Distractor: a normal, healthy log line among the errors.
        logs.append(
            LogEvent(
                service=AFFECTED_SERVICE,
                timestamp=start_time + timedelta(minutes=5),
                level="info",
                message="cache miss for cart:8391, fetching from primary",
                is_distractor=True,
            )
        )

        return IncidentDraft(
            service=AFFECTED_SERVICE,
            severity="critical",
            description="Checkout API error rate increased to 42%",
            start_time=start_time,
            end_time=end_time,
            ground_truth=GroundTruth(
                scenario_id=SCENARIO_ID,
                root_cause="database_connection_pool_exhaustion",
                affected_component="postgres",
                trigger="deployment",
            ),
            logs=logs,
            metrics=metrics,
            deployments=deployments,
        )
