# Architecture

This document describes the system as it exists today. It grows with each
implementation phase (see `docs/IMPLEMENTATION_STATUS.md`) rather than
describing the full target design up front.

## Phase 1: Foundation

```mermaid
flowchart LR
    subgraph Docker Compose
        web[apps/web<br/>Next.js] -->|HTTP| api[apps/api<br/>FastAPI]
        api -->|SQLAlchemy / asyncpg| db[(Postgres)]
    end
```

- **`apps/web`** — Next.js (App Router, TypeScript). Currently a single page
  that calls the API's `/health` endpoint to prove end-to-end wiring.
- **`apps/api`** — FastAPI. Exposes:
  - `GET /health` — liveness only, no dependencies checked.
  - `GET /health/ready` — readiness; opens a real connection to Postgres and
    returns `503` if it can't.
- **Postgres** — schema now exists (see Phase 2 below), owned by `core/`.
- **`core/config.py`** — Pydantic Settings, reads from environment
  variables / `.env`. `.env.example` documents every variable in use.

Nothing in this phase talks to an LLM or a vector store — those are
introduced in later phases as the `docs/IMPLEMENTATION_STATUS.md` tracker
is updated.

## Phase 2: Incident Simulator

```mermaid
flowchart LR
    cli["make incident SCENARIO=db_connection_pool"] --> replay[simulator/replay.py]
    replay --> injector[simulator/failure_injector/<br/>db_connection_pool.py]
    injector -->|IncidentDraft| replay
    replay -->|"incidents (public)"| db[(Postgres)]
    replay -->|"incident_ground_truths (private)"| db
    replay -->|"log_events / metric_points / deployments"| db
```

- **`core/models.py`** — the shared ORM schema, deliberately split so
  ground truth can never leak into an investigator-facing query:
  - `incidents` — service, severity, description, start/end time. This is
    the only table any future agent/tool is allowed to read.
  - `incident_ground_truths` — root cause, affected component, trigger,
    and the scenario_id that generated it. Evaluation-only (spec §8, §18).
    A separate table, not columns on `incidents`, specifically so a normal
    query against `incidents` can't accidentally join it in.
  - `log_events` / `metric_points` / `deployments` — raw telemetry, each
    row tagged `is_distractor` for the Phase 6 evaluation harness. **Any
    Phase 3+ tool that exposes these rows to an agent must strip
    `is_distractor`** — leaving it in would hand the agent the answer.
- **`simulator/failure_injector/`** — one class per scenario. Given an
  `anchor_time`, deterministically generates the full `IncidentDraft`
  (timeline, logs, metrics, deployments, ground truth) — no randomness, no
  real service under load (see `docs/design-decisions.md` DDR-007). The
  first scenario, `db_connection_pool`, reproduces spec §8's worked
  example: a deploy shrinks a connection pool, the pool saturates, error
  rate and latency spike, plus a few unrelated distractor events (a Redis
  warning, an unrelated deploy, a CPU blip on another service).
- **`simulator/scenarios/`** — the scenario_id → injector registry
  (`get_injector`).
- **`simulator/replay.py`** — `run_scenario(scenario_id)`: resolves the
  injector, creates the schema if missing, assigns the next sequential
  `INC-XXXX` id, and persists everything in one transaction. `main()`
  wraps it as the `make incident SCENARIO=<id>` CLI.
- **Schema creation** — still `Base.metadata.create_all()`, not Alembic
  (DDR-004 extended: still true, the schema is still young enough that
  migrations would just be churn).

Nothing yet *exposes* this telemetry to an agent as scored, provenanced
evidence — that abstraction (spec §9's Evidence model, `relevance`,
`evidence_id`) is Phase 3.

## Phase 3: Evidence Layer

```mermaid
flowchart LR
    caller[future agent / test] --> incidents[tools/incidents.py]
    caller --> logs[tools/logs.py]
    caller --> metrics[tools/metrics.py]
    caller --> deployments[tools/deployments.py]

    logs --> scoring[evidence/scoring.py]
    metrics --> scoring
    deployments --> scoring
    logs --> provenance[evidence/provenance.py]
    metrics --> provenance
    deployments --> provenance

    logs -->|SELECT| db[(Postgres:<br/>log_events / metric_points /<br/>deployments / incidents)]
    metrics -->|SELECT| db
    deployments -->|SELECT| db
    incidents -->|SELECT| db
```

- **`evidence/models.py`** — `Evidence` (evidence_id, source_type, source,
  timestamp, content, relevance, provenance) and `SourceType` (spec §9's
  full enum, though only `log`/`metric`/`deployment` are produced so far —
  see DDR-008). `Evidence` has no `is_distractor` field by construction:
  a tool physically cannot leak it through this model, not just by
  convention.
