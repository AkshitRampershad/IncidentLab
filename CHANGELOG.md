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
  health checks; configurable CORS; automated GHCR image publishing on
  every green `main`; a deployment guide (`docs/deployment.md`).
- **Open source readiness:** `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, issue/PR templates.

### Known limitations (see `docs/IMPLEMENTATION_STATUS.md` for the full, current list)

- No authentication or rate limiting on the API.
- No TLS/reverse proxy, no managed-Postgres story, no real horizontal
  scaling — single-host Docker Compose is the only deployment path
  documented today.
- Two incident scenarios, evaluated on a small (6-incident), honestly
  disclosed dataset — not spec-scale (50-100+ incidents).
- No live LLM has been exercised end-to-end in this project's own build
  environment; the deterministic path is what's been verified there.

[Unreleased]: https://github.com/AkshitRampershad/incidentlab/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AkshitRampershad/incidentlab/releases/tag/v0.1.0
