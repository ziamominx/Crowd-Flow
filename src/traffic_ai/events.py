from dataclasses import dataclass
from typing import List

@dataclass
class CityEvent:
    """Represents a live scheduled event in the city."""
    name: str
    primary_intersection_id: str
    risk_level: str  # "NORMAL", "HIGH", "CRITICAL"

class CityEventTracker:
    """Tracks live events that dramatically alter predictive traffic behaviors."""
    
    def __init__(self):
        # In production this would query an external API (like a City Hall database or Ticketmaster)
        self.active_events = [
            CityEvent(name="IPL Cricket Match", primary_intersection_id="mg_road", risk_level="CRITICAL"),
            CityEvent(name="Political Protest", primary_intersection_id="majestic", risk_level="CRITICAL"),
            CityEvent(name="Tech Expo 2026", primary_intersection_id="bellandur", risk_level="HIGH")
        ]

    def get_risk_for_intersection(self, intersection_id: str) -> str:
        """Returns the highest risk level caused by events near this intersection."""
        # Right now using a simple 1:1 ID match, in future this would use geospatial radius math
        for event in self.active_events:
            if event.primary_intersection_id == intersection_id:
                return event.risk_level
        return "NORMAL"
