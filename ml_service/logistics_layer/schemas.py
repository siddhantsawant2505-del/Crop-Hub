"""
schemas.py — Pydantic request/response models for the Logistics Layer.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, field_validator


# ── Request Models ─────────────────────────────────────────────────────────────

class CropAllocationIn(BaseModel):
    """A single crop allocation coming from Fathom Layer results."""
    crop: str
    icon: str = "🌿"
    color: str = "#00e87a"
    acres: float
    cost: float           # total cultivation cost for this crop (INR)
    revenue: float
    profit: float
    margin_pct: float
    pct_of_land: float
    market_price_qtl: Optional[float] = None


class OptimizeRequest(BaseModel):
    """
    Main optimization request from the frontend.
    Expects the farmer's GPS and the full Fathom allocation result.
    """
    lat: float
    lon: float
    allocations: List[CropAllocationIn]
    quantity_qtl: float = 10.0        # how many quintals to sell per crop
    radius_km: float = 150.0
    cultivation_cost_override: Optional[float] = None  # optional per-qtl cost override

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError("lon must be between -180 and 180")
        return v

    @field_validator("radius_km")
    @classmethod
    def validate_radius(cls, v: float) -> float:
        if v <= 0 or v > 300:
            raise ValueError("radius_km must be between 1 and 300")
        return v


class NearbyRequest(BaseModel):
    lat: float
    lon: float
    radius_km: float = 150.0


# ── Contact Details ───────────────────────────────────────────────────────────

class MandiContact(BaseModel):
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    secretary_name: Optional[str] = None
    address: str
    timings: str = "6:00 AM – 2:00 PM (Mon–Sat)"
    website: Optional[str] = None
    helpline: Optional[str] = None


# ── Mandi Info (raw, from discovery) ─────────────────────────────────────────

class MandiInfo(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    state: str
    district: str
    market_code: Optional[str] = None
    type: str = "APMC"    # "APMC" | "Sabji_Mandi" | "Wholesaler"
    contact: MandiContact


# ── Per-Crop Mandi Result ─────────────────────────────────────────────────────

class FeeBreakdown(BaseModel):
    modal_price_per_qtl: float          # Agmarknet live price
    transport_cost_per_qtl: float
    mandi_rent_per_qtl: float
    commission_per_qtl: float
    loading_unloading_per_qtl: float
    misc_fees_per_qtl: float
    total_deductions_per_qtl: float
    net_price_per_qtl: float            # what farmer actually gets per qtl


class MandiResult(BaseModel):
    mandi: MandiInfo
    distance_km: float
    estimated_road_km: float
    drive_time_min: float
    modal_price_per_qtl: float
    fee_breakdown: FeeBreakdown
    # Totals for the given quantity
    gross_revenue: float                # modal_price × quantity
    total_deductions: float
    net_revenue: float                  # what farmer pockets
    # True net profit = net_revenue − cultivation_cost
    cultivation_cost: float
    true_net_profit: float
    profit_per_qtl: float
    best: bool = False
    rank: int = 0
    why_best: Optional[str] = None      # short explanation string


class CropOptimizationResult(BaseModel):
    crop: str
    icon: str
    color: str
    quantity_qtl: float
    mandis: List[MandiResult]           # ranked, best first
    best_mandi_name: str
    best_net_profit: float


class OptimizeResponse(BaseModel):
    lat: float
    lon: float
    radius_km: float
    quantity_qtl: float
    results: List[CropOptimizationResult]   # one per crop
    overall_best_crop: str                  # crop with highest total profit
    overall_best_mandi: str


class NearbyResponse(BaseModel):
    mandis: List[MandiInfo]
    total: int
    radius_km: float
