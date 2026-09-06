import asyncio
import random
import os

class WeatherIngestor:
    """Daemon for polling OpenWeatherAPI to automatically trigger 'Rain Mode'."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    async def poll_precipitation(self):
        import aiohttp
        print("[WEATHER-DAEMON] Initializing Real Atmospheric Sensor tracking via OpenWeatherMap...")
        lat, lon = os.getenv("BENGALURU_LAT", "12.9716"), os.getenv("BENGALURU_LON", "77.5946")
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={self.api_key}&units=metric"
        
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            weather_main = data.get("weather", [{}])[0].get("main", "Clear")
                            rain_data = data.get("rain", {}).get("1h", 0.0)
                            
                            is_raining = "Rain" in weather_main or rain_data > 0.0
                            status = "RAIN MODE ENABLED (CRITICAL)" if is_raining else "CLEAR"
                            
                            print(f"[WEATHER-DAEMON] Sensor Check: {weather_main} ({rain_data}mm) -> SYSTEM STATUS: {status}")
                        else:
                            print(f"[WEATHER-DAEMON] API Error: {response.status}")
            except Exception as e:
                print(f"[WEATHER-DAEMON] Tracking Error: {e}")
            
            await asyncio.sleep(300) # Poll every 5 minutes to stay within free tier limits

if __name__ == "__main__":
    weather = WeatherIngestor(api_key=os.getenv("OPENWEATHER_API_KEY", "mock_key"))
    asyncio.run(weather.poll_precipitation())
