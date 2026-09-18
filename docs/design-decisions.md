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

## DDR-013: a small canonical-grouping table merges cross-agent hypothesis signals; unmapped signals still stand alone

**Context:** the Log agent might produce the signal text "Connection pool
exhaustion" and the Metrics agent might independently produce
"db_connections_active anomaly" — two different phrasings of the *same*
underlying root cause, from two different sources. Left ungrouped, the
Hypothesis Manager would score them as two separate, individually weaker,
single-source hypotheses, instead of one well-corroborated, multi-source
one — directly undermining spec §15's "correlate evidence across
sources."

**Decision:** `hypotheses/manager.py`'s `_CANONICAL_HYPOTHESES` maps a
canonical description to the list of per-agent signal texts that count as
support for it. Any `HypothesisSignal` text not listed in any group still
becomes its own standalone `Hypothesis` — nothing is silently dropped for
being unmapped, it just doesn't get merged-evidence credit.

**Why:** this is the same shape of decision as `agents/base.py`'s
`_HYPOTHESIS_PATTERNS` (DDR-010) — a small, explicit, deterministic table
rather than trying to infer semantic equivalence between hypothesis
strings automatically (which would mean either fuzzy text matching,
fragile and wrong in both directions, or an LLM call, reintroducing the
exact "LLM arbitrarily decides" problem spec §16 warns against). Grows
alongside `_HYPOTHESIS_PATTERNS` as more scenarios are added — the two
tables are companions, not independent.

The same table is reused by `hypotheses/contradiction.py`'s
`detect_contradictions()`: for a canonical hypothesis, if one of its
member signals is a `"<metric> anomaly"` text and that metric was
actually measured but did *not* cross its threshold, that measured
(non-anomalous) point is contradicting evidence — spec §17's own worked
example ("Metrics Agent: Database connection utilization remained
normal") in exactly this shape. For the one scenario that exists today,
this correctly finds *zero* contradictions (metrics do confirm what logs
show) — matching spec §21's own worked RCA example ("Contradictions: None
detected"). The rule is general enough to fire for a future scenario
where evidence genuinely disagrees, without needing to special-case one.

## DDR-014: the orchestration graph is single-pass — no loop-back for more investigation

**Context:** spec §5's architecture diagram shows an arrow from "Low
confidence" back to "Agents" for further investigation, and §19 mentions
this as a possibility.

**Decision:** `orchestration/graph.py`'s graph is a straight line (with
one parallel fan-out/fan-in): Triage → {Logs, Metrics, Code, Knowledge}
→ Hypothesis Manager → Adjudicator → END. Low confidence produces
`needs_human_review=True` in the final result (spec §20's human review,
which this phase treats as a valid terminal outcome, not an error) — it
does not re-invoke the agents with a different, narrower investigation
plan.

**Why:** a real loop-back needs real logic deciding *what* to investigate
next and *why* — which evidence source to re-query, with what different
parameters — which is a meaningfully new capability (dynamic replanning),
not a graph-wiring change. Phase 5's definition of done is "incident →
agents → hypotheses → evidence → RCA," which a single pass already
satisfies end to end, verified by `make investigate`. Building speculative
replanning logic now, before there's a second scenario to prove it
against, risks getting the shape wrong. Revisit once evaluation (Phase 6)
shows *which* low-confidence cases would actually benefit from a second
pass, rather than guessing now.

## DDR-015: the Knowledge agent's evidence corroborates the winning hypothesis at adjudication time, not during hypothesis-building

**Context:** the Knowledge agent (unlike Logs/Metrics/Code) doesn't
produce its own `hypotheses_supported` — see `agents/knowledge.py`. Its
evidence still needs to reach the final result somehow.

**Decision:** `hypotheses/manager.py`'s `build_hypotheses()` only ever
looks at Logs/Metrics/Code. `agents/adjudicator.py` attaches Knowledge
evidence to the *already-selected* winning hypothesis's
`supporting_evidence` — via simple shared-keyword overlap between the
hypothesis description and the knowledge content — after the winner is
chosen, not before.

