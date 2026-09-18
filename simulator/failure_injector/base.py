from abc import ABC, abstractmethod
from datetime import datetime

from simulator.models import IncidentDraft


class FailureInjector(ABC):
    """Deterministically synthesizes the telemetry for one failure scenario.

    Deliberately does not run a real service under real load (see
    docs/design-decisions.md DDR-007): given the same `anchor_time`, an
    injector must return byte-for-byte the same IncidentDraft, so a
    scenario is reproducible without depending on wall-clock randomness or
    an actual running system.
    """

    scenario_id: str

    @abstractmethod
    def generate(self, anchor_time: datetime) -> IncidentDraft:
        """Build the full incident: telemetry, timeline, and ground truth.

        `anchor_time` is the moment the incident is considered to have been
        resolved (its end_time) — everything else is generated relative to
        it so the scenario is deterministic given a fixed anchor.
        """
