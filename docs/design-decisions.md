# Design Decision Records

Decisions are recorded when made, not retrofitted. Each entry says what was
decided, why, and what the alternative would have cost.

## DDR-001: Separate repo from the author's portfolio site

**Context:** this project was originally requested to be built inside
`akshitrampershad/portfolio`, a static GitHub Pages site.

**Decision:** build IncidentLab in its own repository
(`akshitrampershad/incidentlab`).

**Why:** the portfolio repo's own README convention links out to standalone
repos for real projects (CYBER-GPT, personal-rag-assistant, etc.) rather than
vendoring them. IncidentLab is a multi-service application (FastAPI, Next.js,
Postgres, eventually Qdrant/LangGraph) that would break the portfolio's
GitHub Pages deployment and has nothing to do with a static site's build.

## DDR-002: `uv` for Python dependency management

**Decision:** `pyproject.toml` + `uv`, not Poetry or plain `pip -r
requirements.txt`.

**Why:** already available in the target environment, resolves and installs
fast, has an official slim Docker story, and `uv.lock` gives the
reproducibility the spec asks for without Poetry's heavier tooling.

## DDR-003: npm for the web app

**Decision:** npm, not pnpm/yarn.

**Why:** ships with Node, zero extra tooling to install or explain in the
README. Revisit only if workspace/monorepo needs (multiple JS packages)
actually materialize — they don't exist yet.

## DDR-004: No ORM models or Alembic in Phase 1

**Decision:** Postgres is running and reachable (checked by
`/health/ready`), but no SQLAlchemy models or migrations exist yet.

**Why:** Phase 1's definition of done is "`docker compose up` starts
backend, frontend, and database" — it says nothing about schema. Writing
models before Phase 3 defines the incident/evidence data model would mean
rewriting them almost immediately. Alembic is introduced when there's an
actual schema to migrate.

## DDR-005: Directory scaffolding follows phases, not the full target tree

**Decision:** only `apps/`, `docs/`, `tests/unit/`, `.github/` exist so far.
The full repository layout in the spec (`agents/`, `orchestration/`,
`tools/`, `retrieval/`, `evidence/`, `hypotheses/`, `evaluation/`,
`simulator/`, `knowledge/`) is created phase-by-phase as each subsystem is
implemented.

**Why:** empty placeholder directories with no code are noise — they don't
compile, can't be tested, and git doesn't even track empty directories. The
target structure is documented; it doesn't need to exist as empty folders
today.
