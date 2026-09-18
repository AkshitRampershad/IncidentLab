# Deployment

This describes deploying IncidentLab to a real host — not local dev
(`docker compose up --build` from the README already covers that).
Single-host Docker Compose (Options A/B below) and Render (a Blueprint,
`render.yaml` in the repo root) are both covered; neither is the only
possible option, and nothing here needs a specific cloud provider beyond
what each section is actually about.

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

## Option A: build on the host

Run `docker compose up -d --build` directly on the target host —
identical to local dev, just on a real machine with `.env` set for that
machine's real values instead of `.env.example`'s dev defaults.

## Option B: pre-built images from GHCR

`.github/workflows/docker-publish.yml` builds and pushes both images to
GHCR (`ghcr.io/<owner>/incidentlab-api` and `-web`, tagged `latest` and
by commit SHA) on every push to `main` that passes CI. Its first three
runs all failed at the build step with `Cache export is not supported
for the docker driver` (the workflow's `cache-to: type=gha` needs the
`docker-container` buildx driver, which requires an explicit
`docker/setup-buildx-action` step) — that step was added, and the
workflow has since run successfully end to end (verified against
GitHub's own Actions run history, both the `api` and `web` jobs green,
not assumed from the workflow file alone). Check the
[Actions tab](https://github.com/AkshitRampershad/incidentlab/actions/workflows/docker-publish.yml)
for the current status of the latest run on `main` before relying on
this path — a workflow succeeding once doesn't guarantee every future
run will too, and the images at `ghcr.io/<owner>/incidentlab-*` only
ever reflect whichever commit's run last completed.

Once it works: replace the `build:` block for `api` and `web` in
`docker-compose.yml` with `image:`, pointing at the published tags, then
`docker compose up -d`.

## Deploying to Render (Blueprint)

`render.yaml` in the repo root is a
[Render Blueprint](https://render.com/docs/infrastructure-as-code) —
Render reads it and creates a Postgres database plus the `api`/`web`
services from the existing Dockerfiles, no manual service configuration
needed for the parts it *can* express. Two values it genuinely can't
(each service's URL doesn't exist until Render creates it) are called
out explicitly below.

**Cost, stated plainly up front:** every plan in `render.yaml` is
`free`. That is real for both web services indefinitely, and real for
the database **for 30 days from creation** — Render's free Postgres plan
expires after 30 days (a 14-day grace period to upgrade before Render
deletes it), which is Render's platform limitation, not something this
file or this project can configure around. Free web services also spin
down after 15 minutes with no traffic and take about a minute to wake up
on the next request — expect that cold-start delay, especially for the
first request after a while, and expect it potentially twice in a row
(web spins up, then calls an also-asleep api).

1. **Deploy the Blueprint.** In the Render dashboard: **New** →
   **Blueprint** → select the `incidentlab` GitHub repo (already
   connected) → Render parses `render.yaml` and shows the three
   resources it will create (`incidentlab-db`, `incidentlab-api`,
   `incidentlab-web`) → **Apply**. Render creates the database first,
   then builds and deploys both Docker services from their existing
   Dockerfiles.
2. **Wait for the first deploy to finish**, then note both services'
   real URLs from the Render dashboard (each service's page shows it
   near the top, shaped like `https://incidentlab-api-xxxx.onrender.com`
   — Render may append a short suffix if the exact name is taken; use
   whatever Render actually assigned, not the plain
   `incidentlab-api.onrender.com` guess).
3. **Set the two manual environment variables** this file cannot compute
   (see DDR-034 for why `render.yaml` doesn't attempt this via
   `fromService`):
   - On **`incidentlab-api`** → Environment → `CORS_ALLOWED_ORIGINS` →
     the **web** service's real URL from step 2 (e.g.
     `https://incidentlab-web-xxxx.onrender.com`, no trailing slash).
   - On **`incidentlab-web`** → Environment → `API_URL` → the **api**
     service's real URL from step 2 (e.g.
     `https://incidentlab-api-xxxx.onrender.com`).
   - Save each — Render redeploys that service automatically. `api`'s
     redeploy just picks up the new CORS value; `web`'s doesn't even
     need a rebuild for this to take effect, since `API_URL` is read
     live per-request (DDR-033), not baked into the image — but Render
     restarts the container on an env var change regardless, which is
     enough.
4. **Verify.** Open the web service's URL, generate an incident, run an
   investigation. If it hangs on "Investigating…" with a CORS error in
   the browser console, `CORS_ALLOWED_ORIGINS` doesn't exactly match the
   web URL (scheme and no trailing slash both matter). If the page loads
   but every action 404s or times out, re-check `API_URL` on the web
   service.

No LLM is configured in `render.yaml` — the deployment runs in the fully
deterministic fallback path every agent already has (DDR-010), same as
this project's own build/test environment. Pointing `LLM_PROVIDER` at
`openai`/`anthropic` with a real `LLM_API_KEY` (added manually in the
dashboard, never in `render.yaml` — see "Do NOT commit secrets" in this
doc's own scope) works the same way here as anywhere else in this
project.

**What's been verified about this path, and what hasn't:** every field
in `render.yaml` was checked against Render's actual published Blueprint
schema before being written (see DDR-034) — `docker compose config` was
also re-run after this section's changes and still validates. Render
itself has never actually built or deployed this Blueprint — `render.com`
is unreachable from the sandbox this was written in, so no service was
created, no cost was incurred, and no public URL exists as a result of
writing this file. The steps above are correct by matching Render's
documented behavior, not by having been clicked through.

## Required changes for a real deployment

`.env.example`'s defaults are for `localhost` dev and are **not safe or
functional** as-is anywhere else:

| Variable | Dev default | Change to |
|---|---|---|
| `POSTGRES_PASSWORD` | `incidentlab` | a real generated secret |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | the actual origin the web app is served from (e.g. `https://incidentlab.example.com`) — the API rejects browser requests from any origin not listed here (see `docs/design-decisions.md` DDR-028) |
| `API_URL` | `http://localhost:8000` | the API's actual public URL — read live, per request, by `apps/web/app/api/config/route.ts` (DDR-033); this is *not* the same mechanism as a `NEXT_PUBLIC_`-prefixed var, which Next.js bakes into the browser bundle at `docker build` time and can't be changed by an env var set later, at container start |
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

On Render specifically: free-plan Postgres databases don't support any
form of backup at all (Render's own limitation, not configurable), on
top of the 30-day expiry mentioned above — another reason this project's
"regeneratable data" framing matters for that path in particular, not
just as a general disclaimer.

## Logs

`LOG_LEVEL` (default `INFO`) controls both the app's own structured
`structlog` JSON output and the OpenTelemetry console span exporter
(`core/telemetry.py` — see `docs/design-decisions.md` DDR-026 for why
there's no real trace collector yet). `docker compose logs -f api` is the
whole observability story today; piping that into a real log aggregator
is a straightforward next step with no IncidentLab-specific wiring
needed (it's already structured JSON lines).
