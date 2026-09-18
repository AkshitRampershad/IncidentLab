# RCAEval sample fixture

A small, real slice of one failure case from
[RCAEval](https://github.com/phamquiluan/RCAEval) (`multi-source-data.zip`,
their `0.2.0` GitHub release — a chaos-engineering run against Google's
Online Boutique microservices demo), used only to test
`simulator/rcaeval_import.py`'s parsing against real telemetry shapes.

Trimmed from the original ~1,441-row `metrics.csv` / ~171k-row `logs.csv`
down to a ±20s window around `inject_time.txt` (metrics) and a further
thinned ±10s window (logs, every 15th real line kept) — small enough to
check into the repo, still real values and real log text, not synthesized.

This specific case is **unlabeled**: the bundle it came from has no
`root_cause`/`fault` field, only real telemetry + the injection timestamp.
(RCAEval's 735 *labeled* cases live on Zenodo/Hugging Face, not this
GitHub release.) Tests using this fixture supply a ground truth label as
an argument, the same way `simulator/rcaeval_import.py`'s CLI requires one
for this bundle — they don't assert anything about what the real fault
actually was.

Original files, for reference: `metrics.csv` (73 columns, one
`{service}_{metric}` pair per column, one row per second),
`logs.csv` (`time, timestamp(ns), container_name, message, level,
req_path, error, cluster_id, log_template`), `inject_time.txt` (Unix
seconds).
