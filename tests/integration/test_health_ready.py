from httpx import ASGITransport, AsyncClient

from apps.api.main import app


async def test_readiness_reports_ok_when_database_reachable():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}
