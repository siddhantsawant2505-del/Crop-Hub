"""
config.py — Fathom Layer single source of truth.
Every constant, file path, and hyperparameter lives here.
No other module should hardcode values that belong in this file.
"""

import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any

# Load environment variables from .env file
load_dotenv()

# ── Package root: the directory that contains this file ──────────────────────
_PACKAGE_ROOT = Path(__file__).parent


@dataclass
class FathomConfig:
    # ── File Paths ────────────────────────────────────────────────────────────
    RAW_CROP_REC_PATH: Path = _PACKAGE_ROOT / "data" / "raw" / "crop_recommendation.csv"
    RAW_FERTILIZER_PATH: Path = _PACKAGE_ROOT / "data" / "raw" / "fertilizer_prediction.csv"
    RAW_YIELD_PATH: Path = _PACKAGE_ROOT / "data" / "raw" / "india_crop_yield.csv"
    PROCESSED_DIR: Path = _PACKAGE_ROOT / "data" / "processed"
    MODELS_DIR: Path = _PACKAGE_ROOT / "models"
    EVAL_DIR: Path = _PACKAGE_ROOT / "evaluation"

    # ── Data Split Ratios ─────────────────────────────────────────────────────
    TRAIN_RATIO: float = 0.80
    VAL_RATIO: float = 0.10
    TEST_RATIO: float = 0.10
    RANDOM_STATE: int = 42

    # ── Random Forest Hyperparameters (yield model) ───────────────────────────
    RF_N_ESTIMATORS: int = 200
    RF_MAX_DEPTH: int = 10
    RF_MIN_SAMPLES_LEAF: int = 3
    RF_N_JOBS: int = -1

    # ── XGBoost Hyperparameters (margin + suitability models) ─────────────────
    XGB_N_ESTIMATORS: int = 300
    XGB_MAX_DEPTH: int = 6
    XGB_LEARNING_RATE: float = 0.03
    XGB_SUBSAMPLE: float = 0.8
    XGB_EARLY_STOPPING: int = 20

    # ── Optimizer Constraints ─────────────────────────────────────────────────
    MAX_SINGLE_CROP_PCT: float = 0.60   # max fraction of land for any one crop
    ACRE_STEP: float = 0.25             # minimum allocation granularity (acres)
    MIN_BUDGET_INR: float = 5_000.0
    MAX_LAND_ACRES: float = 10_000.0
    MIN_SUITABILITY_SCORE: float = 0.30
    PRIORITIZE_UTILIZATION: bool = True  # Ensures 100% land coverage
    OVERHEAD_PCT: float = 0.25           # Logistics, harvest, market fees (reduces revenue)
    MAX_POSSIBLE_MARGIN: float = 0.40    # Caps profit margin for financial realism
    UTILIZATION_WEIGHT: float = 0.85     # Favor coverage over per-acre profit when budget is tight

    # ── Market Price API (data.gov.in) ────────────────────────────────────────
    # Register at https://data.gov.in to get your API key
    AGMARKNET_API_KEY: str = os.getenv("AGMARKNET_API_KEY", "579b464db66ec23bdd0000016dc65698281b4f374b8834ad0d49ec10")
    AGMARKNET_RESOURCE_ID: str = os.getenv("AGMARKNET_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
    FATHOM_ADMIN_TOKEN: str = os.getenv("FATHOM_ADMIN_TOKEN", "fathom-admin-secret-2024")

    # ── MSP Prices INR / quintal (2023-24 Government of India) ───────────────
    MSP_PRICES: Dict[str, float] = field(default_factory=lambda: {
        "Rice":      2183,
        "Wheat":     2275,
        "Cotton":    6620,
        "Soybean":   4600,
        "Maize":     2090,
        "Groundnut": 6377,
        "Sugarcane":  315,
        "Lentils":   6425,
    })

    # ── Soil Boost Multipliers ────────────────────────────────────────────────
    SOIL_BOOST: Dict[str, float] = field(default_factory=lambda: {
        "Black_Soil":    1.20,
        "Alluvial_Soil": 1.15,
        "Red_Soil":      1.00,
        "Yellow_Soil":   0.95,
        "Laterite_Soil": 0.90,
        "Mountain_Soil": 0.88,
        "Arid_Soil":     0.80,
    })

    # ── Crop Database ─────────────────────────────────────────────────────────
    # Comprehensive metadata per crop used by optimizer and pipeline.
    # cost_per_acre_inr: typical cultivation cost (seed + labour + inputs)
    # yield_fallback_qtl: fallback yield quintal/acre when yield DS has no data
    CROP_DB: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "Rice": {
            "best_soils": ["Alluvial_Soil", "Yellow_Soil"],
            "ok_soils":   ["Black_Soil", "Red_Soil", "Mountain_Soil"],
            "cost_per_acre_inr": 8_500,
            "yield_fallback_qtl": 20.0,
            "season": "Kharif",
            "icon": "🌾",
            "color": "#c49a6c",
        },
        "Wheat": {
            "best_soils": ["Alluvial_Soil", "Black_Soil"],
            "ok_soils":   ["Yellow_Soil", "Mountain_Soil"],
            "cost_per_acre_inr": 7_500,
            "yield_fallback_qtl": 16.0,
            "season": "Rabi",
            "icon": "🌿",
            "color": "#ffb955",
        },
        "Cotton": {
            "best_soils": ["Black_Soil"],
            "ok_soils":   ["Alluvial_Soil", "Red_Soil"],
            "cost_per_acre_inr": 12_000,
            "yield_fallback_qtl": 8.0,
            "season": "Kharif",
            "icon": "🌸",
            "color": "#60b4ff",
        },
        "Soybean": {
            "best_soils": ["Black_Soil", "Alluvial_Soil"],
            "ok_soils":   ["Red_Soil", "Yellow_Soil", "Mountain_Soil"],
            "cost_per_acre_inr": 8_000,
            "yield_fallback_qtl": 10.0,
            "season": "Kharif",
            "icon": "🫘",
            "color": "#00e87a",
        },
        "Maize": {
            "best_soils": ["Alluvial_Soil", "Red_Soil"],
            "ok_soils":   ["Black_Soil", "Yellow_Soil", "Mountain_Soil"],
            "cost_per_acre_inr": 7_000,
            "yield_fallback_qtl": 22.0,
            "season": "Kharif",
            "icon": "🌽",
            "color": "#f5a623",
        },
        "Groundnut": {
            "best_soils": ["Red_Soil", "Yellow_Soil", "Arid_Soil"],
            "ok_soils":   ["Alluvial_Soil", "Black_Soil"],
            "cost_per_acre_inr": 9_000,
            "yield_fallback_qtl": 9.0,
            "season": "Kharif",
            "icon": "🥜",
            "color": "#d4a574",
        },
        "Sugarcane": {
            "best_soils": ["Alluvial_Soil", "Black_Soil"],
            "ok_soils":   ["Yellow_Soil", "Red_Soil"],
            "cost_per_acre_inr": 16_000,
            "yield_fallback_qtl": 300.0,
            "season": "Annual",
            "icon": "🎋",
            "color": "#7fce78",
        },
        "Lentils": {
            "best_soils": ["Alluvial_Soil", "Black_Soil"],
            "ok_soils":   ["Mountain_Soil", "Yellow_Soil"],
            "cost_per_acre_inr": 5_000,
            "yield_fallback_qtl": 6.0,
            "season": "Rabi",
            "icon": "🫛",
            "color": "#c084fc",
        },
    })


# ── Module-level singleton ────────────────────────────────────────────────────
CFG = FathomConfig()

# ── Convenience dicts derived from CROP_DB ────────────────────────────────────
CROP_COSTS: Dict[str, float] = {k: v["cost_per_acre_inr"] for k, v in CFG.CROP_DB.items()}
FALLBACK_YIELDS: Dict[str, float] = {k: v["yield_fallback_qtl"] for k, v in CFG.CROP_DB.items()}
SUPPORTED_SOIL_TYPES: List[str] = list(CFG.SOIL_BOOST.keys())
SUPPORTED_CROPS: List[str] = list(CFG.CROP_DB.keys())
