# Implementation Status

- [x] Phase 1 — Repository + Infrastructure
- [x] Phase 2 — Incident Simulator
- [x] Phase 3 — Evidence Layer
- [x] Phase 4 — Agents
- [x] Phase 5 — Orchestration
- [x] Phase 6 — Evaluation
- [x] Phase 7 — UI
- [ ] Phase 8 — Security + Observability
- [ ] Phase 9 — Deployment
- [ ] Phase 10 — Open Source Release

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
