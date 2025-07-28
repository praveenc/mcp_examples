import asyncio
from typing import Any

import httpx
from loguru import logger
from rich import print

# Constants
USER_AGENT = "weather-app/1.0"
GEOCODE_URL = "https://geocode.xyz"

async def get_lat_long(place: str) -> dict[str, Any] | None:
    """Make a request to the geocode.xyz API with proper error handling."""
    place = place.replace(" ", "%20").strip()
    params = {"locate": place, "geoit": "JSON", "region": "US"}
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(GEOCODE_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            lat_long_dict = response.json()
            print(f"Response: {lat_long_dict}")

            if lat_long_dict and "longt" in lat_long_dict and "latt" in lat_long_dict:
                longt = lat_long_dict["longt"]
                latt = lat_long_dict["latt"]
                print(f"Place: {place.replace("%20", " ")}, Longitude: {longt}, Latitude: {latt}")
                return {"latitude": latt, "longitude": longt}

            print(f"No location data found for {place}")
            return None

        except Exception as e:
            logger.error(f"Request error: {e}")
            return None

if __name__ == "__main__":
    asyncio.run(get_lat_long("santa clara"))
