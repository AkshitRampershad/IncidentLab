"""spec §41's security test list: prompt injection, malformed inputs, tool
abuse, oversized requests, invalid incident IDs — exercised against the
real API (real Postgres, real routing), not mocked. The bar for all of
these is the same: never a 500, and never any effect beyond a clean 4xx.
"""

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


_MALICIOUS_INCIDENT_IDS = [
    "INC-0001'; DROP TABLE incidents;--",
    "' OR '1'='1",
    "../../etc/passwd",
    "<script>alert(1)</script>",
    "INC-0001%00INC-0002",  # pre-encoded null byte — a raw \x00 is rejected
    # client-side by httpx itself before it ever reaches the server, so it
    # wouldn't exercise the server's own handling at all.
    "A" * 10_000,
]


@pytest.mark.parametrize("bad_id", _MALICIOUS_INCIDENT_IDS)
async def test_get_incident_with_malicious_id_never_500s(client, bad_id):
    """None of these match the enforced `INC-<n>` shape
    (apps/api/validation.py's IncidentId), so FastAPI itself rejects them
    with a 422 before any route code — let alone the database — ever sees
    the value. A couple (a literal `/` inside a payload, `../..`) instead
    fail to match the route's path template at all and get Starlette's
    own generic 404 first — still never touching route code either."""
    response = await client.get(f"/incidents/{bad_id}")
    assert response.status_code in (404, 422)


async def test_get_incident_with_empty_id_is_a_clean_redirect_not_500(client):
    """`/incidents/` (empty id) hits FastAPI's own trailing-slash
    redirect to the list route rather than the single-incident route —
    documenting that as intentional, not a 500 or an accidental match."""
    response = await client.get("/incidents/", follow_redirects=True)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.parametrize("bad_id", _MALICIOUS_INCIDENT_IDS)
async def test_investigate_with_malicious_id_never_500s(client, bad_id):
    response = await client.post(f"/incidents/{bad_id}/investigate")
    assert response.status_code in (404, 422)


@pytest.mark.parametrize("bad_id", _MALICIOUS_INCIDENT_IDS)
async def test_investigation_timeline_with_malicious_id_never_500s(client, bad_id):
    response = await client.get(f"/investigations/{bad_id}/timeline")
    assert response.status_code in (404, 422)


async def test_a_malicious_id_never_actually_matches_a_real_incident(client, incident_id):
    """Confirms the rejections above aren't accidental — a crafted id must
    never be treated as equivalent to a real one, and never disturbs it
    (SQLAlchemy's ORM `get`/`where` already parameterize everything on top
    of the shape check; this is the regression test proving both hold, not
    just an assumption)."""
    response = await client.get(f"/incidents/{incident_id}'; DROP TABLE incidents;--")
    assert response.status_code == 422

    # And the real incident must still be there afterwards.
    still_there = await client.get(f"/incidents/{incident_id}")
    assert still_there.status_code == 200


async def test_well_formed_but_nonexistent_id_is_a_clean_404_not_422(client):
    """A syntactically valid `INC-<n>` that just doesn't exist is a
    different case from a malformed one — it must still reach the
    database and come back 404, not get rejected by shape validation."""
    response = await client.get("/incidents/INC-99999999")
    assert response.status_code == 404


async def test_create_incident_with_wrong_field_type_is_422_not_500(client):
    response = await client.post("/incidents", json={"scenario_id": 12345})
    assert response.status_code == 422


async def test_create_incident_with_missing_field_is_422_not_500(client):
    response = await client.post("/incidents", json={})
    assert response.status_code == 422


async def test_create_incident_with_unknown_scenario_is_400_not_500(client):
    response = await client.post("/incidents", json={"scenario_id": "does-not-exist"})
    assert response.status_code == 400


async def test_create_incident_with_oversized_body_is_rejected_not_500(client):
    response = await client.post("/incidents", json={"scenario_id": "x" * 1_000_000})
    assert response.status_code in (400, 413, 422)
    assert response.status_code != 500


async def test_run_evaluation_with_oversized_instance_count_is_422(client):
    """spec §41's "oversized requests": each instance runs 3 architectures
    worth of real investigations, so an unbounded count is a genuine
    resource-exhaustion vector on a public endpoint — see
    apps/api/routes/evaluations.py's RunEvaluationRequest."""
    response = await client.post("/evaluations/run", json={"instances_per_scenario": 1_000_000})
    assert response.status_code == 422


async def test_run_evaluation_with_negative_instance_count_is_422(client):
    response = await client.post("/evaluations/run", json={"instances_per_scenario": -1})
    assert response.status_code == 422


async def test_run_evaluation_with_zero_instance_count_is_422(client):
    response = await client.post("/evaluations/run", json={"instances_per_scenario": 0})
    assert response.status_code == 422


async def test_get_unknown_evaluation_id_is_404_not_500(client):
    response = await client.get(f"/evaluations/{'x' * 5000}")
    assert response.status_code == 404


async def test_malformed_json_body_is_422_not_500(client):
    response = await client.post(
        "/incidents", content=b"{not valid json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