- **`evidence/provenance.py`** — `build_evidence_id` (the `LOG-1842` /
  `METRIC-203` / `DEPLOY-482` format from spec §9's example) and
  `build_provenance` (which table/row this came from, when it was
  fetched).
- **`evidence/scoring.py`** — `temporal_relevance`: 1.0 inside the
  incident's `[start_time, end_time]`, decaying the further outside it a
  timestamp falls (floor 0.2). A documented experimental baseline (spec
  §16), not a calibrated model — the point is that it's deterministic and
  reproducible, not that the decay curve is "correct". `matches_query`:
  case-insensitive substring filter.
- **`tools/incidents.py`** — `get_incident` (the public `IncidentPublic`
  model — service/severity/description/start/end, structurally incapable
  of carrying ground truth) and `get_incident_timeline` (every log/metric/
  deployment Evidence in the window, chronologically merged).
- **`tools/logs.py`** — `search_logs` (optionally filtered by substring)
  and `find_error_spikes` (minute-bucketed error counts ≥3 — a derived
  aggregate over several rows, so it's a separate `LogSpike` model, not
  forced into the single-row-backed `Evidence` shape).
- **`tools/metrics.py`** — `query_metrics` and `detect_anomaly` (a fixed,
  documented per-metric threshold table — e.g. `error_rate > 0.05`,
  `db_connections_active >= 5`). `compare_baseline` (spec §12) is *not*
  implemented: it needs a genuine pre-incident "normal" window the
  simulator doesn't generate, and fabricating one would violate "never
  invent evidence" (spec §4.3).
- **`tools/deployments.py`** — `get_recent_deployments`, across every
  service in the window (not just the affected one — an unrelated
  service's deploy is exactly the kind of distractor an agent needs to
  see and correctly discount, not have pre-filtered away).

All four tool modules search a padded window
(`evidence.scoring.SEARCH_WINDOW_PADDING`, 15 minutes either side of
`[start_time, end_time]`) rather than the exact incident window, so a
precursor deployment a few minutes before `start_time` is still found.

Not yet built: `tools/github.py`, `tools/traces.py` (DDR-008 — no real
commit/PR data or tracing backend exists yet), `evidence/graph.py`
(DDR-009 — no consumer until the Phase 7 UI). Nothing here is wrapped as
an LLM-callable tool yet either — these are plain typed async functions;
Phase 4 wires them into agents.

## Phase 4: Agents

```mermaid
flowchart LR
    caller[future orchestrator / test] --> triage[agents/triage.py]
    caller --> logsA[agents/logs.py]
    caller --> metricsA[agents/metrics.py]
    caller --> codeA[agents/code.py]
    caller --> knowledgeA[agents/knowledge.py]

    triage --> tools3[Phase 3 tools]
    logsA --> tools3
    metricsA --> tools3
    codeA --> tools3
    knowledgeA --> toolsK[tools/knowledge.py]

    logsA -.optional.-> llm[core/llm/<br/>LLMProvider]
    metricsA -.optional.-> llm
    codeA -.optional.-> llm
    knowledgeA -.optional.-> llm
    triage -.optional.-> llm

    llm -.-> ollama[(Ollama,<br/>default — not<br/>installed in this<br/>sandbox)]
```

- **`core/llm/`** — spec §44's model abstraction. `LLMProvider` (ABC,
  `generate(prompt, system=None) -> str`) with three implementations —
  `OllamaProvider` (default), `OpenAICompatibleProvider`,
  `AnthropicCompatibleProvider` — all raising the single
  `LLMUnavailableError` on any failure, so callers never need to know
  which HTTP shape or client failed underneath. `core/llm/factory.py`'s
  `get_llm_provider()` reads `core.config.Settings` (`llm_provider`,
  `llm_model`, `llm_base_url`, `llm_api_key`). No live LLM exists in this
  sandbox (no Ollama, no API access), so every provider is tested via
  `httpx.MockTransport` — real request/response shape verified, zero
  network dependency.
- **`agents/base.py`** — the two pieces of logic shared by every agent:
  `hypotheses_from_content` (a small, deliberately non-exhaustive keyword
  → hypothesis-text pattern table — grows as `simulator/failure_injector/`
  grows more scenarios) and `summarize_or_fallback` (try the LLM, degrade
  to a deterministic fallback on absence or failure — never blocks, never
  fabricates). See DDR-010 for why an agent's structured output never
  depends on the LLM being reachable, only its prose `summary` does.
- **`agents/models.py`** — `TriageFinding` (spec §10's shape) and
  `InvestigatorFinding` (spec §11's shared shape for the other four
  agents).
- **`agents/triage.py`** — affected services, time window, investigation
  targets (every service actually seen in the window — including
  distractor services, deliberately: the agent isn't told which are
  real), and evidence-grounded initial hypotheses from nearby
  deployments. No `get_service_metadata()` — no service registry exists
  to back one.
- **`agents/logs.py` / `agents/metrics.py`** — thin wrappers over the
  Phase 3 tools, turning spikes/anomalies into structured `findings`.
- **`agents/code.py`** — reuses `tools.deployments.get_recent_deployments`
  rather than a new git-backed tool (DDR-011): a deployment record already
  carries a commit_sha and change description.
- **`agents/knowledge.py`** — searches the new `knowledge/` corpus (three
  real markdown documents: a runbook, an architecture note, one
  clearly-labeled synthetic historical incident) via
  `tools/knowledge.py`'s keyword search (DDR-012 — no Qdrant/embeddings
  yet, and at this corpus size a vector store would be pure overhead).

Every agent's `investigate(incident_id, llm=None)` is independently
callable and independently tested against a real seeded incident — there
is no orchestrator wiring them together yet (that's Phase 5), and none of
this is wrapped as an LLM-callable tool with allowlisting/timeouts (that's
Phase 8's security hardening, spec §39).
