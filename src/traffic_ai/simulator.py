from __future__ import annotations

from dataclasses import asdict
from random import Random
from typing import Iterable

from .schemas import IntersectionSnapshot


def generate_event_surge(seed: int = 42, steps: int = 10) -> Iterable[IntersectionSnapshot]:
    """Generate synthetic event-time snapshots.

    This baseline generator mimics:
    - pre-event gradual traffic buildup
    - event peak with high crowd density
    - post-event dispersion
    """

    rng = Random(seed)

    for t in range(steps):
        if t < steps * 0.3:
            vehicles = 20 + t * 6 + rng.randint(0, 6)
            crowd = min(0.2 + t * 0.05 + rng.random() * 0.05, 1.0)
        elif t < steps * 0.7:
            vehicles = 60 + rng.randint(10, 35)
            crowd = min(0.65 + rng.random() * 0.35, 1.0)
        else:
            vehicles = 30 + rng.randint(0, 20)
            crowd = min(0.3 + rng.random() * 0.25, 1.0)

        emergency = rng.random() < 0.1
        yield IntersectionSnapshot(
            vehicle_count=vehicles,
            crowd_density=round(crowd, 2),
            emergency_vehicle_present=emergency,
        )


def to_dict(snapshot: IntersectionSnapshot) -> dict:
    return asdict(snapshot)
