"""
mandi_discovery.py — Loads and filters the curated APMC mandi dataset.

Filters mandis within a given radius of the farmer's GPS coordinates
using the Haversine formula.
"""

from __future__ import annotations

import json
import logging
from typing import List

from .config import CFG
from .distance_service import haversine_km
from .schemas import MandiContact, MandiInfo

log = logging.getLogger(__name__)

# Module-level cache — load JSON once
_mandi_db: List[MandiInfo] | None = None


def _load_mandis() -> List[MandiInfo]:
    global _mandi_db
    if _mandi_db is not None:
        return _mandi_db

    if not CFG.MANDIS_JSON_PATH.exists():
        log.error("mandis_india.json not found at %s", CFG.MANDIS_JSON_PATH)
        return []

    raw = json.loads(CFG.MANDIS_JSON_PATH.read_text(encoding="utf-8"))
    mandis = []
    for entry in raw:
        try:
            contact_data = entry.get("contact", {})
            contact = MandiContact(
                phone=contact_data.get("phone"),
                alternate_phone=contact_data.get("alternate_phone"),
                secretary_name=contact_data.get("secretary_name"),
                address=contact_data.get("address", ""),
                timings=contact_data.get("timings", "6:00 AM – 2:00 PM (Mon–Sat)"),
                website=contact_data.get("website"),
                helpline=contact_data.get("helpline"),
            )
            mandis.append(MandiInfo(
                id=entry["id"],
                name=entry["name"],
                lat=float(entry["lat"]),
                lon=float(entry["lon"]),
                state=entry["state"],
                district=entry["district"],
                market_code=entry.get("market_code"),
                type=entry.get("type", "APMC"),
                contact=contact,
            ))
        except Exception as exc:
            log.warning("Skipping malformed mandi entry '%s': %s", entry.get("id"), exc)

    log.info("Loaded %d mandis from dataset", len(mandis))
    _mandi_db = mandis
    return _mandi_db


def discover_nearby(
    farm_lat: float,
    farm_lon: float,
    radius_km: float = 150.0,
) -> List[MandiInfo]:
    """
    Return all mandis within `radius_km` of the farm, sorted by distance ascending.
    Automatically relaxes the radius if fewer than MIN_MANDIS_TO_RETURN are found.
    """
    all_mandis = _load_mandis()

    def within_radius(m: MandiInfo, r: float) -> bool:
        return haversine_km(farm_lat, farm_lon, m.lat, m.lon) <= r

    nearby = [m for m in all_mandis if within_radius(m, radius_km)]

    # Relax radius progressively until we have enough mandis
    extended_radius = radius_km
    while len(nearby) < CFG.MIN_MANDIS_TO_RETURN and extended_radius < CFG.MAX_SEARCH_RADIUS_KM:
        extended_radius = min(extended_radius + 50, CFG.MAX_SEARCH_RADIUS_KM)
        nearby = [m for m in all_mandis if within_radius(m, extended_radius)]
        if extended_radius >= CFG.MAX_SEARCH_RADIUS_KM:
            break

    if extended_radius > radius_km:
        log.info(
            "Radius relaxed from %.0f km → %.0f km to find %d mandis",
            radius_km, extended_radius, len(nearby),
        )

    # Sort by distance ascending
    nearby.sort(key=lambda m: haversine_km(farm_lat, farm_lon, m.lat, m.lon))

    return nearby[: CFG.MAX_MANDIS_TO_RETURN]
