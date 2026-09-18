import time
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from agents.adjudicator import AdjudicationResult
from core.config import get_settings
from core.llm import LLMProvider
from evaluation.baselines import direct_llm_investigate, single_agent_investigate
from evaluation.datasets import generate_dataset
from evaluation.ground_truth import get_ground_truth
from evaluation.metrics import AggregateMetrics, Trial, aggregate
from orchestration.graph import investigate as _run_multi_agent_graph

ArchitectureFn = Callable[[str, LLMProvider | None], Awaitable[AdjudicationResult]]


class BenchmarkReport(BaseModel):
    dataset_size: int
    architectures: list[AggregateMetrics]
    trials: list[Trial]  # per-(incident, architecture) raw results, for inspection


async def _multi_agent_investigate(incident_id: str, llm: LLMProvider | None) -> AdjudicationResult:
    state = await _run_multi_agent_graph(incident_id, llm=llm)
    return state["adjudication"]


_ARCHITECTURES: dict[str, ArchitectureFn] = {
    "direct_llm": direct_llm_investigate,
    "single_agent": single_agent_investigate,
    "multi_agent": _multi_agent_investigate,
}


async def _run_architecture(
    name: str, run_fn: ArchitectureFn, dataset: list[tuple[str, str]], llm: LLMProvider | None
) -> list[Trial]:
    trials = []
    for incident_id, _scenario_id in dataset:
        start = time.perf_counter()
        result = await run_fn(incident_id, llm)
        latency = time.perf_counter() - start
        ground_truth = await get_ground_truth(incident_id)
        trials.append(
            Trial(
                incident_id=incident_id,
                architecture=name,
                ground_truth=ground_truth,
                result=result,
                latency_seconds=latency,
            )
        )
    return trials


async def run_benchmark(
    *, instances_per_scenario: int = 3, llm: LLMProvider | None = None
) -> BenchmarkReport:
    """spec §26-27: runs every registered architecture against the same
    dataset and scores each against ground truth (evaluation/ground_truth.py
    — never seen by any of the architectures themselves)."""
    dataset = await generate_dataset(instances_per_scenario)
    settings = get_settings()

    all_trials: list[Trial] = []
    aggregates: list[AggregateMetrics] = []
    for name, run_fn in _ARCHITECTURES.items():
        trials = await _run_architecture(name, run_fn, dataset, llm)
        all_trials.extend(trials)
        aggregates.append(
            aggregate(name, trials, strong_threshold=settings.confidence_strong_threshold)
        )

    return BenchmarkReport(dataset_size=len(dataset), architectures=aggregates, trials=all_trials)
