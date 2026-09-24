"""
distance_service.py — Haversine-based distance and drive-time estimation.

No external API required. Uses straight-line distance × road-correction factor.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from .config import CFG


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometres between two lat/lon points.
    Uses the Haversine formula.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def estimated_road_km(straight_km: float) -> float:
    """Apply road-correction factor to straight-line distance."""
    return straight_km * CFG.HAVERSINE_ROAD_FACTOR


def estimated_drive_minutes(road_km: float, avg_speed_kmh: float = 40.0) -> float:
    """
    Estimate driving time in minutes.
    Default avg speed 40 km/h accounts for Indian rural/semi-urban roads.
    """
    return (road_km / avg_speed_kmh) * 60.0


def compute_distances(
    farm_lat: float,
    farm_lon: float,
    mandi_coords: List[Tuple[float, float]],
) -> List[dict]:
    """
    For a list of (lat, lon) mandi coordinates, return a list of dicts:
      {straight_km, road_km, drive_minutes}
    """
    results = []
    for lat, lon in mandi_coords:
        straight = haversine_km(farm_lat, farm_lon, lat, lon)
        road = estimated_road_km(straight)
        mins = estimated_drive_minutes(road)
        results.append({
            "straight_km": round(straight, 2),
            "road_km": round(road, 2),
            "drive_minutes": round(mins, 1),
        })
    return results
