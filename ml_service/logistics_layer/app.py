"""
app.py — Logistics Layer FastAPI microservice.
Port: 8002
Run: uvicorn app:app --port 8002 --reload
"""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import CFG
from .mandi_discovery import discover_nearby
from .optimizer import run_optimization
from .schemas import (
    NearbyRequest,
    NearbyResponse,
    OptimizeRequest,
    OptimizeResponse,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Application ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Logistics Layer — Market Profit Optimiser",
    description=(
        "Microservice that discovers nearby APMC mandis, fetches live Agmarknet prices, "
        "and computes the optimal selling destination for each crop to maximise farmer profit."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Validation error handler ───────────────────────────────────────────────────
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc) -> JSONResponse:
    errors = []
    try:
        for err in exc.errors():
            errors.append({
                "field":   " → ".join(str(l) for l in err["loc"]),
                "message": err["msg"],
                "type":    err["type"],
            })
    except Exception:
        errors = [{"message": str(exc)}]
    return JSONResponse(status_code=422, content={"detail": errors})


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health() -> dict:
    """Health check."""
    return {
        "status": "ok",
        "service": "logistics_layer",
        "port": 8002,
        "agmarknet_key_configured": (
            bool(CFG.AGMARKNET_API_KEY) and CFG.AGMARKNET_API_KEY != "YOUR_API_KEY_HERE"
        ),
    }


@app.post("/optimize", response_model=OptimizeResponse, tags=["Optimizer"])
async def optimize(req: OptimizeRequest) -> OptimizeResponse:
    """
    Core endpoint. Given the farmer's GPS coordinates and Fathom Layer crop allocations,
    returns the optimal mandi per crop ranked by true net profit after all deductions.
    """
    try:
        result = await run_optimization(req)
        return result
    except Exception as exc:
        log.exception("Optimization failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Optimization error: {str(exc)}")


@app.post("/mandis/nearby", response_model=NearbyResponse, tags=["Mandis"])
async def mandis_nearby(req: NearbyRequest) -> NearbyResponse:
    """
    Return all mandis within the given radius, sorted by distance.
    Useful for rendering pins on the map without running the full optimizer.
    """
    try:
        mandis = discover_nearby(req.lat, req.lon, req.radius_km)
        return NearbyResponse(
            mandis=mandis,
            total=len(mandis),
            radius_km=req.radius_km,
        )
    except Exception as exc:
        log.exception("Mandi discovery failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/crops", tags=["Metadata"])
async def list_crops() -> dict:
    """List all supported crops and their Agmarknet commodity names."""
    return {
        "crops": [
            {
                "name": crop,
                "commodity": CFG.COMMODITY_MAP.get(crop, crop),
                "msp_price_per_qtl": CFG.MSP_PRICES.get(crop),
            }
            for crop in CFG.SUPPORTED_CROPS
        ]
    }


@app.get("/config/fees", tags=["Metadata"])
async def fee_structure() -> dict:
    """Return the current fee structure used in profit calculations."""
    return {
        "transport_rate_per_km_per_qtl": CFG.TRANSPORT_RATE_PER_KM_PER_QTL,
        "min_transport_cost_per_qtl": CFG.MIN_TRANSPORT_COST_PER_QTL,
        "mandi_rent_pct": CFG.MANDI_RENT_PCT,
        "commission_pct": CFG.COMMISSION_PCT,
        "loading_unloading_per_qtl": CFG.LOADING_UNLOADING_PER_QTL,
        "misc_fees_per_qtl": CFG.MISC_FEES_PER_QTL,
        "haversine_road_factor": CFG.HAVERSINE_ROAD_FACTOR,
    }


# ── Main entry ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)
