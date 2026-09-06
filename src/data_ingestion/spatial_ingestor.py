import asyncio
import random
import os

class TomTomSpatialIngestor:
    """Daemon for polling TomTom API to extract real-world macro congestion scores."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    async def pull_macro_telemetry(self):
        import aiohttp
        print("[TOMTOM-DAEMON] Initializing REAL GPS speed aggregations via TomTom...")
        
        # Grid points for key junctions
        locations = {
            "Silk Board": "12.9177,77.6238",
            "Hebbal": "13.0358,77.5970",
            "MG Road": "12.9756,77.6065"
        }
        
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    for name, coords in locations.items():
                        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={coords}&key={self.api_key}"
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                flow = data.get("flowSegmentData", {})
                                current_speed = flow.get("currentSpeed", 20)
                                free_flow = flow.get("freeFlowSpeed", 40)
                                
                                # Congestion ratio
                                congestion = max(0, 10 - int((current_speed / free_flow) * 10))
                                
                                print(f"[TOMTOM-DAEMON] {name}: {current_speed}km/h (Intensity: {congestion}/10)")
                                
                                # Send to our main API to update the map live!
                                try:
                                    await session.post("http://localhost:8000/traffic", json={
                                        "location": name,
                                        "congestion_score": congestion,
                                        "speed": current_speed
                                    })
                                except: pass
                            else:
                                print(f"[TOMTOM-DAEMON] API Error {response.status} for {name}")
            except Exception as e:
                print(f"[TOMTOM-DAEMON] Sync Error: {e}")
            
            await asyncio.sleep(60) # Respect rate limits

if __name__ == "__main__":
    tomtom = TomTomSpatialIngestor(api_key=os.getenv("TOMTOM_API_KEY", "mock_key_001"))
    asyncio.run(tomtom.pull_macro_telemetry())