**Why:** attaching Knowledge evidence to *every* candidate hypothesis
equally during scoring would inflate every hypothesis's evidence count
and source diversity by the same fixed amount, without helping
distinguish between them (the entire point of the Hypothesis Manager).
Attaching it only to the winner keeps hypothesis *scoring* clean
(driven only by evidence that actually differentiates candidates) while
still surfacing genuinely relevant runbooks/historical incidents in the
final adjudicated result — which is also where `agents/adjudicator.py`'s
`recommend_action()` looks for a matching runbook to cite, rather than
inventing a remediation step (spec §4.3). (Both `corroborating_knowledge`
and `recommend_action` are public — Phase 6's single-agent baseline reuses
them, see `docs/architecture.md`'s Phase 6 section.)

## DDR-016: a second scenario (`redis_unavailable`) before evaluation, not after

**Context:** Phase 2 shipped with exactly one scenario
(`db_connection_pool`). Phase 6's whole job is comparing architectures'
accuracy — but accuracy against a single possible answer is nearly
meaningless (every architecture either gets 100% or 0%, and there's
nothing to confuse a system that always guesses the same thing).

**Decision:** before building the evaluation harness, added
`simulator/failure_injector/redis_unavailable.py` (spec §23 Scenario 2):
Redis becomes unreachable, latency degrades but — per
`knowledge/architecture/checkout-service.md`'s own documented
fallback-to-Postgres behavior — error rate does *not* spike. Deliberately
built to never say "pool exhausted" or "connection timeout" anywhere, so
it can't accidentally trigger the DB-pool pattern by keyword collision.

**Why:** this turned out to genuinely exercise the Contradiction Detector,
not just the happy path: `latency_p99_ms` crosses its threshold in this
scenario too (elevated latency is real), which pulls a competing
"Database or downstream connectivity issue" hypothesis into contention
via the same canonical-grouping table (DDR-013) — but the confirmed-normal
`error_rate` reading contradicts it, and the detector correctly penalizes
it (confidence 0.93 → 0.17 in practice, verified in
`tests/integration/test_orchestration.py`). A benchmark that can't
possibly be wrong about which scenario it's in isn't really measuring
anything. Also added a matching runbook
(`knowledge/runbooks/redis-unavailable.md`) so the Knowledge agent and
Adjudicator have something real to find here too, not a second-class
scenario with a first scenario's polish.

## DDR-017: the evaluation dataset is small and honestly disclosed, not padded to look like spec §28-29's "50 incidents"

**Context:** spec §28 aims for 50-100+ incidents (10 scenarios × 5
variations, later expanded). This project has 2 scenarios, and each
failure injector is a pure function of `anchor_time` alone — running the
same scenario at a different anchor_time produces a distinct incident_id
and absolute timestamps, but *identical* relative structure and content
(same log messages, same relative offsets, same evidence counts).

**Decision:** `evaluation/datasets.py`'s `generate_dataset()` runs each of
the 2 registered scenarios 3 times (6 incidents total, configurable via
`--instances-per-scenario`), generated fresh on every `make benchmark`
run rather than stored as static fixtures. Docs (this one, README,
`docs/IMPLEMENTATION_STATUS.md`) say plainly that same-scenario repeats
are structurally identical except wall-clock time — not spec §29's "5
variations" varying services/distractors/severity/volume.

**Why:** claiming real diversity that doesn't exist would be exactly the
kind of fabrication the spec repeatedly warns against (§4.3, §29's own
"never fabricate metrics") — a dataset row that's byte-for-byte the same
scenario just relabeled isn't a genuine additional sample, and pretending
otherwise would make the benchmark's percentages look more statistically
meaningful than they are. Six honestly-described incidents across two
real, distinguishable root causes is a legitimate small benchmark;
padding to a fake "50" would not be. Generating on demand (not static
fixtures) also means the dataset can never drift out of sync with the
scenarios that define it. Growing this — both more scenarios and real
per-scenario parameter variation (error counts, timing offsets, severity)
— is future work, not attempted here for the sake of a bigger number.

## DDR-018: Direct LLM's confidence is structurally fixed at 0.0, never the LLM's own guess

**Context:** spec §27 Baseline A calls for an LLM given only the
incident's summary, no tools. With zero evidence, there is nothing
deterministic to score a confidence against — but spec §16 is explicit
that an LLM must never assign its own confidence.

**Decision:** `evaluation/baselines.py`'s `direct_llm_investigate()`
always returns `confidence=0.0`, regardless of whether the LLM answered,
timed out, or wasn't configured. This structurally forces
`needs_human_review=True` in every case.

**Why:** the alternative — asking the LLM to also state a confidence
number — would be exactly the "arbitrarily decides" failure mode spec
§16 rules out, and a fabricated-looking non-zero number here would
misrepresent what this baseline actually is: a guess with no evidence
behind it. Forcing escalation in every case is the honest behavior for
that situation (spec §4.4: "I don't have enough evidence" is a valid,
expected outcome, not an error) — and it's also the real, disclosed
reason this baseline scores 0% accuracy in this sandbox: no LLM is
reachable here at all (confirmed by trying, same as Phases 4-5), so
`selected_hypothesis` is always `None`. That's a genuine finding about
what a tool-free approach can do without a working model, not an
artifact of how the harness is wired.

## DDR-019: `GET /investigations/*` recomputes on every call — nothing is persisted

**Context:** spec §38 lists `GET /investigations/{id}`,
`/timeline`, `/evidence`, `/hypotheses`, `/agents` as if each reads a
stored investigation record.

**Decision:** none of these routes read a persisted "investigation" row.
`apps/api/routes/investigations.py` re-runs
`orchestration.graph.investigate()` fresh on every call (a shared `_run()`
helper), and the sub-resource endpoints (`/timeline`, `/evidence`, ...)
just slice the same fresh result. `POST /incidents/{id}/investigate` and
`GET /investigations/{id}` are therefore identical in effect — an
`investigation_id` is just the `incident_id`, because there's only ever
one deterministic investigation per incident right now.

**Why:** the system has no randomness and no ground-truth dependency in
its output, and without a live LLM (this sandbox has none) a full
investigation completes in well under a second — recomputing is simpler
than a cache or a new `investigations` table, and it can never go stale
relative to the incident's actual evidence the way a cached row could.
The web UI calls the POST endpoint exactly once per "Run Investigation"
click and holds the result in React state, so the sub-resource endpoints
existing for spec-completeness doesn't mean the UI pays for five
re-runs per page. Revisit if a future phase adds real per-run variance
(e.g. actual LLM sampling at nonzero temperature) that would make "the
investigation" not a pure function of `incident_id` anymore.

## DDR-020: evaluation runs are stored in memory only, not in Postgres

**Context:** spec §38 lists `GET /evaluations` and
`GET /evaluations/{id}` as if benchmark runs are durably recorded.

**Decision:** `apps/api/routes/evaluations.py` keeps a module-level
`dict[str, BenchmarkReport]` keyed by a generated UUID. It's gone on
API restart.

**Why:** this is dev/demo tooling for comparing architectures, not a
production audit trail — adding a schema (and a migration story, given
DDR-004 already deferred Alembic) for data nobody has asked to keep past
one process's lifetime would be speculative infrastructure. The dataset
itself is also regenerated fresh on every run (DDR-017), so a "past
evaluation" is already not reproducible byte-for-byte from its ID alone
in the way a real audit record would need to be. Revisit if evaluation
history genuinely needs to survive a restart — that's a real, boundable
feature, not a hard one, when there's an actual need for it.

## DDR-021: Approve/Reject are acknowledgment-only, and say so in the response

**Context:** spec §20 describes Approve / Reject / Request More
Investigation as real human-in-the-loop actions. Phase 5 (DDR-014)
already deferred any re-investigation loop; nothing downstream of a
human decision exists yet.

**Decision:** `POST /investigations/{id}/approve` and `/reject` return a
`ReviewDecision` whose `note` field states plainly that the action is
acknowledged only, with no persisted audit trail or re-investigation
effect — visible in the API response itself, not just in this doc.

**Why:** implementing the buttons with no disclosure of what they
actually do would look like a working review workflow when it isn't one
— exactly the "no placeholder functionality... call it complete" trap
(spec §57). Saying so directly in the response (and the web UI surfacing
that note after clicking) keeps the honesty at the point someone would
actually notice, not buried in a doc they may never open.

## DDR-022: the "Evidence Graph" is a grouped, linked list — not an interactive node graph

**Context:** spec §35 describes a clickable node/edge visualization
(Incident → Deployment → Log → Metric → historical incident).
`evidence/graph.py` was deferred in Phase 3 (DDR-009) specifically until
Phase 7 had a real consumer for it.

**Decision:** the investigation view (`apps/incidents/[id]/page.tsx`)
renders evidence as two grouped, labeled lists — Supporting and
Contradicting, each item showing its evidence_id/source_type/source/
relevance and full content (long documents collapse behind a native
`<details>` toggle) — rather than an interactive graph library
(react-flow or similar).

**Why:** at this project's evidence volumes (a dozen-ish items per
investigation), a graph adds a new heavy frontend dependency and
real interaction-design work for the same information a list already
conveys — every item already carries its `evidence_id` and
`provenance`, which is what would back a graph's edges. `evidence/graph.py`
stays unbuilt for the same reason: nothing consumes a graph-shaped
payload yet. Revisit once evidence volume or genuinely graph-shaped
relationships (e.g. multi-hop provenance chains) make a list hard to
scan — a real UI need, not a mockup to match for its own sake.

