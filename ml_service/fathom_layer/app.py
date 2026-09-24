"""
app.py — Fathom Layer FastAPI microservice.
Port: 8001
Run: uvicorn app:app --port 8001 --reload
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, model_validator

from .config import CFG, SUPPORTED_CROPS, SUPPORTED_SOIL_TYPES
from .optimizer import CropAllocation, FathomOptimizer, FathomResult
from .market_service import MarketService

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Application factory ────────────────────────────────────────────────────────
app = FastAPI(
    title="Fathom Layer — Crop Mix Optimiser",
    description=(
        "ML microservice that recommends the optimal crop mix maximising profit "
        "for a given soil type, soil quality score, land area, and budget."
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

# ── Singleton optimizer — initialised at startup ───────────────────────────────
_optimizer: FathomOptimizer | None = None
_retrain_lock = threading.Lock()

# ── Admin token (loaded from config or env) ────────────────────────────────────
ADMIN_TOKEN = CFG.FATHOM_ADMIN_TOKEN


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class RecommendRequest(BaseModel):
    soil_type:    str
    soil_quality: float
    land_acres:   float
    budget_inr:   float
    lat:          Optional[float] = None
    lon:          Optional[float] = None

    @field_validator("soil_type")
    @classmethod
    def validate_soil_type(cls, v: str) -> str:
        if v not in SUPPORTED_SOIL_TYPES:
            raise ValueError(
                f"'{v}' is not a supported soil type. "
                f"Valid options: {SUPPORTED_SOIL_TYPES}"
            )
        return v

    @field_validator("budget_inr")
    @classmethod
    def validate_budget(cls, v: float) -> float:
        if v < CFG.MIN_BUDGET_INR:
            raise ValueError(
                f"budget_inr must be at least ₹{CFG.MIN_BUDGET_INR:,.0f} "
                f"(minimum budget). Got: ₹{v:,.0f}"
            )
        return v

    @field_validator("land_acres")
    @classmethod
    def validate_land(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("land_acres must be greater than 0")
        if v > CFG.MAX_LAND_ACRES:
            raise ValueError(f"land_acres cannot exceed {CFG.MAX_LAND_ACRES:,.0f}")
        return v

    @field_validator("soil_quality")
    @classmethod
    def validate_quality(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError("soil_quality must be between 0 and 100")
        return v


class CropAllocationOut(BaseModel):
    crop:        str
    icon:        str
    color:       str
    acres:       float
    cost:        float
    revenue:     float
    profit:      float
    margin_pct:  float
    pct_of_land: float
    market_price_qtl: Optional[float] = None


class FathomResultOut(BaseModel):
    allocations:     List[CropAllocationOut]
    total_acres:     float
    total_cost:      float
    total_revenue:   float
    expected_profit: float
    roi_pct:         float
    soil_type:       str
    soil_quality:    float
    budget_inr:      float
    land_acres:      float
    location_detected: Optional[str] = None
    price_source: Optional[str] = None
    budget_exhausted: bool = False
    budget_shortfall_inr: float = 0.0
    budget_utilization_pct: float = 0.0
    budget_surplus_advisory: str = ""


class SoilInfo(BaseModel):
    soil_type:   str
    boost:       float
    description: str


class CropInfo(BaseModel):
    crop:              str
    icon:              str
    color:             str
    cost_per_acre:     float
    best_soils:        List[str]
    ok_soils:          List[str]
    season:            str
    msp_price_per_qtl: Optional[float] = None


# ── Startup event ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event() -> None:
    global _optimizer

    meta_path = CFG.MODELS_DIR / "model_metadata.json"

    if not meta_path.exists():
        log.warning("⚠️  model_metadata.json not found — auto-training before accepting requests …")
        _auto_train()
    else:
        # Warn if models are older than 30 days
        try:
            meta = json.loads(meta_path.read_text())
            trained_at = datetime.fromisoformat(meta["trained_at"])
            age_days = (datetime.now(timezone.utc) - trained_at).days
            if age_days > 30:
                log.warning("⚠️  Models are %d days old. Consider retraining.", age_days)
        except Exception:
            pass

    try:
        _optimizer = FathomOptimizer()
        log.info("✅  FathomOptimizer ready")
    except RuntimeError as exc:
        log.error("❌  Could not load models: %s", exc)
        log.error("    Run: python -m train  then restart the server.")

    # ── Price Cache Warmer ──────────────────────────────────────────────────
    try:
        TOP_STATES = ["Maharashtra", "Punjab", "Uttar Pradesh", "Madhya Pradesh"]
        for state in TOP_STATES:
            await MarketService.get_market_prices(state, None)
        log.info("✅  Price cache warmed for top states")
    except Exception as e:
        log.error("❌  Price cache warming failed: %s", e)


def _auto_train() -> None:
    """Blocking auto-train called at startup when no models exist."""
    try:
        from data_pipeline import DataPipeline
        from train import ModelTrainer
        DataPipeline().run()
        ModelTrainer().train_all(retrain=False)
    except Exception as exc:
        log.error("Auto-train failed: %s", exc)
        log.error("Place CSVs in fathom_layer/data/raw/ and run the pipeline manually.")


def _background_retrain() -> None:
    """Background retrain — used by POST /retrain."""
    with _retrain_lock:
        global _optimizer
        try:
            from data_pipeline import DataPipeline
            from train import ModelTrainer
            DataPipeline().run()
            ModelTrainer().train_all(retrain=True)
            _optimizer = FathomOptimizer()
            log.info("✅  Background retrain complete")
        except Exception as exc:
            log.error("Background retrain failed: %s", exc)


def _get_optimizer() -> FathomOptimizer:
    global _optimizer
    if _optimizer is None:
        try:
            _optimizer = FathomOptimizer()
            log.info("✅  FathomOptimizer lazily loaded")
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Models not loaded",
                    "hint": "Run: python -m train  then restart the server",
                },
            )
    return _optimizer


# ── Error handler for Pydantic validation errors ───────────────────────────────
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
    return {"status": "ok", "service": "fathom_layer", "port": 8001}


@app.get("/soils", response_model=List[SoilInfo], tags=["Metadata"])
async def list_soils() -> List[SoilInfo]:
    """List all supported soil types with boost multipliers."""
    descriptions = {
        "Black_Soil":    "Rich in clay, moisture retentive, ideal for cotton and wheat",
        "Alluvial_Soil": "Fertile river deposits, supports most crops",
        "Red_Soil":      "Well-drained, iron-rich, good for groundnut and millets",
        "Yellow_Soil":   "Moderate fertility, suited for groundnut, potato",
        "Laterite_Soil": "Acidic, leached soil, used for plantation crops",
        "Mountain_Soil": "Shallow, organic-rich; suited for tea, coffee, spices",
        "Arid_Soil":     "Dry, sandy, low fertility; drought-resistant crops only",
    }
    return [
        SoilInfo(
            soil_type=st,
            boost=CFG.SOIL_BOOST.get(st, 1.0),
            description=descriptions.get(st, ""),
        )
        for st in SUPPORTED_SOIL_TYPES
    ]


@app.get("/crops", response_model=List[CropInfo], tags=["Metadata"])
async def list_crops() -> List[CropInfo]:
    """List all crops with cost, MSP, soil compatibility, and display metadata."""
    return [
        CropInfo(
            crop=name,
            icon=info.get("icon", "🌿"),
            color=info.get("color", "#00e87a"),
            cost_per_acre=info.get("cost_per_acre_inr", 0),
            best_soils=info.get("best_soils", []),
            ok_soils=info.get("ok_soils", []),
            season=info.get("season", "Kharif"),
            msp_price_per_qtl=CFG.MSP_PRICES.get(name),
        )
        for name, info in CFG.CROP_DB.items()
    ]


@app.get("/model-info", tags=["System"])
async def model_info() -> dict:
    """Return training metadata for all three models."""
    meta_path = CFG.MODELS_DIR / "model_metadata.json"
    if not meta_path.exists():
        raise HTTPException(
            status_code=404,
            detail="model_metadata.json not found. Run: python -m train",
        )
    return json.loads(meta_path.read_text())


@app.post("/recommend", response_model=FathomResultOut, tags=["Optimizer"])
async def recommend(
    req: RecommendRequest,
    opt: FathomOptimizer = Depends(_get_optimizer),
) -> FathomResultOut:
    """
    Recommend the optimal crop mix for the given inputs.

    - **soil_type**: One of the 7 supported soil types (from Terra Layer)
    - **soil_quality**: Score 0–100 (from Terra Layer pipeline)
    - **land_acres**: Total available land in acres (> 0)
    - **budget_inr**: Total cultivation budget in INR (min ₹5,000)
    """
    try:
        result = await opt.optimise(
            soil_type    = req.soil_type,
            soil_quality = req.soil_quality,
            land_acres   = req.land_acres,
            budget_inr   = req.budget_inr,
            lat          = req.lat,
            lon          = req.lon,
        )
    except Exception as exc:
        log.exception("Optimizer error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Optimizer error: {str(exc)}")

    return FathomResultOut(
        allocations=[
            CropAllocationOut(
                crop        = a.crop,
                icon        = a.icon,
                color       = a.color,
                acres       = a.acres,
                cost        = a.cost,
                revenue     = a.revenue,
                profit      = a.profit,
                margin_pct  = a.margin_pct,
                pct_of_land = a.pct_of_land,
                market_price_qtl = a.market_price_qtl,
            )
            for a in result.allocations
        ],
        total_acres     = result.total_acres,
        total_cost      = result.total_cost,
        total_revenue   = result.total_revenue,
        expected_profit = result.expected_profit,
        roi_pct         = result.roi_pct,
        soil_type       = result.soil_type,
        soil_quality    = result.soil_quality,
        budget_inr      = result.budget_inr,
        land_acres      = result.land_acres,
        location_detected = result.location_detected,
        price_source    = result.price_source,
        budget_exhausted = result.budget_exhausted,
        budget_shortfall_inr = result.budget_shortfall_inr,
        budget_utilization_pct = result.budget_utilization_pct,
        budget_surplus_advisory = result.budget_surplus_advisory,
    )


@app.post("/retrain", tags=["System"])
async def retrain(
    background_tasks: BackgroundTasks,
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> dict:
    """
    Trigger a full retrain in the background.
    Requires `X-Admin-Token` header.
    """
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    background_tasks.add_task(_background_retrain)
    return {"status": "retraining started"}


import io
from fastapi.responses import StreamingResponse

@app.post("/plan-pdf", tags=["Optimizer"])
async def download_plan_pdf(result: FathomResultOut):
    """Generate a PDF document of the crop plan."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF generation library 'reportlab' is not installed.")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(1 * inch, 10 * inch, "CropHub - Optimal Fathom Allocation Plan")
    p.setFont("Helvetica", 12)
    
    y = 9.5 * inch
    p.drawString(1 * inch, y, f"Soil Type: {result.soil_type}")
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"Soil Quality: {result.soil_quality:.1f} / 100")
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"Budget: INR {result.budget_inr:,.2f}")
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"Land Size: {result.land_acres:.1f} acres")
    y -= 0.5 * inch
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1 * inch, y, "Crop Allocations:")
    y -= 0.3 * inch
    p.setFont("Helvetica", 12)
    for a in result.allocations:
        p.drawString(1.2 * inch, y, f"- {a.crop}: {a.acres:.1f} acres (Cost: INR {a.cost:,.0f}, Revenue: INR {a.revenue:,.0f}, Profit: INR {a.profit:,.0f})")
        y -= 0.25 * inch
        if y < 1 * inch:
            p.showPage()
            p.setFont("Helvetica", 12)
            y = 10 * inch
        
    y -= 0.3 * inch
    if y < 2 * inch:
        p.showPage()
        y = 10 * inch
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1 * inch, y, "Summary:")
    y -= 0.3 * inch
    p.setFont("Helvetica", 12)
    p.drawString(1.2 * inch, y, f"Total Cost: INR {result.total_cost:,.0f}")
    y -= 0.25 * inch
    p.drawString(1.2 * inch, y, f"Expected Revenue: INR {result.total_revenue:,.0f}")
    y -= 0.25 * inch
    p.drawString(1.2 * inch, y, f"Expected Profit: INR {result.expected_profit:,.0f}")
    y -= 0.25 * inch
    p.drawString(1.2 * inch, y, f"ROI: {result.roi_pct:.1f}%")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return StreamingResponse(
        buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": "attachment; filename=CropHub_Fathom_Plan.pdf"}
    )


# ── Main entry ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
