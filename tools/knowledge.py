from datetime import UTC, datetime
from pathlib import Path

from evidence.models import Evidence, SourceType
from evidence.provenance import build_evidence_id, build_provenance
from evidence.scoring import matches_query
from tools.registry import allowlisted_tool

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
_RUNBOOKS_DIR = KNOWLEDGE_ROOT / "runbooks"
_ARCHITECTURE_DIR = KNOWLEDGE_ROOT / "architecture"
_HISTORICAL_INCIDENTS_DIR = KNOWLEDGE_ROOT / "historical_incidents"

# Knowledge docs aren't dated telemetry, so there's no incident time window
# to score temporal proximity against — every keyword match gets the same
# static relevance. A documented simplification, not a calibrated score.
_STATIC_RELEVANCE = 0.8


def _search_dir(
    directory: Path, source_type: SourceType, *, incident_id: str, query: str | None
) -> list[Evidence]:
    evidence = []
    for path in sorted(directory.glob("*.md")):
        content = path.read_text()
        if not matches_query(content, query):
            continue
        evidence.append(
            Evidence(
                evidence_id=build_evidence_id(source_type, path.stem),
                source_type=source_type,
                source=str(path.relative_to(KNOWLEDGE_ROOT)),
                timestamp=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                content=content,
                relevance=_STATIC_RELEVANCE,
                provenance=build_provenance(
                    table=directory.name, row_id=path.stem, incident_id=incident_id
                ),
            )
        )
    return evidence


@allowlisted_tool("search_knowledge")
async def search_knowledge(incident_id: str, query: str | None = None) -> list[Evidence]:
    """spec §14's search_knowledge(): runbooks + architecture docs,
    keyword-matched. No vector search yet — see docs/design-decisions.md;
    this is plain substring search over a handful of real, hand-authored
    markdown files, not a stand-in for one."""
    return _search_dir(
        _RUNBOOKS_DIR, SourceType.RUNBOOK, incident_id=incident_id, query=query
    ) + _search_dir(
        _ARCHITECTURE_DIR, SourceType.DOCUMENTATION, incident_id=incident_id, query=query
    )


@allowlisted_tool("search_historical_incidents")
async def search_historical_incidents(incident_id: str, query: str | None = None) -> list[Evidence]:
    """spec §14's search_historical_incidents()."""
    return _search_dir(
        _HISTORICAL_INCIDENTS_DIR,
        SourceType.HISTORICAL_INCIDENT,
        incident_id=incident_id,
        query=query,
    )


@allowlisted_tool("get_runbook")
async def get_runbook(incident_id: str, name: str) -> Evidence | None:
    """spec §14's get_runbook(): fetch one runbook by filename stem (e.g.
    "db-connection-pool-exhaustion"), or None if it doesn't exist."""
    matches = await search_knowledge(incident_id, query=None)
    for e in matches:
        if e.source_type == SourceType.RUNBOOK and Path(e.source).stem == name:
            return e
    return None
