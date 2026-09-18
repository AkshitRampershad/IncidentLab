from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from simulator.replay import run_scenario

ANCHOR = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def incident_id():
    return await run_scenario("db_connection_pool", anchor_time=ANCHOR)


async def test_list_scenarios(client):
    response = await client.get("/scenarios")
    assert response.status_code == 200
    assert set(response.json()) == {"db_connection_pool", "redis_unavailable"}


async def test_list_incidents_includes_seeded_incident(client, incident_id):
    response = await client.get("/incidents")
    assert response.status_code == 200
    ids = {row["incident_id"] for row in response.json()}
    assert incident_id in ids


async def test_get_incident_exposes_only_public_fields(client, incident_id):
    response = await client.get(f"/incidents/{incident_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "checkout"
    assert "root_cause" not in body
    assert "ground_truth" not in body


async def test_get_incident_404_for_unknown_id(client):
    response = await client.get("/incidents/INC-9999")
    assert response.status_code == 404


async def test_create_incident(client):
    response = await client.post("/incidents", json={"scenario_id": "redis_unavailable"})
    assert response.status_code == 201
    assert response.json()["service"] == "checkout"


async def test_create_incident_rejects_unknown_scenario(client):
    response = await client.post("/incidents", json={"scenario_id": "does_not_exist"})
    assert response.status_code == 400
