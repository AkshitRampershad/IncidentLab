from typing import Annotated

from fastapi import Path

# spec §41's "malformed inputs": incident_id is always this project's own
# generated `INC-<n>` form (simulator/replay.py's _next_incident_id) —
# constraining every route's path parameter to that shape rejects null
# bytes, SQL-metacharacters, path-traversal sequences, script tags, and
# oversized strings before any of it reaches the database, rather than
# trying to catch every downstream failure mode those could cause one at a
# time (a real one was found this way: a null byte in incident_id reached
# asyncpg raw and came back as an uncaught 500, not a clean 404).
IncidentId = Annotated[str, Path(pattern=r"^INC-\d+$", max_length=32)]
