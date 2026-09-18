from datetime import UTC, datetime, timedelta

import pytest

from evidence.models import SourceType
from evidence.provenance import build_evidence_id, build_provenance


def test_evidence_id_prefixes():
    assert build_evidence_id(SourceType.LOG, 1842) == "LOG-1842"
    assert build_evidence_id(SourceType.METRIC, 203) == "METRIC-203"
    assert build_evidence_id(SourceType.DEPLOYMENT, 482) == "DEPLOY-482"


def test_evidence_id_raises_for_unregistered_source_type():
    with pytest.raises(ValueError, match="TRACE"):
        build_evidence_id(SourceType.TRACE, 1)


def test_provenance_carries_the_row_reference():
    before = datetime.now(UTC)
    provenance = build_provenance(table="log_events", row_id=42, incident_id="INC-0001")
    after = datetime.now(UTC)

    assert provenance.table == "log_events"
    assert provenance.row_id == 42
    assert provenance.incident_id == "INC-0001"
    assert before - timedelta(seconds=1) <= provenance.retrieved_at <= after + timedelta(seconds=1)
