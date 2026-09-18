from agents.base import summarize_or_fallback
from agents.models import TimeWindow, TriageFinding
from core.llm import LLMProvider
from tools.deployments import get_recent_deployments
from tools.incidents import get_incident, get_incident_timeline

_SYSTEM_PROMPT = (
    "You are the Triage Agent in an incident investigation system. Given "
    "an incident's timeline and recent deployments, identify likely "
    "investigation targets and candidate root-cause hypotheses in one "
    "short paragraph. Base every claim strictly on the evidence given — "
    "never invent facts not present in it."
)


async def investigate(incident_id: str, llm: LLMProvider | None = None) -> TriageFinding:
    """spec §10: identifies affected services, the time window, which
    services deserve investigation, and an initial (not final — that's
    Phase 5's Hypothesis Manager) set of hypotheses.

    No get_service_metadata() tool exists — there's no service registry in
    this project to back one, and inventing service ownership/dependency
    data would violate "never invent evidence". Investigation targets are
    derived from what's actually observed in the window instead.
    """
    incident = await get_incident(incident_id)
    timeline = await get_incident_timeline(incident_id)
    deployments = await get_recent_deployments(incident_id)

    investigation_targets = sorted({e.source for e in timeline})
    initial_hypotheses = [
        f"Deployment to {d.source}: {d.content.split(' (version=')[0]}" for d in deployments
    ]

    fallback = (
        f"{incident.service} incident ({incident.severity}): {incident.description}. "
        f"{len(investigation_targets)} service(s) active in the window: "
        f"{', '.join(investigation_targets) or 'none'}. "
    )
    fallback += (
        "Candidate hypotheses from nearby deployments: " + "; ".join(initial_hypotheses) + "."
        if initial_hypotheses
        else "No deployments found near the incident window."
    )

    prompt = (
        f"Incident: {incident.description}\n"
        f"Service: {incident.service}, severity: {incident.severity}\n"
        f"Window: {incident.start_time.isoformat()} to {incident.end_time.isoformat()}\n"
        f"Services active in window: {', '.join(investigation_targets)}\n"
        "Deployments near the window:\n"
        + "\n".join(f"- {d.source} at {d.timestamp.isoformat()}: {d.content}" for d in deployments)
    )
    summary = await summarize_or_fallback(
        llm, prompt=prompt, system=_SYSTEM_PROMPT, fallback=fallback
    )

    return TriageFinding(
        affected_services=[incident.service],
        time_window=TimeWindow(start=incident.start_time, end=incident.end_time),
        investigation_targets=investigation_targets,
        initial_hypotheses=initial_hypotheses,
        summary=summary,
    )
