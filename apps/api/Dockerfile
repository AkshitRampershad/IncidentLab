FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Everything apps/api transitively imports at runtime (agents/orchestration
# call into all of these; tools/knowledge.py reads knowledge/ as files on
# disk, not from the DB, so it needs to be copied too, not just importable).
COPY core ./core
COPY evidence ./evidence
COPY tools ./tools
COPY simulator ./simulator
COPY agents ./agents
COPY hypotheses ./hypotheses
COPY orchestration ./orchestration
COPY evaluation ./evaluation
COPY knowledge ./knowledge
COPY apps/api ./apps/api

ENV PATH="/app/.venv/bin:${PATH}"

# Phase 9: run as an unprivileged user rather than the image's default
# root — this process never needs to write anywhere but its own working
# directory (no host mounts, no writes to /app at runtime), so there's no
# reason for a compromised process to have root inside the container.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# spec §42-adjacent: makes the container's own health legible to whatever
# runs it (`docker inspect`, an orchestrator's liveness probe) even
# outside docker-compose, which already has its own equivalent check for
# the compose-specific `depends_on: condition: service_healthy` case.
# Reads $PORT (falls back to 8000, this image's EXPOSEd default) so this
# stays correct on a PaaS that assigns its own port — see CMD below.
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/health')" || exit 1

# Shell form (not exec-form JSON) so $PORT actually expands; `exec` still
# replaces the shell as PID 1 so SIGTERM reaches uvicorn directly instead
# of being swallowed by an intermediate /bin/sh. Defaults to 8000 (this
# image's EXPOSEd port) when $PORT is unset, e.g. plain `docker compose
# up` — most PaaS hosts (Render included) assign their own via $PORT.
CMD ["sh", "-c", "exec uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
