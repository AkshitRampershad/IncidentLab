from evidence.models import SourceType
from tools.knowledge import get_runbook, search_historical_incidents, search_knowledge


async def test_search_knowledge_with_no_query_returns_every_doc():
    results = await search_knowledge("INC-0001")
    assert len(results) == 3  # 2 runbooks + 1 architecture doc
    assert {e.source_type for e in results} == {SourceType.RUNBOOK, SourceType.DOCUMENTATION}


async def test_search_knowledge_query_filters_to_matching_docs():
    redis_results = await search_knowledge("INC-0001", query="Redis")
    assert len(redis_results) == 2  # the redis runbook + the architecture doc
    assert {e.source_type for e in redis_results} == {SourceType.RUNBOOK, SourceType.DOCUMENTATION}

    no_match = await search_knowledge("INC-0001", query="does-not-exist-anywhere")
    assert no_match == []


async def test_search_knowledge_evidence_ids_and_provenance():
    results = await search_knowledge("INC-0001")
    runbook = next(e for e in results if e.source_type == SourceType.RUNBOOK)
    assert runbook.evidence_id.startswith("RUNBOOK-")
    assert runbook.provenance.incident_id == "INC-0001"


async def test_search_historical_incidents_finds_the_seed_example():
    results = await search_historical_incidents("INC-0001")
    assert len(results) == 1
    assert results[0].source_type == SourceType.HISTORICAL_INCIDENT
    assert "INC-HIST-001" in results[0].content


async def test_get_runbook_returns_named_runbook_or_none():
    found = await get_runbook("INC-0001", "db-connection-pool-exhaustion")
    assert found is not None
    assert "Connection Pool Exhaustion" in found.content

    missing = await get_runbook("INC-0001", "does-not-exist")
    assert missing is None
