from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.logging_config import configure_logging
from apps.api.routes import evaluations, health, incidents, investigations
from core.config import get_settings
from core.db import create_all_tables

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """`simulator.replay.run_scenario()` already creates the schema before
    its first write, but a GET (e.g. the dashboard's `GET /incidents` on
    first load, before anyone has ever created an incident) has no write
    to piggyback that on — without this, the very first request to a
    freshly-started API against an empty Postgres 500s with
    "relation incidents does not exist" instead of just returning []."""
    await create_all_tables()
    yield


app = FastAPI(
    title="IncidentLab API",
    description="Multi-agent incident investigation & evaluation lab",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(investigations.router)
app.include_router(evaluations.router)
