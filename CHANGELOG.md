# Changelog

All notable changes to this project are documented here, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. This is
the release-facing summary; `docs/IMPLEMENTATION_STATUS.md` is the
detailed, phase-by-phase engineering log (verification commands, real
bugs found and fixed, known limitations) this file is distilled from.

## [Unreleased]

Nothing yet.

## [0.1.0] — 2026-09-18

Initial public release. Built phase-by-phase — see
`docs/IMPLEMENTATION_STATUS.md` for the full history and
`docs/design-decisions.md` for the reasoning behind every non-obvious
choice.

### Added

- **Foundation:** FastAPI + Next.js + Postgres, Docker Compose, CI
  (ruff/eslint/pytest against a real Postgres service container).
- **Incident simulator:** deterministic failure injection
  (`simulator/failure_injector/`) — `db_connection_pool` and
  `redis_unavailable` scenarios — with ground truth stored separately
  from investigator-visible data by construction.
- **Evidence layer:** structured, provenanced `Evidence` over
  logs/metrics/deployments/knowledge, with temporal relevance scoring.
- **Five investigation agents** (Triage, Logs, Metrics, Code, Knowledge):
  fully deterministic structured output; an LLM (local Ollama by
  default, or any OpenAI/Anthropic-compatible API) only ever enhances
  free-text narration and is never required.
- **Orchestration:** a LangGraph pipeline — Triage → parallel
  investigators → Hypothesis Manager (cross-source evidence merging +
  contradiction detection) → Adjudicator (confidence-gated RCA).
- **Evaluation harness:** Direct LLM / Single Agent / Multi-Agent
  architectures scored against the same held-out ground truth on real
  metrics (accuracy, evidence recall/precision, unsupported-claim rate,
  false-confidence rate, human escalation rate, latency).
- **Web UI:** generate an incident, run and review a full investigation,
  and run the benchmark — no CLI required.
- **Security + observability:** an explicit tool allowlist with per-call
  timeouts, a per-investigation call budget, and structured audit
  logging (`tools/registry.py`); graceful per-agent degradation instead
  of whole-investigation crashes; prompt-injection defense in depth on
  top of a structural guarantee that no agent's actual conclusion ever
  depends on an LLM response; OpenTelemetry tracing.
- **Deployment:** hardened, non-root container images with built-in
  health checks; configurable CORS; a deployment guide
  (`docs/deployment.md`); pre-built images published to GHCR on every
  green `main` (`.github/workflows/docker-publish.yml` — its first three
  runs failed on a buildx configuration issue, since fixed and verified
  working); a Render Blueprint (`render.yaml`) deployed to Render's free
  tier at https://incidentlab-web.onrender.com (API:
  https://incidentlab-api.onrender.com), subject to free-tier spin-down
  and Postgres expiry.
- **Open source readiness:** issue/PR templates; security vulnerability
  reports go through GitHub's private security advisory form.

### Known limitations (see `docs/IMPLEMENTATION_STATUS.md` for the full, current list)

- No authentication or rate limiting on the API.
- No TLS/reverse proxy, no managed-Postgres story, no real horizontal
  scaling — single-host Docker Compose is the only deployment path
  documented today.
- Two incident scenarios, evaluated on a small (6-incident), honestly
  disclosed dataset — not spec-scale (50-100+ incidents).
- No live LLM has been exercised end-to-end in this project's own build
  environment; the deterministic path is what's been verified there.
- The `render.yaml` Render Blueprint has never actually been deployed —
  no Render service exists and no cost has been incurred as a result of
  it being in this repo (see `docs/deployment.md`).

**Note on the links below:** as of this writing, the `v0.1.0` git tag
exists in the codebase's history locally but has not been pushed to
GitHub, and no GitHub Release has been published — these links will
404 until that happens. They're included per the standard
Keep a Changelog format and will resolve once the tag/release exist.

[Unreleased]: https://github.com/AkshitRampershad/incidentlab/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AkshitRampershad/incidentlab/releases/tag/v0.1.0
