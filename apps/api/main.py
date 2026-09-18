from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.logging_config import configure_logging
from apps.api.routes import health
from core.config import get_settings

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="IncidentLab API",
    description="Multi-agent incident investigation & evaluation lab",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
