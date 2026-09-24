"""
config.py — Logistics Layer single source of truth.
All constants, cost rates, and env vars live here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()

_PACKAGE_ROOT = Path(__file__).parent


@dataclass
class LogisticsConfig:
    # ── File Paths ────────────────────────────────────────────────────────────
    MANDIS_JSON_PATH: Path = _PACKAGE_ROOT / "data" / "mandis_india.json"

    # ── API Keys ──────────────────────────────────────────────────────────────
    AGMARKNET_API_KEY: str = os.getenv("AGMARKNET_API_KEY", "YOUR_API_KEY_HERE")
    AGMARKNET_RESOURCE_ID: str = os.getenv(
        "AGMARKNET_RESOURCE_ID", "9ef842fd-9a74-4050-a155-397d9013c4f9"
    )
    LOGISTICS_ADMIN_TOKEN: str = os.getenv("LOGISTICS_ADMIN_TOKEN", "logistics-admin-2024")

    # ── Search Defaults ───────────────────────────────────────────────────────
    DEFAULT_SEARCH_RADIUS_KM: float = float(os.getenv("DEFAULT_SEARCH_RADIUS_KM", "150"))
    MAX_SEARCH_RADIUS_KM: float = 300.0
    MIN_MANDIS_TO_RETURN: int = 3       # always return at least N mandis (relax radius if needed)
    MAX_MANDIS_TO_RETURN: int = 15

    # ── Road-correction factor (Haversine → estimated road distance) ──────────
    HAVERSINE_ROAD_FACTOR: float = 1.30  # straight-line × 1.30 ≈ road distance

    # ── Transport Cost Model ──────────────────────────────────────────────────
    # INR per km per quintal for a tractor/truck
    TRANSPORT_RATE_PER_KM_PER_QTL: float = float(
        os.getenv("TRANSPORT_RATE_PER_KM_PER_QTL", "8.5")
    )
    # Minimum transport cost even for nearby mandis (loading etc.)
    MIN_TRANSPORT_COST_PER_QTL: float = 50.0

    # ── Mandi Fee Structure (applied per quintal) ─────────────────────────────
    # Market committee rent / cess  — % of sale value
    MANDI_RENT_PCT: float = 0.015          # 1.5%
    # Commission to aadatiya (commission agent) — % of sale value
    COMMISSION_PCT: float = 0.02           # 2.0%
    # Flat loading & unloading (per quintal)
    LOADING_UNLOADING_PER_QTL: float = 20.0
    # Weighing / token / misc flat (per quintal)
    MISC_FEES_PER_QTL: float = 10.0

    # ── Agmarknet commodity name map (internal crop → API commodity name) ────
    COMMODITY_MAP: Dict[str, str] = field(default_factory=lambda: {
        "Rice":      "Paddy(Dhan)(Common)",
        "Wheat":     "Wheat",
        "Cotton":    "Cotton",
        "Soybean":   "Soyabean",
        "Maize":     "Maize",
        "Groundnut": "Groundnut",
        "Sugarcane": "Sugarcane",
        "Lentils":   "Lentil (Masur)",
    })

    # ── MSP fallback prices (INR / quintal) ──────────────────────────────────
    MSP_PRICES: Dict[str, float] = field(default_factory=lambda: {
        "Rice":      2183,
        "Wheat":     2275,
        "Cotton":    6620,
        "Soybean":   4600,
        "Maize":     2090,
        "Groundnut": 6377,
        "Sugarcane":  315,
        "Lentils":   6425,
    })

    # ── Supported crops list ──────────────────────────────────────────────────
    SUPPORTED_CROPS: List[str] = field(default_factory=lambda: [
        "Rice", "Wheat", "Cotton", "Soybean", "Maize",
        "Groundnut", "Sugarcane", "Lentils",
    ])

    # ── Price cache duration ──────────────────────────────────────────────────
    PRICE_CACHE_SECONDS: int = 43200   # 12 hours


# Module-level singleton
CFG = LogisticsConfig()
