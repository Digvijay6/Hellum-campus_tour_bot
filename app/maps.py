import requests
import math
from typing import Tuple, List, Union
import polyline  # Make sure to install: pip install polyline
import os
from dotenv import load_dotenv

load_dotenv()

def geocode_address(api_key: str, address: str) -> Union[Tuple[float, float], None]:
    """Convert an address to coordinates using Google Geocoding API."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] != "OK":
            print(f"Geocoding error: {data['status']}")
            return None

        location = data["results"][0]["geometry"]["location"]
        return (location["lat"], location["lng"])

    except Exception as e:
        print(f"Failed to geocode address: {e}")
        return None

def decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    """Decode a polyline string into list of coordinates."""
    return polyline.decode(encoded)

def get_waypoints(api_key: str, start_location: Tuple[float, float], end_location: Union[str, Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Get fine-grained waypoints using Google Directions API with polyline decoding."""
    
    # Geocode if end_location is an address
    if isinstance(end_location, str):
        geocoded_end = geocode_address(api_key, end_location)
        if not geocoded_end:
            print("Failed to geocode destination address")
            return []
        end_location = geocoded_end
        print(f"Geocoded destination to coordinates: {geocoded_end}")

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{start_location[0]},{start_location[1]}",
        "destination": f"{end_location[0]},{end_location[1]}",
        "mode": "walking",
        "key": api_key
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] != "OK":
            print(f"Error: {data['status']}")
            return []

        print("--------------------------------RESULT---------------------------------")
        print(data)
        print("-----------------------------------------------------------------------")
        # Decode polyline from each step for detailed path
        waypoints = []
        for leg in data["routes"][0]["legs"]:
            for step in leg["steps"]:
                step_polyline = step["polyline"]["points"]
                points = decode_polyline(step_polyline)
                waypoints.extend(points)

        # Remove duplicates while preserving order
        filtered_waypoints = []
        seen = set()
        for pt in waypoints:
            if pt not in seen:
                filtered_waypoints.append(pt)
                seen.add(pt)

        return filtered_waypoints

    except Exception as e:
        print(f"Failed to get route: {e}")
        return []

def main():
    # Replace with your actual Google Maps API key
    API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

    # Get start location
    start_lat = float(input("Enter starting latitude: "))
    start_lng = float(input("Enter starting longitude: "))
    start_location = (start_lat, start_lng)

    # Get destination
    destination = input("Enter destination (address or coordinates): ")

    # Convert coordinates string to tuple if needed
    if "," in destination and all(part.replace(".", "", 1).replace("-", "", 1).isdigit()
                                  for part in destination.split(",")):
        parts = destination.split(",")
        destination = (float(parts[0].strip()), float(parts[1].strip()))

    # Get detailed waypoints
    waypoints = get_waypoints(API_KEY, start_location, destination)

    if waypoints:
        print(f"\nSuccessfully retrieved {len(waypoints)} fine-grained waypoints:")
        for i, point in enumerate(waypoints):
            print(f"Waypoint {i+1}: {point}")
    else:
        print("Failed to get waypoints")

if __name__ == "__main__":
    main()
