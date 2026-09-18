# IncidentLab

Open-source multi-agent incident investigation & evaluation lab.

> **Status: Phase 5 of 10 (Orchestration).** `make investigate
> INCIDENT=<id>` runs a full investigation end to end — five agents in
> parallel, hypothesis correlation, contradiction detection, confidence
> gating, an adjudicated result. The evaluation harness, baselines, and
> web UI described below don't exist yet. See
> `docs/IMPLEMENTATION_STATUS.md` for what's actually implemented today,
> and don't take the rest of this README as a description of current
> capability.

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

## Roadmap

Agent architecture detail, evaluation, benchmark results, security, and
limitations sections will be filled in as each
phase (see `docs/IMPLEMENTATION_STATUS.md`) actually ships — not written
speculatively ahead of the code.

## License

Apache-2.0 — see `LICENSE`.
