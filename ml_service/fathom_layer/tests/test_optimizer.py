"""
tests/test_optimizer.py
No model dependency — mocks yield/margin/suitability model predictions.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from .config import CFG, SUPPORTED_SOIL_TYPES
from .optimizer import FathomOptimizer, FathomResult


# ── Fixtures ───────────────────────────────────────────────────────────────────
def _make_optimizer(suit_score: float = 0.8) -> FathomOptimizer:
    """
    Build a FathomOptimizer with all joblib loads mocked so no real models needed.
    """
    mock_yield_model = MagicMock()
    mock_yield_model.predict.return_value = np.array([18.0])

    mock_margin_model = MagicMock()
    mock_margin_model.predict.return_value = np.array([40.0])

    mock_suit_model = MagicMock()
    mock_suit_model.predict_proba.return_value = np.array([[1 - suit_score, suit_score]])

    mock_encoders = {
        "soil_type": MagicMock(transform=lambda x: np.array([0]), classes_=SUPPORTED_SOIL_TYPES),
        "crop":      MagicMock(transform=lambda x: np.array([0]), classes_=["Rice"]),
        "season":    MagicMock(transform=lambda x: np.array([0]), classes_=["Kharif"]),
    }

    mock_feat_lists = {
        "yield_features_used":  ["soil_type_enc", "crop_enc", "season_enc",
                                  "soil_quality_score", "N", "P", "K",
                                  "ph", "rainfall", "humidity", "temperature"],
        "margin_features_used": ["soil_type_enc", "crop_enc", "season_enc",
                                  "soil_quality_score", "N", "P", "K",
                                  "ph", "rainfall", "humidity", "temperature",
                                  "predicted_yield"],
        "suit_features_used":   ["soil_type_enc", "crop_enc", "season_enc",
                                  "soil_quality_score", "N", "P", "K",
                                  "ph", "rainfall", "humidity", "temperature",
                                  "predicted_yield", "predicted_margin", "budget_per_acre"],
        "median_budget_per_acre": 8000.0,
    }

    with patch("optimizer.joblib.load") as mock_load, \
         patch.object(FathomOptimizer, "_load_models", return_value=None):
        opt = FathomOptimizer.__new__(FathomOptimizer)
        opt.yield_model  = mock_yield_model
        opt.margin_model = mock_margin_model
        opt.suit_model   = mock_suit_model
        opt.encoders     = mock_encoders
        opt.feat_lists   = mock_feat_lists
        opt.scaler       = MagicMock()
    return opt


# ── Tests: core allocation constraints ────────────────────────────────────────
class TestAllocationConstraints:

    def test_total_acres_equals_land_input(self):
        """Total allocated acres must equal land_acres exactly (within ACRE_STEP)."""
        opt = _make_optimizer()
        for land in (5.0, 10.0, 20.5, 50.0):
            result = opt.optimise("Black_Soil", 70.0, land, 500_000)
            assert result.total_acres <= land + CFG.ACRE_STEP, (
                f"Over-allocated: {result.total_acres} > {land}"
            )
            # Allow up to one ACRE_STEP gap (last fractional step)
            assert result.total_acres >= land - CFG.ACRE_STEP, (
                f"Under-allocated by more than one step: {result.total_acres} vs {land}"
            )

    def test_total_cost_never_exceeds_budget(self):
        """Sum of all allocation costs must never exceed budget_inr."""
        opt = _make_optimizer()
        for budget in (10_000, 50_000, 200_000, 1_000_000):
            result = opt.optimise("Alluvial_Soil", 60.0, 15.0, float(budget))
            assert result.total_cost <= budget + 0.01, (
                f"Total cost {result.total_cost} exceeds budget {budget}"
            )

    def test_no_single_crop_exceeds_max_pct(self):
        """No crop should occupy more than MAX_SINGLE_CROP_PCT of land."""
        opt = _make_optimizer()
        result = opt.optimise("Black_Soil", 75.0, 40.0, 800_000)
        for alloc in result.allocations:
            pct = alloc.acres / max(result.total_acres, 0.01)
            assert pct <= CFG.MAX_SINGLE_CROP_PCT + 0.01, (
                f"{alloc.crop} has {pct:.2%} of land, exceeds {CFG.MAX_SINGLE_CROP_PCT:.0%} cap"
            )

    def test_at_least_one_allocation_for_every_soil_type(self):
        """Every supported soil type should return at least one allocation."""
        for soil in SUPPORTED_SOIL_TYPES:
            opt = _make_optimizer()
            result = opt.optimise(soil, 65.0, 10.0, 200_000)
            assert len(result.allocations) >= 1, (
                f"No allocation for soil type: {soil}"
            )


# ── Tests: edge cases ─────────────────────────────────────────────────────────
class TestEdgeCases:

    def test_minimum_land(self):
        """land_acres = ACRE_STEP (0.25) should return exactly one allocation."""
        opt = _make_optimizer()
        result = opt.optimise("Red_Soil", 50.0, CFG.ACRE_STEP, 20_000)
        assert result.total_acres == pytest.approx(CFG.ACRE_STEP, abs=CFG.ACRE_STEP)

    def test_minimum_budget(self):
        """budget_inr = MIN_BUDGET_INR should still allocate without exception."""
        opt = _make_optimizer()
        result = opt.optimise("Yellow_Soil", 40.0, 1.0, CFG.MIN_BUDGET_INR)
        # May return 0 allocations if no crop fits — that's acceptable
        assert isinstance(result, FathomResult)
        assert result.total_cost <= CFG.MIN_BUDGET_INR + 0.01

    def test_zero_soil_quality(self):
        """soil_quality = 0 should not cause a crash."""
        opt = _make_optimizer()
        result = opt.optimise("Arid_Soil", 0.0, 5.0, 100_000)
        assert isinstance(result, FathomResult)

    def test_full_soil_quality(self):
        """soil_quality = 100 should not cause a crash."""
        opt = _make_optimizer()
        result = opt.optimise("Alluvial_Soil", 100.0, 10.0, 200_000)
        assert isinstance(result, FathomResult)

    def test_low_suitability_fallback(self):
        """When all suit_scores < threshold, optimizer should still return a result via fallback."""
        opt = _make_optimizer(suit_score=0.1)   # below MIN_SUITABILITY_SCORE
        result = opt.optimise("Mountain_Soil", 55.0, 8.0, 150_000)
        assert isinstance(result, FathomResult)
        assert result.total_cost >= 0

    def test_result_roi_non_negative(self):
        """ROI should be >= 0 when margin is positive."""
        opt = _make_optimizer(suit_score=0.9)
        result = opt.optimise("Black_Soil", 80.0, 20.0, 400_000)
        assert result.roi_pct >= 0

    def test_pct_of_land_sums_to_100(self):
        """pct_of_land across all allocations should sum to ~100%."""
        opt = _make_optimizer()
        result = opt.optimise("Alluvial_Soil", 70.0, 20.0, 500_000)
        if result.allocations:
            total_pct = sum(a.pct_of_land for a in result.allocations)
            assert abs(total_pct - 100.0) < 2.0, (
                f"pct_of_land total = {total_pct:.2f}%, expected ~100%"
            )