## Bug found by manually testing the UI in a browser, fixed same phase

Building the investigation view surfaced two real bugs that no existing
test caught:

1. **`GET /incidents` 500'd on a truly fresh database.**
   `simulator.replay.run_scenario()` always called
   `core.db.create_all_tables()` before its first write, but no read-only
   route ever did — so the very first request to a freshly-started API
   against an empty Postgres (e.g. the dashboard's own initial load)
   threw `UndefinedTableError` instead of returning `[]`. Fixed with a
   FastAPI `lifespan` hook in `apps/api/main.py` that creates the schema
   at startup. **This had zero test coverage before this phase** — every
   integration test's `clean_db` fixture calls `create_all_tables()`
   itself before each test runs, which silently masked the bug from the
   entire existing suite; `tests/integration/test_api_lifespan.py` now
   drops everything and drives the app's actual `lifespan` context
   manager directly, the one place it's exercised at all (plain
   `httpx.ASGITransport` doesn't trigger ASGI lifespan events the way a
   real server does).
2. **`corroborating_knowledge()`'s any-keyword-matches rule was too
   loose.** A hypothesis about database connection pool exhaustion was
   pulling in the *Redis* runbook and the architecture doc as
   "supporting evidence" purely because they all share the word
   "connection" — visibly obvious once rendered in the actual UI, far
   less obvious from unit tests using short fabricated content. Fixed by
   requiring at least two matching keywords (or all of them, if only one
   qualifies) — see `agents/adjudicator.py`.

