# Implementation Status

- [x] Phase 1 — Repository + Infrastructure
- [x] Phase 2 — Incident Simulator
- [x] Phase 3 — Evidence Layer
- [x] Phase 4 — Agents
- [x] Phase 5 — Orchestration
- [x] Phase 6 — Evaluation
- [x] Phase 7 — UI
- [x] Phase 8 — Security + Observability
- [x] Phase 9 — Deployment
- [x] Phase 10 — Open Source Release

---

## Phase 1 — Repository + Infrastructure

**Implemented:**
- FastAPI skeleton (`apps/api`) with Pydantic Settings configuration and
  structured (JSON) logging via `structlog`.
- Two health endpoints: `GET /health` (liveness) and `GET /health/ready`
  (readiness — verifies a live Postgres connection, returns 503 if
  unreachable instead of raising).
- Next.js 15 (App Router, TypeScript) skeleton (`apps/web`) with a landing
  page that calls the API's `/health` endpoint to prove end-to-end wiring.
- PostgreSQL 16 via Docker Compose, with a healthcheck gating API startup.
- `docker-compose.yml` wiring `postgres` → `api` → `web`, all ports
  configurable through `.env` (see `.env.example`).
- `pyproject.toml` (`uv`-managed, committed `uv.lock`) and
  `apps/web/package.json` (committed `package-lock.json`); both Dockerfiles
  use frozen/`ci` installs from those locks.
- `Makefile`: `setup`, `dev`, `test`, `lint`, `format`, `reset`, `clean` are
  fully implemented; `incident`, `investigate`, `evaluate`, `benchmark` are
  stubs that name the phase that implements them.
- GitHub Actions CI (`.github/workflows/ci.yml`): ruff lint + format check +
  pytest for the API, eslint + build for the web app. No LLM API key
  required.
- `docs/architecture.md` (Phase 1 slice, Mermaid diagram) and
  `docs/design-decisions.md` (DDR-001 through DDR-005).
- Apache-2.0 `LICENSE`.

**Files changed:** everything under `apps/`, `docs/`, `tests/unit/`,
`.github/workflows/`, plus `docker-compose.yml`, `Makefile`,
`pyproject.toml`, `uv.lock`, `apps/web/package-lock.json`, `.env.example`,
`.gitignore`, `LICENSE`, `README.md`.

**Tests added:** `tests/unit/test_health.py` — liveness returns 200;
readiness returns 503 with no Postgres reachable (proves the probe degrades
gracefully instead of raising).

**Commands actually run in this session, with real output:**
```
uv sync                       # resolved + installed 34 packages, clean
uv run pytest -v              # 2 passed
uv run ruff check .           # All checks passed!
uv run ruff format --check .  # 14 files already formatted
npm install                   # 0 vulnerabilities (after pinning postcss
                               # via an override — see below)
npm run lint                  # clean, no output
npm run build                 # next build succeeded, 4 static pages generated
docker compose config         # validates; env-var interpolation resolves
                               # correctly for all three services
```

