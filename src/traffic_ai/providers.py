from __future__ import annotations

from dataclasses import dataclass
from random import Random

from .schemas import IntersectionSnapshot


from .events import CityEventTracker

@dataclass
class MockEventProvider:
    """Deterministic mock provider for early development/testing."""

    seed: int = 7
    event_tracker: CityEventTracker | None = None
    weather_mode: str = "clear"

    def __post_init__(self) -> None:
        self._rng = Random(self.seed)

    def get_snapshot(self, intersection_id: str) -> IntersectionSnapshot:
        # Intersection id can be used later to route to source-specific models.
        base = sum(ord(ch) for ch in intersection_id) % 40
        vehicle_count = 25 + base + self._rng.randint(0, 45)
        crowd_density = round(min(0.15 + (base / 100) + self._rng.random() * 0.4, 1.0), 2)
        emergency_vehicle_present = self._rng.random() < 0.08
        
        risk = self.event_tracker.get_risk_for_intersection(intersection_id) if self.event_tracker else "NORMAL"

        # Monsoon Simulation
        if self.weather_mode == "rain":
            vehicle_count += 60
            crowd_density = min(crowd_density + 0.35, 1.0)
            emergency_vehicle_present = self._rng.random() < 0.25 # rain causes more accidents

        return IntersectionSnapshot(
            vehicle_count=vehicle_count,
            crowd_density=crowd_density,
            emergency_vehicle_present=emergency_vehicle_present,
            event_risk_level=risk,
            weather=self.weather_mode
        )