Neither would have been caught by unit or integration tests alone; both
came directly from following the "start the dev server and use the
feature in a browser" instruction rather than treating a clean test run
as sufficient.

## DDR-023: tool permissions, timeouts, budget, and audit logging are one decorator, not four separate mechanisms

**Context:** spec §38-40 ask for an explicit tool allowlist, per-call
timeouts, a cap on tool calls per investigation, and an audit trail of
every call — four requirements that all attach to the same event (a tool
function being called).

**Decision:** `tools/registry.py`'s `@allowlisted_tool("name")` decorator,
applied to all ten tool functions (`tools/incidents.py`,
`tools/logs.py`, `tools/metrics.py`, `tools/deployments.py`,
`tools/knowledge.py`), does all four at once: registering the name in a
live allowlist (`allowed_tools()`), wrapping the call in
`asyncio.wait_for(..., timeout=Settings.tool_timeout_seconds)`,
incrementing a shared per-investigation counter against
`Settings.max_tool_calls_per_investigation`, and emitting a structured
`structlog` line (tool name, duration, outcome) plus an OpenTelemetry span
on every call, success or failure. A `call_tool(name, ...)` dispatch
function also exists, raising `ToolNotAllowed` for any unregistered name —
giving the allowlist real teeth for a future LLM-driven tool-calling loop,
even though today's agents call tool functions directly via Python
imports (the LLM here never chooses which tool to call).

**Why:** all four concerns fire at exactly the same two points (before the
call, after it succeeds or fails) — four separate wrapping mechanisms
(a permission check, a timeout wrapper, a budget middleware, a logging
decorator) would mean four places to apply to every tool function instead
of one, and four places that could drift out of sync. The per-investigation
budget uses a single-element mutable list behind a `ContextVar`
(`_call_count`), not a plain int: LangGraph's parallel investigator nodes
run as concurrent asyncio Tasks spawned from the same parent context, and
a `ContextVar` copies its *mapping* into each new Task but shares each
entry's *value* by reference — a mutable list lets every node draw down
the same shared budget; a plain int would silently give each node its own
independent copy the first time it tried to rebind the var. Verified
directly by `tests/unit/test_tools_registry.py`'s
`test_budget_is_shared_across_concurrent_calls_in_the_same_context`, and
by measuring a real investigation (`db_connection_pool`, no LLM): 38 tool
calls end to end, which set `Settings.max_tool_calls_per_investigation`'s
default of 100 (comfortable headroom, not an arbitrary round number).
`reset_tool_budget()` is called once, by `orchestration.graph.investigate()`
— a tool called directly outside a real investigation (a unit test, or a
standalone route like `GET /investigations/{id}/timeline`) is deliberately
unbudgeted, since it isn't "an investigation" the budget is scoped to.

