from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.validation import IncidentId
from core.db import get_session_factory
from core.models import IncidentRecord
from simulator.replay import run_scenario
from simulator.scenarios import SCENARIOS
from tools.incidents import IncidentPublic, get_incident

router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=list[IncidentPublic])
async def list_incidents() -> list[IncidentPublic]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.scalars(select(IncidentRecord).order_by(IncidentRecord.created_at.desc()))
        ).all()
    return [
        IncidentPublic(
            incident_id=r.incident_id,
            service=r.service,
            severity=r.severity,
            description=r.description,
            start_time=r.start_time,
            end_time=r.end_time,
        )
        for r in rows
    ]


@router.get("/incidents/{incident_id}", response_model=IncidentPublic)
async def get_incident_route(incident_id: IncidentId) -> IncidentPublic:
    try:
        return await get_incident(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class CreateIncidentRequest(BaseModel):
    scenario_id: str


@router.post("/incidents", response_model=IncidentPublic, status_code=201)
async def create_incident(payload: CreateIncidentRequest) -> IncidentPublic:
    try:
        incident_id = await run_scenario(payload.scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await get_incident(incident_id)


@router.get("/scenarios")
async def list_scenarios() -> list[str]:
    """Not in spec §38's literal endpoint list, but the web UI's incident
    creation flow needs to know which scenario_ids actually exist."""
    return sorted(SCENARIOS)
