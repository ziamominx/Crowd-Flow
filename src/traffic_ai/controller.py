from .schemas import IntersectionSnapshot, SignalPlan


class SignalController:
    """Simple adaptive signal policy used as Phase-1 baseline.

    Policy intent:
    - prioritize emergency movement immediately
    - increase green time when traffic + crowd pressure increases
    - cap ranges to safe operational values
    """

    def __init__(self, min_green: int = 20, max_green: int = 90, cycle_time: int = 120):
        if min_green <= 0 or max_green <= min_green:
            raise ValueError("Invalid green bounds")
        if cycle_time <= max_green:
            raise ValueError("cycle_time must be larger than max_green")

        self.min_green = min_green
        self.max_green = max_green
        self.cycle_time = cycle_time

    def recommend(self, snapshot: IntersectionSnapshot) -> SignalPlan:
        if snapshot.emergency_vehicle_present:
            green = self.max_green
            red = max(self.cycle_time - green, 10)
            return SignalPlan(
                green_seconds=green,
                red_seconds=red,
                reason="Emergency vehicle detected: priority green extension",
            )
            
        if snapshot.weather == "rain":
            return SignalPlan(
                green_seconds=self.max_green,
                red_seconds=max(self.cycle_time - self.max_green, 10),
                reason="MONSOON ALERT: Activating extreme weather drainage routine.",
            )
            
        if snapshot.event_risk_level == "CRITICAL" or snapshot.event_risk_level == "HIGH":
            # Force high green allocation specifically geared at flushing event surge safely
            green = int(self.max_green * 0.85)
            red = max(self.cycle_time - green, 10)
            return SignalPlan(
                green_seconds=green,
                red_seconds=red,
                reason=f"ACTIVE {snapshot.event_risk_level} EVENT: Forcing defensive surge routing.",
            )

        pressure_score = snapshot.vehicle_count + int(snapshot.crowd_density * 40)

        if pressure_score < 40:
            green = self.min_green
            reason = "Low congestion pressure"
        elif pressure_score < 80:
            green = int(self.min_green + (self.max_green - self.min_green) * 0.35)
            reason = "Moderate congestion pressure"
        elif pressure_score < 120:
            green = int(self.min_green + (self.max_green - self.min_green) * 0.65)
            reason = "High congestion pressure"
        else:
            green = self.max_green
            reason = "Severe congestion pressure"

        red = max(self.cycle_time - green, 10)
        return SignalPlan(green_seconds=green, red_seconds=red, reason=reason)
