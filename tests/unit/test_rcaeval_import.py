from datetime import UTC, datetime
from pathlib import Path

from simulator.rcaeval_import import build_incident_draft

FIXTURE = Path(__file__).parent.parent / "fixtures" / "rcaeval_sample"
ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def _build(**overrides):
    kwargs = dict(
        root_cause="cpu_stress",
        affected_component="checkoutservice",
        trigger="resource_exhaustion",
        anchor_time=ANCHOR,
    )
    kwargs.update(overrides)
    return build_incident_draft(FIXTURE, **kwargs)


def test_ground_truth_comes_from_caller_not_the_case_directory():
    draft = _build()
    assert draft.ground_truth.root_cause == "cpu_stress"
    assert draft.ground_truth.affected_component == "checkoutservice"
    assert draft.ground_truth.trigger == "resource_exhaustion"
    assert draft.ground_truth.scenario_id == "rcaeval:rcaeval_sample"


def test_no_deployments_fabricated():
    """RCAEval carries no deploy/version data — the honest answer is an
    empty list, not an invented one."""
    assert _build().deployments == []


def test_nothing_is_labeled_a_distractor():
    """Unlike a synthetic FailureInjector, nothing here was deliberately
    planted as a red herring, so nothing should claim to be one."""
    draft = _build()
    assert all(not m.is_distractor for m in draft.metrics)
    assert all(not log.is_distractor for log in draft.logs)


def test_metrics_are_melted_from_wide_to_long():
    draft = _build(metric_stride_sec=10, window_before_min=1, window_after_min=1)
    assert draft.metrics
    checkout_cpu = [
        m for m in draft.metrics if m.service == "checkoutservice" and m.metric_name == "cpu"
    ]
    assert checkout_cpu
    # real value from the fixture — the actual measured checkoutservice CPU
    # reading right around the fault, not a synthesized number
    assert all(v.value > 0 for v in checkout_cpu)


def test_metric_stride_reduces_point_count():
    fine = _build(metric_stride_sec=1, window_before_min=1, window_after_min=1)
    coarse = _build(metric_stride_sec=10, window_before_min=1, window_after_min=1)
    assert len(coarse.metrics) < len(fine.metrics)


def test_logs_are_parsed_and_capped():
    draft = _build(max_logs=20)
    assert 0 < len(draft.logs) <= 20
    assert all(log.service for log in draft.logs)
    assert all(log.message for log in draft.logs)


def test_logs_sorted_chronologically():
    draft = _build(max_logs=50)
    timestamps = [log.timestamp for log in draft.logs]
    assert timestamps == sorted(timestamps)


def test_window_ends_at_anchor_time():
    """Real 2024 timestamps get shifted so the window ends at anchor_time —
    the imported incident feels current, like every synthetic scenario."""
    draft = _build()
    assert draft.end_time == ANCHOR
    assert draft.start_time < ANCHOR
    for log in draft.logs:
        assert draft.start_time <= log.timestamp <= draft.end_time
    for metric in draft.metrics:
        assert draft.start_time <= metric.timestamp <= draft.end_time


def test_generation_is_deterministic_given_the_same_anchor():
    assert _build() == _build()


def test_service_defaults_to_affected_component():
    draft = _build()
    assert draft.service == "checkoutservice"


def test_service_override_is_respected():
    draft = _build(service="frontend")
    assert draft.service == "frontend"
    assert draft.ground_truth.affected_component == "checkoutservice"
