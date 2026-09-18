import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.db import check_connection

logger = structlog.get_logger()

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe: process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """Readiness probe: confirms the API can reach Postgres."""
    try:
        await check_connection()
    except Exception as exc:  # noqa: BLE001 - reported as a health status, not raised
        logger.warning("readiness_check_failed", error=str(exc))
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "database": "unreachable"}
        )
    return JSONResponse(status_code=200, content={"status": "ok", "database": "reachable"})
