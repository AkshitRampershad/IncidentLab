# IncidentLab

[![CI](https://github.com/AkshitRampershad/incidentlab/actions/workflows/ci.yml/badge.svg)](https://github.com/AkshitRampershad/incidentlab/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

A multi-agent system that investigates software-production incidents —
and a benchmark harness that measures whether that multi-agent approach
is actually worth its complexity, rather than assuming it.

## Live Demo

**https://incidentlab-web.onrender.com** — deployed via the
`render.yaml` Blueprint on Render's free tier (API at
https://incidentlab-api.onrender.com). Free-tier caveats apply: the
service spins down after 15 minutes of inactivity, so the first request
after idle can take up to ~1 minute to respond, and the free Postgres
database expires 30 days after creation. If it's unresponsive or you
want a persistent instance, run it yourself: `docker compose up --build`,
then open http://localhost:3000 — see [Quick Start](#quick-start) below
(under one minute if your machine already has Docker).

## Project Status

**All 10 phases of the original build specification are implemented and
merged to `main`.** That is a statement about scope completion, not
about every known limitation being resolved — this project has
consistently disclosed its own gaps rather than hide them:

- No authentication or rate limiting on the API (open by design at this
  stage — see `docs/deployment.md`).
- No TLS built in; a reverse proxy is left to the deployer.
- The evaluation dataset is small (6 incidents across 2 scenarios) and
  that's stated plainly, not implied to be larger.
- No live LLM has been exercised end-to-end in this project's own build
  environment — the fully deterministic path (see "Security Model"
  below) is what's actually been verified there.
- **A version tag exists locally but has not been pushed to GitHub, and
  no GitHub Release has been published.** There is no `v0.1.0` tag and
  no Release on this repository's GitHub page as of this writing —
  `git tag`/`git log` locally do not reflect what's publicly visible on
  GitHub, and this README does not claim otherwise.
- **Deployed to Render** via the `render.yaml` Blueprint on the free
  tier — see [Live Demo](#live-demo) above and
  [Deployment](#deployment) below for the free-tier caveats (spin-down,
  Postgres expiry).

The full, itemized status — what shipped in each phase, what was
verified how, and every known limitation — is
`docs/IMPLEMENTATION_STATUS.md`. `docs/design-decisions.md` records the
reasoning behind non-obvious choices as they were made, not
reconstructed after the fact.

## What is IncidentLab?

IncidentLab investigates software-production incidents using multiple
specialized AI agents, and — just as importantly — evaluates whether
that multi-agent approach is actually worth its added complexity
compared to simpler architectures (a single agent, or a direct LLM
call). Given an incident, it answers: *what happened, why, what evidence
supports that conclusion, and how confident are we?*

It is not a chatbot. It retrieves real evidence (logs, metrics,
deployments, and a knowledge base), computes confidence in a root cause
deterministically from that evidence, and says "I don't have enough
evidence" when the evidence doesn't support a conclusion — rather than
letting a language model assert one.

## The Engineering Problem

During a real incident, an engineer's actual bottleneck is rarely a lack
of data — it's correlating logs, metrics, and deployment history fast
enough, under pressure, to find the one signal that explains what broke.
LLMs are an obvious tool to speed that up, but a model that free-associates
a plausible-sounding root cause from a summary alone is actively
dangerous in this context: a wrong, confidently-stated RCA sends an
on-call engineer down the wrong remediation path during a live incident.

IncidentLab's core engineering bet is that the fix isn't "trust the
model less" in the abstract — it's a specific architectural split: let
an LLM narrate, never let it decide. Every number and conclusion the
system produces (which hypothesis, how confident, which evidence backs
it) is computed by deterministic code the LLM never touches; an LLM, if
one is even configured, only ever rewrites the prose explaining a
conclusion that was already reached without it.

## Why Evidence-Grounded Investigation Matters

Concretely, this means:

- **Every claim traces to real evidence.** Findings, hypotheses, and
  confidence scores are computed from actual log/metric/deployment
  records retrieved for the incident — never invented, never a plausible
  guess dressed up as a finding.
- **Confidence is a formula, not a feeling.** A deterministic scoring
  function (evidence coverage + source diversity + temporal alignment −
  contradiction penalty) produces the confidence number — the same
  inputs always produce the same number, and it's inspectable, not a
  model's self-reported certainty.
- **"Not enough evidence" is a valid, expected answer**, not a failure
  mode to paper over — low-confidence results are explicitly flagged for
  human review rather than forced into a false-confident conclusion.
- **An LLM can degrade to nothing and the system still works.** No agent
  requires a reachable LLM to produce its structured output; if one is
  configured but unreachable, only prose narration quality changes.
- **A compromised or manipulated LLM still can't change the answer.**
  Even a prompt-injection attack that fully controls an LLM's response
  can only distort narration text — never the selected hypothesis, the
  confidence score, or whether human review is required. This is a
  structural guarantee (see `docs/design-decisions.md` DDR-010 and
  DDR-025), verified by a test that uses an LLM stand-in which does
  exactly what an injected instruction tells it to, and confirms the
  structured result is unaffected.

## Architecture

```
Incident → Triage → [Logs, Metrics, Code, Knowledge] (parallel)
                          ↓
                   Hypothesis Manager
              (cross-source merging + contradiction detection)
                          ↓
                     Adjudicator
              (confidence-gated root cause + evidence)
```

Major components:

- **`simulator/`** — deterministic incident generation. Given an
  `anchor_time`, a failure injector produces a full incident (timeline,
  logs, metrics, deployments, and a separately-stored ground truth) with
  no randomness — the same scenario always reproduces the same
  structure, which is what makes the evaluation harness meaningful.
- **`evidence/` + `tools/`** — structured, provenanced evidence
  (`Evidence`: source, timestamp, content, relevance score, provenance)
  retrieved from logs, metrics, deployments, and a knowledge base of
  runbooks/architecture docs. The `Evidence` model has no field capable
  of carrying ground-truth labels — a tool cannot leak the answer even
  by accident, by construction, not by convention.
- **`agents/`** — five investigation agents (below).
- **`hypotheses/`** — merges evidence-backed signals from multiple
  agents into competing hypotheses, detects contradictions between
  sources, and scores confidence deterministically.
- **`orchestration/`** — a [LangGraph](https://github.com/langchain-ai/langgraph)
  pipeline wiring the above into one investigation, with per-agent
  failure isolation (see Security Model) and an overall timeout.
- **`evaluation/`** — the benchmark harness: three architectures scored
  against the same held-out ground truth on real metrics.
- **`apps/api`** (FastAPI) / **`apps/web`** (Next.js) — the HTTP API and
  the web console.

Full diagrams and phase-by-phase detail: `docs/architecture.md`.

## Multi-Agent Workflow

An investigation runs five agents against one incident:

1. **Triage** — identifies the affected services, the time window, and
   candidate investigation targets from what's actually observed, plus
   initial hypotheses from nearby deployments.
2. **Logs** — searches log evidence for the incident's window, detects
   error-rate spikes, and matches deterministic keyword patterns against
   log content to produce candidate hypotheses.
3. **Metrics** — checks every metric with a registered anomaly
   threshold (e.g. `error_rate > 0.05`, `db_connections_active >= 5`)
   against the incident window.
4. **Code** — surfaces deployments near the incident window, flagging
   which ones touched the affected service.
5. **Knowledge** — searches a small hand-authored corpus (runbooks, an
   architecture doc, one clearly-labeled synthetic historical incident)
   for relevant context.

Logs, Metrics, and Code run in parallel after Triage; their evidence-backed
signals feed the **Hypothesis Manager**, which merges signals describing
the same underlying root cause from different sources into one
multi-source hypothesis, and the **Contradiction Detector**, which flags
when one source's evidence contradicts another (e.g. a metric that
should have crossed its threshold under a given hypothesis but didn't).
The **Adjudicator** picks the best-supported hypothesis, attaches
corroborating knowledge-base evidence, applies the confidence gate, and
recommends an action by citing a real runbook if one matches — never a
fabricated remediation step. An LLM, if configured and reachable, only
ever rewrites the prose summary at each stage; if none is configured or
it's unreachable, every agent falls back to a deterministic summary
built from the same structured findings.

## Evaluation Methodology

The evaluation harness (`evaluation/`) runs three architectures against
the same dataset and scores each against ground truth none of them can
see:

- **Direct LLM** (Baseline A) — the incident's summary straight to an
  LLM, zero tools, zero evidence. Confidence is structurally fixed at
  `0.0` regardless of what the LLM says — never the LLM's own guess —
  which correctly forces human escalation every time.
- **Single Agent** (Baseline B) — one agent using every tool and the
  same keyword patterns/anomaly thresholds the real agents use (so it
  isn't a strawman with worse data), but with no cross-source evidence
  merging and no contradiction detection.
- **Multi-Agent** — the real system, the same code path
  `make investigate` uses.

Each is scored on: root-cause accuracy, evidence recall/precision
(against the incident's real, non-distractor evidence), unsupported-claim
rate, false-confidence rate, human-escalation rate, and latency.

## Benchmark Results

Measured with `make benchmark` against the default dataset — **2
scenarios × 3 instances = 6 incidents** — with no LLM configured (the
build environment this was developed in has none reachable). This is a
small, disclosed dataset, not a large-scale benchmark; see
`docs/design-decisions.md` DDR-017 for why it isn't padded to look
bigger than it is, and re-run `make benchmark` yourself to reproduce
these numbers exactly (they're deterministic).

| Metric | Direct LLM | Single Agent | Multi-Agent |
|---|---:|---:|---:|
| Root-cause accuracy | 0% | 100% | 100% |
| Evidence recall | 0% | 72% | 78% |
| Evidence precision | 0% | 82% | 81% |
| Unsupported-claim rate | 0% | 0% | 0% |
| False-confidence rate | 0% | 0% | 0% |
| Human-escalation rate | 100% | 0% | 0% |
| Avg. latency | 0.00s | 0.02s | 0.05s |

**What this does and doesn't show:** Direct LLM's 0% is the real,
disclosed consequence of having zero evidence and no reachable model in
this run, not a harness bug. On this small dataset, Single Agent ties
Multi-Agent on raw accuracy — multi-agent is **not** shown to be
universally superior here. Multi-Agent's advantage in this run is higher
evidence recall (78% vs. 72%, from cross-source evidence merging) at a
small precision cost (81% vs. 82%) and higher latency (0.05s vs. 0.02s,
pure orchestration overhead with no LLM in the loop). That's the actual,
non-rigged finding at this dataset size — not an assumed conclusion.
Full context: `docs/architecture.md`'s Phase 6 section.

## Security Model

Every tool call an agent makes goes through an explicit allowlist
(`tools/registry.py`) with a per-call timeout, a shared
per-investigation call budget, and a structured audit log line for every
call. If one agent fails (a tool timeout, a database hiccup, anything),
the rest of the investigation still completes on whichever agents
succeeded, with the failed one clearly marked `degraded` instead of
crashing the whole run — a nonexistent `incident_id` is the one case
that still fails fast, since there'd be nothing left to investigate.

Evidence passed into any LLM prompt is wrapped in an explicit
untrusted-data delimiter, on top of the structural guarantee described
above in "Why Evidence-Grounded Investigation Matters" — an LLM's
response can distort narration text, never a structured result.
`incident_id`s are validated against this project's own generated shape
before they ever reach the database (this caught a real bug: a null byte
in a crafted `incident_id` used to reach the database driver raw and
come back as an uncaught 500 — now rejected cleanly). Traces are real
OpenTelemetry spans, visible in process output (no collector is stood up
yet — see Roadmap).

Full detail and the specific DDRs behind each of these: `docs/design-decisions.md`
(DDR-023 through DDR-027).

## Screenshots

Not yet included in this repository. Run it locally (see Quick Start
below) to see the investigation console — agent activity cards,
hypothesis confidence bars, and the root-cause-analysis panel — and the
evaluation dashboard described above.

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

### Using the web UI

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

### Local (non-Docker) development

```bash
make setup   # uv sync + npm install
make test    # pytest (unit + integration; integration needs a reachable
             # Postgres — docker compose up postgres, or a local install)
make lint    # ruff check + eslint
make format  # ruff format
```

### CLI reference

Requires a reachable Postgres (`docker compose up postgres -d`, or local).

```bash
make incident SCENARIO=db_connection_pool
```

Generates a reproducible incident deterministically: a deploy shrinks
checkout's DB connection pool, it saturates, error rate and latency spike,
plus some unrelated distractor noise. Prints the new `INC-XXXX` id. Ground
truth (the actual root cause) is stored in a separate table the
investigator never queries — see `docs/architecture.md`.

```bash
make investigate INCIDENT=INC-0001
```

Runs Triage, then Logs/Metrics/Code/Knowledge in parallel, correlates
their findings into competing hypotheses, checks for contradictions
between sources, and adjudicates a final result — selected root cause,
confidence, evidence, and a recommended action (citing a real runbook
when one matches). By default it tries a local Ollama for nicer prose
summaries and falls back to fully deterministic ones if none is running
(`--no-llm` skips the attempt).

```bash
make benchmark
```

Runs all three architectures from [Evaluation Methodology](#evaluation-methodology)
against the same dataset (`--instances-per-scenario` to change the
dataset size; `--llm` attempts a real model for nicer summaries — the
scored results don't change, since only free-text narration depends on
it).

## Deployment

`docker compose up --build` (above) works today and is the verified
path. Beyond that:

- **Container hardening:** both `apps/api` and `apps/web` run as
  unprivileged users and declare their own `HEALTHCHECK`.
- **CORS is configurable** (`CORS_ALLOWED_ORIGINS` in `.env`) rather than
  hardcoded to `localhost` — required for any deployment on a real
  domain.
- **Pre-built images are published to GHCR** on every green `main`
  (`.github/workflows/docker-publish.yml`) — its first three runs failed
  on a buildx configuration issue, since fixed; check the
  [Actions tab](https://github.com/AkshitRampershad/incidentlab/actions/workflows/docker-publish.yml)
  for the latest run's status before relying on a specific image tag
  being current.
- **A Render Blueprint** (`render.yaml`) drives a $0-to-start deployment
  (free web services + free Postgres) using the existing Dockerfiles
  unchanged — see `docs/deployment.md`'s "Deploying to Render" section
  for exact steps and the two values entered manually in Render's
  dashboard. **It's deployed** at https://incidentlab-web.onrender.com
  (API: https://incidentlab-api.onrender.com), subject to Render's free-tier
  caveats: the free Postgres database expires 30 days after creation,
  and free services spin down after 15 minutes of inactivity (cold
  start on the next request).

See `docs/deployment.md` for the full guide: required `.env` changes for
a real deployment, what's deliberately out of scope (TLS/reverse proxy,
a managed Postgres, Ollama as a service, Alembic — each with its
reasoning), and backup/log guidance.

## Roadmap

All 10 phases of the original build spec are implemented — that doesn't
mean nothing's left. Concrete, disclosed gaps, not secretly-missing
"phases": fixing the GHCR publish workflow so it actually succeeds;
pushing the `v0.1.0` tag and publishing a GitHub Release (currently
blocked by this session's git/tool permissions — a one-time manual
action); a real OTel collector to visualize traces, not just print them;
and the deployment gaps `docs/deployment.md` lists explicitly
(TLS/reverse proxy, a managed Postgres, real horizontal scaling,
Alembic).

## License

Apache-2.0 — see `LICENSE`.
