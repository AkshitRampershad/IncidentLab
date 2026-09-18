from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agents.adjudicator import AdjudicationResult
from agents.models import InvestigatorFinding, TriageFinding
from core.llm import get_llm_provider
from evidence.models import Evidence
from hypotheses.models import Hypothesis
from orchestration.graph import investigate as run_investigation
from tools.incidents import get_incident_timeline

router = APIRouter(tags=["investigations"])


class InvestigationResponse(BaseModel):
    """spec §38 treats /investigations/{id} as its own resource; this
    project has no separate investigation-persistence layer (see
    docs/design-decisions.md) — "the investigation" is just the full,
    deterministic result of running the graph against an incident_id, so
    that's what this id is."""

    incident_id: str
    triage: TriageFinding
    agents: dict[str, InvestigatorFinding]
    hypotheses: list[Hypothesis]
    adjudication: AdjudicationResult


async def _run(incident_id: str, use_llm: bool) -> InvestigationResponse:
    llm = get_llm_provider() if use_llm else None
    try:
        state = await run_investigation(incident_id, llm=llm)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return InvestigationResponse(
        incident_id=incident_id,
        triage=state["triage"],
        agents={
            "logs": state["logs_finding"],
            "metrics": state["metrics_finding"],
            "code": state["code_finding"],
            "knowledge": state["knowledge_finding"],
        },
        hypotheses=state["hypotheses"],
        adjudication=state["adjudication"],
    )


@router.post("/incidents/{incident_id}/investigate", response_model=InvestigationResponse)
async def investigate_incident(
    incident_id: str, use_llm: bool = Query(False, alias="llm")
) -> InvestigationResponse:
    return await _run(incident_id, use_llm)


@router.get("/investigations/{incident_id}", response_model=InvestigationResponse)
async def get_investigation(
    incident_id: str, use_llm: bool = Query(False, alias="llm")
) -> InvestigationResponse:
    """Re-runs the investigation fresh rather than reading a persisted
    record — the system is deterministic (no ground truth or randomness
    involved) and fast (well under a second with no LLM), so recomputing
    on every call is simpler than a cache/persistence layer and can never
    go stale. The web UI calls the POST endpoint once per "Run
    Investigation" click and holds the result client-side rather than
    re-hitting this or the sub-resource endpoints below repeatedly."""
    return await _run(incident_id, use_llm)


@router.get("/investigations/{incident_id}/timeline", response_model=list[Evidence])
async def get_investigation_timeline(incident_id: str) -> list[Evidence]:
    try:
        return await get_incident_timeline(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/investigations/{incident_id}/evidence", response_model=list[Evidence])
async def get_investigation_evidence(
    incident_id: str, use_llm: bool = Query(False, alias="llm")
) -> list[Evidence]:
    result = await _run(incident_id, use_llm)
    return result.adjudication.supporting_evidence


@router.get("/investigations/{incident_id}/hypotheses", response_model=list[Hypothesis])
async def get_investigation_hypotheses(
    incident_id: str, use_llm: bool = Query(False, alias="llm")
) -> list[Hypothesis]:
    result = await _run(incident_id, use_llm)
    return result.hypotheses


@router.get("/investigations/{incident_id}/agents", response_model=dict[str, InvestigatorFinding])
async def get_investigation_agents(
    incident_id: str, use_llm: bool = Query(False, alias="llm")
) -> dict[str, InvestigatorFinding]:
    result = await _run(incident_id, use_llm)
    return result.agents


class ReviewDecision(BaseModel):
    status: str
    incident_id: str
    note: str


_REVIEW_NOTE = (
    "Acknowledged only — no persisted audit trail or re-investigation "
    "loop exists yet (spec §20's approve/reject/request-more-investigation "
    "workflow; see docs/design-decisions.md)."
)


@router.post("/investigations/{incident_id}/approve", response_model=ReviewDecision)
async def approve_investigation(incident_id: str) -> ReviewDecision:
    return ReviewDecision(status="approved", incident_id=incident_id, note=_REVIEW_NOTE)


@router.post("/investigations/{incident_id}/reject", response_model=ReviewDecision)
async def reject_investigation(incident_id: str) -> ReviewDecision:
    return ReviewDecision(status="rejected", incident_id=incident_id, note=_REVIEW_NOTE)
