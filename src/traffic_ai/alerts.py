from dataclasses import dataclass
from typing import List
from .schemas import DecisionRecord

@dataclass
class Alert:
    level: str  # WARNING, CRITICAL
    type: str   # CROWD_SURGE, EMERGENCY_BLOCKED, SEVERE_GRIDLOCK
    message: str

class AlertEngine:
    """Evaluates snapshots and decisions against stringent safety rules to emit alerts."""
    
    def __init__(self, crowd_threshold: float = 0.80, gridlock_threshold: int = 80):
        # By default, trigger warnings when crowd is >80% or vehicles exceed 80
        self.crowd_threshold = crowd_threshold
        self.gridlock_threshold = gridlock_threshold

    def evaluate(self, decision: DecisionRecord) -> List[Alert]:
        alerts = []
        snap = decision.snapshot
        
        # 1. Critical Crowd Risk (Stampede/Overcrowding avoidance)
        if snap.crowd_density >= self.crowd_threshold:
            alerts.append(Alert(
                level="CRITICAL",
                type="CROWD_SURGE",
                message=f"Dangerous crowd density ({snap.crowd_density*100:.1f}%) detected at {decision.intersection_id}."
            ))
            
        # 2. Emergency Blockage (Ambulance in heavy traffic)
        # Even moderate traffic (50% of gridlock threshold) restricts emergency movement
        if snap.emergency_vehicle_present and snap.vehicle_count > (self.gridlock_threshold * 0.5):
            alerts.append(Alert(
                level="CRITICAL",
                type="EMERGENCY_BLOCKED",
                message=f"Emergency vehicle stuck in heavy traffic ({snap.vehicle_count} vehicles) at {decision.intersection_id}."
            ))

        # 3. Severe Gridlock
        if snap.vehicle_count >= self.gridlock_threshold:
            alerts.append(Alert(
                level="WARNING",
                type="SEVERE_GRIDLOCK",
                message=f"Severe gridlock buildup ({snap.vehicle_count} vehicles) at {decision.intersection_id}."
            ))
            
        return alerts
