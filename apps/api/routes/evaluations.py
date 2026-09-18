from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.llm import get_llm_provider
from evaluation.runner import BenchmarkReport, run_benchmark

router = APIRouter(tags=["evaluations"])

# In-memory only, keyed by a generated evaluation_id — lost on API
# restart. No persistence table exists yet: this is dev/demo tooling for
# comparing architectures, not a production audit trail, and adding a
# schema for it now would be ahead of any real need to keep results past
# one process's lifetime (see docs/design-decisions.md).
_EVALUATIONS: dict[str, BenchmarkReport] = {}


class RunEvaluationRequest(BaseModel):
    instances_per_scenario: int = 3
    use_llm: bool = False


class EvaluationSummary(BaseModel):
    evaluation_id: str
    dataset_size: int


class EvaluationResponse(BaseModel):
    evaluation_id: str
    report: BenchmarkReport


@router.get("/evaluations", response_model=list[EvaluationSummary])
async def list_evaluations() -> list[EvaluationSummary]:
    return [
        EvaluationSummary(evaluation_id=eid, dataset_size=report.dataset_size)
        for eid, report in _EVALUATIONS.items()
    ]


@router.post("/evaluations/run", response_model=EvaluationResponse)
async def run_evaluation(payload: RunEvaluationRequest | None = None) -> EvaluationResponse:
    payload = payload or RunEvaluationRequest()
    llm = get_llm_provider() if payload.use_llm else None
    report = await run_benchmark(instances_per_scenario=payload.instances_per_scenario, llm=llm)

    evaluation_id = str(uuid4())
    _EVALUATIONS[evaluation_id] = report
    return EvaluationResponse(evaluation_id=evaluation_id, report=report)


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(evaluation_id: str) -> EvaluationResponse:
    report = _EVALUATIONS.get(evaluation_id)
    if report is None:
        raise HTTPException(
            status_code=404, detail=f"No evaluation recorded with id '{evaluation_id}'"
        )
    return EvaluationResponse(evaluation_id=evaluation_id, report=report)