## DDR-024: one agent failing degrades that agent's finding; it never crashes the investigation — except a nonexistent incident, which still does

**Context:** spec §43's own worked example: *"If Log Agent fails: Continue
investigation with: Metrics, Code, Knowledge. Note: 'Log evidence not
available'."* Before this phase, any exception inside any
`orchestration/graph.py` node (an agent's tool call, an LLM timeout, a bad
DB connection) propagated straight out of `investigate()` and failed the
whole investigation.

**Decision:** every node function (`_triage_node`, `_run_investigator`
wrapping the four investigator nodes, `_adjudicate_node`) now catches
`Exception` around its agent's call and returns a `degraded=True` finding
(`agents/models.py`'s new `TriageFinding.degraded` /
`InvestigatorFinding.degraded` field) with empty evidence/findings and a
`summary` stating what went wrong, instead of letting the exception
propagate. The one deliberate exception: a `ValueError` — raised only when
`incident_id` doesn't exist at all (`tools/incidents.get_incident`) — is
explicitly re-raised, not degraded, because every agent would fail
identically and there is no investigation to salvage; degrading it would
turn a clean, already-tested 404 (`apps/api/routes/investigations.py`)
into a confusing "investigation" full of five degraded agents and no
result. `orchestration/graph.py`'s `investigate()` also now wraps the
whole graph invocation in `asyncio.wait_for(...,
timeout=Settings.investigation_timeout_seconds)`, raising a new
`InvestigationTimeoutError` (mapped to HTTP 504) — a ceiling on top of
each individual tool's own timeout, for the case where many
individually-fine calls still add up to an unacceptably slow run.

**Why:** this is the literal behavior spec §43 asks for, verified end to
end (not just unit-tested in isolation) by
`tests/integration/test_orchestration_resilience.py`: monkeypatching
`agents.logs.investigate` to raise still produces a complete investigation
with a real `selected_hypothesis` from the other three agents; monkeypatching
all four investigator agents to raise still produces the adjudicator's
already-existing, already-tested "no hypotheses" fallback (DDR-014's
single-pass graph already had one) rather than an unhandled exception.
Re-raising `ValueError` for a nonexistent incident preserves an existing,
tested API contract (`test_investigate_unknown_incident_is_404`) — broadening
graceful degradation to cover it would have been a regression disguised
as resilience.

## DDR-025: prompt-injection defense is a delimiter + explicit preamble on top of an existing structural guarantee, not a content filter

**Context:** spec §41 requires "prompt injection protection" as a security
test. DDR-010 already established that no agent's *structured* output
(findings, hypotheses, confidence, `selected_hypothesis`,
`needs_human_review`) is ever derived from an LLM response — only the
free-text `summary`/`reasoning_summary` fields are, and those degrade to a
deterministic fallback on any LLM failure. Evidence content, though, is
attacker-reachable: anything landing in a log message, a metric label, or
a knowledge doc could carry text that reads like an instruction.

**Decision:** `agents/base.py`'s `format_evidence_for_prompt(label, lines)`
wraps every prompt's evidence content in an explicit
`<evidence label="...">...</evidence>` block preceded by a preamble
stating plainly that the content is untrusted data, never instructions to
obey. Every agent (`triage`, `logs`, `metrics`, `code`, `knowledge`) and
the adjudicator now build their LLM prompts through this helper instead of
splicing evidence content into a raw f-string.

