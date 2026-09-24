"""
tests/test_models.py
Requires trained models (run data_pipeline + train first).
Tests value ranges and determinism of all three models.
"""

from __future__ import annotations

import pytest
import numpy as np
import joblib

from .config import CFG, SUPPORTED_CROPS, SUPPORTED_SOIL_TYPES

# Skip entire module if models not yet trained
pytestmark = pytest.mark.skipif(
    not (CFG.MODELS_DIR / "model_metadata.json").exists(),
    reason="Models not trained yet. Run: python -m train",
)


@pytest.fixture(scope="module")
def artifacts():
    """Load all model artifacts once for the module."""
    return {
        "yield_model":  joblib.load(CFG.MODELS_DIR / "yield_model.joblib"),
        "margin_model": joblib.load(CFG.MODELS_DIR / "margin_model.joblib"),
        "suit_model":   joblib.load(CFG.MODELS_DIR / "suitability_model.joblib"),
        "encoders":     joblib.load(CFG.MODELS_DIR / "label_encoders.joblib"),
        "feat_lists":   joblib.load(CFG.MODELS_DIR / "feature_lists.joblib"),
    }


def _encode_safe(le, val: str) -> int:
    try:
        return int(le.transform([val])[0])
    except ValueError:
        return 0


def _build_row(artifacts, soil_type: str, crop: str) -> dict:
    """Build a minimal feature row for the given soil+crop combo."""
    encoders   = artifacts["encoders"]
    feat_lists = artifacts["feat_lists"]

    info   = CFG.CROP_DB.get(crop, {})
    season = info.get("season", "Kharif")

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
        "soil_type_enc":      _encode_safe(encoders["soil_type"], soil_type),
        "crop_enc":           _encode_safe(encoders["crop"],      crop),
        "season_enc":         _encode_safe(encoders["season"],    season),
        "soil_quality_score": 60.0,
        "N":          npk["N"], "P": npk["P"], "K": npk["K"],
        "ph":         npk["ph"],
        "rainfall":   npk["rainfall"],
        "humidity":   npk["humidity"],
        "temperature": npk["temperature"],
        "predicted_yield":  0.0,
        "predicted_margin": 0.0,
        "budget_per_acre":  feat_lists["median_budget_per_acre"],
    }


# ── Yield model tests ──────────────────────────────────────────────────────────
class TestYieldModel:

    def test_predictions_positive(self, artifacts):
        """All yield predictions must be positive."""
        model    = artifacts["yield_model"]
        y_feats  = artifacts["feat_lists"]["yield_features_used"]
        for crop in SUPPORTED_CROPS:
            for soil in SUPPORTED_SOIL_TYPES:
                row = _build_row(artifacts, soil, crop)
                x   = np.array([[row.get(f, 0.0) for f in y_feats]])
                pred = float(model.predict(x)[0])
                assert pred > 0, f"Non-positive yield for {crop}/{soil}: {pred}"

    def test_predictions_in_range(self, artifacts):
        """Yield predictions should be within 1–100 qtl/acre."""
        model   = artifacts["yield_model"]
        y_feats = artifacts["feat_lists"]["yield_features_used"]
        for crop in SUPPORTED_CROPS:
            row = _build_row(artifacts, "Alluvial_Soil", crop)
            x   = np.array([[row.get(f, 0.0) for f in y_feats]])
            pred = float(model.predict(x)[0])
            assert 0.5 <= pred <= 500, (
                f"Yield out of expected range for {crop}: {pred:.2f}"
            )

    def test_determinism(self, artifacts):
        """Same input must always return the same output."""
        model   = artifacts["yield_model"]
        y_feats = artifacts["feat_lists"]["yield_features_used"]
        row = _build_row(artifacts, "Black_Soil", "Cotton")
        x   = np.array([[row.get(f, 0.0) for f in y_feats]])
        p1  = model.predict(x)[0]
        p2  = model.predict(x)[0]
        assert p1 == p2, "Yield model is not deterministic"


# ── Margin model tests ─────────────────────────────────────────────────────────
class TestMarginModel:

    def test_predictions_in_range(self, artifacts):
        """Margin predictions should be between 0–85%."""
        model   = artifacts["margin_model"]
        y_model = artifacts["yield_model"]
        y_feats = artifacts["feat_lists"]["yield_features_used"]
        m_feats = artifacts["feat_lists"]["margin_features_used"]

        for crop in SUPPORTED_CROPS:
            row = _build_row(artifacts, "Alluvial_Soil", crop)
            x_y  = np.array([[row.get(f, 0.0) for f in y_feats]])
            pred_yield = float(y_model.predict(x_y)[0])
            row["predicted_yield"] = pred_yield
            x_m  = np.array([[row.get(f, 0.0) for f in m_feats]])
            pred_margin = float(model.predict(x_m)[0])
            assert -5 <= pred_margin <= 90, (
                f"Margin out of range for {crop}: {pred_margin:.2f}%"
            )

    def test_determinism(self, artifacts):
        model   = artifacts["margin_model"]
        m_feats = artifacts["feat_lists"]["margin_features_used"]
        row = _build_row(artifacts, "Black_Soil", "Wheat")
        row["predicted_yield"] = 15.0
        x   = np.array([[row.get(f, 0.0) for f in m_feats]])
        p1  = model.predict(x)[0]
        p2  = model.predict(x)[0]
        assert p1 == p2, "Margin model is not deterministic"


# ── Suitability model tests ────────────────────────────────────────────────────
class TestSuitabilityModel:

    def test_probabilities_valid(self, artifacts):
        """Suitability predict_proba output must be valid probability (0–1) for all combos."""
        model   = artifacts["suit_model"]
        s_feats = artifacts["feat_lists"]["suit_features_used"]

        for crop in SUPPORTED_CROPS:
            for soil in SUPPORTED_SOIL_TYPES:
                row = _build_row(artifacts, soil, crop)
                row["predicted_yield"]  = 15.0
                row["predicted_margin"] = 35.0
                x   = np.array([[row.get(f, 0.0) for f in s_feats]])
                proba = model.predict_proba(x)[0]
                assert proba.shape == (2,), f"Expected shape (2,), got {proba.shape}"
                assert abs(proba.sum() - 1.0) < 1e-5, (
                    f"Probabilities don't sum to 1 for {crop}/{soil}: {proba}"
                )
                assert all(0 <= p <= 1 for p in proba), (
                    f"Probability out of [0,1] for {crop}/{soil}: {proba}"
                )

    def test_determinism(self, artifacts):
        model   = artifacts["suit_model"]
        s_feats = artifacts["feat_lists"]["suit_features_used"]
        row = _build_row(artifacts, "Alluvial_Soil", "Rice")
        row["predicted_yield"]  = 20.0
        row["predicted_margin"] = 40.0
        x   = np.array([[row.get(f, 0.0) for f in s_feats]])
        p1  = model.predict_proba(x)[0, 1]
        p2  = model.predict_proba(x)[0, 1]
        assert p1 == p2, "Suitability model is not deterministic"
