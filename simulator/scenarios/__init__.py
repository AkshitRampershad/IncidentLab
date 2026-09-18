from simulator.failure_injector.base import FailureInjector
from simulator.failure_injector.db_connection_pool import DbConnectionPoolInjector
from simulator.failure_injector.redis_unavailable import RedisUnavailableInjector

SCENARIOS: dict[str, FailureInjector] = {
    injector.scenario_id: injector
    for injector in [
        DbConnectionPoolInjector(),
        RedisUnavailableInjector(),
    ]
}


def get_injector(scenario_id: str) -> FailureInjector:
    try:
        return SCENARIOS[scenario_id]
    except KeyError:
        available = ", ".join(sorted(SCENARIOS)) or "(none registered)"
        raise ValueError(
            f"Unknown scenario '{scenario_id}'. Available scenarios: {available}"
        ) from None
