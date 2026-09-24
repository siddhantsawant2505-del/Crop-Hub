"""
optimizer.py — Core profit optimization logic for the Logistics Layer.

For each crop × mandi combination, computes:
  Net Profit = Gross Revenue − Transport − Rent − Commission − Loading − Misc − Cultivation Cost

Then ranks mandis by Net Profit (descending) and marks the best one.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import List

from .config import CFG
from .distance_service import (
    compute_distances,
    estimated_road_km,
    haversine_km,
)
from .market_fetcher import get_modal_price
from .mandi_discovery import discover_nearby
from .schemas import (
    CropAllocationIn,
    CropOptimizationResult,
    FeeBreakdown,
    MandiInfo,
    MandiResult,
    OptimizeRequest,
    OptimizeResponse,
)

log = logging.getLogger(__name__)


# ── Fee Computation ───────────────────────────────────────────────────────────

def _compute_transport_cost(road_km: float, quantity_qtl: float) -> float:
    """Transport cost = rate × km × quintals, with a minimum floor."""
    raw = CFG.TRANSPORT_RATE_PER_KM_PER_QTL * road_km * quantity_qtl
    return max(raw, CFG.MIN_TRANSPORT_COST_PER_QTL * quantity_qtl)


def _compute_fees(
    modal_price_per_qtl: float,
    road_km: float,
    quantity_qtl: float,
) -> FeeBreakdown:
    """Compute the full fee breakdown for a single mandi × crop combination."""
    gross_per_qtl = modal_price_per_qtl

    # Variable fees (per quintal)
    rent_per_qtl = round(gross_per_qtl * CFG.MANDI_RENT_PCT, 2)
    commission_per_qtl = round(gross_per_qtl * CFG.COMMISSION_PCT, 2)

    # Fixed fees (per quintal)
    loading_per_qtl = CFG.LOADING_UNLOADING_PER_QTL
    misc_per_qtl = CFG.MISC_FEES_PER_QTL

    # Transport allocated per quintal
    total_transport = _compute_transport_cost(road_km, quantity_qtl)
    transport_per_qtl = round(total_transport / max(quantity_qtl, 0.01), 2)

    total_deductions_per_qtl = round(
        transport_per_qtl + rent_per_qtl + commission_per_qtl
        + loading_per_qtl + misc_per_qtl,
        2,
    )

    net_price_per_qtl = round(gross_per_qtl - total_deductions_per_qtl, 2)

    return FeeBreakdown(
        modal_price_per_qtl=round(gross_per_qtl, 2),
        transport_cost_per_qtl=transport_per_qtl,
        mandi_rent_per_qtl=rent_per_qtl,
        commission_per_qtl=commission_per_qtl,
        loading_unloading_per_qtl=loading_per_qtl,
        misc_fees_per_qtl=misc_per_qtl,
        total_deductions_per_qtl=total_deductions_per_qtl,
        net_price_per_qtl=net_price_per_qtl,
    )


# ── Profit Calculation for One Mandi × One Crop ───────────────────────────────

async def _evaluate_mandi(
    mandi: MandiInfo,
    crop: CropAllocationIn,
    quantity_qtl: float,
    farm_lat: float,
    farm_lon: float,
) -> MandiResult:
    """Fetch price and compute net profit for one mandi × one crop."""
    # Distance
    straight_km = haversine_km(farm_lat, farm_lon, mandi.lat, mandi.lon)
    road_km = estimated_road_km(straight_km)
    drive_mins = (road_km / 40.0) * 60.0  # 40 km/h avg

    # Live price from Agmarknet
    modal_price = await get_modal_price(
        crop=crop.crop,
        state=mandi.state,
        district=mandi.district,
        market_name=mandi.name,
    )

    # Fee breakdown
    fees = _compute_fees(modal_price, road_km, quantity_qtl)

    # Revenue totals
    gross_revenue = round(modal_price * quantity_qtl, 2)
    total_deductions = round(fees.total_deductions_per_qtl * quantity_qtl, 2)
    net_revenue = round(gross_revenue - total_deductions, 2)

    # Cultivation cost for this quantity
    # Use per-acre cost from allocation, estimate qtl/acre ~ revenue/price/acres
    # Safer: use the total cost from fathom, allocate proportionally to quantity
    cultivation_cost_per_qtl = (
        crop.cost / max(quantity_qtl, 0.01)
        if crop.cost > 0
        else 0.0
    )
    cultivation_cost = round(cultivation_cost_per_qtl * quantity_qtl, 2)

    true_net_profit = round(net_revenue - cultivation_cost, 2)
    profit_per_qtl = round(true_net_profit / max(quantity_qtl, 0.01), 2)

    return MandiResult(
        mandi=mandi,
        distance_km=round(straight_km, 2),
        estimated_road_km=round(road_km, 2),
        drive_time_min=round(drive_mins, 1),
        modal_price_per_qtl=round(modal_price, 2),
        fee_breakdown=fees,
        gross_revenue=gross_revenue,
        total_deductions=total_deductions,
        net_revenue=net_revenue,
        cultivation_cost=cultivation_cost,
        true_net_profit=true_net_profit,
        profit_per_qtl=profit_per_qtl,
        best=False,
        rank=0,
    )


# ── Per-Crop Optimizer ────────────────────────────────────────────────────────

async def _optimize_crop(
    crop: CropAllocationIn,
    nearby_mandis: List[MandiInfo],
    quantity_qtl: float,
    farm_lat: float,
    farm_lon: float,
) -> CropOptimizationResult:
    """Run profit optimization for a single crop across all nearby mandis."""
    log.info("Optimizing %s across %d mandis", crop.crop, len(nearby_mandis))

    # Fetch all mandi results concurrently
    tasks = [
        _evaluate_mandi(mandi, crop, quantity_qtl, farm_lat, farm_lon)
        for mandi in nearby_mandis
    ]
    results: list[MandiResult] = await asyncio.gather(*tasks)

    # Sort by true_net_profit descending
    results.sort(key=lambda r: r.true_net_profit, reverse=True)

    # Annotate rank and best
    for i, r in enumerate(results):
        r.rank = i + 1
        r.best = i == 0

    # Explain why the best is best
    if results:
        best = results[0]
        reasons = []
        if best.modal_price_per_qtl == max(r.modal_price_per_qtl for r in results):
            reasons.append("highest live market price")
        if best.distance_km == min(r.distance_km for r in results):
            reasons.append("lowest transport cost")
        if best.fee_breakdown.commission_per_qtl == min(
            r.fee_breakdown.commission_per_qtl for r in results
        ):
            reasons.append("lowest commission fee")
        best.why_best = (
            "Best combination of " + ", ".join(reasons)
            if reasons
            else "Highest overall net profit after all deductions"
        )

    best_result = results[0] if results else None

    return CropOptimizationResult(
        crop=crop.crop,
        icon=crop.icon,
        color=crop.color,
        quantity_qtl=quantity_qtl,
        mandis=results,
        best_mandi_name=best_result.mandi.name if best_result else "N/A",
        best_net_profit=best_result.true_net_profit if best_result else 0.0,
    )


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def run_optimization(req: OptimizeRequest) -> OptimizeResponse:
    """
    Full optimization pipeline:
      1. Discover nearby mandis
      2. For each crop from Fathom allocations, score every mandi
      3. Return ranked results per crop + overall best recommendation
    """
    # Step 1: Discover mandis
    nearby_mandis = discover_nearby(req.lat, req.lon, req.radius_km)
    if not nearby_mandis:
        log.warning("No mandis found within %.0f km of (%.4f, %.4f)", req.radius_km, req.lat, req.lon)
        # Return empty results
        return OptimizeResponse(
            lat=req.lat,
            lon=req.lon,
            radius_km=req.radius_km,
            quantity_qtl=req.quantity_qtl,
            results=[],
            overall_best_crop="N/A",
            overall_best_mandi="N/A",
        )

    log.info("Found %d nearby mandis for optimization", len(nearby_mandis))

    # Step 2: Optimize per crop concurrently
    crop_tasks = [
        _optimize_crop(crop, nearby_mandis, req.quantity_qtl, req.lat, req.lon)
        for crop in req.allocations
    ]
    crop_results: list[CropOptimizationResult] = await asyncio.gather(*crop_tasks)

    # Step 3: Determine overall best (crop + mandi combo with highest true_net_profit)
    best_crop_result = max(
        crop_results,
        key=lambda cr: cr.best_net_profit,
        default=None,
    )
    overall_best_crop = best_crop_result.crop if best_crop_result else "N/A"
    overall_best_mandi = best_crop_result.best_mandi_name if best_crop_result else "N/A"

    return OptimizeResponse(
        lat=req.lat,
        lon=req.lon,
        radius_km=req.radius_km,
        quantity_qtl=req.quantity_qtl,
        results=crop_results,
        overall_best_crop=overall_best_crop,
        overall_best_mandi=overall_best_mandi,
    )
