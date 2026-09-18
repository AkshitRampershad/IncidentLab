from agents.models import InvestigatorFinding
from evidence.models import Evidence


def detect_contradictions(
    expected_signal_texts: list[str], metrics_finding: InvestigatorFinding
) -> list[Evidence]:
    """spec §17: if a hypothesis's canonical group (see
    hypotheses/manager.py) expects corroboration from a specific metric
    (a "<metric_name> anomaly" signal text) and that metric was actually
    measured in the window but did NOT cross its anomaly threshold, the
    measured (non-anomalous) point is contradicting evidence — this is
    exactly spec §17's own worked example ("Metrics Agent: Database
    connection utilization remained normal") in this project's shape.

    Absence of a metric-anomaly signal alone is not a contradiction (maybe
    that metric just wasn't relevant) — only an actual "we measured it and
    it was normal" reading counts.
    """
    expected_metric_names = [
        text.removesuffix(" anomaly") for text in expected_signal_texts if text.endswith(" anomaly")
    ]
    flagged_metric_names = {
        s.hypothesis.removesuffix(" anomaly") for s in metrics_finding.hypotheses_supported
    }

    contradictions: list[Evidence] = []
    for metric_name in expected_metric_names:
        if metric_name in flagged_metric_names:
            continue  # confirmed anomalous — no contradiction
        measured = [e for e in metrics_finding.evidence if e.content.startswith(f"{metric_name}=")]
        contradictions.extend(measured)
    return contradictions
