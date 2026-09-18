from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
    # spec §41's "oversized requests": each instance runs 3 architectures'
    # worth of real DB writes and investigations, so an unbounded value
    # here (e.g. a request for a million instances) is a real resource-
    # exhaustion vector on a public endpoint, not just a slow response.
    # 20 comfortably covers the documented default of 3 and any deliberate
    # "run a bigger benchmark from the UI" use case; a genuinely large
    # research run still has the uncapped `make benchmark` CLI.
    instances_per_scenario: int = Field(default=3, ge=1, le=20)
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
