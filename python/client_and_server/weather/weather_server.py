import math
from typing import Any

import httpx
from loguru import logger
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Weather")

logger.add("weather_server.log", rotation="1 day", mode="a", encoding="utf-8")

# Constants
GEOCODE_API_BASE = "https://geocode.xyz"
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

# ========
# Helper functions
# ========


# helper function to get the weather data from the NWS API
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to  the NWS API with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None


# helper function to format alert data into a string
def format_alert(feature: dict) -> str:
    """Format an alert feature into a readablestring."""
    props = feature["properties"]
    return f"""
    Event: {props.get("event", "Unknown")}
    Area: {props.get("areaDesc", "Unknown")}
    Severity: {props.get("severity", "Unknown")}
    Description: {props.get("description", "No description available")}
    Instructions: {props.get("instruction", "No specific instructions provided")}
    """


def round_up_coordinate(value, decimal_places=4):
    """Round up coordinate to specified decimal places."""
    multiplier = 10**decimal_places
    return math.ceil(value * multiplier) / multiplier


# ========
# MCP Tools
# ========
@mcp.tool()
async def get_alerts(state: str) -> str:
    """
    Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)

    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    logger.info(f"Fetching weather alerts for {state}...")
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return f"No active alerts found for {state}."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_lat_long(place: str) -> str:
    """
    Get latitude and longitude for a given city in US.

    Args:
        place: City name in US. For example san diego, santa cruz, seattle etc.,

    Returns:
        str: Latitude and longitude for the given city

    """
    logger.info(f"Starting geocoding request for place: {place}")
    place_encoded = place.replace(" ", "%20").strip()
    params = {"locate": place_encoded, "geoit": "JSON", "region": "US"}
    headers = {"User-Agent": USER_AGENT}

    try:
        # logger.info(f"Making geocoding request to {GEOCODE_API_BASE} with params: {params}")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                GEOCODE_API_BASE, params=params, headers=headers,
            )
            logger.info(f"Geocoding response status: {response.status_code}")
            response.raise_for_status()

            lat_long_dict = response.json()
            logger.info(f"Geocoding response data: {lat_long_dict}")

            if lat_long_dict and "longt" in lat_long_dict and "latt" in lat_long_dict:
                longt = float(lat_long_dict["longt"])
                latt = float(lat_long_dict["latt"])
                rounded_lat = round_up_coordinate(latt)
                rounded_lon = round_up_coordinate(longt)
                logger.info(
                    f"Successfully geocoded {place}: Latitude={rounded_lat}, Longitude={rounded_lon}",
                )
                return f"Latitude={rounded_lat}, Longitude={rounded_lon}"
            error_msg = f"No location data found for {place}"
            logger.error(error_msg)
            return error_msg

    except httpx.TimeoutException:
        error_msg = f"Geocoding request timed out for {place}"
        logger.error(error_msg)
        return error_msg
    except httpx.HTTPStatusError as e:
        error_msg = (
            f"HTTP error {e.response.status_code} for {place}: {e.response.text}"
        )
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Geocoding error for {place}: {e!s}"
        logger.error(error_msg)
        return error_msg


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """
    Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location

    Returns:
        str: Weather forecast for the given location

    """
    url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    logger.info(f"Fetching weather forecast for {latitude}, {longitude}...")
    data = await make_nws_request(url)

    if not data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = data["properties"]["forecast"]
    logger.info(f"Fetching forecast data from {forecast_url}...")
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast data."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period["name"]}:
Temperature: {period["temperature"]}°{period["temperatureUnit"]}
Wind: {period["windSpeed"]} {period["windDirection"]}
Forecast: {period["detailedForecast"]}
"""
    forecasts.append(forecast)
    return "\n---\n".join(forecasts)


def main():
    # Initialize and run the server
    logger.info("Starting Weather server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
