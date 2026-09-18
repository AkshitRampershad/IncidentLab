"""Import one real failure case from RCAEval (github.com/phamquiluan/RCAEval)
as an IncidentLab incident, instead of a synthetic `FailureInjector`.

RCAEval ships real telemetry collected from actual chaos-engineering runs
against three open-source microservice systems (Online Boutique, Sock
Shop, Train Ticket) — see docs/design-decisions.md DDR-035 for why this
is a separate script rather than a `FailureInjector` subclass, and for
exactly how to point it at one of RCAEval's 735 *labeled* cases.

Expects a case directory containing, at minimum:
  - metrics.csv     wide format: one `time` column (Unix seconds) plus one
                     column per `{service}_{metric_name}` pair, one row
                     per second (RCAEval's own format — see their README's
                     "File Structure" section).
  - inject_time.txt a single Unix timestamp: when the fault was injected.
  - logs.csv        optional. Columns include `timestamp` (nanoseconds),
                     `container_name`, `message`, `level`.

RCAEval carries no deployment/version data, so the resulting incident's
`deployments` list is always empty — nothing is fabricated to fill it.
Every imported log/metric has `is_distractor=False`: unlike a synthetic
scenario, nothing here was deliberately planted as a red herring, so
nothing is labeled as one.
"""

import argparse
import asyncio
import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from simulator.models import GroundTruth, IncidentDraft, LogEvent, MetricPoint
from simulator.replay import persist_incident_draft

_NANOS_PER_SECOND = 1_000_000_000


def _read_inject_time(case_dir: Path) -> int:
    text = (case_dir / "inject_time.txt").read_text().strip()
    return int(text)


def _melt_metrics(
    case_dir: Path,
    *,
    window_start: int,
    window_end: int,
    stride_seconds: int,
    time_offset: timedelta,
) -> list[MetricPoint]:
    """Turn RCAEval's wide `metrics.csv` (one column per service+metric)
    into one `MetricPoint` per (service, metric, timestamp) — the shape
    `simulator/models.py` expects — keeping only whole-second rows that
    fall on `stride_seconds` and land inside the requested window.
    """
    points: list[MetricPoint] = []
    path = case_dir / "metrics.csv"
    if not path.exists():
        return points

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        columns = [c for c in reader.fieldnames or [] if c != "time" and "_" in c]
        for row in reader:
            t = int(row["time"])
            if not (window_start <= t <= window_end):
                continue
            if (t - window_start) % stride_seconds != 0:
                continue
            timestamp = datetime.fromtimestamp(t, tz=UTC) + time_offset
            for column in columns:
                raw = row.get(column, "")
                if raw in ("", None):
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                service, metric_name = column.rsplit("_", 1)
                points.append(
                    MetricPoint(
                        service=service,
                        timestamp=timestamp,
                        metric_name=metric_name,
                        value=value,
                    )
                )
    return points


