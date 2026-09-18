# Implementation Status

- [x] Phase 1 — Repository + Infrastructure
- [x] Phase 2 — Incident Simulator
- [ ] Phase 3 — Evidence Layer
- [ ] Phase 4 — Agents
- [ ] Phase 5 — Orchestration
- [ ] Phase 6 — Evaluation
- [ ] Phase 7 — UI
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
