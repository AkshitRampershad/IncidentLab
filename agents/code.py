from agents.base import summarize_or_fallback
from agents.models import InvestigatorFinding
from core.llm import LLMProvider
from tools.deployments import get_recent_deployments
from tools.incidents import get_incident

_SYSTEM_PROMPT = (
    "You are the Code Investigator agent. Summarize which deployments "
    "might be related to this incident, based only on their timing and "
    "description. Base every claim strictly on the evidence given — "
    "never invent facts not present in it."
)


async def investigate(incident_id: str, llm: LLMProvider | None = None) -> InvestigatorFinding:
    """spec §13's Code Investigator, scoped to what's actually available:
    deployment records (each already carries a commit_sha + description of
    the change — spec §13's own worked example is exactly this). No real
    git integration exists (search_commits/get_commit/get_diff/
    search_files) — there's no repository to inspect, and building one
    against fabricated commit history would violate "never invent
    evidence". Lands in a later phase alongside real GitHub access.
    """
    incident = await get_incident(incident_id)
    evidence = await get_recent_deployments(incident_id)

    def _label(e):
        return "same service as incident" if e.source == incident.service else "different service"

    findings = [
        f"Deployment to {e.source} at {e.timestamp.isoformat()} ({_label(e)}): {e.content}"
        for e in evidence
    ]
    if not findings:
        findings.append("No deployments found near the incident window.")

    hypotheses_supported = [
        f"Deployment to {e.source} may be related (same service, near incident start)"
        for e in evidence
        if e.source == incident.service
    ]

    fallback = " ".join(findings)
    prompt = "Deployments near the incident window:\n" + "\n".join(f"- {f}" for f in findings)
    summary = await summarize_or_fallback(
        llm, prompt=prompt, system=_SYSTEM_PROMPT, fallback=fallback
    )

    return InvestigatorFinding(
        agent_name="code",
        findings=findings,
        evidence=evidence,
        hypotheses_supported=hypotheses_supported,
        summary=summary,
    )
