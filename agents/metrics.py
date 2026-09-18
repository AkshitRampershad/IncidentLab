from agents.base import summarize_or_fallback
from agents.models import InvestigatorFinding
from core.llm import LLMProvider
from tools.metrics import detect_anomaly, known_anomaly_metrics, query_metrics

_SYSTEM_PROMPT = (
    "You are the Metrics Investigator agent. Summarize what the metric "
    "evidence shows in 2-3 sentences. Base every claim strictly on the "
    "evidence given — never invent facts not present in it."
)


async def investigate(incident_id: str, llm: LLMProvider | None = None) -> InvestigatorFinding:
    """spec §12: query_metrics() + detect_anomaly() for every metric with
    a registered threshold. compare_baseline() is not implemented — see
    tools/metrics.py's docstring for why."""
    evidence = await query_metrics(incident_id)

    findings: list[str] = []
    hypotheses_supported: list[str] = []
    for metric_name in known_anomaly_metrics():
        anomalies = await detect_anomaly(incident_id, metric_name)
        if not anomalies:
            continue
        values = ", ".join(
            f"{e.content.split('=')[1]}@{e.timestamp.isoformat()}" for e in anomalies
        )
        findings.append(f"{metric_name} crossed its anomaly threshold: {values}")
        hypotheses_supported.append(f"{metric_name} anomaly")

    if not findings:
        findings.append("No metrics crossed a known anomaly threshold in the incident window.")

    fallback = " ".join(findings)
    prompt = "Metric evidence:\n" + "\n".join(
        f"- [{e.timestamp.isoformat()}] {e.content}" for e in evidence
    )
    summary = await summarize_or_fallback(
        llm, prompt=prompt, system=_SYSTEM_PROMPT, fallback=fallback
    )

    return InvestigatorFinding(
        agent_name="metrics",
        findings=findings,
        evidence=evidence,
        hypotheses_supported=hypotheses_supported,
        summary=summary,
    )
