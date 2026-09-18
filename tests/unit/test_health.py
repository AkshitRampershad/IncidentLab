from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from apps.api.main import app


async def test_health_liveness():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_unavailable_when_database_unreachable():
    """The probe must degrade gracefully (503) instead of raising, regardless
    of whether a real Postgres happens to be reachable in the environment
    running this test."""
    transport = ASGITransport(app=app)
    with patch("apps.api.routes.health.check_connection", side_effect=ConnectionError("boom")):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unreachable"
