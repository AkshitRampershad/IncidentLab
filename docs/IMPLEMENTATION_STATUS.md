# Implementation Status

- [x] Phase 1 — Repository + Infrastructure
- [ ] Phase 2 — Incident Simulator
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
