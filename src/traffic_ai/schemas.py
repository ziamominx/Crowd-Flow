from dataclasses import dataclass


@dataclass(slots=True)
class IntersectionSnapshot:
    """Single timestamp view of an intersection."""

    vehicle_count: int
    crowd_density: float
    emergency_vehicle_present: bool = False
    event_risk_level: str = "NORMAL"
    weather: str = "clear"


@dataclass(slots=True)
class SignalPlan:
    """Recommended signal timing (seconds)."""

    green_seconds: int
    red_seconds: int
    reason: str

@dataclass(slots=True)
class DecisionRecord:
    intersection_id: str
    snapshot: IntersectionSnapshot
    plan: SignalPlan
