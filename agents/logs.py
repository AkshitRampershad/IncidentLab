from agents.base import hypotheses_from_content, summarize_or_fallback
from agents.models import InvestigatorFinding
from core.llm import LLMProvider
from tools.logs import find_error_spikes, search_logs

_SYSTEM_PROMPT = (
    "You are the Log Investigator agent. Summarize what the log evidence "
    "shows in 2-3 sentences. Base every claim strictly on the evidence "
    "given — never invent facts not present in it."
)


async def investigate(incident_id: str, llm: LLMProvider | None = None) -> InvestigatorFinding:
    """spec §11: search_logs() + find_error_spikes(). aggregate_errors()
    and find_correlated_events() are not separately implemented — a spike
    bucket already is the aggregate, and cross-source correlation is
    Phase 5's Contradiction Detector's job, not one agent's."""
    evidence = await search_logs(incident_id)
    spikes = await find_error_spikes(incident_id)

    findings = [
        f"{spike.error_count} error-level log(s) clustered at "
        f"{spike.bucket_start.isoformat()} ({spike.service})"
        for spike in spikes
    ]
    if not findings:
        findings.append("No error-level log spikes found in the incident window.")

    hypotheses_supported = hypotheses_from_content(evidence)

    fallback = " ".join(findings)
    if hypotheses_supported:
        pattern_text = "; ".join(s.hypothesis for s in hypotheses_supported)
        fallback += f" Patterns observed: {pattern_text}."

    prompt = "Log evidence:\n" + "\n".join(
        f"- [{e.timestamp.isoformat()}] {e.content}" for e in evidence
    )
    summary = await summarize_or_fallback(
        llm, prompt=prompt, system=_SYSTEM_PROMPT, fallback=fallback
    )

    return InvestigatorFinding(
        agent_name="logs",
        findings=findings,
        evidence=evidence,
        hypotheses_supported=hypotheses_supported,
        summary=summary,
    )
