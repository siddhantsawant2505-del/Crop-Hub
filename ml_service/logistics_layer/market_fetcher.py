"""
market_fetcher.py — Fetches live modal prices from Agmarknet (data.gov.in).

3-Tier fallback:
  Tier 1 → Agmarknet API (district-level filter)
  Tier 2 → Agmarknet API (state-level filter)
  Tier 3 → Simulated jitter around MSP (±8%)
"""

from __future__ import annotations

import logging
import random
import time
from typing import Dict, Optional

import httpx

from .config import CFG

log = logging.getLogger(__name__)

# In-memory price cache: key = "market_name|state|commodity", value = price
_price_cache: Dict[str, float] = {}
_cache_timestamp: float = 0.0


def _is_cache_fresh() -> bool:
    return (time.time() - _cache_timestamp) < CFG.PRICE_CACHE_SECONDS


async def get_modal_price(
    crop: str,
    state: Optional[str] = None,
    district: Optional[str] = None,
    market_name: Optional[str] = None,
) -> float:
    """
    Return the modal price (INR/quintal) for a crop at a given location.
    Falls back through 3 tiers as described in module docstring.
    """
    commodity = CFG.COMMODITY_MAP.get(crop)
    if not commodity:
        log.warning("No commodity mapping for crop '%s' — using MSP", crop)
        return _simulated_price(crop)

    cache_key = f"{market_name or ''}|{state or ''}|{district or ''}|{commodity}"
    if cache_key in _price_cache and _is_cache_fresh():
        return _price_cache[cache_key]

    api_key = CFG.AGMARKNET_API_KEY
    res_id = CFG.AGMARKNET_RESOURCE_ID
    price: Optional[float] = None

    if api_key and api_key not in ("YOUR_API_KEY_HERE", ""):
        price = await _fetch_agmarknet(api_key, res_id, commodity, state, district, market_name)

    if price is None or price <= 0:
        price = _simulated_price(crop)
        log.info("Using simulated price for %s @ %s: ₹%.0f/qtl", crop, market_name, price)
    else:
        log.info("Live Agmarknet price for %s @ %s: ₹%.0f/qtl", crop, market_name, price)

    _price_cache[cache_key] = price
    return price


async def _fetch_agmarknet(
    api_key: str,
    resource_id: str,
    commodity: str,
    state: Optional[str],
    district: Optional[str],
    market_name: Optional[str],
) -> Optional[float]:
    """Try district → state level Agmarknet queries."""
    base_url = f"https://api.data.gov.in/resource/{resource_id}"
    base_params = {
        "api-key": api_key,
        "format": "json",
        "filters[commodity]": commodity,
        "limit": 20,
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        # Tier 1: market + district + state
        if state and district and market_name:
            p = {**base_params,
                 "filters[state]": state,
                 "filters[district]": district,
                 "filters[market]": market_name}
            price = await _try_fetch(client, base_url, p)
            if price:
                return price

        # Tier 2: district + state (no market filter)
        if state and district:
            p = {**base_params,
                 "filters[state]": state,
                 "filters[district]": district}
            price = await _try_fetch(client, base_url, p)
            if price:
                return price

        # Tier 3: state only
        if state:
            p = {**base_params, "filters[state]": state}
            price = await _try_fetch(client, base_url, p)
            if price:
                return price

    return None


async def _try_fetch(client: httpx.AsyncClient, url: str, params: dict) -> Optional[float]:
    try:
        resp = await client.get(url, params=params)
        data = resp.json()
        records = data.get("records", [])
        if records:
            return _extract_modal(records)
    except Exception as exc:
        log.debug("Agmarknet fetch error: %s", exc)
    return None


def _extract_modal(records: list) -> Optional[float]:
    """Average the modal_price field across records."""
    prices = []
    for r in records:
        try:
            prices.append(float(r["modal_price"]))
        except (KeyError, ValueError, TypeError):
            continue
    return round(sum(prices) / len(prices), 2) if prices else None


def _simulated_price(crop: str) -> float:
    """MSP ± random jitter for demo / fallback purposes."""
    msp = CFG.MSP_PRICES.get(crop, 2000.0)
    jitter = 1.0 + random.uniform(-0.05, 0.10)
    return round(msp * jitter, 2)
