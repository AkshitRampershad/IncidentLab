# Deployment

This describes deploying IncidentLab to a real host — not local dev
(`docker compose up --build` from the README already covers that). It's
one option (a single VM/box running Docker Compose), not the only one;
nothing here needs a specific cloud provider.

**Disclosure, same as every other phase of this project:** the sandbox
this was built in cannot pull images from Docker Hub (confirmed two ways
while writing this phase — a blob download returns `403 Forbidden` from
the organization's egress policy, and a registry metadata request
separately hits Docker Hub's own anonymous rate limit), so `docker build`
and `docker compose up --build` have never been run to completion inside
that sandbox, in this phase or any prior one. `docker compose config
--quiet` (which needs no image pulls) has been run and is the actual
verification behind this doc; the Dockerfiles and compose file below are
correct by inspection and existing convention, not by a build that
finished. The repo owner running `docker compose up --build` themselves
(as in Phase 1) remains the real end-to-end check.

## Option A: build on the host (recommended today)

Run `docker compose up -d --build` directly on the target host —
identical to local dev, just on a real machine with `.env` set for that
machine's real values instead of `.env.example`'s dev defaults.

## Option B: pre-built images from GHCR — not currently available

`.github/workflows/docker-publish.yml` exists and is wired to build and
push both images to GHCR (`ghcr.io/<owner>/incidentlab-api` and
`-web`, tagged `latest` and by commit SHA) on every push to `main` that
passes CI. **As of this writing it has not succeeded on any of its runs**
— every run so far has failed at the build step with `Cache export is
not supported for the docker driver` (the workflow's `cache-to:
type=gha` needs the `docker-container` buildx driver, which the runner
doesn't have by default without an explicit `docker/setup-buildx-action`
step; this hasn't been added yet). No image has ever been successfully
pushed, so there is nothing at `ghcr.io/<owner>/incidentlab-*` to pull
today. Check the
[Actions tab](https://github.com/AkshitRampershad/incidentlab/actions/workflows/docker-publish.yml)
for current status before relying on this path — if a run has since
succeeded, the commands below work as described; until then, use Option
A.

Once it works: replace the `build:` block for `api` and `web` in
`docker-compose.yml` with `image:`, pointing at the published tags, then
`docker compose up -d`.

## Required changes for a real deployment

`.env.example`'s defaults are for `localhost` dev and are **not safe or
functional** as-is anywhere else:

| Variable | Dev default | Change to |
|---|---|---|
| `POSTGRES_PASSWORD` | `incidentlab` | a real generated secret |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | the actual origin the web app is served from (e.g. `https://incidentlab.example.com`) — the API rejects browser requests from any origin not listed here (see `docs/design-decisions.md` DDR-028) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | the API's actual public URL — this is baked into the web app at container **start** time via `docker compose`'s environment substitution, but Next.js's standalone server reads `NEXT_PUBLIC_*` vars at runtime here since nothing pre-renders API calls at build time (every fetch is client-side) |
| `ENVIRONMENT` | `development` | `production` |

Everything else (`LLM_*`, `CONFIDENCE_*`, `TOOL_TIMEOUT_SECONDS` and its
neighbors) is safe to leave at its default and tune later — none of them
affect whether the deployment *works*, only investigation behavior.

## What's deliberately not included here

- **TLS / a reverse proxy.** `docker compose up` exposes plain HTTP on
  the ports in `.env`. Put a reverse proxy in front for real TLS
  (Caddy's automatic HTTPS is the least setup; nginx or Traefik work too)
  — not included here because it's a genuinely free choice with no
  IncidentLab-specific opinion to encode, and none of the three can be
  meaningfully verified without a real domain and real DNS this project
  doesn't have.
- **A managed/external Postgres.** The compose file's `postgres` service
  is a real, working default (a named volume persists data across
  restarts — see "Backups" below) — swapping it for a managed database is
  just pointing `POSTGRES_HOST`/`POSTGRES_PORT` at it and dropping the
  `postgres` service from `docker-compose.yml`.
- **Ollama as a service.** Deliberately never added to
  `docker-compose.yml` (see `docs/design-decisions.md`, Phase 4 and
  Phase 7's architecture notes) — Ollama is meant to run natively for GPU
  access. For a server deployment without a GPU, point `LLM_PROVIDER` at
  `openai` or `anthropic` (meaning any OpenAI/Anthropic-*compatible*
  HTTP API via `LLM_BASE_URL` — not a vendor lock-in) instead, or leave
  no LLM configured at all: every agent's structured output is fully
  deterministic and works with zero LLM regardless (DDR-010).
- **Horizontal scaling / a real orchestrator.** Single-host Docker
  Compose is this doc's whole scope. `apps/api`'s Dockerfile has a
  built-in `HEALTHCHECK` so the same image works correctly under an
  orchestrator that reads it (Kubernetes, ECS, Swarm) if that's ever
  needed, but wiring one up is future work with no current user to build
  it for.
- **Database migrations (Alembic).** Still deferred — see
  `docs/design-decisions.md` DDR-031 for why this deployment phase is
  exactly where that decision was revisited, not just carried over
  unexamined.

## Backups

Postgres data lives in the named volume `postgres_data`. A point-in-time
dump:

```bash
docker compose exec postgres pg_dump -U incidentlab incidentlab > backup.sql
```

Restore into a fresh volume with `psql -U incidentlab incidentlab <
backup.sql` after `docker compose up -d postgres`. There's no automated
backup schedule here — this is a lab/demo system with regeneratable data
(`make incident` produces fresh incidents deterministically; nothing here
is irreplaceable user data), so a cron/managed-backup story is scoped out
for the same reason a managed Postgres is: add it when there's an actual
deployment that needs it, not speculatively.

## Logs

`LOG_LEVEL` (default `INFO`) controls both the app's own structured
`structlog` JSON output and the OpenTelemetry console span exporter
(`core/telemetry.py` — see `docs/design-decisions.md` DDR-026 for why
there's no real trace collector yet). `docker compose logs -f api` is the
whole observability story today; piping that into a real log aggregator
is a straightforward next step with no IncidentLab-specific wiring
needed (it's already structured JSON lines).
