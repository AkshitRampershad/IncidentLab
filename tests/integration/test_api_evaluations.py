import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_run_evaluation(client):
    response = await client.post("/evaluations/run", json={"instances_per_scenario": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["dataset_size"] == 2
    architectures = {a["architecture"] for a in body["report"]["architectures"]}
    assert architectures == {"direct_llm", "single_agent", "multi_agent"}


async def test_run_evaluation_with_empty_body_uses_defaults(client):
    response = await client.post("/evaluations/run")
    assert response.status_code == 200
    assert response.json()["report"]["dataset_size"] == 6  # 2 scenarios x default 3 instances


async def test_list_evaluations_includes_run_ones(client):
    run_response = await client.post("/evaluations/run", json={"instances_per_scenario": 1})
    evaluation_id = run_response.json()["evaluation_id"]

    list_response = await client.get("/evaluations")
    assert list_response.status_code == 200
    ids = {row["evaluation_id"] for row in list_response.json()}
    assert evaluation_id in ids


async def test_get_evaluation_by_id(client):
    run_response = await client.post("/evaluations/run", json={"instances_per_scenario": 1})
    evaluation_id = run_response.json()["evaluation_id"]

    get_response = await client.get(f"/evaluations/{evaluation_id}")
    assert get_response.status_code == 200
    assert get_response.json()["evaluation_id"] == evaluation_id


async def test_get_unknown_evaluation_is_404(client):
    response = await client.get("/evaluations/does-not-exist")
    assert response.status_code == 404
