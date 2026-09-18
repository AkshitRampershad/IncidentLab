from datetime import UTC, datetime

from agents.models import HypothesisSignal, InvestigatorFinding
from evidence.models import Evidence, Provenance, SourceType
from hypotheses.contradiction import detect_contradictions

NOW = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def _metric_evidence(evidence_id: str, metric_name: str, value: float) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_type=SourceType.METRIC,
        source="checkout",
        timestamp=NOW,
        content=f"{metric_name}={value}",
        relevance=1.0,
        provenance=Provenance(
            table="metric_points", row_id="1", incident_id="INC-0001", retrieved_at=NOW
        ),
    )


def _metrics_finding(
    *, evidence: list[Evidence], flagged_metrics: list[str]
) -> InvestigatorFinding:
    return InvestigatorFinding(
        agent_name="metrics",
        findings=[],
        evidence=evidence,
        hypotheses_supported=[
            HypothesisSignal(
                hypothesis=f"{m} anomaly", evidence_ids=[e.evidence_id for e in evidence]
            )
            for m in flagged_metrics
        ],
        summary="",
    )


def test_confirmed_metric_produces_no_contradiction():
    evidence = [_metric_evidence("METRIC-1", "db_connections_active", 5.0)]
    finding = _metrics_finding(evidence=evidence, flagged_metrics=["db_connections_active"])

    contradictions = detect_contradictions(["db_connections_active anomaly"], finding)
    assert contradictions == []


def test_measured_but_not_flagged_metric_is_a_contradiction():
    evidence = [_metric_evidence("METRIC-1", "db_connections_active", 2.0)]
    finding = _metrics_finding(evidence=evidence, flagged_metrics=[])  # measured, but not anomalous

    contradictions = detect_contradictions(["db_connections_active anomaly"], finding)
    assert contradictions == evidence


def test_metric_never_measured_produces_no_contradiction():
    finding = _metrics_finding(evidence=[], flagged_metrics=[])

    contradictions = detect_contradictions(["db_connections_active anomaly"], finding)
    assert contradictions == []


def test_non_metric_expected_texts_are_ignored():
    finding = _metrics_finding(evidence=[], flagged_metrics=[])
    contradictions = detect_contradictions(["Connection pool exhaustion"], finding)
    assert contradictions == []
