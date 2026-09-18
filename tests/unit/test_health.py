from httpx import ASGITransport, AsyncClient

from apps.api.main import app


async def test_health_liveness():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_unavailable_without_database():
    """No Postgres is running for this unit test, so the probe must degrade
    gracefully (503) instead of raising."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unreachable"
