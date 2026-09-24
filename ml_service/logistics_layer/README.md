# Logistics Layer — Market Profit Optimiser

> **Part of the CropHub Unified ML Service** · Mounted at `/logistics` · Internally ran on port `8002`

The Logistics Layer is a real-time market arbitrage engine that helps farmers decide **where to sell** their crops for maximum net profit. Given a farmer's GPS coordinates and their crop allocation plan (produced by the Fathom Layer), it discovers nearby APMC mandis, fetches live Agmarknet commodity prices, and computes the true net profit per crop × mandi combination after accounting for all transport, mandi, and operational costs.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Module Structure](#module-structure)
- [API Endpoints](#api-endpoints)
- [Data Models](#data-models)
- [Configuration Reference](#configuration-reference)
- [Price Fetching & Fallback Strategy](#price-fetching--fallback-strategy)
- [Profit Calculation Formula](#profit-calculation-formula)
- [Mandi Dataset](#mandi-dataset)
- [Environment Variables](#environment-variables)
- [Running Standalone](#running-standalone)
- [Integration with the Unified ML Service](#integration-with-the-unified-ml-service)

---

## How It Works

The optimization pipeline runs in three stages:

```
[Farmer GPS + Fathom Allocations]
          │
          ▼
  ┌───────────────────┐
  │  Mandi Discovery  │  ← Haversine filter on mandis_india.json
  │  (radius-relaxed) │    Returns up to 15 closest APMCs
  └────────┬──────────┘
           │
           ▼  (concurrent per crop × mandi)
  ┌────────────────────────┐
  │   Market Price Fetch   │  ← Agmarknet API (data.gov.in)
  │   (3-tier fallback)    │    Tier 1: market+district+state
  │                        │    Tier 2: district+state
  │                        │    Tier 3: MSP ± jitter (demo)
  └────────┬───────────────┘
           │
           ▼
  ┌────────────────────────┐
  │   Profit Optimizer     │  ← True Net Profit = Gross Revenue
  │   (per crop × mandi)   │    − Transport − Rent − Commission
  │                        │    − Loading − Misc − Cultivation
  └────────┬───────────────┘
           │
           ▼
  [Ranked Results: Best Mandi per Crop + Overall Best]
```

---

## Module Structure

```text
logistics_layer/
├── __init__.py             # Package marker
├── app.py                  # FastAPI application, CORS middleware, all route handlers
├── config.py               # LogisticsConfig dataclass — all constants and env vars
├── schemas.py              # Pydantic v2 request/response models
├── optimizer.py            # Core async profit optimization pipeline
├── market_fetcher.py       # Agmarknet API client with 3-tier fallback + in-memory cache
├── mandi_discovery.py      # Loads mandis_india.json, filters by Haversine radius
├── distance_service.py     # Haversine formula, road-correction factor, drive-time estimate
└── data/
    └── mandis_india.json   # Curated APMC mandi dataset (GPS, contact, type)
```

### File Responsibilities

| File | Responsibility |
|---|---|
| `app.py` | FastAPI app definition, CORS, route handlers, 422 error formatting |
| `config.py` | `LogisticsConfig` singleton (`CFG`) — single source of truth for all constants |
| `schemas.py` | All Pydantic models: `OptimizeRequest`, `OptimizeResponse`, `MandiResult`, `FeeBreakdown`, etc. |
| `optimizer.py` | Async pipeline: discovers mandis → scores each crop×mandi → ranks by net profit → annotates best |
| `market_fetcher.py` | Async Agmarknet REST client, 12-hour in-memory price cache, MSP-jitter fallback |
| `mandi_discovery.py` | Module-level mandi DB cache, Haversine filtering, progressive radius relaxation |
| `distance_service.py` | Pure maths: Haversine formula, road-correction (×1.30), drive-time at 40 km/h |
| `data/mandis_india.json` | Static dataset of Indian APMC mandis with GPS coords, state, district, contact info |

---

## API Endpoints

All routes are prefixed with `/logistics` when served through the unified ML service.

### `GET /logistics/health`
Health check. Returns service status and whether the Agmarknet API key is configured.

**Response:**
```json
{
  "status": "ok",
  "service": "logistics_layer",
  "port": 8002,
  "agmarknet_key_configured": true
}
```

---

### `POST /logistics/optimize`
**Core endpoint.** Full optimization pipeline — discovers mandis, fetches live prices, and returns the best selling destination per crop ranked by true net profit.

**Request Body:**
```json
{
  "lat": 20.5937,
  "lon": 78.9629,
  "allocations": [
    {
      "crop": "Wheat",
      "icon": "🌾",
      "color": "#f5c842",
      "acres": 5.0,
      "cost": 45000,
      "revenue": 80000,
      "profit": 35000,
      "margin_pct": 43.75,
      "pct_of_land": 50.0
    }
  ],
  "quantity_qtl": 10.0,
  "radius_km": 150.0
}
```

**Response:** Full `OptimizeResponse` — one `CropOptimizationResult` per crop, each containing a ranked list of `MandiResult` objects with complete fee breakdowns, plus `overall_best_crop` and `overall_best_mandi`.

---

### `POST /logistics/mandis/nearby`
Returns all mandis within the given radius, sorted by distance. Useful for rendering map pins without running the full optimizer.

**Request Body:**
```json
{
  "lat": 20.5937,
  "lon": 78.9629,
  "radius_km": 150.0
}
```

**Response:**
```json
{
  "mandis": [ { "id": "...", "name": "...", "lat": ..., "lon": ..., ... } ],
  "total": 12,
  "radius_km": 150.0
}
```

---

### `GET /logistics/crops`
Lists all supported crops, their Agmarknet commodity name mappings, and current MSP prices.

**Response:**
```json
{
  "crops": [
    { "name": "Wheat", "commodity": "Wheat", "msp_price_per_qtl": 2275 },
    { "name": "Rice",  "commodity": "Paddy(Dhan)(Common)", "msp_price_per_qtl": 2183 }
  ]
}
```

---

### `GET /logistics/config/fees`
Returns the current fee structure used in all profit calculations. Useful for transparency/debugging.

**Response:**
```json
{
  "transport_rate_per_km_per_qtl": 8.5,
  "min_transport_cost_per_qtl": 50.0,
  "mandi_rent_pct": 0.015,
  "commission_pct": 0.02,
  "loading_unloading_per_qtl": 20.0,
  "misc_fees_per_qtl": 10.0,
  "haversine_road_factor": 1.3
}
```

---

### Swagger UI
Interactive API documentation is auto-generated by FastAPI:
- **Standalone:** `http://localhost:8002/docs`
- **Unified service:** `http://localhost:8000/logistics/docs`

---

## Data Models

### `OptimizeRequest`
| Field | Type | Default | Description |
|---|---|---|---|
| `lat` | `float` | required | Farm latitude (−90 to 90) |
| `lon` | `float` | required | Farm longitude (−180 to 180) |
| `allocations` | `List[CropAllocationIn]` | required | Fathom Layer crop allocations |
| `quantity_qtl` | `float` | `10.0` | Quintals to sell per crop |
| `radius_km` | `float` | `150.0` | Search radius (1–300 km) |
| `cultivation_cost_override` | `float` | `None` | Optional per-qtl cost override |

### `FeeBreakdown` (per quintal)
| Field | Description |
|---|---|
| `modal_price_per_qtl` | Live Agmarknet price |
| `transport_cost_per_qtl` | Distance-based transport cost |
| `mandi_rent_per_qtl` | Market committee cess (1.5% of sale value) |
| `commission_per_qtl` | Aadatiya commission (2.0% of sale value) |
| `loading_unloading_per_qtl` | Flat ₹20 per quintal |
| `misc_fees_per_qtl` | Weighing/token/misc flat ₹10 per quintal |
| `total_deductions_per_qtl` | Sum of all above |
| `net_price_per_qtl` | What the farmer actually receives per quintal |

### `MandiResult`
Each result includes: mandi info, straight-line & road distance, estimated drive time, full fee breakdown, gross/net revenue, true net profit, profit per quintal, rank, and a `why_best` explanation string for the top-ranked mandi.

---

## Configuration Reference

All configuration lives in `config.py` as the `LogisticsConfig` dataclass. Environment variables override defaults at startup.

| Constant | Default | Description |
|---|---|---|
| `DEFAULT_SEARCH_RADIUS_KM` | `150` | Default search radius |
| `MAX_SEARCH_RADIUS_KM` | `300` | Hard cap on radius expansion |
| `MIN_MANDIS_TO_RETURN` | `3` | Minimum mandis before radius auto-relaxes |
| `MAX_MANDIS_TO_RETURN` | `15` | Maximum mandis returned per search |
| `HAVERSINE_ROAD_FACTOR` | `1.30` | Straight-line → road distance multiplier |
| `TRANSPORT_RATE_PER_KM_PER_QTL` | `₹8.50` | Transport cost rate |
| `MIN_TRANSPORT_COST_PER_QTL` | `₹50` | Minimum transport floor |
| `MANDI_RENT_PCT` | `1.5%` | Market committee cess |
| `COMMISSION_PCT` | `2.0%` | Aadatiya commission |
| `LOADING_UNLOADING_PER_QTL` | `₹20` | Flat loading/unloading |
| `MISC_FEES_PER_QTL` | `₹10` | Weighing, token, misc |
| `PRICE_CACHE_SECONDS` | `43200` | In-memory price cache TTL (12 hours) |

---

## Price Fetching & Fallback Strategy

The `market_fetcher.py` uses a 3-tier strategy to ensure a price is always returned:

```
Tier 1 ── Agmarknet API filtered by market + district + state
             │ (if no result or API unavailable)
             ▼
Tier 2 ── Agmarknet API filtered by district + state
             │ (if no result)
             ▼
Tier 3 ── MSP ± random jitter (−5% to +10%)
          Used for demo / when API key is not configured
```

- Prices are cached in-memory for **12 hours** to prevent excessive API calls.
- The cache key is `market_name|state|district|commodity`.
- The Agmarknet Resource ID is `9ef842fd-9a74-4050-a155-397d9013c4f9` (Agmarknet daily arrivals dataset).

---

## Profit Calculation Formula

```
Gross Revenue         = Modal Price (₹/qtl)  × Quantity (qtl)
Transport Cost        = max(Rate × Road KM × Qtl,  Min Floor × Qtl)
Mandi Rent            = Gross Revenue × 1.5%
Commission            = Gross Revenue × 2.0%
Loading & Unloading   = ₹20 × Qtl
Misc Fees             = ₹10 × Qtl

Total Deductions      = Transport + Rent + Commission + Loading + Misc
Net Revenue           = Gross Revenue − Total Deductions
True Net Profit       = Net Revenue − Cultivation Cost
```

Road distance is estimated as: `Haversine distance × 1.30` (road-correction factor).  
Drive time is estimated at an average speed of **40 km/h** (Indian rural roads).

---

## Mandi Dataset

The static dataset at `data/mandis_india.json` contains curated APMC mandi records. Each entry includes:

| Field | Description |
|---|---|
| `id` | Unique mandi identifier |
| `name` | Mandi market name |
| `lat`, `lon` | GPS coordinates |
| `state`, `district` | Location for Agmarknet API filtering |
| `market_code` | Optional Agmarknet market code |
| `type` | `"APMC"`, `"Sabji_Mandi"`, or `"Wholesaler"` |
| `contact` | Phone, address, secretary name, timings, website, helpline |

> **Note:** `mandis_india.json` is committed to the repository as a static reference dataset. It is **not** excluded by `.gitignore`. The dynamic price data fetched from Agmarknet is never persisted to disk.

---

## Environment Variables

These variables are loaded from `ml_service/.env` (via `python-dotenv`):

| Variable | Required | Description |
|---|---|---|
| `AGMARKNET_API_KEY` | ✅ Recommended | API key from [data.gov.in](https://data.gov.in) for live prices. Without this, Tier 3 (MSP jitter) is used. |
| `AGMARKNET_RESOURCE_ID` | ❌ Optional | Defaults to `9ef842fd-9a74-4050-a155-397d9013c4f9` |
| `LOGISTICS_ADMIN_TOKEN` | ❌ Optional | Auth token for admin operations. Defaults to `logistics-admin-2024` |
| `DEFAULT_SEARCH_RADIUS_KM` | ❌ Optional | Override default search radius (default: `150`) |
| `TRANSPORT_RATE_PER_KM_PER_QTL` | ❌ Optional | Override transport cost rate (default: `8.5`) |

**.env example:**
```dotenv
AGMARKNET_API_KEY=your_data_gov_in_api_key_here
AGMARKNET_RESOURCE_ID=9ef842fd-9a74-4050-a155-397d9013c4f9
LOGISTICS_ADMIN_TOKEN=your-secure-token-here
DEFAULT_SEARCH_RADIUS_KM=150
TRANSPORT_RATE_PER_KM_PER_QTL=8.5
```

> ⚠️ **Never commit your `.env` file.** It is excluded by `ml_service/.gitignore`.

---

## Running Standalone

> In production, this layer runs as part of the unified ML service. Use standalone mode only for isolated development/debugging.

```powershell
# Navigate to the ml_service directory
cd ml_service

# Activate the virtual environment
.\\venv\\Scripts\\activate

# Run the logistics layer standalone on port 8002
uvicorn logistics_layer.app:app --port 8002 --reload
```

Health check: `http://localhost:8002/health`  
Swagger UI: `http://localhost:8002/docs`

---

## Integration with the Unified ML Service

In production, the Logistics Layer is mounted on the unified FastAPI app in `ml_service/main.py`:

```python
from logistics_layer.app import app as logistics_app
app.mount("/logistics", logistics_app)
```

All routes are then available under the `/logistics` prefix at `http://localhost:8000`:

| Endpoint | URL |
|---|---|
| Health | `http://localhost:8000/logistics/health` |
| Optimize | `http://localhost:8000/logistics/optimize` |
| Nearby Mandis | `http://localhost:8000/logistics/mandis/nearby` |
| Crops Metadata | `http://localhost:8000/logistics/crops` |
| Fee Config | `http://localhost:8000/logistics/config/fees` |
| Swagger Docs | `http://localhost:8000/logistics/docs` |

### Data Flow with Other Layers

```
Terra Layer  →  Fathom Layer  →  Logistics Layer
(soil type)     (crop allocation  (optimal mandi +
                 + costs)          net profit)
```

The `allocations` field in `OptimizeRequest` is designed to accept the direct output of the Fathom Layer — each allocation object carries the crop name, acreage, and cultivation cost that the Logistics Layer uses for true net profit calculation.
