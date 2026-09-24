"""
tests/test_api.py
FastAPI endpoint tests using httpx.AsyncClient with TestClient.
Tests /health, /recommend (valid + invalid), and /model-info.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from .config import CFG
from .optimizer import CropAllocation, FathomResult


# ── Mock optimizer fixtures ────────────────────────────────────────────────────
def _mock_result() -> FathomResult:
    """Build a synthetic FathomResult for mocking."""
    return FathomResult(
        allocations=[
            CropAllocation(
                crop="Rice", icon="🌾", color="#c49a6c",
                acres=5.0, cost=51_000.0, revenue=110_000.0,
                profit=59_000.0, margin_pct=53.6, pct_of_land=50.0,
            ),
            CropAllocation(
                crop="Wheat", icon="🌿", color="#ffb955",
                acres=5.0, cost=34_000.0, revenue=72_500.0,
                profit=38_500.0, margin_pct=46.9, pct_of_land=50.0,
            ),
        ],
        total_acres=10.0,
        total_cost=85_000.0,
        total_revenue=182_500.0,
        expected_profit=97_500.0,
        roi_pct=114.7,
        soil_type="Black_Soil",
        soil_quality=75.0,
        budget_inr=100_000.0,
        land_acres=10.0,
    )


@pytest.fixture(scope="module")
def test_app():
    """
    Import the FastAPI app, patch out model loading and optimizer,
    and return a synchronous TestClient.
    """
    import app as fathom_app

    mock_opt = MagicMock()
    mock_opt.optimise.return_value = _mock_result()

    with patch.object(fathom_app, "_optimizer", mock_opt):
        # Also patch model-info file
        with patch("app.CFG") as mock_cfg:
            # Keep real CFG values but override MODELS_DIR
            mock_cfg.MODELS_DIR = CFG.MODELS_DIR
            mock_cfg.MIN_BUDGET_INR = CFG.MIN_BUDGET_INR
            mock_cfg.MAX_LAND_ACRES = CFG.MAX_LAND_ACRES
            mock_cfg.SOIL_BOOST = CFG.SOIL_BOOST
            mock_cfg.CROP_DB = CFG.CROP_DB
            mock_cfg.MSP_PRICES = CFG.MSP_PRICES

        client = TestClient(fathom_app.app, raise_server_exceptions=False)
        yield client, mock_opt


# ── Health check ──────────────────────────────────────────────────────────────
class TestHealth:
    def test_health_returns_200(self, test_app):
        client, _ = test_app
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── /recommend ────────────────────────────────────────────────────────────────
class TestRecommend:

    _VALID_PAYLOAD = {
        "soil_type":    "Black_Soil",
        "soil_quality": 75.0,
        "land_acres":   10.0,
        "budget_inr":   100_000.0,
    }

    def test_valid_payload_returns_200(self, test_app):
        client, mock_opt = test_app
        mock_opt.optimise.return_value = _mock_result()
        resp = client.post("/recommend", json=self._VALID_PAYLOAD)
        assert resp.status_code == 200

    def test_valid_payload_schema(self, test_app):
        """Response must contain all required top-level keys."""
        client, mock_opt = test_app
        mock_opt.optimise.return_value = _mock_result()
        resp = client.post("/recommend", json=self._VALID_PAYLOAD)
        body = resp.json()
        required_keys = {
            "allocations", "total_acres", "total_cost", "total_revenue",
            "expected_profit", "roi_pct", "soil_type", "soil_quality",
            "budget_inr", "land_acres",
        }
        assert required_keys.issubset(set(body.keys()))

    def test_valid_payload_allocation_schema(self, test_app):
        """Each allocation item must contain required fields."""
        client, mock_opt = test_app
        mock_opt.optimise.return_value = _mock_result()
        resp = client.post("/recommend", json=self._VALID_PAYLOAD)
        allocs = resp.json()["allocations"]
        assert len(allocs) > 0
        alloc_keys = {"crop", "icon", "color", "acres", "cost", "revenue",
                      "profit", "margin_pct", "pct_of_land"}
        for a in allocs:
            assert alloc_keys.issubset(set(a.keys()))

    def test_budget_below_minimum_returns_422(self, test_app):
        client, _ = test_app
        payload = {**self._VALID_PAYLOAD, "budget_inr": 100.0}
        resp = client.post("/recommend", json=payload)
        assert resp.status_code == 422
        body = str(resp.json())
        assert "minimum" in body.lower() or "budget" in body.lower() or "5000" in body

    def test_invalid_soil_type_returns_422(self, test_app):
        client, _ = test_app
        payload = {**self._VALID_PAYLOAD, "soil_type": "Mud"}
        resp = client.post("/recommend", json=payload)
        assert resp.status_code == 422

    def test_zero_land_returns_422(self, test_app):
        client, _ = test_app
        payload = {**self._VALID_PAYLOAD, "land_acres": 0.0}
        resp = client.post("/recommend", json=payload)
        assert resp.status_code == 422

    def test_negative_budget_returns_422(self, test_app):
        client, _ = test_app
        payload = {**self._VALID_PAYLOAD, "budget_inr": -1000.0}
        resp = client.post("/recommend", json=payload)
        assert resp.status_code == 422

    def test_quality_out_of_range_returns_422(self, test_app):
        client, _ = test_app
        payload = {**self._VALID_PAYLOAD, "soil_quality": 150.0}
        resp = client.post("/recommend", json=payload)
        assert resp.status_code == 422


# ── /model-info ───────────────────────────────────────────────────────────────
class TestModelInfo:

    def test_model_info_schema_if_exists(self, test_app):
        """If model_metadata.json exists, validate required keys."""
        import json
        meta_path = CFG.MODELS_DIR / "model_metadata.json"
        if not meta_path.exists():
            pytest.skip("model_metadata.json not found — skipping schema test")

        client, _ = test_app
        resp = client.get("/model-info")
        if resp.status_code == 200:
            body = resp.json()
            required_keys = {"trained_at", "train_rows", "val_rows",
                             "yield_model", "margin_model", "suitability_model"}
            assert required_keys.issubset(set(body.keys()))

            for model_key in ("yield_model", "margin_model"):
                assert "val_mae"  in body[model_key]
                assert "val_rmse" in body[model_key]
                assert "val_r2"   in body[model_key]

            suit = body["suitability_model"]
            assert "val_accuracy" in suit
            assert "val_f1"       in suit
            assert "val_roc_auc"  in suit


# ── /soils ─────────────────────────────────────────────────────────────────────
class TestSoils:
    def test_soils_returns_7(self, test_app):
        client, _ = test_app
        resp = client.get("/soils")
        assert resp.status_code == 200
        assert len(resp.json()) == 7


# ── /crops ─────────────────────────────────────────────────────────────────────
class TestCrops:
    def test_crops_returns_8(self, test_app):
        client, _ = test_app
        resp = client.get("/crops")
        assert resp.status_code == 200
        assert len(resp.json()) == 8
