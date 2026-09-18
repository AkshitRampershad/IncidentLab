from datetime import UTC, datetime

from agents.models import HypothesisSignal, InvestigatorFinding
from evidence.models import Evidence, Provenance, SourceType
from hypotheses.manager import build_hypotheses

NOW = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


def _evidence(evidence_id: str, source_type: SourceType, content: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_type=source_type,
        source="checkout",
        timestamp=NOW,
        content=content,
        relevance=1.0,
        provenance=Provenance(table="t", row_id="1", incident_id="INC-0001", retrieved_at=NOW),
    )


def _fixture():
    log_ids = [f"LOG-{i}" for i in range(1, 13)]
    log_evidence = [
        _evidence(i, SourceType.LOG, "database connection timeout (pool exhausted)")
        for i in log_ids
    ]
    redis_evidence = _evidence("LOG-13", SourceType.LOG, "redis cache eviction warning")

    logs_finding = InvestigatorFinding(
        agent_name="logs",
        findings=[],
        evidence=[*log_evidence, redis_evidence],
        hypotheses_supported=[
            HypothesisSignal(hypothesis="Connection pool exhaustion", evidence_ids=log_ids),
            HypothesisSignal(
                hypothesis="Database or downstream connectivity issue (connection timeouts)",
                evidence_ids=log_ids,
            ),
            HypothesisSignal(hypothesis="Cache layer (Redis) involvement", evidence_ids=["LOG-13"]),
        ],
        summary="",
    )

    metric_evidence = [
        _evidence("METRIC-1", SourceType.METRIC, "db_connections_active=5.0"),
        _evidence("METRIC-2", SourceType.METRIC, "error_rate=0.42"),
        _evidence("METRIC-3", SourceType.METRIC, "latency_p99_ms=3200.0"),
    ]
    metrics_finding = InvestigatorFinding(
        agent_name="metrics",
        findings=[],
        evidence=metric_evidence,
        hypotheses_supported=[
            HypothesisSignal(hypothesis="db_connections_active anomaly", evidence_ids=["METRIC-1"]),
            HypothesisSignal(hypothesis="error_rate anomaly", evidence_ids=["METRIC-2"]),
            HypothesisSignal(hypothesis="latency_p99_ms anomaly", evidence_ids=["METRIC-3"]),
        ],
        summary="",
    )

    deploy_evidence = _evidence(
        "DEPLOY-1", SourceType.DEPLOYMENT, "Reduce checkout-db connection pool size"
    )
    code_finding = InvestigatorFinding(
        agent_name="code",
        findings=[],
        evidence=[deploy_evidence],
        hypotheses_supported=[
            HypothesisSignal(
                hypothesis="Deployment to checkout may be related (near incident start)",
                evidence_ids=["DEPLOY-1"],
            )
        ],
        summary="",
    )

    return logs_finding, metrics_finding, code_finding


def test_signals_across_agents_merge_into_one_canonical_hypothesis():
    logs_finding, metrics_finding, code_finding = _fixture()
    hypotheses = build_hypotheses(logs_finding, metrics_finding, code_finding)

    pool = next(h for h in hypotheses if h.description == "Connection pool exhaustion")
    assert len(pool.supporting_evidence) == 13  # 12 logs + 1 metric
    assert pool.source_diversity == 2  # LOG + METRIC


def test_unmapped_signal_becomes_a_standalone_hypothesis():
    logs_finding, metrics_finding, code_finding = _fixture()
    hypotheses = build_hypotheses(logs_finding, metrics_finding, code_finding)

    descriptions = {h.description for h in hypotheses}
    assert "Deployment to checkout may be related (near incident start)" in descriptions


def test_hypotheses_sorted_by_confidence_descending():
    logs_finding, metrics_finding, code_finding = _fixture()
    hypotheses = build_hypotheses(logs_finding, metrics_finding, code_finding)

    confidences = [h.confidence for h in hypotheses]
    assert confidences == sorted(confidences, reverse=True)


def test_multi_source_hypotheses_outscore_single_source_ones():
    logs_finding, metrics_finding, code_finding = _fixture()
    hypotheses = build_hypotheses(logs_finding, metrics_finding, code_finding)
    by_description = {h.description: h for h in hypotheses}

    assert by_description["Connection pool exhaustion"].confidence > 0.9
    assert by_description["Cache layer (Redis) involvement"].confidence < 0.5


def test_confirmed_metric_means_no_contradiction():
    logs_finding, metrics_finding, code_finding = _fixture()
    hypotheses = build_hypotheses(logs_finding, metrics_finding, code_finding)

    pool = next(h for h in hypotheses if h.description == "Connection pool exhaustion")
    assert pool.contradicting_evidence == []
