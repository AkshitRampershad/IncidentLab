"""Phase 9: CORS origins are now configurable (core.config.Settings.
cors_allowed_origins) instead of Phase 1's hardcoded "http://localhost:3000"
— this confirms the real, running app actually reflects whichever origin
is configured, not just that the setting parses correctly in isolation
(tests/unit/test_config.py covers that half).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_configured_origin_is_allowed(client):
    response = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_unconfigured_origin_gets_no_cors_header(client):
    """starlette's CORSMiddleware doesn't reject the request outright (a
    browser enforces the same-origin policy client-side using this
    header) — but an origin that was never configured must not get an
    `access-control-allow-origin` echoing it back, or the browser-side
    protection this exists for is a no-op."""
    response = await client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
