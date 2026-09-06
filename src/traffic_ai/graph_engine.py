import time
from collections import deque

class TransitWave:
    def __init__(self, source: str, destination: str, vehicle_count: int, impact_timestamp: float):
        self.source = source
        self.destination = destination
        self.vehicle_count = vehicle_count
        self.impact_timestamp = impact_timestamp

class CityGraphPhysics:
    """PHASE 2 - Directed Graph Network connecting the Digital Twin."""
    
    def __init__(self):
        # Directed Edges: Source -> [(Destination, Distance_km)]
        self.topography = {
            "silk_board": [("madiwala", 2.1)],
            "madiwala": [("koramangala", 1.8)],
            "koramangala": [] # Terminal Node
        }
        # The Buffer holding cars physically travelling between nodes
        self.transit_waves = deque()

    def dispatch_wave(self, source: str, throughput: int, current_speed_kmh: float):
        """Triggered when an AI Agent turns its signal Green."""
        if source not in self.topography or throughput <= 0:
            return
            
        for dest, distance_km in self.topography[source]:
            # Physics: Calculate Real-World Travel Time
            speed = max(current_speed_kmh, 5.0)
            travel_time_seconds = (distance_km / speed) * 3600
            
            # PMO Simulation Scale (e.g., 10x speed so we don't wait 15 minutes during a demo)
            simulated_delay = travel_time_seconds / 10.0 
            impact_time = time.time() + simulated_delay
            
            self.transit_waves.append(TransitWave(source, dest, throughput, impact_time))
            print(f"[GRAPH-PHYSICS] 🌊 Wave Dispatched: {throughput} cars left {source} -> Arriving at {dest} in {round(simulated_delay, 1)}s")

    def process_arrivals(self) -> dict:
        """Polls the physical distance buffer continuously."""
        current_time = time.time()
        arrivals = {"silk_board": 0, "madiwala": 0, "koramangala": 0}
        
        pending_waves = []
        while self.transit_waves:
            wave = self.transit_waves.popleft()
            if current_time >= wave.impact_timestamp:
                # The vehicles physically arrived!
                arrivals[wave.destination] += wave.vehicle_count
                print(f"[GRAPH-PHYSICS] 💥 Shockwave Impact: {wave.vehicle_count} cars slammed into {wave.destination}!")
            else:
                pending_waves.append(wave) # Still driving
                
        self.transit_waves.extend(pending_waves)
        return arrivals

    def peek_waves(self):
        """Non-destructive array read extracting spatial distance for PMO UI."""
        return [(w.source, w.destination, w.vehicle_count, w.impact_timestamp) for w in list(self.transit_waves)]
