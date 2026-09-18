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

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
