import pytest

from simulator.failure_injector.db_connection_pool import DbConnectionPoolInjector
from simulator.scenarios import get_injector


def test_known_scenario_resolves():
    injector = get_injector("db_connection_pool")
    assert isinstance(injector, DbConnectionPoolInjector)


def test_unknown_scenario_lists_available_ids():
    with pytest.raises(ValueError, match="db_connection_pool"):
        get_injector("nope")
