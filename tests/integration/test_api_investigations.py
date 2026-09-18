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


async def test_investigate_incident(client, incident_id):
    response = await client.post(f"/incidents/{incident_id}/investigate")
    assert response.status_code == 200
    body = response.json()

    assert body["incident_id"] == incident_id
    assert body["adjudication"]["selected_hypothesis"] == "Connection pool exhaustion"
    assert body["adjudication"]["confidence"] > 0.9
    assert set(body["agents"]) == {"logs", "metrics", "code", "knowledge"}
    assert len(body["hypotheses"]) > 0


async def test_investigate_unknown_incident_is_404(client):
    response = await client.post("/incidents/INC-9999/investigate")
    assert response.status_code == 404


async def test_get_investigation_matches_post(client, incident_id):
    response = await client.get(f"/investigations/{incident_id}")
    assert response.status_code == 200
    assert response.json()["adjudication"]["selected_hypothesis"] == "Connection pool exhaustion"


async def test_investigation_timeline(client, incident_id):
    response = await client.get(f"/investigations/{incident_id}/timeline")
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    timestamps = [item["timestamp"] for item in body]
    assert timestamps == sorted(timestamps)


async def test_investigation_evidence(client, incident_id):
    response = await client.get(f"/investigations/{incident_id}/evidence")
    assert response.status_code == 200
    assert len(response.json()) > 0


async def test_investigation_hypotheses(client, incident_id):
    response = await client.get(f"/investigations/{incident_id}/hypotheses")
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    confidences = [h["confidence"] for h in body]
    assert confidences == sorted(confidences, reverse=True)


async def test_investigation_agents(client, incident_id):
    response = await client.get(f"/investigations/{incident_id}/agents")
    assert response.status_code == 200
    assert set(response.json()) == {"logs", "metrics", "code", "knowledge"}


async def test_approve_and_reject(client, incident_id):
    approve = await client.post(f"/investigations/{incident_id}/approve")
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    reject = await client.post(f"/investigations/{incident_id}/reject")
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"