**`docker compose up --build` — verified by the repo owner (not in this
sandbox, which blocks Docker Hub's image CDN by network policy):**
```
✔ Image postgres:16-alpine         Pulled
✔ Image incidentlab-web            Built
✔ Image incidentlab-api            Built
Container incidentlab-postgres-1   Healthy
api-1  | INFO: Application startup complete.
api-1  | INFO: Uvicorn running on http://0.0.0.0:8000
api-1  | INFO: 127.0.0.1:... - "GET /health HTTP/1.1" 200 OK   (x4, from the
                                                                  compose healthcheck)
web-1  | ▲ Next.js 15.5.25
web-1  | ✓ Ready in 440ms
```
All three services built, started, and reported healthy with no restart
loops or crash traces; teardown (`Gracefully Stopping...`) was the owner
hitting Ctrl+C, not a failure. Phase 1's definition of done is met.

**Fixed along the way:** `npm install` initially reported 2 vulnerabilities
(1 high) in `postcss`, pulled in transitively by `next@15`'s CSS tooling —
GHSA-qx2v-qp2m-jg93 (XSS in stringified output) and related path-traversal
advisories. Pinned via `"overrides": {"postcss": "^8.5.28"}` in
`apps/web/package.json` rather than jumping to `next@16` (unnecessary
breaking change for Phase 1); `npm audit` now reports 0 vulnerabilities.

**Known limitations:**
- No database schema yet — Postgres is proven reachable, nothing else.
- No auth, no rate limiting — read-only, no sensitive endpoints exist yet.
- Web app has no design system yet; it's a wiring proof, not the SRE
  console UI from Phase 7.
- CI doesn't yet run `docker compose up` end-to-end (no GHA job for it) —
  consider adding a compose-based CI smoke test in a later phase if it
  earns its cost.

**Next phase:** Phase 2 — Incident Simulator.

---

## Phase 2 — Incident Simulator

**Implemented:**
- `core/` package (new, factored out of `apps/api` — see DDR-006):
  `core/config.py` (shared Settings), `core/db.py` (shared async engine,
  `Base`, idempotent `create_all_tables()`), `core/models.py` (the ORM
  schema: `IncidentRecord`, `IncidentGroundTruthRecord` — kept as a
  *separate* table specifically so ground truth can't leak into a normal
  `incidents` query — plus `LogEventRecord`, `MetricPointRecord`,
  `DeploymentRecord`, each with an `is_distractor` flag for the future
  evaluation harness).
- `simulator/models.py` — pure Pydantic DTOs (`GroundTruth`, `LogEvent`,
  `MetricPoint`, `Deployment`, `IncidentDraft`) a failure injector returns,
  independent of persistence.
- `simulator/failure_injector/` — `FailureInjector` ABC plus the first
  scenario, `DbConnectionPoolInjector` (spec §23 Scenario 1): a deploy
  shrinks checkout's DB connection pool from 50 to 5, it saturates ~2
  minutes later, 12 "connection timeout" errors fire, error rate hits 42%
  and p99 latency hits 3200ms — plus distractor noise (an unrelated Redis
  warning, an unrelated deploy to a different service, a CPU blip
  elsewhere, a normal cache-miss log line), matching spec §24. Fully
  deterministic given a fixed `anchor_time` — no randomness anywhere.
- `simulator/scenarios/` — the scenario_id → injector registry
  (`get_injector`, raises with the list of valid ids on an unknown one).
- `simulator/replay.py` — `run_scenario()` (assigns the next sequential
  `INC-XXXX` id, persists incident + ground truth + telemetry in one
  transaction) and the `make incident` CLI entrypoint.
- `Makefile`: `incident` target now works:
  `make incident SCENARIO=db_connection_pool`; fails fast with a usage
  message if `SCENARIO` is omitted.
- `.github/workflows/ci.yml`: added a `postgres:16-alpine` service
  container to the `api` job so integration tests run in CI without
  Docker Compose.
- `.env.example`: fixed `POSTGRES_HOST` — was `postgres` (only correct
  *inside* the Docker network), now `localhost` (correct for host-side
  tools like `make incident` reading `.env` directly; the containerized
  API still hardcodes `postgres` in `docker-compose.yml`, unaffected).

**Files changed:** `core/` (new), `simulator/` (new),
`tests/unit/test_db_connection_pool_scenario.py`,
`tests/unit/test_scenario_registry.py`, `tests/integration/` (new),
`apps/api/main.py` + `apps/api/routes/health.py` (import from `core`
instead of the now-deleted `apps/api/dependencies/`), `Makefile`,
`.github/workflows/ci.yml`, `.env.example`, `pyproject.toml` (pytest
event-loop scope fix — see below), `docs/architecture.md`,
`docs/design-decisions.md` (DDR-006, DDR-007).

**Tests added:**
- Unit (no DB): `test_db_connection_pool_scenario.py` — generation is
  deterministic; timeline bounds are correct; ground truth matches the
  scenario; both real and distractor evidence are present; the trigger
  deployment precedes incident start; non-distractor telemetry is
  correctly scoped to the affected service. `test_scenario_registry.py` —
  known scenario resolves, unknown scenario raises listing valid ids.
- Integration (real Postgres, via `tests/integration/conftest.py`'s
  `clean_db` fixture): `test_replay.py` — a scenario run persists the
  incident and all telemetry; ground truth is confirmed absent from
  `IncidentRecord`'s own columns and present, correctly, in the separate
  table; two runs produce sequential ids (`INC-0001`, `INC-0002`); an
  unknown scenario raises before writing anything. `test_health_ready.py`
  — the readiness probe returns 200 when Postgres is actually reachable
  (the positive case Phase 1 couldn't test without a real DB).
- Fixed a latent bug in Phase 1's own readiness test: it asserted 503
  based on the *accidental* absence of a reachable Postgres in the
  sandbox, not a controlled condition. Rewrote it to mock
  `check_connection` raising, so it's correct regardless of environment
  state (this is what surfaced once a real local Postgres existed for
  Phase 2's integration tests).

**Commands actually run in this session, with real output:**
```
uv run pytest -v         # 15 passed (against a real local Postgres 16 —
                          # this sandbox has `postgresql` installed even
                          # though Docker itself is blocked, so integration
                          # tests could run for real, not just be asserted)
uv run ruff check .      # All checks passed!
uv run ruff format --check .   # 28 files already formatted
make incident SCENARIO=db_connection_pool   # -> Created incident INC-0001
make incident SCENARIO=db_connection_pool   # -> Created incident INC-0002 (sequential)
make incident                                # -> usage error, exit 1 (no SCENARIO)
python -m simulator.replay --scenario nope   # -> "Unknown scenario 'nope'.
                                              #     Available scenarios: db_connection_pool"
psql ... "\d incidents"                      # confirmed: no root_cause /
                                              # affected_component / trigger
                                              # / scenario_id columns on the
                                              # public table
psql ... "SELECT * FROM incident_ground_truths"  # confirmed ground truth
                                                   # rows exist, keyed by
                                                   # incident_id, correct
                                                   # values for both runs
```

**Two real bugs found and fixed while actually running this (not just
reviewed):**
1. `DateTime` columns without `timezone=True` — asyncpg rejected the
   timezone-aware datetimes the simulator generates
   ("can't subtract offset-naive and offset-aware datetimes"). Fixed by
   making every timestamp column `DateTime(timezone=True)`.
2. Cross-mapper insert ordering — `IncidentRecord` and its FK-dependent
   children (`DeploymentRecord`, etc.) were added to the same session
   without an explicit `relationship()`, and SQLAlchemy's flush did not
   reliably insert the parent first, producing a
   `ForeignKeyViolationError`. Fixed with an explicit `await
   session.flush()` after adding the incident, before adding anything
   that references it.

**Known limitations:**
- Only one scenario implemented (`db_connection_pool`) — spec §23 lists
  ten; the rest are future work, added scenario-by-scenario.
- No `simulator/services/` — no real microservice actually runs; see
  DDR-007 for why that's a deliberate simplification, not a gap.
- Still no Alembic — `create_all_tables()` remains fine while the schema
  is this small and still moving.
- Nothing consumes this telemetry as scored, provenanced Evidence yet —
  that's Phase 3.
- Integration tests need a reachable Postgres and are not silently
  skipped without one — documented in the README, not yet auto-detected.

**Next phase:** Phase 3 — Evidence Layer.

---

## Phase 3 — Evidence Layer

**Implemented:**
- `evidence/models.py` — `Evidence` (evidence_id, source_type, source,
  timestamp, content, relevance, provenance) and the full `SourceType`
  enum from spec §9 (only `log`/`metric`/`deployment` are produced so far
  — see DDR-008). No `is_distractor` field exists on `Evidence` at all, so
  a tool can't leak it even by accident.
- `evidence/provenance.py` — `build_evidence_id` (`LOG-1842` /
  `METRIC-203` / `DEPLOY-482`, matching spec §9's own example format) and
  `build_provenance`.
- `evidence/scoring.py` — `temporal_relevance` (1.0 inside the incident
  window, decaying outside it, floor 0.2 — documented as an experimental
  baseline, not a calibrated model) and `matches_query`.
- `tools/incidents.py` — `get_incident` (public fields only) and
  `get_incident_timeline` (chronological merge across logs/metrics/
  deployments).
- `tools/logs.py` — `search_logs` (spec §11) and `find_error_spikes`
  (minute-bucketed error counts).
- `tools/metrics.py` — `query_metrics` and `detect_anomaly` (spec §12),
  against a fixed, documented threshold table.
  `compare_baseline` is intentionally not implemented — no real
  pre-incident baseline data exists to compare against yet (see
  docs/architecture.md).
- `tools/deployments.py` — `get_recent_deployments` (spec §13),
  deliberately not filtered to only the affected service.
- `docs/architecture.md` (Phase 3 slice) and `docs/design-decisions.md`
  (DDR-008: `tools/github.py`/`tools/knowledge.py` deferred to Phase 4 —
  no real commit/PR/runbook data exists yet; DDR-009: `evidence/graph.py`
  deferred to Phase 7 — no consumer until the UI).

**Files changed:** `evidence/` (new), `tools/` (new),
`tests/unit/test_evidence_scoring.py`,
`tests/unit/test_evidence_provenance.py`,
`tests/integration/test_tools.py`, `docs/architecture.md`,
`docs/design-decisions.md`.

**Tests added:**
- Unit (no DB): scoring (`temporal_relevance` inside/outside/floor,
  `matches_query`), provenance (`evidence_id` prefixes, unregistered
  source type raises, provenance fields correct).
- Integration (real Postgres, seeded via `run_scenario`):
  `Evidence.model_fields` structurally has no `is_distractor`;
  `get_incident` exposes only public fields and raises for an unknown id;
  `search_logs` returns exactly the 14 rows the scenario generates
  (including distractor content, unflagged) and its query filter narrows
  correctly; `find_error_spikes` finds exactly one 12-error spike bucket;
  `query_metrics` filters by name; `detect_anomaly` flags the saturated
  connection-pool point but not the healthy baseline one, and rejects an
  unregistered metric name; `get_recent_deployments` spans both the
  affected and the distractor service; `get_incident_timeline` merges all
  three sources in chronological order.

**Commands actually run in this session, with real output:**
```
uv run pytest -v            # 34 passed (11 new for Phase 3), against the
                             # same real local Postgres as Phase 2
uv run ruff check .         # All checks passed!
uv run ruff format --check . # 40 files already formatted
```
Also manually ran the full pipeline (`run_scenario` → `get_incident_timeline`
→ `find_error_spikes`) and printed the actual output to eyeball realism —
correct chronological order, sensible relevance scores (1.00 inside the
window, 0.97 for the trigger deploy 1 minute before it, 0.70 for the
distractor deploy 10 minutes before it), and the error spike detector
correctly found the one 12-error-in-one-minute bucket.

**Known limitations:**
- Only 3 of the spec's 9 source types are backed by real data
  (log/metric/deployment) — commit, pull_request, documentation, runbook,
  historical_incident, and trace all wait on Phase 4's Code/Knowledge
  investigator work landing real data behind them.
- `detect_anomaly`'s thresholds are a hardcoded, documented heuristic
  tuned to make this one scenario legible, not a statistically grounded
  anomaly detector.
- `compare_baseline` (spec §12) doesn't exist — no real baseline data to
  compare against.
- These are plain async functions, not yet wrapped as LangGraph/LLM-
  callable tools (no allowlisting, timeouts, or max-call limits yet) —
  that wiring, and the security hardening from spec §39, are Phase 4/8.

**Next phase:** Phase 4 — Agents.

---

## Phase 4 — Agents

**Implemented:**
- `core/llm/` — spec §44's `LLMProvider` abstraction: `OllamaProvider`
  (default), `OpenAICompatibleProvider`, `AnthropicCompatibleProvider`,
  all raising one `LLMUnavailableError` on any failure, plus
  `factory.get_llm_provider()` reading `core.config.Settings`. `httpx`
  moved from a dev-only to a main dependency (now used by production
  code, not just tests).
- `agents/base.py` — `hypotheses_from_content` (deterministic keyword →
  hypothesis-text pattern matching) and `summarize_or_fallback` (LLM
  narration with a deterministic fallback — see DDR-010 for why an
  agent's *structured* output never depends on LLM availability).
- `agents/models.py` — `TriageFinding`, `InvestigatorFinding`.
- Five agents, each an independently-callable
  `investigate(incident_id, llm=None)`: `agents/triage.py`,
  `agents/logs.py`, `agents/metrics.py`, `agents/code.py` (reuses
  `tools.deployments` — DDR-011), `agents/knowledge.py`.
- `knowledge/` — three real, hand-authored markdown documents: a runbook
  (`db-connection-pool-exhaustion.md`), an architecture note
  (`checkout-service.md`), and one clearly-labeled synthetic historical
  incident (`001.md`).
- `tools/knowledge.py` — `search_knowledge`, `search_historical_incidents`,
  `get_runbook`, keyword search (DDR-012 — no Qdrant/embeddings yet).
- `evidence/models.py` — widened `Provenance.row_id` from `int` to `str`
  so it can reference either a DB row or a knowledge-base file path with
  one shape; `evidence/provenance.py` registered prefixes for
  RUNBOOK/DOCUMENTATION/HISTORICAL_INCIDENT.
- `tools/metrics.py` — added `known_anomaly_metrics()` (public accessor
  agents use instead of reaching into the module's private threshold
  table).
- `docs/architecture.md` (Phase 4 slice) and `docs/design-decisions.md`
  (DDR-010, DDR-011, DDR-012; DDR-008 updated to note `knowledge.py`
  landed).

**Files changed:** `core/llm/` (new), `agents/` (new), `knowledge/` (new),
`tools/knowledge.py` (new), `tools/metrics.py`, `evidence/models.py`,
`evidence/provenance.py`, `core/config.py`, `pyproject.toml` (httpx →
main deps), `tests/unit/test_llm_providers.py`,
`tests/unit/test_agent_base.py`, `tests/unit/test_tools_knowledge.py`,
`tests/integration/test_agents.py`, `docs/architecture.md`,
`docs/design-decisions.md`.

**Tests added:**
- Unit: LLM providers (Ollama/OpenAI-compatible/Anthropic-compatible),
  each tested against `httpx.MockTransport` — success, HTTP error,
  connection error, malformed response, all mapped to
  `LLMUnavailableError`; the factory returns the right type per
  `llm_provider` setting and rejects an unknown one.
  `agents/base.py`'s pattern matching and LLM-or-fallback behavior
  (no LLM, LLM succeeds, LLM raises). `tools/knowledge.py` (no DB
  needed — pure filesystem + no incident-window scoping): default search
  returns every doc, query filters correctly, evidence_id/provenance
  format, `get_runbook` hit and miss.
- Integration (real Postgres, seeded via `run_scenario`): each of the
  five agents' `investigate()` produces the exact structured output
  expected from the scenario's real evidence (triage's two hypotheses
  matching the two deployments; logs' spike finding and the
  connection-pool-exhaustion hypothesis; metrics flagging exactly the
  three metrics that cross their thresholds; code correctly separating
  same-service from different-service deployments; knowledge finding all
  three corpus documents); an agent's `evidence` structurally cannot
  carry `is_distractor`; passing a fake LLM provider is reflected in the
  `summary` field.

**Commands actually run in this session, with real output:**
```
uv sync                   # httpx promoted to main deps, resolved cleanly
uv run pytest -v          # 61 passed (27 new for Phase 4), against the
                           # same real local Postgres as Phases 2-3
uv run ruff check .       # All checks passed!
uv run ruff format --check .   # 62 files already formatted
```
Also manually ran all five agents end-to-end against a fresh incident and
printed their actual structured output (no LLM configured — this sandbox
genuinely has none, confirmed by trying to reach Ollama and both major
hosted APIs before writing this phase). Real, correct results: Triage
found both deployments and both services; Logs found the two error-log
spike buckets and correctly surfaced "Connection pool exhaustion",
"connectivity issue", **and** "Cache layer (Redis) involvement" as
candidate patterns (the Redis distractor is surfaced, not asserted as the
cause — exactly the intended behavior); Metrics flagged exactly the three
anomalous metrics; Code correctly labeled the checkout deploy as
"same service as incident" and the auth deploy as "different service";
Knowledge found all three corpus documents.

**Known limitations:**
- No LLM was actually exercised end-to-end in this sandbox (none is
  reachable) — the Ollama/OpenAI/Anthropic-compatible request/response
  shapes are verified against mocked HTTP, not a live model. Whoever runs
  this with a real Ollama instance is the first real-world exercise of
  that path.
- `hypotheses_from_content`'s pattern table is small and specific to the
  one scenario that exists — by design (DDR-010), but it means it needs
  active upkeep as `simulator/failure_injector/` grows more scenarios.
- No orchestrator ties the five agents together yet — each is
  independently callable and independently tested, matching Phase 4's
  definition of done ("each agent independently executes tools"), but
  nothing yet produces one incident-level result. That's Phase 5.
- Agents are plain async functions, not LangGraph nodes and not wrapped
  as LLM-callable tools with allowlisting/timeouts/max-call-limits (spec
  §39) — that hardening is Phase 5/8.
- `docker-compose.yml` doesn't include an Ollama service yet — nothing
  automatically calls an agent with an LLM today (no orchestrator, no API
  route), so a multi-GB model-serving container would sit idle in the
  default `docker compose up` stack. Add it once Phase 5 gives it a real
  caller, per the same "don't build ahead of the consumer" reasoning as
  DDR-005/DDR-009.

**Next phase:** Phase 5 — Orchestration.

---

## Phase 5 — Orchestration

**Implemented:**
- Refactored `InvestigatorFinding.hypotheses_supported` from `list[str]`
  to `list[HypothesisSignal]` (hypothesis text + exactly which
  evidence_ids support it) across all four investigator agents — the
  Hypothesis Manager needs precise evidence linkage, not fragile
  re-parsing of hypothesis text after the fact.
- `hypotheses/` package: `models.py` (`Hypothesis`), `scoring.py`
  (spec §16's deterministic confidence formula), `contradiction.py`
  (spec §17's Contradiction Detector), `manager.py` (spec §15's
  Hypothesis Manager — merges cross-agent signals via a canonical
  grouping table, DDR-013).
- `agents/adjudicator.py` — spec §18's Adjudicator: `AdjudicationResult`,
  picks the best hypothesis, attaches corroborating Knowledge evidence to
  the winner (DDR-015), recommends an action by citing a real runbook if
  one matched (never a fabricated remediation step).
- `orchestration/` package: `state.py` (`InvestigationState` TypedDict),
  `routing.py` (spec §19's confidence gate, thresholds configurable via
  `core.config.Settings`), `graph.py` (the actual `langgraph.StateGraph`:
  Triage → parallel {Logs, Metrics, Code, Knowledge} → Hypothesis Manager
  → Adjudicator → END, plus the `make investigate INCIDENT=<id>` CLI).
- `langgraph` added as a dependency.
- `core/config.py`: `confidence_strong_threshold` (0.90),
  `confidence_review_threshold` (0.70) — spec §19's own instruction that
  these be configurable, not hardcoded.
- `Makefile`: `investigate` target now works.
- `docs/architecture.md` (Phase 5 slice) and `docs/design-decisions.md`
  (DDR-013, DDR-014, DDR-015).

**Files changed:** `hypotheses/` (new), `orchestration/` (new, beyond the
Phase 1 stub), `agents/adjudicator.py` (new), `agents/models.py`,
`agents/base.py`, `agents/logs.py`, `agents/metrics.py`, `agents/code.py`,
`agents/knowledge.py`, `core/config.py`, `Makefile`, `pyproject.toml`
(langgraph), `tests/unit/test_agent_base.py`,
`tests/integration/test_agents.py` (updated for the `HypothesisSignal`
shape), plus five new test files (see below), `docs/architecture.md`,
`docs/design-decisions.md`.

**Tests added:**
- Unit (no DB — all pure functions over fabricated data):
  `test_hypotheses_scoring.py` (formula cases: zero evidence, full
  coverage, partial coverage, contradiction penalty, floor at zero);
  `test_hypotheses_contradiction.py` (confirmed metric → no contradiction;
  measured-but-not-flagged → contradiction; never-measured → no
  contradiction; non-metric signal → ignored);
  `test_hypotheses_manager.py` (cross-agent signals merge into one
  canonical hypothesis with combined evidence; unmapped signals stand
  alone; sorted descending; multi-source hypotheses outscore
  single-source ones; confirmed metrics produce no contradiction);
  `test_orchestration_routing.py` (gate boundaries, configurable
  thresholds); `test_adjudicator.py` (no hypotheses → insufficient
  evidence; selects the top hypothesis; strong vs. weak confidence gating;
  runbook-matched vs. generic recommended action; contradicting evidence
  carried through; LLM override).
- Integration (real Postgres, seeded via `run_scenario`):
  `test_orchestration.py` — the full graph end to end selects "Connection
  pool exhaustion" with confidence > 0.9, `needs_human_review: False`,
  zero contradictions, and cites the real runbook; hypotheses are sorted;
  no `is_distractor` leakage anywhere in the final result.

**Commands actually run in this session, with real output:**
```
uv add langgraph          # resolved cleanly (PyPI is directly reachable
                           # in this sandbox, unlike Docker Hub)
uv run pytest -v          # 88 passed (27 new for Phase 5), against the
                           # same real local Postgres as Phases 2-4
uv run ruff check .       # All checks passed!
uv run ruff format --check .   # 78 files already formatted
make incident SCENARIO=db_connection_pool   # -> Created incident INC-0001
make investigate INCIDENT=INC-0001
  # Selected hypothesis: Connection pool exhaustion
  # Confidence: 93%
  # Needs human review: False
  # Recommended action: See runbook
  #   'runbooks/db-connection-pool-exhaustion.md' for remediation steps.
  # Contradicting evidence: none detected
  # (6 "llm_summary_unavailable" warnings logged first — Ollama isn't
  #  running here, every agent tried it, failed fast, degraded
  #  gracefully; total wall time ~2 seconds for the whole graph)
uv run python -m orchestration.graph --incident INC-0001 --no-llm
  # identical result, instantly, no LLM attempt at all
make investigate                    # -> usage error (no INCIDENT), exit 1
python -m orchestration.graph --incident INC-9999
  # -> ValueError "Incident 'INC-9999' not found", propagated clearly
  #    through the graph (not swallowed, not fabricated)
```

**Known limitations:**
- No loop-back for more investigation on low confidence (DDR-014) — a
  low-confidence result sets `needs_human_review: True` and stops; it
  doesn't re-invoke agents with a narrower plan. Deferred until there's a
  second scenario to design that against.
- The canonical hypothesis-grouping table (`_CANONICAL_HYPOTHESES`) and
  the keyword-pattern table (`_HYPOTHESIS_PATTERNS`, Phase 4) are both
  small and specific to the one scenario that exists — by design, but
  both need active upkeep as more scenarios are added.
- No LLM was actually exercised end-to-end (same as Phase 4 — none is
  reachable in this sandbox); `make investigate`'s default attempt to
  reach Ollama and gracefully degrade was verified for real, but the
  "LLM actually produces a reasoning summary" path has only been unit
  tested against a fake provider.
- No `/investigations` API endpoints yet (spec §38) — `make investigate`
  is a CLI only; wiring this into `apps/api` is future work once there's
  a UI (Phase 7) to actually call it.
- Still no full spec §21 RCA report format (Executive Summary, Timeline,
  Impact, Uncertainty, Investigation Trace sections) — `AdjudicationResult`
  has the substance (selected hypothesis, confidence, evidence,
  contradictions, recommended action) but not that presentation; that's
  Phase 7's UI layer built on top of this.

**Next phase:** Phase 6 — Evaluation.

---

## Phase 6 — Evaluation

**Implemented:**
- Second scenario, `simulator/failure_injector/redis_unavailable.py`
  (spec §23 Scenario 2), added *before* the evaluation harness itself —
  see DDR-016 for why a benchmark needs more than one possible answer to
  mean anything. New `cache_hit_rate` metric with a `<` anomaly threshold
  (`tools/metrics.py` now supports `>`, `>=`, `<`, `<=`). New runbook
  `knowledge/runbooks/redis-unavailable.md`. Extended
  `hypotheses/manager.py`'s canonical-grouping table to merge
  `cache_hit_rate anomaly` into the Redis hypothesis.
- `agents/adjudicator.py`: `_corroborating_knowledge`/`_recommend_action`
  made public (`corroborating_knowledge`/`recommend_action`) and
  `corroborating_knowledge`'s signature simplified to take
  `list[Evidence]` directly — both now reused by the single-agent
  baseline instead of being duplicated.
- `evaluation/ground_truth.py` — the only module (besides the simulator)
  allowed to read ground truth or `is_distractor` directly; holds the
  root_cause → correct-hypothesis-text mapping.
- `evaluation/baselines.py` — spec §27's Direct LLM (Baseline A,
  confidence structurally fixed at 0.0 — DDR-018) and Single Agent
  (Baseline B, reuses real tools/patterns but no Hypothesis Manager
  sophistication) architectures. Multi-Agent reuses
  `orchestration.graph.investigate` directly — no separate function
  needed.
- `evaluation/metrics.py` — spec §27's metrics as pure functions over a
  `Trial` (result + matching ground truth): root cause accuracy, evidence
  recall/precision, unsupported-claim rate, false-confidence rate, human
  escalation rate, latency; `aggregate()` averages a list into one row.
- `evaluation/datasets.py` — generates the dataset fresh each run (2
  scenarios × 3 instances by default) rather than static fixtures —
  DDR-017 on why this is honestly small, not padded to look like spec
  §28's "50 incidents".
- `evaluation/runner.py` / `evaluation/reports.py` — runs all three
  architectures against the same dataset, scores each, renders spec
  §29's table format; `make benchmark` (and `make evaluate`, an alias)
  now work.
- `docs/architecture.md` (Phase 6 slice) and `docs/design-decisions.md`
  (DDR-016, DDR-017, DDR-018).

**Files changed:** `simulator/failure_injector/redis_unavailable.py`
(new), `knowledge/runbooks/redis-unavailable.md` (new), `evaluation/`
(new package), `tools/metrics.py`, `hypotheses/manager.py`,
`agents/adjudicator.py`, `simulator/scenarios/__init__.py`, `Makefile`,
plus new/updated tests (see below), `docs/architecture.md`,
`docs/design-decisions.md`.

**Tests added:**
- Unit: `test_redis_unavailable_scenario.py` (deterministic, correct
  ground truth, no accidental DB-pool keyword collisions, error_rate
  stays low, cache_hit_rate collapses); `test_evaluation_metrics.py`
  (every metric function against fabricated `Trial`s, including
  aggregation and the empty-dataset edge case).
- Integration (real Postgres): `test_orchestration.py` gained a test
  proving the Redis scenario selects the *different*, correct hypothesis
  and that the Contradiction Detector actually fires and penalizes the
  false "connectivity issue" candidate; `test_tools.py` gained a direct
  test of the new `<` comparison; `test_evaluation.py` — ground truth
  lookup excludes distractor evidence and includes real evidence; Direct
  LLM without an LLM is honestly insufficient; Single Agent picks a
  hypothesis with zero contradiction detection by construction;
  `generate_dataset` produces distinct incidents across both scenarios;
  a full `run_benchmark()` end to end, asserting Direct LLM's 0%
  accuracy/100% escalation and Multi-Agent's 100% accuracy are the real,
  computed numbers, not placeholders.

**Commands actually run in this session, with real output:**
```
uv run pytest -v            # 111 passed (15 new for Phase 6), against
                             # the same real local Postgres as Phases 2-5
uv run ruff check .         # All checks passed!
uv run ruff format --check . # 90 files already formatted
make benchmark               # ran for real — see actual results below
uv run python -m evaluation.reports --instances-per-scenario 1 --llm
                              # confirmed the --llm path works too (tries
                              # Ollama, fails fast, same results, just
                              # higher latency numbers)
```

**Real `make benchmark` output** (6 incidents, no LLM — none reachable in
this sandbox, same as every prior phase):
```
RCA Accuracy         Direct LLM 0%    Single Agent 100%   Multi-Agent 100%
Evidence Recall       Direct LLM 0%    Single Agent 72%    Multi-Agent 78%
Evidence Precision    Direct LLM 0%    Single Agent 82%    Multi-Agent 81%
Unsupported Claims    Direct LLM 0%    Single Agent 0%     Multi-Agent 0%
False Confidence      Direct LLM 0%    Single Agent 0%     Multi-Agent 0%
Human Escalation      Direct LLM 100%  Single Agent 0%     Multi-Agent 0%
Avg Latency           Direct LLM 0.00s Single Agent 0.02s  Multi-Agent 0.05s
```
This is a genuine, non-rigged result, not an assumed conclusion (spec §3
explicitly warns against assuming the answer): for this small dataset,
Single Agent ties Multi-Agent on raw accuracy, but Multi-Agent shows
higher evidence recall at a small precision and latency cost — a real,
disclosed trade-off, not "multi-agent wins everything."

**Known limitations:**
- The dataset is small (6 incidents, 2 scenarios) and honestly disclosed
  as such (DDR-017) — not spec §28's 50-100+, and same-scenario repeats
  are structurally identical except timestamps, not spec §29's "5
  variations" varying services/distractors/severity/volume.
- No LLM was exercised end-to-end for real (same as every prior phase) —
  Direct LLM's 0% accuracy is a genuine finding about this sandbox
  lacking a reachable model, not a demonstration of the baseline's
  ceiling with one configured.
- `tool_calls`/`agent_calls`/`model_tokens` columns from spec §27 aren't
  reported — no call-count instrumentation exists yet (that's closer to
  Phase 8's observability work), and fabricating token counts with no
  live LLM would violate "never fabricate metrics" (spec §29).
- Single Agent's confidence formula is deliberately cruder than
  `hypotheses/scoring.py`'s (a single ratio, no diversity/temporal/
  contradiction terms) — that's the point of the comparison, not an
  oversight, but it means its confidence numbers aren't directly
  comparable to Multi-Agent's in an absolute sense, only in relative
  gating behavior (needs_human_review).
- No CI job runs `make benchmark` — it's exercised by
  `tests/integration/test_evaluation.py`'s `run_benchmark()` call, but
  the formatted-report CLI path itself isn't covered by automated CI.

**Next phase:** Phase 7 — UI.

---

## Phase 7 — UI

**Implemented:**
- `apps/api/routes/incidents.py`, `investigations.py`, `evaluations.py` —
  spec §38's endpoint surface (`GET/POST /incidents`, `GET
  /incidents/{id}`, `POST /incidents/{id}/investigate`, `GET
  /investigations/{id}` + `/timeline` + `/evidence` + `/hypotheses` +
  `/agents`, `POST .../approve` + `.../reject`, `GET /evaluations`,
  `POST /evaluations/run`, `GET /evaluations/{id}`), plus `GET
  /scenarios` (not in spec's list; the UI needs it). None of this is
  persisted beyond what already existed — see DDR-019 (investigations
  recompute fresh, they're not cached/stored), DDR-020 (evaluations live
  in an in-memory dict, not Postgres), DDR-021 (approve/reject are
  acknowledgment-only and say so in the response).
- `apps/api/main.py`: FastAPI `lifespan` hook creating the schema at
  startup — fixes a real bug, see "Bugs found" below.
- `apps/web`: three pages (`/` incident dashboard, `/incidents/[id]`
  investigation console, `/evaluation` benchmark dashboard), a dark
  "SRE console" theme (`app/globals.css`), typed API client
  (`lib/api.ts` + `lib/types.ts`), two small shared components
  (`SeverityBadge`, `ConfidenceBar`). Evidence is rendered as a grouped,
  linked list rather than an interactive graph — DDR-022.
- `apps/api/Dockerfile` updated to copy every package the API now
  transitively imports (`agents`, `orchestration`, `hypotheses`,
  `evidence`, `tools`, `simulator`, `evaluation`, `knowledge`) — it only
  copied `core` and `apps/api` before, which would have broken the
  containerized image the moment these routes were added.

**Files changed:** `apps/api/routes/incidents.py` (new),
`investigations.py` (new), `evaluations.py` (new), `apps/api/main.py`,
`apps/api/Dockerfile`, `agents/adjudicator.py` (precision fix — see
below), `apps/web/app/page.tsx` (rewritten), `apps/web/app/layout.tsx`,
`apps/web/app/globals.css` (new), `apps/web/app/incidents/[id]/page.tsx`
(new), `apps/web/app/evaluation/page.tsx` (new),
`apps/web/components/SeverityBadge.tsx` (new),
`apps/web/components/ConfidenceBar.tsx` (new), `apps/web/lib/api.ts`
(new), `apps/web/lib/types.ts` (new), `apps/web/eslint.config.mjs`
(exclude generated `next-env.d.ts`), plus new/updated tests (below),
`docs/architecture.md`, `docs/design-decisions.md`.

**Tests added:**
- Integration (real Postgres): `test_api_incidents.py`,
  `test_api_investigations.py`, `test_api_evaluations.py` — every route,
  including 404s for unknown incidents/evaluations and 400 for an
  unknown scenario_id. `test_api_lifespan.py` — a dedicated regression
  test for the schema-creation bug (see below): drops every table, drives
  the app's actual `lifespan` context manager directly (the one place
  it's exercised at all — plain `httpx.ASGITransport` doesn't trigger
  ASGI lifespan events the way a real server does), confirms a query
  against the now-recreated table succeeds.
- `tests/unit/test_adjudicator.py` gained a regression test for the
  keyword-matching precision bug (see below): a doc sharing only one
  generic word with the hypothesis must not be treated as corroborating.

**Commands actually run in this session, with real output:**
```
uv run pytest -v              # 132 passed (17 new for Phase 7)
uv run ruff check .           # All checks passed!
uv run ruff format --check .  # 97 files already formatted
cd apps/web && npm run lint   # clean
cd apps/web && npm run build  # succeeds, types check
```
Then — per the "start the dev server and use the feature in a browser"
instruction — actually ran both servers (`uvicorn` + `next dev`) and
drove the whole UI with a real headless browser (Playwright): generated
an incident, ran an investigation, reviewed the RCA, approved it, ran the
benchmark. Screens captured at every step. This is what caught both real
bugs below — neither showed up in `pytest`, `npm run build`, or a code
read.

**Bugs found by manually testing the UI, fixed same phase:**
1. `GET /incidents` 500'd (`UndefinedTableError`) against a truly fresh
   database — only `run_scenario()` ever created the schema, and a
   read-only route (like the dashboard's own first load) had no write to
   piggyback that on. Fixed with the `lifespan` hook above. This had
   **zero test coverage before this phase** — every integration test's
   `clean_db` fixture calls `create_all_tables()` itself, which silently
   masked the bug from the entire existing suite regardless of the API
   code; `test_api_lifespan.py` is the first test that actually exercises
   the app's own schema-creation path.
2. `corroborating_knowledge()`'s any-keyword-match rule was pulling the
   *wrong* runbook (and the architecture doc) into "supporting evidence"
   for the DB connection-pool hypothesis, purely because they all share
   the generic word "connection" — obvious the moment it rendered as a
   wall of irrelevant markdown in the actual UI, far less obvious from
   unit tests using short fabricated strings. Fixed by requiring at least
   two matching keywords. See `docs/design-decisions.md`'s closing
   section for both, in more detail.

**Known limitations:**
- No Ollama service in `docker-compose.yml` — the UI's "use LLM" toggle
  now has a genuine caller (unlike when this was deferred in Phase 4),
  but a multi-GB model pull as the default `docker compose up` experience
  is still the wrong trade-off; Ollama is meant to be run natively
  anyway (GPU access). Documented in the README instead of wired in.
- Approve/Reject and the evaluation store are exactly as limited as
  DDR-021/DDR-020 say — acknowledgment-only, in-memory, not audited.
- No loading skeletons/error retry UX beyond a plain error box — this is
  a working console, not a polished product; revisit if it's ever
  user-facing beyond local dev.
- The `/investigations/*` sub-resource endpoints (`/timeline`,
  `/evidence`, `/hypotheses`, `/agents`) exist for spec §38 completeness
  but the web UI doesn't call them — it uses the one `POST
  .../investigate` response for everything, so they're tested at the API
  level but not exercised by the frontend.
- No CI job builds or lints the web app on every push — Phase 1's
  `.github/workflows/ci.yml` has a `web` job (lint + build), so this is
  covered, but nothing runs the Playwright-driven browser check from
  this phase in CI; it was a one-time manual verification.

**Next phase:** Phase 8 — Security + Observability.

---

## Phase 8 — Security + Observability

**Implemented:**
- `tools/registry.py` — spec §38-40's tool permission layer as one
  decorator (`@allowlisted_tool`) applied to all ten tool functions
  (`tools/incidents.py`, `tools/logs.py`, `tools/metrics.py`,
  `tools/deployments.py`, `tools/knowledge.py`), rather than four separate
  mechanisms — see DDR-023:
  - A live allowlist (`allowed_tools()`) and a `call_tool(name, ...)`
    dispatch function raising `ToolNotAllowed` for any unregistered name.
  - A per-call timeout (`asyncio.wait_for`, `Settings.tool_timeout_seconds`,
    default 10s), raising `ToolTimeoutError`.
  - A shared per-investigation call budget
    (`Settings.max_tool_calls_per_investigation`, default 100), enforced
    via a mutable counter behind a `ContextVar` so it's correctly shared
    across LangGraph's parallel investigator nodes; raises
    `ToolBudgetExceededError`. Reset once per investigation by
    `orchestration.graph.investigate()`.
  - A structured `structlog` audit log line (tool, duration, outcome) and
    an OpenTelemetry span on every call, satisfying spec §39's audit
    trail and §42's observability with one mechanism.
- `core/telemetry.py` — spec §42's structured traces: a private
  `TracerProvider` (not the global `opentelemetry.trace` API, which only
  allows being set once per process — DDR-026), defaulting to a
  `ConsoleSpanExporter`. No real collector stood up (same reasoning as
  never standing up Qdrant, DDR-012).
- `orchestration/graph.py` — graceful degradation (DDR-024, spec §43's
  own worked example): every node (`triage`, the four investigators,
  `adjudicate`) catches its agent's exceptions and returns a
  `degraded=True` finding instead of crashing the whole investigation,
  except a nonexistent `incident_id` (`ValueError`), which still fails
  fast — every agent would fail identically and there's no investigation
  to salvage. `investigate()` now enforces an overall
  `Settings.investigation_timeout_seconds` ceiling
  (`InvestigationTimeoutError`, mapped to HTTP 504 in
  `apps/api/routes/investigations.py`) on top of each tool's own timeout.
- `agents/models.py` — `TriageFinding.degraded` /
  `InvestigatorFinding.degraded` (default `False`), mirrored in
  `apps/web/lib/types.ts` and surfaced as a "degraded" badge in the
  investigation console instead of the usual success checkmark.
- `agents/base.py` — `format_evidence_for_prompt()`, spec §41's
  prompt-injection defense in depth on top of DDR-010's existing
  structural guarantee (DDR-025): every agent and the adjudicator now
  build LLM prompts through this helper, which wraps evidence content in
  an explicit `<evidence label="...">` block with an untrusted-data
  preamble.
- `apps/api/validation.py` — `IncidentId`, a FastAPI `Path` type
  constraining every route's `incident_id` parameter to this project's
  own `INC-<n>` shape (DDR-027) — found and fixed a real bug (a null byte
  reaching asyncpg raw and coming back as an uncaught 500). Applied across
  `apps/api/routes/incidents.py` and `investigations.py`.
- `apps/api/routes/evaluations.py` — `RunEvaluationRequest.
  instances_per_scenario` capped at 20 (`Field(ge=1, le=20)`) — spec
  §41's "oversized requests" in practice: each instance runs three
  architectures' worth of real investigations.
- `core/config.py` — `tool_timeout_seconds` (10.0),
  `max_tool_calls_per_investigation` (100, validated against a real
  measured investigation — see below), `investigation_timeout_seconds`
  (120.0).
- `opentelemetry-api`/`opentelemetry-sdk` added as main dependencies.
- `docs/architecture.md` (Phase 8 slice) and `docs/design-decisions.md`
  (DDR-023 through DDR-027).

**Files changed:** `tools/registry.py` (new), `core/telemetry.py` (new),
`apps/api/validation.py` (new), `core/config.py`, `orchestration/graph.py`,
`agents/models.py`, `agents/base.py`, `agents/triage.py`, `agents/logs.py`,
`agents/metrics.py`, `agents/code.py`, `agents/knowledge.py`,
`agents/adjudicator.py`, `tools/incidents.py`, `tools/logs.py`,
`tools/metrics.py`, `tools/deployments.py`, `tools/knowledge.py`,
`apps/api/routes/incidents.py`, `apps/api/routes/investigations.py`,
`apps/api/routes/evaluations.py`, `apps/web/lib/types.ts`,
`apps/web/app/incidents/[id]/page.tsx`, `pyproject.toml`, plus five new
test files (below), `docs/architecture.md`, `docs/design-decisions.md`.

**Tests added:**
- Unit: `test_tools_registry.py` (allowlist registration, `call_tool`
  dispatch and its `ToolNotAllowed` rejection, unbudgeted calls outside an
  investigation context, budget enforcement and its concurrent-sharing
  behavior, timeout enforcement, structured audit logs on both success and
  failure). `test_prompt_injection_defense.py` (delimiter wrapping,
  untrusted-data framing, deterministic hypothesis matching is unaffected
  by an injection payload, and — the sharpest version of the claim — a
  fully-compromised `EchoLLM` that does exactly what an injected
  instruction says can still only distort the `summary` field, never the
  structured signal). `test_telemetry.py` (real spans with real
  attributes via an attached `InMemorySpanExporter`).
- Integration (real Postgres): `test_orchestration_resilience.py` —
  monkeypatches real agent functions (`agents.logs.investigate`,
  `agents.triage.investigate`, all four investigators at once) to raise,
  confirming the rest of the investigation still completes with a real
  result, and that a nonexistent incident still raises `ValueError`
  rather than degrading; a slow triage agent is actually cancelled by
  `Settings.investigation_timeout_seconds`. `test_api_security.py` —
  SQL-injection-shaped, null-byte, path-traversal, script-tag, and
  10,000-character `incident_id`s; malformed/oversized/missing JSON
  bodies; an oversized/negative/zero `instances_per_scenario`; confirms
  every one reaches a clean 4xx and never disturbs a real incident.

**Commands actually run in this session, with real output:**
```
uv add opentelemetry-api opentelemetry-sdk   # resolved cleanly, 3 packages
uv run pytest -q             # 182 passed (50 new for Phase 8), against
                              # the same real local Postgres as every
                              # prior phase
uv run ruff check .          # All checks passed!
uv run ruff format --check . # clean (one file auto-reformatted along
                              # the way)
```
Also measured a real investigation's actual tool-call volume directly
(not guessed): `db_connection_pool`, no LLM configured — **38 tool calls**
end to end, which is what set `max_tool_calls_per_investigation`'s default
of 100 (comfortable headroom, not an arbitrary round number). Console span
output was captured and inspected during that run — real
`tool.<name>`/`agent.<name>`/`investigation` spans with real
`incidentlab.*` attributes (tool name, incident_id, outcome,
duration_seconds), not just asserted to exist.

**A real bug found while writing this phase's own security tests (not
reviewed in beforehand):** a null byte inside `incident_id`
(`INC-0001%00INC-0002`) reached asyncpg raw and came back as an uncaught
`asyncpg.exceptions.CharacterNotInRepertoireError` — a 500, not the clean
404 every other malformed id already got. Fixed with
`apps/api/validation.py`'s `IncidentId` path-pattern constraint
(`^INC-\d+$`) rather than trying to catch every downstream failure mode
one at a time — see DDR-027. Same pattern as both Phase 7 bugs: found by
actually exercising the system adversarially, not by code review.

**Known limitations:**
- No real OTel collector (Jaeger, Tempo, etc.) is stood up — spans are
  real and inspectable via `ConsoleSpanExporter`/`InMemorySpanExporter`
  (tests), but nothing in `docker-compose.yml` visualizes them yet. Same
  reasoning as never standing up Qdrant (DDR-012): nothing in this
  project's infra exists for a collector to be verified against here.
- The tool-call budget and timeouts are per-investigation defaults tuned
  against this project's one well-measured scenario (38 calls); they
  haven't been stress-tested against a pathological/adversarial tool
  (e.g. one that hangs just under the timeout on every call) — the
  mechanism is tested directly (`test_tools_registry.py`), but not that
  specific failure shape end to end.
- `call_tool()`'s name-based dispatch exists for a future LLM-driven
  tool-calling loop but has no real caller yet — today's agents still
  call tool functions directly via Python imports, since the LLM here
  never chooses which tool to call. Groundwork, not a currently-exercised
  path.
- Prompt-injection defense is structural + a labeled delimiter, not a
  content filter or classifier — deliberately, since DDR-010's existing
  guarantee already makes the structured output immune; a content filter
  would be defending a surface (`summary`/`reasoning_summary` prose) that
  was already understood to be low-stakes narration, not the
  investigation's actual conclusion.
- No rate limiting or auth exists at the API layer — this phase hardens
  against malformed/oversized/adversarial *content*, not against a
  high-volume or unauthenticated *caller*; still explicitly out of scope
  per the project's local-first, no-auth-yet posture (Phase 1's own known
  limitations).

**Next phase:** Phase 9 — Deployment.

---

## Phase 9 — Deployment

**Implemented:**
- `core/config.py` / `apps/api/main.py` — CORS origins are now
  `Settings.cors_allowed_origins` (comma-separated, configurable) instead
  of Phase 1's hardcoded `http://localhost:3000` — see DDR-028. Found
  while scoping this phase: any real deployment would have had the web
  UI silently broken by the browser's own CORS enforcement, with no
  server-side error pointing at the cause.
- `apps/api/Dockerfile` / `apps/web/Dockerfile` — both now run as an
  unprivileged user (`appuser` uid 1000 / the official Node image's
  built-in `node` user) and declare their own `HEALTHCHECK` instruction,
  not relying solely on `docker-compose.yml`'s (DDR-029).
- `docker-compose.yml` — `restart: unless-stopped` on all three services;
  `CORS_ALLOWED_ORIGINS` threaded through to `api`.
- `.dockerignore` — extended (already existed since Phase 1) to also
  exclude `__pycache__`, `*.pyc`, `.github`.
- `.github/workflows/docker-publish.yml` — new: intended to build and
  push `apps/api`/`apps/web` to GHCR, gated on the existing `CI` workflow
  succeeding on `main` (`workflow_run`, not a direct `push` trigger), so
  a red `main` never gets published as a good build — DDR-030. **Not yet
  working in practice** — see this file's Phase 10 entry (added during a
  later review pass) for the confirmed failure reason and current
  status; do not treat "the workflow exists" as "images are published."
- `docs/deployment.md` — new: pre-built-image vs. build-on-host
  deployment options, the `.env` values that must change for a real
  deployment (table: `POSTGRES_PASSWORD`, `CORS_ALLOWED_ORIGINS`,
  `NEXT_PUBLIC_API_URL`, `ENVIRONMENT`), what's deliberately out of scope
  and why (TLS/reverse proxy, managed Postgres, Ollama as a service, real
  scaling, Alembic), backup guidance (`pg_dump` against the named
  volume), and log guidance.
- `.env.example` — added `CORS_ALLOWED_ORIGINS`; also backfilled Phase
  8's `TOOL_TIMEOUT_SECONDS`/`MAX_TOOL_CALLS_PER_INVESTIGATION`/
  `INVESTIGATION_TIMEOUT_SECONDS`, which existed in `core/config.py` but
  were never added to this file.
- `docs/architecture.md` (Phase 9 slice) and `docs/design-decisions.md`
  (DDR-028 through DDR-031 — CORS, container hardening, GHCR publishing,
  and Alembic's deferral explicitly reaffirmed for this phase rather than
  silently carried over).

**Files changed:** `core/config.py`, `apps/api/main.py`,
`apps/api/Dockerfile`, `apps/web/Dockerfile`, `docker-compose.yml`,
`.dockerignore`, `.env.example`, `.github/workflows/docker-publish.yml`
(new), `docs/deployment.md` (new), plus two new test files (below),
`docs/architecture.md`, `docs/design-decisions.md`.

**Tests added:**
- Unit: `test_config.py` — `cors_allowed_origins_list` parsing: default,
  comma-separated, whitespace-trimmed, empty-entry-dropping (a trailing
  comma must not produce a `""` origin — starlette's `CORSMiddleware`
  treats that as a real, wrong value), fully-empty-string case.
- Integration (real Postgres, real running app via `httpx.ASGITransport`):
  `test_api_cors.py` — a request from the configured origin gets
  `access-control-allow-origin` echoed back; a request from an
  unconfigured origin gets no such header at all (the actual property a
  browser relies on, not just that the setting parses).

**Commands actually run in this session, with real output:**
```
uv run pytest -q              # 189 passed (7 new for Phase 9), against
                               # the same real local Postgres as every
                               # prior phase
uv run ruff check .           # All checks passed!
uv run ruff format --check .  # 99 files already formatted
docker compose config --quiet # valid — env-var interpolation, the new
                               # CORS_ALLOWED_ORIGINS pass-through, and
                               # restart: unless-stopped on all three
                               # services all resolve correctly
```
Also actually started the Docker daemon in this sandbox (it can run —
new information this phase; prior phases only knew Docker Hub was
unreachable, not whether `dockerd` itself would even start here) and
attempted a real `docker build` of `apps/api/Dockerfile`, to see how far
image resolution would actually get: `docker pull hello-world` returned
`403 Forbidden` from `production.cloudfront.docker.com` (Docker Hub's
blob CDN, blocked by the organization's egress policy — matches Phase
1's finding); `docker build` separately got as far as a metadata `HEAD`
request to `registry-1.docker.io` before hitting a `429 Too Many
Requests` from Docker Hub's own anonymous-pull rate limit, on a retry
too. Two different, independently-confirmed reasons neither `docker
build` nor `docker compose up --build` can complete in this sandbox —
not a single flaky failure. `docs/deployment.md` states this precisely
rather than glossing over it.

**Known limitations:**
- Still genuinely unverified end to end: no `docker build`/`docker
  compose up --build` has completed in this sandbox in any phase,
  including this one — everything Docker-related here is correct by
  inspection, by `docker compose config` validation, and by matching
  well-established patterns (multi-stage builds, `docker/build-push-action`),
  not by a build/run that finished. The repo owner completing a real
  `docker compose up --build` (as in Phase 1) is still the actual
  end-to-end check.
- `docker-publish.yml` had never executed as of when this entry was
  first written (no GitHub Actions runner in this sandbox). **Update
  (later review pass, see this file's Phase 10 entry):** it has since
  run for real on GitHub's own runners and failed every time — a real
  bug, not a hypothetical caveat. Left here, uncorrected in place, as an
  honest record of what was known at the time; do not read this bullet
  as current status.
- No TLS/reverse proxy, no managed Postgres, no Ollama service, no real
  horizontal scaling story — all explicitly scoped out in
  `docs/deployment.md` with reasons, not silently absent.
- Alembic is still not implemented — DDR-031 reaffirms Phase 1's
  original deferral (DDR-004) with deployment-specific reasoning rather
  than treating it as settled from four phases ago.
- No automated backup schedule — `docs/deployment.md`'s `pg_dump`
  guidance is manual; this is disclosed as a deliberate scope cut (a
  lab/demo system with regeneratable data), not an oversight.
- `docker-publish.yml` builds a single architecture (whatever the GitHub
  runner provides, currently `linux/amd64`) — no multi-arch `buildx`
  matrix; revisit if an actual arm64 deployment need shows up.

**Next phase:** Phase 10 — Open Source Release.

---

## Phase 10 — Open Source Release

**Implemented:**
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1, unmodified.
- `SECURITY.md` — private vulnerability-reporting path (GitHub security
  advisory + email), scope, and an explicit "known, deliberate
  limitations — not vulnerabilities to report" section naming what
  Phases 1/8/9 already disclosed (no auth/rate-limiting, no TLS, the
  bounded-but-real cost of `/evaluations/run`).
- `CONTRIBUTING.md` — dev setup (mirrors the README), the DDR convention
  explained for a newcomer (with pointers to specific existing DDRs as
  examples of the expected honesty/specificity), the concrete
  "adding a scenario needs these five pieces together" checklist, code
  style (including this project's "no comments unless the why is
  non-obvious" convention), and a PR checklist.
- `.github/ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml`,
  `config.yml` (security advisories + discussions as contact links,
  rather than a blank issue for either) — both templates point at
  `docs/architecture.md`/`design-decisions.md` before someone re-files
  something already reasoned through there.
- `.github/pull_request_template.md` — mirrors `CONTRIBUTING.md`'s
  checklist exactly, so the two can't drift apart silently.
- `CHANGELOG.md` — Keep a Changelog format; a `0.1.0` entry summarizing
  all ten phases at release-note granularity (distilled from this file,
  not duplicating its exhaustive per-phase detail), including a
  "Known limitations" section so the release notes themselves don't
  overclaim.
- `pyproject.toml` — added `authors` and `[project.urls]`
  (Homepage/Repository/Issues/Changelog).
- `README.md` — CI/License/Contributor-Covenant badges, status line
  changed from "Phase 9 of 10" to "v0.1.0 — all 10 phases complete" with
  an explicit sentence that this means every phase shipped, not that
  every disclosed limitation is resolved; a new "Contributing" section
  linking `CONTRIBUTING.md`/`CODE_OF_CONDUCT.md`/`SECURITY.md`/
  `CHANGELOG.md`.
- A `v0.1.0` annotated git tag, created locally (see "Known limitations"
  below — pushing it hit a real, confirmed permission gap in this
  session, not something silently skipped).
- `docs/architecture.md` (Phase 10 slice) and `docs/design-decisions.md`
  (DDR-032).

**Files changed:** `CODE_OF_CONDUCT.md` (new), `SECURITY.md` (new),
`CONTRIBUTING.md` (new), `CHANGELOG.md` (new),
`.github/ISSUE_TEMPLATE/bug_report.yml` (new),
`.github/ISSUE_TEMPLATE/feature_request.yml` (new),
`.github/ISSUE_TEMPLATE/config.yml` (new),
`.github/pull_request_template.md` (new), `pyproject.toml`, `README.md`,
`docs/architecture.md`, `docs/design-decisions.md`. The `v0.1.0` tag
exists locally in this session only (see "Known limitations") — it is
not part of the pushed commit history.

**Tests added:** none — this phase is documentation and repository
metadata, not application code. `uv sync` was re-run to confirm the
`pyproject.toml` metadata additions (`authors`, `[project.urls]`) don't
break dependency resolution; the full existing suite (189 tests) and
`ruff check`/`format --check` were re-run to confirm nothing else
regressed.

**Commands actually run in this session, with real output:**
```
uv sync                       # Resolved 64 packages — authors/urls
                               # metadata doesn't affect resolution
uv run pytest -q               # 189 passed (no new tests this phase —
                               # see above), same real local Postgres as
                               # every prior phase
uv run ruff check .            # All checks passed!
uv run ruff format --check .   # clean
git tag -a v0.1.0 -m "..."     # created locally
git push origin v0.1.0         # HTTP 403, retried once, still 403 —
                                # NOT a transient network error: this
                                # exact push mechanism had just pushed
                                # this phase's own commit successfully
                                # moments earlier. `git ls-remote --tags
                                # origin` confirms no tag reached origin.
```

**Known limitations:**
- **`docker-publish.yml` (Phase 9) has never successfully published an
  image — discovered in a later review pass, not when this phase was
  first written.** Checking the workflow's actual run history on GitHub
  (`mcp__github__actions_list`/`get_job_logs`, not assumed) shows all 3
  runs since Phase 9 failed identically: `ERROR: failed to build: Cache
  export is not supported for the docker driver.` The runner's default
  `docker` buildx driver doesn't support `cache-to: type=gha` — the
  workflow needs a `docker/setup-buildx-action@v3` step (which selects
  the `docker-container` driver) before `docker/build-push-action`,
  which it doesn't have. No image has ever reached
  `ghcr.io/<owner>/incidentlab-api` or `-web`. This is a real,
  root-caused bug in the workflow file itself, not a permissions issue
  or a sandbox limitation — fixing it (adding the missing setup step)
  was out of scope for the review pass that found it, which was
  documentation/consistency-focused; `README.md` and `docs/deployment.md`
  were corrected to stop claiming images are published, and this is
  flagged here as the concrete next action for whoever picks this back
  up.
- **The `v0.1.0` tag itself never reached `origin`.** `git push origin
  v0.1.0` returned a persistent `HTTP 403` (not a flake — retried once,
  and this session's git credential had just successfully pushed a
  commit to `main` via the same mechanism). This session's credential
  can evidently push `refs/heads/*` but not create `refs/tags/*` — a
  narrower permission scope than branch pushes, discovered by trying,
  not assumed going in. The tag exists only in this session's local
  clone and is lost once it ends. Recreating it is one command from a
  machine with full push access: `git tag -a v0.1.0 -m "..." && git
  push origin v0.1.0` against commit `4652168` (already on
  `origin/main`) — or GitHub's own "Draft a new release" UI, which
  creates the tag and a Release object together, also closing the next
  gap below.
- No GitHub Release object exists (a Releases-UI entry with release
  notes attached to a tag) — no tool available in this session's toolset
  exposes creating one (only reading existing releases/tags). A
  one-time, few-minute action for the repo owner: GitHub's "Draft a new
  release" UI, with `CHANGELOG.md`'s `[0.1.0]` section as the body.
- The repository's GitHub-side description and topics are still unset —
  same reason: no available tool exposes that GitHub API surface. Also a
  one-time manual step (repo Settings, or the gear icon next to "About"
  on the repo's main page).
- `docker-publish.yml` (Phase 9) only tags images `latest` and by commit
  SHA — it doesn't yet build a versioned image tag on a `v*` tag push.
  Not added this phase to keep the two concerns (GHCR publishing
  cadence, semantic-version tagging) from being conflated without an
  actual consumer asking for pinned version tags yet — the same
  "don't build ahead of a real need" reasoning as DDR-030's multi-arch
  call and DDR-031's Alembic deferral.
- `CHANGELOG.md` will need real maintenance discipline going forward
  (an entry per meaningful external-facing change) that this
  phase-based build process didn't previously need, since
  `docs/IMPLEMENTATION_STATUS.md` already served that role internally —
  worth calling out explicitly so it doesn't silently go stale the way
  an added-then-abandoned changelog often does.

**This is the last phase of the original build spec.** IncidentLab
v0.1.0 is a complete, working system across all ten phases — not a
finished product with every disclosed limitation resolved. Continued
work from here is genuinely open-ended (see `README.md`'s Roadmap and
this file's own "Known limitations" sections throughout), which is the
intended shape for an open-source project at this point, not a gap in
the plan.

**Update (repo owner request):** `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`,
and `SECURITY.md` were removed at the repo owner's explicit request,
after this phase and the "Post-release accuracy review" below, to drop
the GitHub-generated community-profile tabs their presence causes and
keep the repo's public-facing surface to just `README.md` and
`LICENSE`. References to the three files were removed from
`CHANGELOG.md`, the issue/PR templates, and `README.md`'s badges and
Contributing section; the security-advisory contact link in
`.github/ISSUE_TEMPLATE/config.yml` was kept as-is (it points at
GitHub's own private reporting form, not at `SECURITY.md`). See
`docs/design-decisions.md` DDR-032's update note.

---

## Post-release accuracy review

Not a new phase — a documentation/consistency review of the completed
10-phase codebase, done at the user's explicit request after Phase 10.
Scope was strictly `README.md` and the consistency of
`CHANGELOG.md`/`SECURITY.md`/`CONTRIBUTING.md`/`CODE_OF_CONDUCT.md`/issue
and PR templates with the actual, verified project state — no
application code, no new agents/integrations/architecture.

**What this found, by actually checking rather than assuming:**
- Queried the real GitHub Actions run history for
  `docker-publish.yml` and `ci.yml` (`mcp__github__actions_list`,
  `mcp__github__get_job_logs`) rather than relying on what earlier
  phases' docs claimed. Result: `ci.yml` has passed on every push (12/12
  runs green); `docker-publish.yml` has failed on all 3 of its runs,
  every time at the same `docker/build-push-action` step, with the same
  root cause (`Cache export is not supported for the docker driver` — a
  missing `docker/setup-buildx-action` step). No image has ever reached
  GHCR. Every place `README.md`, `docs/deployment.md`, and
  `docs/architecture.md` stated or implied that images "are published"
  has been corrected to state plainly that the workflow exists but has
  not yet succeeded, with the specific failure reason and a pointer to
  the Actions tab for current status.
- Re-confirmed via `git ls-remote --tags origin` that the `v0.1.0` tag
  is still not on GitHub, and that no GitHub Release exists — `README.md`
  now states this explicitly in a dedicated "Project Status" section
  rather than leaving it inferrable only from `docs/design-decisions.md`.
- `README.md` was substantially restructured (not just amended) to be
  legible to a reader evaluating the project quickly (what it is, the
  engineering problem, why the architecture is shaped this way, the
  actual measured benchmark numbers in a table, the security model, how
  to run it) while keeping every factual claim traceable to what's
  actually implemented and verified elsewhere in this repo — no new
  metrics, no changed benchmark methodology, no invented public URL. A
  "Live Demo" section states plainly that none exists yet, and a
  "Screenshots" section states plainly that none are included, rather
  than a broken image link or an invented one.
- `CHANGELOG.md`'s `0.1.0` entry's "automated GHCR image publishing"
  bullet was corrected to reflect that the workflow exists but has not
  yet succeeded — the previous wording read as a shipped capability, but
  the underlying automation itself, not just its use, does not yet work
  as described.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and the
  issue/PR templates were reviewed against the corrected `README.md` and
  found already consistent — none of them made a claim this review
  needed to correct.

**Verification run this pass:** `uv run pytest -q` (189 passed, no test
files touched — this was a documentation-only review), `uv run ruff
check .` and `uv run ruff format --check .` (clean), `uv sync` (resolves
cleanly). `git diff`/`git status` were reviewed before committing to
confirm the change set matched exactly what's described above.

**Still requires a manual GitHub-side action, unchanged from Phase 10,
now with one addition:**
1. Push the `v0.1.0` tag and publish a GitHub Release from it (blocked
   by this session's/toolset's permissions, not attempted again this
   pass since nothing about that permission changed).
2. Set the repository's description/topics (same reason).
3. **New:** fix `docker-publish.yml` by adding a
   `docker/setup-buildx-action@v3` step before the build/push step, then
   confirm a run actually succeeds and an image lands on
   `ghcr.io/<owner>/incidentlab-api`/`-web` before re-describing GHCR
   publishing as working in any doc.

**Update (GHCR fixed):** item 3 above was completed (by the repo owner
directly, outside this session) — the missing
`docker/setup-buildx-action@v3` step was added to
`.github/workflows/docker-publish.yml`, and the workflow's next run
succeeded: both the `api` and `web` jobs passed, confirmed against
GitHub's real Actions run history (`mcp__github__actions_list`,
`mcp__github__get_job_logs`) for that specific run, not assumed. Every
place that had been corrected above to say GHCR publishing "has not yet
succeeded" was corrected back — `README.md`, `docs/deployment.md`,
`docs/architecture.md`, `CHANGELOG.md`, and the bug-report issue template
now state that pre-built images are published. Items 1 and 2 above
remain open.

---

## Render deployment readiness

Not a new phase — preparing the existing, already-complete codebase for
deployment to Render specifically, at the user's request (a Render
account already connected to the GitHub repo). Scope: `render.yaml`, a
real bug in the frontend's API-URL handling that this work surfaced and
fixed, `docker-compose.yml`/`.env.example`/both Dockerfiles' small
env-driven adjustments, and `docs/deployment.md`. No new agents, no
orchestration/evaluation changes, no product features.

**A real bug found and fixed, not assumed:** `apps/web/lib/api.ts` read
`process.env.NEXT_PUBLIC_API_URL` at module load — Next.js inlines every
`NEXT_PUBLIC_*` reference into the browser bundle at `docker build`
time, so this value had *never* actually been configurable at container
runtime, in any environment, including this project's own local
`docker compose up`. It only ever "worked" because the hardcoded
`"http://localhost:8000"` fallback happened to match Compose's specific
topology. On Render — where the API's real URL is an assigned hostname —
this would have silently broken every request the deployed frontend
makes. Fixed with a same-origin runtime-config route
(`apps/web/app/api/config/route.ts`, reading a plain, non-prefixed
`API_URL` server env var, `force-dynamic` so it can't be statically
baked either) that `apps/web/lib/api.ts` now calls once per page load
instead of reading a build-time constant. See
`docs/design-decisions.md` DDR-033 for the full mechanism and how it was
verified (grepped the built bundle for zero API-URL references; started
the actual production standalone build with a value that was never
present at build time and confirmed `/api/config` returned exactly that
value; ran the full investigation flow through a real headless browser
against that build).

**Implemented:**
- `render.yaml` (new) — a Render Blueprint: one free Postgres database
  (`incidentlab-db`, version 16, matching `docker-compose.yml`) and two
  `runtime: docker` services (`incidentlab-api`, `incidentlab-web`)
  pointed at the existing Dockerfiles unchanged in build shape. Postgres
  connection info flows to `incidentlab-api` as five separate env vars
  via `fromDatabase`'s per-property references
  (`host`/`port`/`user`/`password`/`database`), matching
  `core/config.py`'s existing five-field `Settings` shape exactly — zero
  backend code changes needed for Render's database wiring.
  `CORS_ALLOWED_ORIGINS` and `API_URL` are both `sync: false` (Render's
  documented "prompt for this in the dashboard" mechanism), not guessed
  at via `fromService`, because it was unclear from Render's own
  Blueprint spec whether that reference's `host` property returns a bare
  hostname or a full URL with scheme — see DDR-034.
- `apps/api/Dockerfile` / `apps/web/Dockerfile` — both `CMD`/`HEALTHCHECK`
  now read `$PORT` with a fallback to their existing `EXPOSE`d default
  (8000/3000) — Render (and most PaaS hosts) assign their own port via
  `$PORT`; auto-detecting an unset port from `EXPOSE` alone is not
  guaranteed per Render's own docs. `docker-compose.yml` never sets
  `PORT`, so local dev behavior is unchanged.
- `docker-compose.yml` / `.env.example` — `NEXT_PUBLIC_API_URL` renamed
  to `API_URL` throughout, matching the actual runtime mechanism above.
- `docs/deployment.md` — a full "Deploying to Render (Blueprint)"
  section: exact dashboard steps, which two values must be entered
  manually and why, and Render's real cost caveats stated up front (free
  Postgres expires 30 days after creation with a 14-day grace period, no
  backups on the free plan, free web services spin down after 15 minutes
  idle with ~1 minute cold starts) — not silently assumed to stay $0
  forever just because every `plan:` in `render.yaml` says `free`.
- `docs/design-decisions.md` — DDR-033 (the API-URL runtime-resolution
  fix) and DDR-034 (`render.yaml`'s specific choices, checked against
  Render's actual published Blueprint spec before being written, since
  `render.com` itself is unreachable from this sandbox — fetched via
  `render-oss`'s and `openai`'s own curated Blueprint field references
  instead of guessed from general PaaS familiarity).

**Files changed:** `render.yaml` (new),
`apps/web/app/api/config/route.ts` (new), `apps/web/lib/api.ts`,
`apps/api/Dockerfile`, `apps/web/Dockerfile`, `docker-compose.yml`,
`.env.example`, `docs/deployment.md`, `docs/design-decisions.md`.

**Tests / verification:**
- `uv run pytest -q` — 189 passed (no backend logic changed; re-run to
  confirm the Dockerfile/compose edits didn't regress anything Python
  side).
- `uv run ruff check .` / `ruff format --check .` — clean.
- `uv sync` — resolves cleanly.
- `docker compose config --quiet` — valid after the `API_URL`
  rename and both Dockerfile changes; full `docker compose config`
  output inspected to confirm `API_URL` and the Postgres env vars
  resolve as expected.
- `render.yaml` parsed with `yaml.safe_load` — valid YAML, structure
  matches Render's documented field names exactly (checked, not
  assumed).
- `npm run build` / `npm run lint` (`apps/web`) — clean.
- **The actual fix, verified for real, not just by reading the diff:**
  built the production standalone bundle with no `API_URL` set (matching
  the Docker builder stage's exact conditions), grepped
  `.next/static/chunks/` for `localhost:8000` — zero matches (confirms
  nothing API-URL-shaped is baked into the browser bundle anymore).
  Started that same build with
  `API_URL="http://distinctive-runtime-proof:9999"` — a value that could
  not possibly have been present at build time — and `/api/config`
  correctly returned it. Then started it again with the real local
  API's address, created a real incident, and drove a full
  generate → investigate flow through a real headless browser
  (Playwright) against that production build; all five agent cards, the
  hypothesis list, and the RCA panel rendered correctly.

**Known limitations / what's still unverified:**
- **Render has never actually deployed this Blueprint.** `render.com` is
  unreachable from this sandbox's egress policy (confirmed, same class
  of restriction as Docker Hub and GHCR in earlier phases) — no service
  was created, no database was provisioned, no cost was incurred, and no
  public URL exists. `render.yaml`'s correctness rests on matching
  Render's documented schema, not on a deploy that completed. The user
  applying the Blueprint themselves (as prompted) is the actual
  end-to-end check.
- The two `sync: false` values (`CORS_ALLOWED_ORIGINS`, `API_URL`) must
  be entered manually after both services exist — `docs/deployment.md`
  says exactly what to enter and why, but this is a real manual step,
  not an oversight to fix later.
- `render.yaml`'s free Postgres plan expires 30 days after creation;
  nothing in this repo can extend that — it's a Render account-level
  decision (upgrade to a paid plan, or accept the database will need
  recreating).
- Port auto-detection risk is mitigated (`$PORT` is now read explicitly)
  but not eliminated as a class of deploy-time surprise — if Render's
  build/runtime environment differs from what's assumed here in some
  other way, the first real deploy is where that would surface, not
  before.

**Update (deployed, live):** the user applied this Blueprint on Render
(outside this sandbox) and it is now live at
https://incidentlab-web.onrender.com (API:
https://incidentlab-api.onrender.com) — the "has never actually deployed"
limitation above no longer holds. The real deploy did surface one
environment difference this sandbox couldn't have caught: Render injects
its own `HOSTNAME` environment variable (the service's public
`*.onrender.com` hostname), which Next's standalone `server.js` binds to
in preference to `0.0.0.0` when set, causing a 502
(`EADDRNOTAVAIL`) even though the process itself started and passed its
own health check. Fixed with an explicit `ENV HOSTNAME=0.0.0.0` in
`apps/web/Dockerfile`'s runner stage (applied by the user directly,
confirmed via `git show` and by the user testing the live URL
afterward). A second, unrelated misconfiguration surfaced after that fix
— the two `sync: false` values above were briefly entered pointing at
the wrong service (`API_URL` set to the web service's own URL instead of
the API's) — corrected to `API_URL=https://incidentlab-api.onrender.com`
on `incidentlab-web` and `CORS_ALLOWED_ORIGINS=https://incidentlab-web.onrender.com`
on `incidentlab-api`. See `docs/design-decisions.md` DDR-033's update
note for the `HOSTNAME` bug in full.

---

## Real-data import (RCAEval)

Not a new phase — added at the user's request, asking where to find real
data to test the app with. Every existing scenario is synthetic by
design (DDR-007); this adds a second, real-data path alongside it rather
than replacing it.

**Implemented:**
- `simulator/rcaeval_import.py` (new) — parses a real RCAEval
  (github.com/phamquiluan/RCAEval) failure-case directory (`metrics.csv`,
  `logs.csv`, `inject_time.txt`) into the same `IncidentDraft` shape a
  synthetic `FailureInjector` produces: melts the wide per-second
  `metrics.csv` into `MetricPoint` rows, windows and caps the real log
  volume (RCAEval's own data runs ~100+ lines/second), and always leaves
  `deployments=[]` and every `is_distractor=False` — RCAEval has no
  deploy data, and nothing in real telemetry was deliberately planted as
  a red herring, so neither is fabricated.
- `simulator/replay.py` — persistence logic extracted into a shared
  `persist_incident_draft()`, called by both `run_scenario()` (synthetic)
  and the new import script, so an imported incident is stored and
  investigatable identically to any other.
- `make import-real-data` (Makefile) — CLI entry point.
- `tests/fixtures/rcaeval_sample/` (new) — a small, real, trimmed slice
  of an actual downloaded RCAEval case, used by
  `tests/unit/test_rcaeval_import.py`'s 11 tests (melting correctness,
  distractor/deployment honesty, window/anchor behavior, determinism).

**Verified, not assumed:** the real case bundle
(`multi-source-data.zip`, RCAEval's own GitHub-release demo, an actual
chaos-engineering run against Online Boutique) was downloaded and
inspected directly — its exact column layout drove the parser, not a
guess from the README. The full untrimmed case (1,441 metric rows,
~171k log rows) was run through `build_incident_draft()` end-to-end
(0.51s, 300 capped logs, 6,552 metric points) to confirm real-world
performance, and the real `checkoutservice_cpu` spike (~0.5 → 14+
average in the 2 minutes after `inject_time.txt`) was confirmed to
survive the import unchanged. `uv run pytest -q --ignore=tests/integration`
(110 passed, up from 99), `ruff check .` and `ruff format .` (clean).

**Known limitations, disclosed rather than papered over:**
- **This bundle is unlabeled.** RCAEval's 735 cases with an actual
  ground-truth root cause live on Zenodo and Hugging Face, both
  unreachable from this sandbox's egress policy — so `--root-cause`,
  `--affected-component`, and `--trigger` are required CLI flags here,
  filled in from a real anomaly found by inspection (the CPU spike
  above), not from an authoritative label. Pointed at a labeled Zenodo
  case instead, those three values are already encoded in that case's
  own directory name / `cases.parquet` row.
- **Auto-scoring isn't wired up.** `evaluation/ground_truth.py`'s
  `_ROOT_CAUSE_TO_HYPOTHESIS` mapping only covers the two synthetic
  scenarios' root-cause strings — an imported incident can be
  investigated end-to-end (`make investigate INCIDENT=...`) but not
  auto-scored by `evaluation/reports.py` until that mapping is extended
  for whatever root-cause string was supplied at import time. The import
  CLI prints this after every run.
- Requires a real Postgres to actually persist and investigate (same
  requirement every other scenario already has) — not verified against
  a running database in this sandbox, same disclosed gap as every other
  phase here.

See `docs/design-decisions.md` DDR-035 for the full reasoning, including
why this is a standalone script rather than a `FailureInjector`
subclass.
