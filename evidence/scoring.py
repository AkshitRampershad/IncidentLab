from datetime import datetime, timedelta

# How far outside the incident's [start_time, end_time] window a tool still
# searches by default — wide enough to catch a precursor deployment a few
# minutes before start_time, per spec §13's "60 seconds before" example.
SEARCH_WINDOW_PADDING = timedelta(minutes=15)

_DECAY_PER_MINUTE_OUTSIDE_WINDOW = 0.03
_MIN_TEMPORAL_RELEVANCE = 0.2


def temporal_relevance(timestamp: datetime, start: datetime, end: datetime) -> float:
    """1.0 for anything inside [start, end], decaying the further outside
    it a timestamp falls.

    This is a deterministic experimental baseline (spec §16), not a
    scientifically calibrated formula — it exists so `relevance` is
    reproducible and inspectable rather than an LLM's guess (spec §4.1,
    §16: "do not let the LLM arbitrarily decide confidence").
    """
    if start <= timestamp <= end:
        return 1.0
    distance_seconds = min(
        abs((timestamp - start).total_seconds()), abs((timestamp - end).total_seconds())
    )
    minutes_outside = distance_seconds / 60
    return max(_MIN_TEMPORAL_RELEVANCE, 1.0 - _DECAY_PER_MINUTE_OUTSIDE_WINDOW * minutes_outside)


def matches_query(content: str, query: str | None) -> bool:
    """Case-insensitive substring match. `query=None` matches everything —
    tools use this to mean "no filter, return the whole window"."""
    if not query:
        return True
    return query.lower() in content.lower()
