from datetime import UTC, datetime, timedelta

from simulator.replay import run_scenario
from simulator.scenarios import SCENARIOS

# spec §28 aims for 50-100+ incidents (10 scenarios x 5 variations). This
# project has 2 scenarios (see docs/design-decisions.md) and each
# generator is a pure function of anchor_time alone — repeating a
# scenario at a different anchor_time produces a distinct incident_id and
# absolute timestamps, but *identical* relative structure and content.
# That's an honest, disclosed limitation (see DDR-016), not "5 real
# variations" in spec §29's sense (varying services/distractors/severity/
# volume) — it exists so the benchmark has more than one sample per
# scenario to average over, not to overstate dataset diversity.
_INSTANCES_PER_SCENARIO = 3
_ANCHOR_SPACING = timedelta(hours=1)


async def generate_dataset(
    instances_per_scenario: int = _INSTANCES_PER_SCENARIO,
) -> list[tuple[str, str]]:
    """Runs every registered scenario `instances_per_scenario` times at
    different anchor_times and returns [(incident_id, scenario_id), ...].

    Regenerated on demand (`make benchmark` calls this fresh each run)
    rather than stored as static fixtures — the simulator is already
    deterministic and reproducible per anchor_time, so a static dataset
    file would just be a redundant, driftable copy of what this function
    already reproduces exactly.
    """
    base_anchor = datetime(2026, 1, 1, tzinfo=UTC)
    dataset: list[tuple[str, str]] = []

    offset = 0
    for scenario_id in sorted(SCENARIOS):
        for _ in range(instances_per_scenario):
            anchor_time = base_anchor + _ANCHOR_SPACING * offset
            incident_id = await run_scenario(scenario_id, anchor_time=anchor_time)
            dataset.append((incident_id, scenario_id))
            offset += 1

    return dataset
