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

## DDR-006: shared config/DB code lives in `core/`, not `apps/api`

**Context:** Phase 2's simulator needs the same database settings and
engine Phase 1 built for the API. The spec's tree has no shared location
for this.

**Decision:** moved `Settings`, `get_engine`, `check_connection` out of
`apps/api/dependencies/` into a new top-level `core/` package
(`core/config.py`, `core/db.py`, `core/models.py` for the shared ORM
schema). `apps/api` now imports from `core`, not the other way around.

**Why:** `simulator/` importing from `apps.api` would be a backwards
dependency — business/domain logic depending on the presentation layer.
`evidence/` and `tools/` (Phase 3) will need the same database access, so
this was going to be needed regardless; doing it now, while only two
call sites use it, is a small refactor. Waiting would mean repeating it
under worse conditions once more code depends on the old location.

## DDR-007: the simulator synthesizes telemetry deterministically — it
doesn't run real microservices under load

**Context:** the spec suggests using "the OpenTelemetry ecosystem or an
equivalent open-source microservice demo" for the incident simulator,
which usually means a multi-language, dozen-service demo application
generating load-driven telemetry.

**Decision:** `simulator/failure_injector/` generates logs, metrics, and
deployment records directly as data, anchored to a single `anchor_time`,
rather than standing up real services and inducing failure in them under
synthetic traffic.

**Why:** a real multi-service demo is a large, mostly-unrelated
undertaking or Phase 2's actual goal, which is a reproducible incident
with known ground truth and realistic-looking evidence (spec §4.5, §8).
Deterministic generation directly satisfies "reproducible" (principle
4.5) and "deterministic systems around probabilistic systems" (principle
4.2) — the same scenario always produces the same structure. It also
means the simulator has no runtime dependency this sandbox can't
exercise: it's pure Python plus Postgres, both already provable in CI
without needing Docker Hub access (see Phase 1's `docker compose up`
verification gap) or a running fleet of containers. Revisit only if a
later phase genuinely needs live request/response behavior (e.g. testing
an agent's tool-call retry logic against a real flaky endpoint) rather
than the evidence a scenario leaves behind.

## DDR-008: `tools/github.py` and `tools/knowledge.py` are deferred, not stubbed

**Context:** the spec's Code Investigator and Knowledge Investigator
tools (spec §13, §14) need real commit/PR history and a searchable
runbook/documentation corpus. Neither exists in this project yet — the
simulator only ever generates a `commit_sha` *string* on a deployment
record, never a real commit, and no runbook content has been authored.

**Decision:** Phase 3 does not create `tools/github.py`, `tools/traces.py`,
or `tools/knowledge.py`. Only `tools/logs.py`, `tools/metrics.py`,
`tools/deployments.py`, and `tools/incidents.py` exist — the four sources
the simulator actually produces data for.

**Why:** a tool with no real backing data behind it is either a mock
(violates "no placeholder functionality... call it complete") or would
have to fabricate commit history / documentation content from nothing
(violates "never invent evidence"). These land in Phase 4 alongside the
Code and Knowledge Investigator agents that actually need them, once
there's real content (a runbook, an architecture doc, a git-backed commit
history) to search.

## DDR-009: `evidence/graph.py` is deferred to Phase 7

**Context:** the spec's file tree includes `evidence/graph.py` inside the
Phase 3 package.

**Decision:** not created yet. Phase 3's definition of done is "an
incident can expose structured evidence through tools" — nothing consumes
a graph structure until the Evidence Graph UI view (spec §35), which is
Phase 7.

**Why:** same reasoning as DDR-005 — a module with no caller yet is
unverifiable scaffolding. `evidence.models.Evidence` already carries
everything a graph view would need (evidence_id, source, timestamp,
provenance); building the graph-shaping code now, before there's a
consumer or even an agreed node/edge shape for the UI, risks writing it
twice.