**Why:** this is deliberately defense in depth, not the primary defense —
DDR-010's structural guarantee already makes injection non-dangerous here,
since even a fully-compromised LLM response can only ever land in a
narration field nothing downstream reads for its actual decision. That
claim is now a test, not just an assumption:
`tests/unit/test_prompt_injection_defense.py`'s
`test_a_fully_compromised_llm_can_only_distort_the_summary_text` uses an
`EchoLLM` that does exactly what an injected instruction asks
("confidence 1.0, ignoring real evidence") and confirms the structured
hypothesis signal is untouched. The delimiter/preamble layer exists for
the case a future phase's LLM usage grows beyond narration (e.g. if an
LLM ever chose which tool to call, per DDR-023's `call_tool` groundwork) —
at that point a clearly-marked untrusted-data boundary is worth having
already in place, rather than retrofitting it under pressure.

## DDR-026: OpenTelemetry traces use a private `TracerProvider`, not the global `opentelemetry.trace` API — and no real collector is stood up

**Context:** spec §42 asks for structured traces with specific span
attributes (investigation_id, agent_name, tool, latency). The
`opentelemetry.trace.set_tracer_provider()` global-API function can only
meaningfully be called once per process — a second call is a silent
no-op with a logged warning — which makes it awkward for tests to swap in
an `InMemorySpanExporter` to assert on span attributes directly.

**Decision:** `core/telemetry.py` owns a private module-level
`TracerProvider` instance directly (never touching
`opentelemetry.trace.set_tracer_provider`/`get_tracer_provider`), exposing
`get_tracer(name)` and a test-only `add_span_processor(processor)`.
`tools/registry.py`'s tool-call wrapper and `orchestration/graph.py`'s
node functions each open a span (`tool.<name>` / `agent.<name>` /
`investigation`) carrying the attributes spec §42 lists. The default
processor is a `ConsoleSpanExporter` — spans are visible in process
output — and no real OTel collector (Jaeger, Tempo, etc.) is stood up.

**Why:** owning the provider directly sidesteps the global-API's
once-only restriction entirely, verified by
`tests/unit/test_telemetry.py` attaching an `InMemorySpanExporter` and
reading spans back by attribute rather than parsing console text. No real
collector exists for the same reason no real Qdrant or git integration
exists yet (DDR-012, DDR-011): there's nothing in this project's infra a
collector could be verified against inside this sandbox, and standing one
up in `docker-compose.yml` with nothing to point it at or prove it works
would be exactly the "add infrastructure before it's needed" the project
has consistently avoided. `ConsoleSpanExporter` at least makes spans real
and inspectable today rather than configured-but-invisible.

## DDR-027: `incident_id` path parameters are validated against the project's own `INC-<n>` shape before touching the database

**Context:** while writing `tests/integration/test_api_security.py`
(spec §41's malformed-inputs test), a null byte inside `incident_id`
(`INC-0001%00INC-0002`) reached asyncpg raw and came back as an uncaught
`asyncpg.exceptions.CharacterNotInRepertoireError` — a real 500, not the
clean 404 every other bad `incident_id` already got via `ValueError`
handling. Every `incident_id` this project ever generates
(`simulator/replay.py`'s `_next_incident_id`) has always had exactly one
shape: `INC-` followed by digits.

**Decision:** `apps/api/validation.py`'s `IncidentId` (a FastAPI `Path`
type with `pattern=r"^INC-\d+$"`, `max_length=32`) replaces the plain
`incident_id: str` parameter on every route that takes one
(`apps/api/routes/incidents.py`, `apps/api/routes/investigations.py`).
Anything not matching — SQL-metacharacter payloads, null bytes, script
tags, 10,000-character strings — is rejected with a 422 by FastAPI itself,
before any route code or the database ever sees the value. A
syntactically valid but nonexistent id (`INC-99999999`) still reaches
`get_incident()` and gets the existing, tested 404.

**Why:** this is a real bug found by testing, the same way Phase 7's two
bugs were (DDR's own "Bug found by manually testing the UI" section
above) — not a hypothetical hardening exercise. Validating shape at the
API boundary catches an entire class of malformed input in one place
rather than trying to anticipate and catch each downstream failure mode
individually (a null byte was the one this sandbox's Postgres happened to
reject loudly; there is no guarantee it's the only character class that
would). `tests/integration/test_api_security.py` also caps
`RunEvaluationRequest.instances_per_scenario` at 20 (`Field(ge=1, le=20)`)
for the same reason in a different shape: each instance runs three
architectures' worth of real investigations, so an unbounded value on a
public endpoint is a genuine resource-exhaustion vector, not just a slow
response — spec §41's "oversized requests" in practice, not in theory.
