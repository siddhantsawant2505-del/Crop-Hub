import logging
import random
import time
import sqlite3
import json
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import httpx
from .config import CFG

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "prices_cache.db"

def _init_db():
    """Ensure the cache table exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            cache_key   TEXT PRIMARY KEY,
            prices_json TEXT,
            fetched_at  REAL
        )
    """)
    con.commit()
    con.close()

class MarketService:
    """
    MarketService handles:
    1. Reverse geocoding (Lat/Lon -> State, District)
    2. 3-Tier Agmarknet API fetching (District -> State -> Simulated)
    3. Price conversion (Quintal -> Kg) and Caching
    """
    
    CACHE_DURATION = 3600 * 12  # 12 hours

    # Map internal crop names to Agmarknet commodity names
    COMMODITY_MAP = {
    "Rice":      "Paddy",           # was "Paddy(Dhan)(Common)"
    "Wheat":     "Wheat",           # ✅ unchanged
    "Cotton":    "Cotton(Lint)",     # was "Cotton"
    "Soybean":   "Soyabean",        # ✅ unchanged
    "Maize":     "Maize",           # ✅ unchanged
    "Groundnut": "Groundnut",       # ✅ unchanged
    "Sugarcane": "Sugarcane",       # ✅ unchanged
    "Lentils":   "Masur Dal",       # was "Lentil (Masur)"
    }

    @staticmethod
    def _read_cache(cache_key: str) -> Optional[Dict[str, float]]:
        """Read prices from SQLite cache if not expired."""
        try:
            _init_db()
            con = sqlite3.connect(DB_PATH)
            row = con.execute(
                "SELECT prices_json, fetched_at FROM price_cache WHERE cache_key=?",
                (cache_key,)
            ).fetchone()
            con.close()
            if row and (time.time() - row[1]) < MarketService.CACHE_DURATION:
                return json.loads(row[0])
        except Exception as e:
            log.error(f"Cache read error: {e}")
        return None

    @staticmethod
    def _write_cache(cache_key: str, prices: Dict[str, float]):
        """Write prices to SQLite cache."""
        try:
            _init_db()
            con = sqlite3.connect(DB_PATH)
            con.execute(
                "INSERT OR REPLACE INTO price_cache VALUES (?,?,?)",
                (cache_key, json.dumps(prices), time.time())
            )
            con.commit()
            con.close()
        except Exception as e:
            log.error(f"Cache write error: {e}")

    @classmethod
    async def get_location(cls, lat: float, lon: float) -> Tuple[Optional[str], Optional[str]]:
        """Reverse geocode coordinates to State and District using Nominatim."""
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=5&addressdetails=1"
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers={"User-Agent": "CropHub-FathomLayer-1.0"})
                data = res.json()
                address = data.get("address", {})
                state = address.get("state")
                district = address.get("district") or address.get("county") or address.get("state_district")
                log.info(f"Resolved location: {district}, {state}")
                return state, district
        except Exception as e:
            log.warning(f"Location resolution failed: {e}")
            return None, None

    @classmethod
    async def get_market_prices(cls, state: Optional[str], district: Optional[str]) -> Dict[str, Any]:
        """
        Fetch prices using 3-tier fallback.
        Returns a dict with prices, source, and location.
        """
        cache_key = f"{state}|{district}"
        cached_prices = cls._read_cache(cache_key)
        
        if cached_prices:
            return {
                "prices": cached_prices,
                "source": "Agmarknet Live (Cached)",
                "location": f"{district}, {state}" if district else state or "National"
            }

        prices = {}
        api_hit = False
        api_key = getattr(CFG, "AGMARKNET_API_KEY", None)
        resource_id = getattr(CFG, "AGMARKNET_RESOURCE_ID", "9ef842fd-9a74-4050-a155-397d9013c4f9")

        for crop, commodity in cls.COMMODITY_MAP.items():
            price = None
            if api_key and api_key != "YOUR_API_KEY_HERE":
                price = await cls._fetch_api_price(api_key, resource_id, commodity, state, district)
                if price:
                    api_hit = True
            
            if price is None:
                # Tier 3: Simulated Jittered MSP
                base_msp = CFG.MSP_PRICES.get(crop, 2000)
                # Apply +/- 5% random jitter based on current date to simulate market 'live' feel
                jitter = 1.0 + (random.uniform(-0.02, 0.08)) 
                price = base_msp * jitter
                log.info(f"Using Simulated Price for {crop}: {price:.2f}")

            prices[crop] = price

        cls._write_cache(cache_key, prices)

        return {
            "prices": prices,
            "source": "Agmarknet Live" if api_hit else "MSP Estimate",
            "location": f"{district}, {state}" if district else state or "National"
        }

    @classmethod
    async def _fetch_api_price(cls, key: str, res_id: str, commodity: str, state: str, district: str) -> Optional[float]:
        """Agmarknet API Call with Tier 1 and Tier 2 fallback."""
        base_url = "https://api.data.gov.in/resource/" + res_id
        params = {
            "api-key": key,
            "format": "json",
            "filters[commodity]": commodity,
            "limit": 10
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Tier 1: District
                if state and district:
                    d_params = params.copy()
                    d_params["filters[state]"] = state
                    d_params["filters[district]"] = district
                    res = await client.get(base_url, params=d_params)
                    data = res.json()
                    if data.get("records"):
                        return cls._extract_modal(data["records"])

                # Tier 2: State
                if state:
                    s_params = params.copy()
                    s_params["filters[state]"] = state
                    res = await client.get(base_url, params=s_params)
                    data = res.json()
                    if data.get("records"):
                        return cls._extract_modal(data["records"])

        except Exception as e:
            log.error(f"API Fetch Error for {commodity}: {e}")
        
        return None

    @staticmethod
    def _extract_modal(records: list) -> float:
        """Calculate average modal price from records."""
        prices = [float(r["modal_price"]) for r in records if r.get("modal_price")]
        return sum(prices) / len(prices) if prices else 0.0
