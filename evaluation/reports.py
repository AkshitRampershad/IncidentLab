import argparse
import asyncio

from core.llm import get_llm_provider
from evaluation.runner import BenchmarkReport, run_benchmark

_DISPLAY_NAMES = {
    "direct_llm": "Direct LLM",
    "single_agent": "Single Agent",
    "multi_agent": "Multi-Agent",
}

# (attribute name, column label, formatter)
_METRIC_COLUMNS = [
    ("root_cause_accuracy", "RCA Accuracy", lambda v: f"{v:.0%}"),
    ("evidence_recall", "Evidence Recall", lambda v: f"{v:.0%}"),
    ("evidence_precision", "Evidence Precision", lambda v: f"{v:.0%}"),
    ("unsupported_claim_rate", "Unsupported Claims", lambda v: f"{v:.0%}"),
    ("false_confidence_rate", "False Confidence", lambda v: f"{v:.0%}"),
    ("human_escalation_rate", "Human Escalation", lambda v: f"{v:.0%}"),
    ("avg_latency_seconds", "Avg Latency", lambda v: f"{v:.2f}s"),
]


def format_report(report: BenchmarkReport) -> str:
    """spec §29's report shape: one table per metric, architectures as
    rows. Every number here comes from `report`, itself built entirely
    from real `investigate()`/baseline runs scored against real ground
    truth (spec §29: "Only populate values from actual benchmark
    execution. Never fabricate metrics.") — there is no other source for
    any value printed here."""
    lines = [
        "IncidentLab Evaluation",
        "=" * 23,
        "",
        f"Dataset: {report.dataset_size} incidents",
        "",
    ]

    name_width = max(len(name) for name in _DISPLAY_NAMES.values())
    for attr, label, fmt in _METRIC_COLUMNS:
        lines.append(label)
        lines.append("-" * (name_width + 12))
        for arch in report.architectures:
            display_name = _DISPLAY_NAMES.get(arch.architecture, arch.architecture)
            value = fmt(getattr(arch, attr))
            lines.append(f"{display_name:<{name_width}}   {value}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the IncidentLab evaluation benchmark.")
    parser.add_argument(
        "--instances-per-scenario",
        type=int,
        default=3,
        help="How many times to run each registered scenario (default: 3)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help=(
            "Attempt a real LLM for each architecture (default: deterministic-only, fast — "
            "note direct_llm's accuracy honestly depends on this)"
        ),
    )
    args = parser.parse_args()

    llm = get_llm_provider() if args.llm else None
    report = asyncio.run(run_benchmark(instances_per_scenario=args.instances_per_scenario, llm=llm))
    print(format_report(report))


if __name__ == "__main__":
    main()
