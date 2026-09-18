# Contributing to IncidentLab

Thanks for considering it. This project was built phase-by-phase (see
`docs/IMPLEMENTATION_STATUS.md`) with a specific set of conventions —
reading this before your first PR will save you a review round.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Dev setup

```bash
git clone https://github.com/AkshitRampershad/incidentlab
cd incidentlab
cp .env.example .env
make setup   # uv sync + npm install
```

Integration tests need a reachable Postgres:
`docker compose up postgres -d`, or a local install with `.env`'s
defaults. Then:

```bash
make test    # pytest (unit + integration)
make lint    # ruff check + eslint
make format  # ruff format
```

CI (`.github/workflows/ci.yml`) runs the same checks against a real
Postgres service container — there's no mocked-database test path to
fall back on, by design (see `docs/design-decisions.md` for why
correctness here has consistently meant "run it for real," not "assert
the shape looks right").

## Before opening a PR

- `make test && make lint` clean, locally, against a real Postgres — not
  just "looks right."
- New behavior gets a new test, in the same style as the file it's
  nearest to (`tests/unit/` for pure functions, `tests/integration/` for
  anything touching Postgres or the real FastAPI app via
  `httpx.ASGITransport`).
- A non-trivial decision (not a bug fix, not a mechanical refactor) gets
  a new DDR in `docs/design-decisions.md` — see "Design decisions" below.
- If you touched `apps/web`, actually run `npm run build` — type errors
  there aren't caught by `make lint` alone in every case.

## Design decisions (DDRs)

`docs/design-decisions.md` is not a changelog — it's *why* the code is
shaped the way it is, written when the decision is made, not
reconstructed later. Each entry states the context, the decision, and
what the alternative would have cost. If your PR makes a real
architectural choice (not "fixed a typo," but "chose X over Y and here's
why"), add one. Look at any existing entry for the expected shape and
level of honesty — including entries that admit a limitation rather than
paper over it (e.g. DDR-017's disclosure that the evaluation dataset is
small, or DDR-031 on why Alembic still isn't used). Padding or vague
justification will get pushback in review; a real, specific "why" that's
honest about the trade-off won't.

## Code style

- Python: `ruff` (lint + format) is the source of truth — `make format`
  before committing. Type hints throughout; async everywhere the code
  already is (don't introduce sync DB calls).
- TypeScript: `eslint` via `next lint`. Plain CSS, no UI framework (see
  `docs/design-decisions.md` for why, if you're tempted to add one).
- Comments: this codebase defaults to *no* comments. Add one only when
  the *why* is genuinely non-obvious (a hidden constraint, a workaround
  for a specific bug, something that would surprise a careful reader) —
  not to restate what well-named code already says. Most "why" belongs
  in a DDR, not an inline comment, so it survives the code being
  refactored.
- No speculative abstractions, no error handling for cases that can't
  happen, no half-finished features gated behind a flag. If something's
  out of scope, say so in the relevant doc (see `docs/deployment.md`'s
  "What's deliberately not included" for the pattern) rather than
  stubbing it.

## Adding a new incident scenario

The most common real extension point. A new scenario needs, together, not
separately:

1. `simulator/failure_injector/<name>.py` — a `FailureInjector`
   subclass, deterministic given an `anchor_time` (see
   `docs/design-decisions.md` DDR-007 for why no randomness and no real
   service load).
2. Registration in `simulator/scenarios/__init__.py`.
3. If it introduces a genuinely new root-cause signal (not a variation on
   an existing one): a new entry in `agents/base.py`'s
   `_HYPOTHESIS_PATTERNS` **and**, if it should merge multi-source
   evidence, `hypotheses/manager.py`'s `_CANONICAL_HYPOTHESES` — these two
   tables are companions (DDR-013); adding to one without the other is a
   partial change.
4. A runbook in `knowledge/runbooks/` if the Adjudicator should be able
   to recommend a real remediation for it (never fabricate one — DDR-011,
   spec §4.3).
5. A test proving the scenario is deterministic and produces the correct
   ground truth, in the style of
   `tests/unit/test_db_connection_pool_scenario.py`.

## Reporting bugs / requesting features

Use the issue templates — they ask for exactly what's needed to act on a
report quickly. Security issues go through `SECURITY.md`, not a public
issue.

## Questions

Open a
[discussion](https://github.com/AkshitRampershad/incidentlab/discussions)
or an issue — there's no separate chat/forum for this project.
