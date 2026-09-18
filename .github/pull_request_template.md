## Summary

<!-- What changed and why, in a sentence or two. -->

## Checklist

- [ ] `make test` passes locally against a real Postgres (not skipped/mocked)
- [ ] `make lint` clean (`ruff check` + `ruff format --check` + `eslint` if `apps/web` changed)
- [ ] `apps/web` changes: `npm run build` actually run, not just `npm run lint`
- [ ] New behavior has a new test, alongside existing tests of the same kind (unit vs. integration)
- [ ] Non-trivial decisions have a new DDR in `docs/design-decisions.md` — a bug fix or mechanical refactor doesn't need one
- [ ] If this changes what's implemented, `docs/IMPLEMENTATION_STATUS.md` and/or `docs/architecture.md` are updated to match

## Test plan

<!-- Commands you ran and their actual output, not just "tests pass." -->
