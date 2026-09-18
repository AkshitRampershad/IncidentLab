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

**Update (Phase 4):** `tools/knowledge.py` now exists — see DDR-012.
`tools/github.py` and `tools/traces.py` are still deferred: still no real
git repository or tracing backend to integrate against.

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

## DDR-010: an agent's structured findings are always deterministic; only its `summary` is LLM-enhanced

**Context:** spec §4.2 assigns "interpretation, summarization, ...
evidence synthesis" to the LLM. But this sandbox has no LLM access at all
(no Ollama installed, no reachable API — confirmed by trying), and the
spec is equally explicit elsewhere that local-first must actually work
and CI must not require a proprietary key (§6, §47).

**Decision:** each investigator agent (`agents/logs.py`,
`agents/metrics.py`, `agents/code.py`, `agents/knowledge.py`,
`agents/triage.py`) computes `findings`, `evidence`, and
`hypotheses_supported` entirely deterministically, from the Phase 3 tool
outputs (spike counts, anomaly thresholds, deployment proximity, keyword
pattern matches). Only the `summary` field is LLM-generated when an
`LLMProvider` is passed in and reachable; `agents/base.py`'s
`summarize_or_fallback` degrades to a deterministic fallback (built from
the same findings, not a blank or an error) on any LLM failure or
absence — never blocking, never fabricating.

**Why:** Phase 4's definition of done is "each agent independently
executes tools and produces **structured** findings" — that's the
deterministic part, and it has to work with zero LLM access to be
testable and runnable in this environment (and honestly, in most
contributors' environments without Ollama already pulled). The LLM
becomes a narration layer on top of an already-complete result, not a
dependency the core behavior needs. `hypotheses_supported` uses a small
keyword-pattern table (`agents/base.py`'s `hypotheses_from_content`)
instead of literally hardcoding the ground-truth taxonomy string
(`database_connection_pool_exhaustion`) into agent code — that would make
the agent look like it's investigating while actually just parroting the
answer, which defeats the entire point of the project once more
scenarios exist to tell apart.

## DDR-011: the Code Investigator reuses `tools/deployments.py`, not a new git tool

**Context:** spec §13's Code Investigator calls `search_commits()`,
`get_commit()`, `get_diff()`, `search_files()` — real git operations
against a real repository. IncidentLab has no such repository to
investigate; the simulator only ever produces a `commit_sha` *string* and
a change description on a deployment record.

**Decision:** `agents/code.py` calls `tools.deployments.
get_recent_deployments()` — the same tool `agents/triage.py` uses —
rather than a new `tools/github.py`.

**Why:** a deployment record already *is* "a code change, with its commit
sha and a description of what changed" (spec §13's own worked example —
"PR #482 changed database connection pool configuration" — is exactly
this shape). Building `tools/github.py` now would mean either mocking
git history or integrating against this project's own repo as a stand-in
for "the production repo," neither of which is real evidence about the
incident being investigated. Real git integration is future work once
there's an actual target repository to search.

## DDR-012: the knowledge base is real hand-authored markdown, searched by keyword — no Qdrant/embeddings yet

**Context:** spec §14 describes the Knowledge Investigator using "metadata
filtering + vector retrieval + reranking" against Qdrant (spec §6). No
embeddings pipeline, reranker, or vector store exists in this project.

**Decision:** `knowledge/` holds three real, hand-authored markdown
documents (a runbook, an architecture note, one clearly-labeled synthetic
historical incident — spec §49's synthetic-data rule). `tools/knowledge.py`
searches them with the same case-insensitive substring match
(`evidence.scoring.matches_query`) every other tool already uses, not
literal vector search.

**Why:** at three documents, a vector store is pure overhead with nothing
to demonstrate — precision/recall over a 3-document corpus is not a
meaningful signal either way. Substring search over real content is
honest about what it is, fully deterministic, needs no embedding model
(which this sandbox can't run — no Ollama, no reachable embedding API),
and gives the Knowledge Investigator agent genuine, correctly-provenanced
evidence today. Revisit once the corpus is large enough that "does the
right document rank first" is an actual question — Qdrant is already in
the target stack (spec §6) for exactly that point.
