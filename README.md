# IncidentLab

Open-source multi-agent incident investigation & evaluation lab.

> **Status: Phase 1 of 10 (Repository + Infrastructure).** The
> investigation agents, evidence layer, and evaluation harness described
> below don't exist yet. See `docs/IMPLEMENTATION_STATUS.md` for what's
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

See `docs/architecture.md` for the current (Phase 1) architecture and
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
make test    # pytest
make lint    # ruff check + eslint
make format  # ruff format
```

## Roadmap

Running an incident, running an investigation, agent architecture,
evaluation, benchmark results, security, and limitations sections will be
filled in as each phase (see `docs/IMPLEMENTATION_STATUS.md`) actually
ships — not written speculatively ahead of the code.

## License

Apache-2.0 — see `LICENSE`.
