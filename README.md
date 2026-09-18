# IncidentLab

Open-source multi-agent incident investigation & evaluation lab.

> **Status: Phase 8 of 10 (Security + Observability).** A web UI
> (`docker compose up`, then http://localhost:3000) lets you generate an
> incident, run a full investigation, and review the result without
> touching the CLI or reading logs — plus a benchmark dashboard. Tool
> calls are now allowlisted, timed out, budgeted, and audit-logged
> (`tools/registry.py`); one agent failing degrades gracefully instead of
> crashing the whole investigation (spec §43); every `incident_id` is
> validated before it reaches the database. Deployment tooling described
> below doesn't exist yet. See `docs/IMPLEMENTATION_STATUS.md` for what's
> actually implemented today, and don't take the rest of this README as a
> description of current capability.

## What is IncidentLab?

IncidentLab investigates software-production incidents using multiple
specialized AI agents, and — just as importantly — evaluates whether that
multi-agent approach is actually worth its complexity compared to simpler
architectures. It answers: *something broke — what happened, why, what
evidence supports that conclusion, and how confident are we?*

It is not a chatbot. Evidence is retrieved from logs, metrics, traces,
deployments, Git history, and prior incidents; confidence in a root cause is
computed deterministically from that evidence, never asserted by an LLM; and
the system says "I don't have enough evidence" when it doesn't.

## Why does it exist?

To experimentally answer: *does specialized multi-agent investigation
improve root-cause accuracy enough to justify its added complexity and
latency, versus a single agent or a direct LLM call?* The project has two
equally important halves — the **investigator** (the multi-agent system)
and the **laboratory** (a reproducible incident simulator, failure
injection, ground-truth dataset, and evaluation harness to answer that
question rather than assume it).

## Architecture

See `docs/architecture.md` for the current architecture and
`docs/design-decisions.md` for why things are built the way they are.

## Quick Start

```bash
git clone https://github.com/AkshitRampershad/incidentlab
cd incidentlab
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Ports are configurable in `.env`.

## Using the web UI

Open http://localhost:3000: pick a scenario and click **Generate** to
create an incident, click **Investigate →** on it, then **Run
Investigation** to see all five agents, the correlated hypotheses, and
the final RCA — no CLI, no reading raw logs. **Evaluation** in the nav
runs the same benchmark as `make benchmark`, rendered as a table.

The "use LLM" toggle on the investigation page tries a real model for
nicer prose summaries and falls back to fully deterministic ones if none
is reachable (see `docs/design-decisions.md` DDR-010) — the underlying
findings, hypotheses, and RCA never depend on it either way. To actually
exercise it, install [Ollama](https://ollama.com) natively (not
dockerized — most Ollama setups are native for GPU access) and `ollama
pull llama3.1` (or set `LLM_MODEL` in `.env` to whatever you pulled).

## Local (non-Docker) development

```bash
make setup   # uv sync + npm install
make test    # pytest (unit + integration; integration needs a reachable
             # Postgres — docker compose up postgres, or a local install)
make lint    # ruff check + eslint
make format  # ruff format
```

## Running an incident

Requires a reachable Postgres (`docker compose up postgres -d`, or local).

```bash
make incident SCENARIO=db_connection_pool
```

Generates a reproducible incident deterministically: a deploy shrinks
checkout's DB connection pool, it saturates, error rate and latency spike,
plus some unrelated distractor noise. Prints the new `INC-XXXX` id. Ground
truth (the actual root cause) is stored in a separate table the
investigator never queries — see `docs/architecture.md`.

## Running an investigation

```bash
make investigate INCIDENT=INC-0001
```

Runs Triage, then Logs/Metrics/Code/Knowledge in parallel, correlates
their findings into competing hypotheses, checks for contradictions
between sources, and adjudicates a final result — selected root cause,
confidence, evidence, and a recommended action (citing a real runbook
when one matches). By default it tries a local Ollama for nicer prose
summaries and falls back to fully deterministic ones if none is running
(`--no-llm` skips the attempt). See `docs/architecture.md`'s Phase 5
section for how the pieces fit together.

## Running the benchmark

```bash
make benchmark
```

Runs Direct LLM (spec's Baseline A — no tools, no evidence), Single Agent
(Baseline B — every tool, no hypothesis correlation), and the real
Multi-Agent system against the same dataset, and scores each against
ground truth the architectures never see. Deterministic and fast by
default (`--llm` attempts a real model for nicer summaries — the results
don't change, since only free-text narration depends on it).

**The dataset is small and that's disclosed, not hidden:** 2 scenarios ×
3 instances = 6 incidents by default
(`--instances-per-scenario` to change it). Repeats of the same scenario
are structurally identical except timestamps — real per-scenario
variation (severity, distractor mix, evidence volume) is future work, not
claimed here. See `docs/design-decisions.md` DDR-017 for the reasoning,
and `docs/architecture.md`'s Phase 6 section for a real result from this
dataset (short version: on 6 incidents, Single Agent ties Multi-Agent on
accuracy but Multi-Agent shows better evidence recall — a genuine,
non-rigged finding, not an assumed conclusion).

## Security + Observability

Every tool call an agent makes goes through `tools/registry.py`: an
explicit allowlist, a per-call timeout, a shared per-investigation call
budget, and a structured audit log line — see
`docs/design-decisions.md` DDR-023. If one agent fails (a tool timeout, a
DB hiccup, anything), the rest of the investigation still completes on
whichever agents succeeded, with the failed one clearly marked
`degraded` instead of crashing the whole run (DDR-024) — a nonexistent
`incident_id` is the one case that still fails fast, since there'd be
nothing left to investigate. Evidence passed into any LLM prompt is
wrapped in an explicit untrusted-data delimiter (DDR-025), on top of the
existing structural guarantee that no agent's actual conclusion ever
depends on the LLM's response (DDR-010). `incident_id`s are validated
against this project's own generated shape before they ever reach
Postgres (DDR-027). Traces are real OpenTelemetry spans
(`core/telemetry.py`) visible in process output — no collector is stood
up yet (see Roadmap below).

## Roadmap

Deployment tooling and the open-source release checklist will be filled
in as each remaining phase (see `docs/IMPLEMENTATION_STATUS.md`) actually
ships — not written speculatively ahead of the code. A real OTel
collector (to visualize the traces above, not just print them) is one of
the concrete gaps left.

## License

Apache-2.0 — see `LICENSE`.