def _parse_logs(
    case_dir: Path,
    *,
    window_start: int,
    window_end: int,
    max_logs: int,
    time_offset: timedelta,
) -> list[LogEvent]:
    """Parse RCAEval's real `logs.csv`, keeping every non-info/debug line
    in the window (there are usually few) plus an evenly-sampled slice of
    the routine info/debug volume, capped at `max_logs` total — real
    production log volume (~100+ lines/sec in RCAEval's own data) is too
    dense to import wholesale.
    """
    path = case_dir / "logs.csv"
    if not path.exists():
        return []

    in_window: list[dict] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t_seconds = int(row["timestamp"]) / _NANOS_PER_SECOND
            if window_start <= t_seconds <= window_end:
                in_window.append(row)

    notable, routine = [], []
    for row in in_window:
        target = notable if row.get("level", "").lower() not in ("info", "debug", "") else routine
        target.append(row)

    remaining_budget = max(max_logs - len(notable), 0)
    if routine and remaining_budget:
        stride = max(len(routine) // remaining_budget, 1)
        sampled_routine = routine[::stride][:remaining_budget]
    else:
        sampled_routine = []

    rows = sorted(notable + sampled_routine, key=lambda r: int(r["timestamp"]))

    return [
        LogEvent(
            service=row["container_name"],
            timestamp=datetime.fromtimestamp(int(row["timestamp"]) / _NANOS_PER_SECOND, tz=UTC)
            + time_offset,
            level=row.get("level") or "info",
            message=row["message"],
        )
        for row in rows
    ]


def build_incident_draft(
    case_dir: Path,
    *,
    root_cause: str,
    affected_component: str,
    trigger: str,
    service: str | None = None,
    severity: str = "warning",
    description: str | None = None,
    case_id: str | None = None,
    window_before_min: int = 10,
    window_after_min: int = 5,
    metric_stride_sec: int = 10,
    max_logs: int = 300,
    anchor_time: datetime | None = None,
) -> IncidentDraft:
    """Build an `IncidentDraft` from a real RCAEval case directory.

    `root_cause`/`affected_component`/`trigger` are supplied by the
    caller because they aren't in the case directory itself for the
    unlabeled sample this script was written against (RCAEval's own
    GitHub-hosted `multi-source-data.zip`). Pointed at one of RCAEval's
    735 labeled Zenodo/Hugging Face cases instead, these three values are
    exactly what that case's `{benchmark}_{service}_{fault}_{instance}`
    directory name and `cases.parquet` row already encode — see
    docs/design-decisions.md DDR-035.

    Real timestamps (RCAEval's cases are all from 2024) are shifted by a
    constant offset so the window ends at `anchor_time` (default: now) —
    preserving every real relative gap between events, just moving the
    whole window to feel current, the same way every synthetic scenario
    anchors itself to `anchor_time` rather than a fixed calendar date.
    """
    inject_time = _read_inject_time(case_dir)
    window_start = inject_time - window_before_min * 60
    window_end = inject_time + window_after_min * 60

    anchor_time = anchor_time or datetime.now(UTC)
    real_end = datetime.fromtimestamp(window_end, tz=UTC)
    time_offset = anchor_time - real_end

    metrics = _melt_metrics(
        case_dir,
        window_start=window_start,
        window_end=window_end,
        stride_seconds=metric_stride_sec,
        time_offset=time_offset,
    )
    logs = _parse_logs(
        case_dir,
        window_start=window_start,
        window_end=window_end,
        max_logs=max_logs,
        time_offset=time_offset,
    )

    resolved_service = service or affected_component
    resolved_case_id = case_id or case_dir.name
    resolved_description = description or (
        f"Imported from RCAEval case '{resolved_case_id}': "
        f"real telemetry, fault injected at {resolved_case_id}'s inject_time"
    )

    return IncidentDraft(
        service=resolved_service,
        severity=severity,
        description=resolved_description,
        start_time=datetime.fromtimestamp(window_start, tz=UTC) + time_offset,
        end_time=anchor_time,
        ground_truth=GroundTruth(
            scenario_id=f"rcaeval:{resolved_case_id}",
            root_cause=root_cause,
            affected_component=affected_component,
            trigger=trigger,
        ),
        logs=logs,
        metrics=metrics,
        deployments=[],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import a real RCAEval failure case (github.com/phamquiluan/RCAEval) as an "
            "IncidentLab incident."
        )
    )
    parser.add_argument("case_dir", type=Path, help="Path to an unzipped RCAEval case directory")
    parser.add_argument(
        "--root-cause",
        required=True,
        help=(
            "Ground-truth root cause, e.g. 'cpu_stress'. Not present in RCAEval's unlabeled "
            "GitHub-release sample — read from the case's own directory name or "
            "cases.parquet row when importing a labeled Zenodo/Hugging Face case instead."
        ),
    )
    parser.add_argument("--affected-component", required=True, help="Ground-truth service name")
    parser.add_argument(
        "--trigger", required=True, help="Ground-truth trigger category, e.g. 'resource_exhaustion'"
    )
    parser.add_argument(
        "--service", help="Incident's headline service (default: affected component)"
    )
    parser.add_argument("--severity", default="warning")
    parser.add_argument("--description")
    parser.add_argument("--case-id", help="Defaults to the case directory's name")
    parser.add_argument("--window-before-min", type=int, default=10)
    parser.add_argument("--window-after-min", type=int, default=5)
    parser.add_argument("--metric-stride-sec", type=int, default=10)
    parser.add_argument("--max-logs", type=int, default=300)
    args = parser.parse_args()

    draft = build_incident_draft(
        args.case_dir,
        root_cause=args.root_cause,
        affected_component=args.affected_component,
        trigger=args.trigger,
        service=args.service,
        severity=args.severity,
        description=args.description,
        case_id=args.case_id,
        window_before_min=args.window_before_min,
        window_after_min=args.window_after_min,
        metric_stride_sec=args.metric_stride_sec,
        max_logs=args.max_logs,
    )

    incident_id = asyncio.run(persist_incident_draft(draft))

    print(f"Created incident {incident_id} from real data (case: {draft.ground_truth.scenario_id})")
    print(f"  {len(draft.logs)} log events, {len(draft.metrics)} metric points, 0 deployments")
    print("Ground truth stored separately — never exposed to the investigator.")
    print(
        f"Note: automatic benchmark scoring (evaluation/ground_truth.py) only recognizes "
        f"root causes already mapped to a canonical hypothesis in "
        f"evaluation/ground_truth.py's _ROOT_CAUSE_TO_HYPOTHESIS — '{args.root_cause}' isn't "
        f"one of them yet, so this incident can be investigated but not auto-scored until "
        f"that mapping is extended."
    )
    print(f"Next: make investigate INCIDENT={incident_id}")


if __name__ == "__main__":
    main()
