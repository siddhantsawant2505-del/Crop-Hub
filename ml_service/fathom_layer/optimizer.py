"""
optimizer.py — Fathom Layer greedy crop-mix optimizer.
Loads trained models once at __init__ (singleton intent).
Exposes .optimise(soil_type, soil_quality, land_acres, budget_inr) -> FathomResult
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List

import joblib
import numpy as np

from .config import (
    CFG,
    CROP_COSTS,
    FALLBACK_YIELDS,
    SUPPORTED_CROPS,
    SUPPORTED_SOIL_TYPES,
)
from .market_service import MarketService

log = logging.getLogger(__name__)


# ── Result dataclasses ─────────────────────────────────────────────────────────
@dataclass
class CropAllocation:
    crop: str
    icon: str
    color: str
    acres: float
    cost: float
    revenue: float
    profit: float
    margin_pct: float
    pct_of_land: float
    market_price_qtl: Optional[float] = None


@dataclass
class FathomResult:
    allocations: List[CropAllocation]
    total_acres: float
    total_cost: float
    total_revenue: float
    expected_profit: float
    roi_pct: float
    soil_type: str
    soil_quality: float
    budget_inr: float
    land_acres: float
    location_detected: Optional[str] = None
    price_source: Optional[str] = None
    budget_exhausted: bool = False
    budget_shortfall_inr: float = 0.0   # how much more budget would cover remaining land
    budget_utilization_pct: float = 0.0
    budget_surplus_advisory: str = ""


# ── Optimizer ─────────────────────────────────────────────────────────────────
class FathomOptimizer:
    """
    Singleton-pattern optimizer.  Models are loaded once at __init__.
    Never trains — only infers.
    """

    def __init__(self) -> None:
        self._load_models()

    # ─────────────────────────────────────────────────────────────────────────
    def _load_models(self) -> None:
        required = [
            "yield_model.joblib", "margin_model.joblib",
            "suitability_model.joblib", "label_encoders.joblib",
            "scaler.joblib", "feature_lists.joblib",
        ]
        missing = [f for f in required if not (CFG.MODELS_DIR / f).exists()]
        if missing:
            raise RuntimeError(
                "No trained models found. Run: python -m train"
            )

        self.yield_model  = joblib.load(CFG.MODELS_DIR / "yield_model.joblib")
        self.margin_model = joblib.load(CFG.MODELS_DIR / "margin_model.joblib")
        self.suit_model   = joblib.load(CFG.MODELS_DIR / "suitability_model.joblib")
        self.encoders     = joblib.load(CFG.MODELS_DIR / "label_encoders.joblib")
        self.scaler       = joblib.load(CFG.MODELS_DIR / "scaler.joblib")
        self.feat_lists   = joblib.load(CFG.MODELS_DIR / "feature_lists.joblib")
        log.info("✅  FathomOptimizer: all models loaded")

    # ─────────────────────────────────────────────────────────────────────────
    def _encode(self, col: str, val: str) -> int:
        """Encode a categorical value, falling back to class 0 on unseen labels."""
        le = self.encoders.get(col)
        if le is None:
            return 0
        try:
            return int(le.transform([val])[0])
        except ValueError:
            log.warning("FathomOptimizer: unseen label '%s' for '%s' — using fallback", val, col)
            return 0

    # ─────────────────────────────────────────────────────────────────────────
    def _build_feature_row(
        self,
        soil_type: str,
        soil_quality: float,
        crop: str,
        budget_per_acre: float,
        *,
        pred_yield: float = 0.0,
        pred_margin: float = 0.0,
    ) -> dict:
        """Build a dict of all raw feature values for a single crop+soil combo."""
        crop_info = CFG.CROP_DB.get(crop, {})
        season    = crop_info.get("season", "Kharif")

        # Representative NPK/climate for the soil type — use midpoint heuristics
        soil_npk = {
            "Black_Soil":    dict(N=90, P=40, K=60, ph=7.5, rainfall=150, humidity=70, temperature=28),
            "Alluvial_Soil": dict(N=60, P=90, K=55, ph=6.2, rainfall=200, humidity=75, temperature=30),
            "Red_Soil":      dict(N=35, P=28, K=40, ph=6.0, rainfall=100, humidity=55, temperature=32),
            "Yellow_Soil":   dict(N=50, P=45, K=50, ph=5.8, rainfall=110, humidity=60, temperature=30),
            "Laterite_Soil": dict(N=40, P=25, K=30, ph=5.0, rainfall=250, humidity=80, temperature=28),
            "Mountain_Soil": dict(N=55, P=35, K=40, ph=5.5, rainfall=100, humidity=65, temperature=18),
            "Arid_Soil":     dict(N=30, P=20, K=120, ph=7.8, rainfall=30, humidity=35, temperature=35),
        }
        npk = soil_npk.get(soil_type, soil_npk["Yellow_Soil"])

        return {
            "soil_type_enc":     self._encode("soil_type", soil_type),
            "crop_enc":          self._encode("crop", crop),
            "season_enc":        self._encode("season", season),
            "soil_quality_score": soil_quality,
            "N":          npk["N"],
            "P":          npk["P"],
            "K":          npk["K"],
            "ph":         npk["ph"],
            "rainfall":   npk["rainfall"],
            "humidity":   npk["humidity"],
            "temperature": npk["temperature"],
            "predicted_yield":  pred_yield,
            "predicted_margin": pred_margin,
            "budget_per_acre":  budget_per_acre,
        }

    # ─────────────────────────────────────────────────────────────────────────
    def _predict_crop(
        self, soil_type: str, soil_quality: float, crop: str, budget_per_acre: float
    ) -> tuple[float, float, float]:
        """
        Returns (pred_yield, pred_margin, suitability_score) for a single crop.
        """
        row = self._build_feature_row(soil_type, soil_quality, crop, budget_per_acre)

        # Step 1 — yield
        y_feats  = self.feat_lists["yield_features_used"]
        x_yield  = np.array([[row.get(f, 0.0) for f in y_feats]])
        pred_yield = float(self.yield_model.predict(x_yield)[0])
        pred_yield = max(pred_yield, 0.5)  # hard floor

        # Step 2 — margin (uses stacked yield)
        row["predicted_yield"] = pred_yield
        m_feats    = self.feat_lists["margin_features_used"]
        x_margin   = np.array([[row.get(f, 0.0) for f in m_feats]])
        pred_margin = float(self.margin_model.predict(x_margin)[0])
        pred_margin = float(np.clip(pred_margin, 0, 85))

        # Step 3 — suitability (uses stacked yield + margin)
        row["predicted_margin"] = pred_margin
        s_feats   = self.feat_lists["suit_features_used"]
        x_suit    = np.array([[row.get(f, 0.0) for f in s_feats]])
        suit_score = float(self.suit_model.predict_proba(x_suit)[0, 1])

        return pred_yield, pred_margin, suit_score

    # ─────────────────────────────────────────────────────────────────────────
    async def optimise(
        self,
        soil_type: str,
        soil_quality: float,
        land_acres: float,
        budget_inr: float,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> FathomResult:
        """
        Greedy allocation algorithm:
          1. Score every crop in CROP_DB
          2. Filter by MIN_SUITABILITY_SCORE
          3. Sort by expected_profit_per_acre descending
          4. Allocate in ACRE_STEP increments respecting hard constraints
        """
        budget_per_acre = budget_inr / max(land_acres, CFG.ACRE_STEP)

        # ── Step 0: Resolve Market Prices based on Location ────────────────────
        state, district = None, None
        if lat and lon:
            state, district = await MarketService.get_location(lat, lon)
        
        market_res = await MarketService.get_market_prices(state, district)
        market_prices = market_res["prices"]
        location_str = market_res["location"]
        price_source = market_res["source"]

        # ── Score all crops ────────────────────────────────────────────────────
        candidates: list[dict] = []
        for crop in SUPPORTED_CROPS:
            crop_info = CFG.CROP_DB.get(crop, {})
            best_s = crop_info.get("best_soils", [])
            ok_s   = crop_info.get("ok_soils", [])

            # Hard exclusion — never consider agronomically incompatible crops
            if soil_type not in best_s and soil_type not in ok_s:
                log.info(f"Hard-excluding {crop} — {soil_type} not in best or ok soils")
                continue

            pred_yield, pred_margin, suit_score = self._predict_crop(
                soil_type, soil_quality, crop, budget_per_acre
            )
            # ── Agronomic Correctness Boost (Knowledge-Based) ─────────────────
            crop_info = CFG.CROP_DB.get(crop, {})
            best_s = crop_info.get("best_soils", [])
            ok_s = crop_info.get("ok_soils", [])
            
            # Suitability score adjustment based on agronomic knowledge
            if soil_type in best_s:
                suit_score = min(suit_score * 1.25, 0.99)  # 25% boost for ideal soils
                log.info(f"Boosting {crop} for {soil_type} (Best Soil)")
            elif soil_type in ok_s:
                pass  # ok soil — no adjustment
            else:
                # Incompatible soil: always penalize regardless of ML confidence
                suit_score *= 0.2
                log.warning(f"Penalizing {crop} for {soil_type} (Incompatible Soil)")

            if suit_score < CFG.MIN_SUITABILITY_SCORE:
                continue

            cost_pa = CROP_COSTS.get(crop, 8_000)

            # Modal price per quintal from Agmarknet or Simulated
            market_price_qtl = market_prices.get(crop, CFG.MSP_PRICES.get(crop, 2000))

            # Revenue = Yield (qtl/acre) * Market Price (INR/qtl)
            revenue_pa = pred_yield * market_price_qtl

            # Apply soil quality boost to the yield/revenue
            soil_mult = CFG.SOIL_BOOST.get(soil_type, 1.0)
            revenue_pa *= soil_mult

            # ── Financial Realism Calibration ────────────────────────────────
            # Deduct post-harvest overhead ONCE (logistics, harvest, market fees)
            revenue_pa *= (1.0 - CFG.OVERHEAD_PCT)
            profit_pa = revenue_pa - cost_pa

            # Cap profit margin for financial realism
            margin_actual = profit_pa / max(revenue_pa, 1)
            if margin_actual > CFG.MAX_POSSIBLE_MARGIN:
                profit_pa = revenue_pa * CFG.MAX_POSSIBLE_MARGIN
                revenue_pa = cost_pa + profit_pa

            # Utilization-aware scoring: penalize crops too expensive for budget/land
            target_cost_pa = budget_inr / max(land_acres, 0.1)
            util_penalty = 1.0
            if cost_pa > target_cost_pa:
                util_penalty = (target_cost_pa / cost_pa) ** CFG.UTILIZATION_WEIGHT

            candidates.append({
                "crop":       crop,
                "suit_score": suit_score,
                "pred_yield": pred_yield,
                "pred_margin": margin_actual * 100,
                "cost_pa":    cost_pa,
                "revenue_pa": revenue_pa,
                "profit_pa":  profit_pa,
                "market_price_qtl": market_price_qtl,
                "rank_score": profit_pa * util_penalty, # Used for sorting
            })

        # If no crop passes the filter, relax threshold and use top-3
        if not candidates:
            log.warning("No crop passed suitability filter — using soil-compatible fallback")
            for crop in SUPPORTED_CROPS:
                crop_info = CFG.CROP_DB.get(crop, {})
                best_s = crop_info.get("best_soils", [])
                ok_s   = crop_info.get("ok_soils", [])

                # Fallback also respects soil — never recommend incompatible crops
                if soil_type not in best_s and soil_type not in ok_s:
                    continue

                pred_yield, pred_margin, suit_score = self._predict_crop(
                    soil_type, soil_quality, crop, budget_per_acre
                )
                cost_pa = CROP_COSTS.get(crop, 8_000)
                margin_frac = min(pred_margin / 100.0, 0.85)
                profit_pa = cost_pa * margin_frac / max(1 - margin_frac, 0.01)
                candidates.append({
                    "crop": crop,
                    "suit_score": suit_score,
                    "pred_yield": pred_yield,
                    "pred_margin": pred_margin,
                    "cost_pa": cost_pa,
                    "revenue_pa": cost_pa + profit_pa,
                    "profit_pa": profit_pa,
                    "rank_score": profit_pa,
                    "market_price_qtl": market_prices.get(crop, CFG.MSP_PRICES.get(crop, 2000)),
                })

            if not candidates:
                log.error(f"CRITICAL: Zero soil-compatible crops found for {soil_type}")
                return FathomResult(
                    allocations=[], total_acres=0, total_cost=0, total_revenue=0,
                    expected_profit=0, roi_pct=0, soil_type=soil_type,
                    soil_quality=soil_quality, budget_inr=budget_inr, land_acres=land_acres,
                    budget_exhausted=True, budget_shortfall_inr=0
                )

            candidates.sort(key=lambda x: x["profit_pa"], reverse=True)
            candidates = candidates[:3]

        # ── Step 1: Sorting by Rank Score (Profit * Utilization Potential) ──
        candidates.sort(key=lambda x: x.get("rank_score", x["profit_pa"]), reverse=True)

        # ── Step 2: Allocation Loop ──
        step    = CFG.ACRE_STEP
        max_pct = CFG.MAX_SINGLE_CROP_PCT
        alloc: dict[str, float] = {}   

        rem_budget = budget_inr
        rem_steps  = math.floor(land_acres / step)

        for cand in candidates:
            if rem_steps <= 0 or rem_budget <= 0:
                break
            crop    = cand["crop"]
            cost_pa = cand["cost_pa"]
            
            # Constraints
            max_by_budget = math.floor(rem_budget / (cost_pa * step)) * step
            max_by_land   = rem_steps * step
            max_by_diversity = math.floor((land_acres * max_pct) / step) * step
            
            acres = min(max_by_budget, max_by_land, max_by_diversity)
            if acres < step:
                continue

            alloc[crop] = acres
            rem_budget -= acres * cost_pa
            rem_steps  -= math.floor(acres / step)

        # ── Step 3: 100% UTILIZATION Sweep (Goal: No acre left unplanted) ──
        if rem_steps > 0 and CFG.PRIORITIZE_UTILIZATION:
            log.info(f"Backfilling {rem_steps * step:.2f} acres to reach 100% utilization")
            # Sort by cost so cheapest fills first
            cheapest = sorted(candidates, key=lambda x: x["cost_pa"])
            for cand in cheapest:
                if rem_steps <= 0:
                    break
                crop = cand["crop"]
                
                affordable_steps = math.floor(max(rem_budget, 0) / (cand["cost_pa"] * step))
                fill_steps = min(rem_steps, affordable_steps)

                if fill_steps <= 0:
                    continue

                fill_acres = fill_steps * step
                alloc[crop] = alloc.get(crop, 0.0) + fill_acres
                rem_budget -= fill_acres * cand["cost_pa"]
                rem_steps  -= fill_steps

        # ── Step 4: Budget Upgrade Pass ──────────────────────────────────────
        # Goal: maximize budget utilization by upgrading cheap crop allocations
        # to more expensive compatible crops, acre-for-acre, using remaining budget.
        # Does NOT change total land allocation — only upgrades crop quality.

        if rem_steps <= 0 and rem_budget >= CFG.ACRE_STEP * min(CROP_COSTS.values()):
            log.info(f"Running upgrade pass — Rs{rem_budget:.0f} remaining budget")

            # Sort current allocations cheapest first (upgrade candidates)
            upgrade_order = sorted(alloc.items(), key=lambda x: CROP_COSTS.get(x[0], 0))

            # Sort compatible candidates most expensive first (upgrade targets)
            upgrade_targets = sorted(
                [c for c in candidates if c['crop'] not in alloc or alloc[c['crop']] < land_acres * CFG.MAX_SINGLE_CROP_PCT],
                key=lambda x: x['cost_pa'],
                reverse=True
            )

            for cheap_crop, cheap_acres in upgrade_order:
                if rem_budget <= 0:
                    break
                cheap_cost_pa = CROP_COSTS.get(cheap_crop, 0)

                for target in upgrade_targets:
                    if target['crop'] == cheap_crop:
                        continue   # no point upgrading to same crop
                    if target['cost_pa'] <= cheap_cost_pa:
                        continue   # only upgrade to MORE expensive crops

                    # How many acres can we upgrade with remaining budget?
                    cost_diff_pa = target['cost_pa'] - cheap_cost_pa
                    upgradeable = math.floor(rem_budget / (cost_diff_pa * CFG.ACRE_STEP)) * CFG.ACRE_STEP
                    upgradeable = min(upgradeable, cheap_acres)   # can't upgrade more than we have

                    # Respect diversity cap on the target crop
                    already_target = alloc.get(target['crop'], 0.0)
                    target_cap = math.floor((land_acres * CFG.MAX_SINGLE_CROP_PCT) / CFG.ACRE_STEP) * CFG.ACRE_STEP
                    cap_remaining = max(target_cap - already_target, 0)
                    upgradeable = min(upgradeable, cap_remaining)

                    if upgradeable < CFG.ACRE_STEP:
                        continue

                    # Perform the upgrade
                    upgrade_cost = upgradeable * cost_diff_pa
                    alloc[cheap_crop] = round(alloc[cheap_crop] - upgradeable, 2)
                    alloc[target['crop']] = round(alloc.get(target['crop'], 0.0) + upgradeable, 2)
                    rem_budget -= upgrade_cost

                    log.info(f"Upgraded {upgradeable}ac {cheap_crop}→{target['crop']}, cost +Rs{upgrade_cost:.0f}")

                    # Remove the cheap crop entry if fully replaced
                    if alloc[cheap_crop] <= 0:
                        del alloc[cheap_crop]
                    break   # move to next cheap crop after one upgrade

        # ── Build result ──────────────────────────────────────────────────────
        crop_info_map = CFG.CROP_DB
        total_acres    = sum(alloc.values())
        allocations: list[CropAllocation] = []

        for crop, acres in alloc.items():
            if acres <= 0:
                continue
            cand_data = next((c for c in candidates if c["crop"] == crop), None)
            if cand_data is None:
                continue
            cost    = acres * cand_data["cost_pa"]
            revenue = acres * cand_data["revenue_pa"]
            profit  = acres * cand_data["profit_pa"]
            info    = crop_info_map.get(crop, {})
            allocations.append(CropAllocation(
                crop        = crop,
                icon        = info.get("icon", "🌿"),
                color       = info.get("color", "#00e87a"),
                acres       = round(acres, 2),
                cost        = round(cost, 2),
                revenue     = round(revenue, 2),
                profit      = round(profit, 2),
                margin_pct  = round(cand_data["pred_margin"], 2),
                pct_of_land = round((acres / max(total_acres, 0.01)) * 100, 2),
                market_price_qtl = cand_data.get("market_price_qtl")
            ))

        # Sort allocations by profit descending for display
        allocations.sort(key=lambda a: a.profit, reverse=True)

        total_cost    = sum(a.cost for a in allocations)
        total_revenue = sum(a.revenue for a in allocations)
        total_profit  = sum(a.profit for a in allocations)
        roi_pct       = round((total_profit / max(total_cost, 1)) * 100, 2)

        # ── Step 5: Compute Budget Advisory Fields ──
        remaining_unplanted = land_acres - total_acres

        if remaining_unplanted >= CFG.ACRE_STEP:
            # Find cheapest viable crop to estimate shortfall
            viable_crops = [cand['crop'] for cand in candidates]
            cheapest_cost_pa = min(
                CROP_COSTS[c] for c in SUPPORTED_CROPS
                if c in viable_crops
            )
            budget_shortfall = round(remaining_unplanted * cheapest_cost_pa, 2)
            budget_exhausted = True
        else:
            budget_shortfall = 0.0
            budget_exhausted = False

        budget_utilization_pct = round((total_cost / max(budget_inr, 1)) * 100, 1)

        # If more than 10% of budget remains unspent after the upgrade pass,
        # the budget exceeds what this soil+land combination can absorb
        if (budget_inr - total_cost) > (budget_inr * 0.10):
            remaining = round(budget_inr - total_cost, 0)
            budget_surplus_advisory = (
                f"Your budget has Rs{remaining:,.0f} more than needed for "
                f"{land_acres}ac of {soil_type.replace('_',' ')}. "
                f"Consider increasing land size or adjusting budget."
            )
        else:
            budget_surplus_advisory = ""

        return FathomResult(
            allocations    = allocations,
            total_acres    = round(total_acres, 2),
            total_cost     = round(total_cost, 2),
            total_revenue  = round(total_revenue, 2),
            expected_profit= round(total_profit, 2),
            roi_pct        = roi_pct,
            soil_type      = soil_type,
            soil_quality   = soil_quality,
            budget_inr     = budget_inr,
            land_acres     = land_acres,
            location_detected = location_str,
            price_source = price_source,
            budget_exhausted = budget_exhausted,
            budget_shortfall_inr = budget_shortfall,
            budget_utilization_pct = budget_utilization_pct,
            budget_surplus_advisory = budget_surplus_advisory
        )
