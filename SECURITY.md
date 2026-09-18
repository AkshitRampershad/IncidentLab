# Security Policy

## Reporting a vulnerability

Please report security issues privately, not as a public GitHub issue:

- Preferred: open a
  [GitHub private security advisory](https://github.com/AkshitRampershad/incidentlab/security/advisories/new)
  for this repository.
- Alternative: email akshitrampershad@gmail.com with a description, steps
  to reproduce, and the potential impact.

Please include enough detail to reproduce the issue (affected
file/endpoint, request/payload shape, expected vs. actual behavior).
There's no formal SLA — this is a single-maintainer open-source project
— but real reports get triaged and acknowledged promptly.

## Scope

In scope: the FastAPI backend (`apps/api`), the Next.js frontend
(`apps/web`), the tool/agent/orchestration layer (`tools/`, `agents/`,
`orchestration/`), and the Docker images/Compose setup.

## Known, deliberate limitations — not vulnerabilities to report

These are already documented, disclosed, and out of scope for this
phase, not oversights:

- **No authentication or rate limiting on the API.** Every endpoint is
  open by design at this stage — see `docs/IMPLEMENTATION_STATUS.md`'s
  Phase 1 and Phase 8 "Known limitations." Deploying this publicly
  without your own auth/rate-limiting layer in front is your
  responsibility, and `docs/deployment.md` says so.
- **No TLS built in.** `docker compose up` serves plain HTTP; putting a
  reverse proxy in front for TLS is explicitly left to the deployer —
  see `docs/deployment.md`.
- **The `/evaluations/run` endpoint runs real investigations against
  real (simulator-generated) data on request**, capped at 20 instances
  per scenario (`RunEvaluationRequest.instances_per_scenario`, spec §41's
  "oversized requests" hardening — see `docs/design-decisions.md`
  DDR-027) precisely so this is a bounded cost, not an unbounded one; if
  you can still make it disproportionately expensive, that *is* worth
  reporting.

If you're unsure whether something is a known limitation or a real bug,
report it anyway — a false positive costs a few minutes; a missed real
issue doesn't.

## What IS a legitimate report

Anything that breaks a guarantee this project actually makes: a 500
instead of a clean 4xx on malformed input (see
`tests/integration/test_api_security.py` for what's already covered), a
way to make ground truth (`IncidentGroundTruthRecord`, `is_distractor`)
leak into investigator-visible data, a prompt injection that changes a
*structured* result (`selected_hypothesis`, `confidence`,
`needs_human_review`) rather than just narration text (see
`docs/design-decisions.md` DDR-010 and DDR-025 for why that split exists
and is meant to be injection-proof), or a way to exceed the tool-call
budget/timeouts Phase 8 introduced (`tools/registry.py`).
