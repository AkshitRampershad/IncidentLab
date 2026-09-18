from datetime import UTC, datetime, timedelta

from evidence.scoring import matches_query, temporal_relevance

START = datetime(2026, 9, 18, 1, 0, 0, tzinfo=UTC)
END = START + timedelta(minutes=15)


def test_inside_window_is_fully_relevant():
    assert temporal_relevance(START + timedelta(minutes=5), START, END) == 1.0
    assert temporal_relevance(START, START, END) == 1.0
    assert temporal_relevance(END, START, END) == 1.0


def test_decays_outside_window():
    just_before = temporal_relevance(START - timedelta(minutes=1), START, END)
    long_before = temporal_relevance(START - timedelta(minutes=20), START, END)
    assert 0.0 < long_before < just_before < 1.0


def test_never_below_floor():
    far_away = temporal_relevance(START - timedelta(days=1), START, END)
    assert far_away == 0.2


def test_matches_query_none_matches_everything():
    assert matches_query("anything at all", None) is True
    assert matches_query("", None) is True


def test_matches_query_is_case_insensitive_substring():
    assert matches_query("Database Connection Timeout", "connection timeout") is True
    assert matches_query("database connection timeout", "REDIS") is False
