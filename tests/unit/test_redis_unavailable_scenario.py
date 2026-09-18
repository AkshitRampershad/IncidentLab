from datetime import UTC, datetime, timedelta

from simulator.failure_injector.redis_unavailable import RedisUnavailableInjector

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def test_generation_is_deterministic():
    injector = RedisUnavailableInjector()
    assert injector.generate(ANCHOR) == injector.generate(ANCHOR)


def test_ground_truth_is_redis_not_database():
    draft = RedisUnavailableInjector().generate(ANCHOR)
    assert draft.ground_truth.scenario_id == "redis_unavailable"
    assert draft.ground_truth.root_cause == "redis_unavailable"
    assert draft.ground_truth.affected_component == "redis"
    assert draft.ground_truth.trigger == "dependency_outage"


def test_no_trigger_deployment_exists():
    """Unlike db_connection_pool, this scenario has no deploy to the
    affected service at all — the trigger is a dependency outage, not a
    deployment. Only the distractor deploy (a different service) exists."""
    draft = RedisUnavailableInjector().generate(ANCHOR)
    assert all(d.is_distractor for d in draft.deployments)
    assert all(d.service != "checkout" for d in draft.deployments)


def test_does_not_trigger_the_connection_pool_pattern():
    """Must never say "pool exhausted" or "connection timeout" — those
    keywords would falsely trigger agents/base.py's DB-pool pattern."""
    draft = RedisUnavailableInjector().generate(ANCHOR)
    all_text = " ".join(log.message.lower() for log in draft.logs)
    assert "pool exhausted" not in all_text
    assert "connection timeout" not in all_text
    assert "redis" in all_text


def test_error_rate_stays_low_despite_latency_impact():
    """The whole point of this scenario: latency degrades, but checkout
    keeps working (falls through to Postgres) — error rate must NOT cross
    its anomaly threshold, unlike db_connection_pool's 0.42."""
    draft = RedisUnavailableInjector().generate(ANCHOR)
    error_rate_points = [m for m in draft.metrics if m.metric_name == "error_rate"]
    assert len(error_rate_points) == 1
    assert error_rate_points[0].value < 0.05


def test_cache_hit_rate_collapses():
    draft = RedisUnavailableInjector().generate(ANCHOR)
    cache_points = sorted(
        (m for m in draft.metrics if m.metric_name == "cache_hit_rate"), key=lambda m: m.timestamp
    )
    assert len(cache_points) == 2
    assert cache_points[0].value > 0.5  # healthy baseline
    assert cache_points[1].value < 0.3  # collapsed


def test_timeline_bounds():
    draft = RedisUnavailableInjector().generate(ANCHOR)
    assert draft.start_time == ANCHOR - timedelta(minutes=15)
    assert draft.end_time == ANCHOR
