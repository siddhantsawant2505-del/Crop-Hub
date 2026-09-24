# 🌾 Fathom Layer — Crop-Mix Optimisation Microservice

The **Fathom Layer** is a Python-based FastAPI microservice that provides **ML-driven crop-mix optimisation**. It takes the soil type and quality score produced by the **Terra Layer**, along with the farmer's land area and budget, and returns a financially optimised, agronomically correct crop allocation plan — including predicted yield, profit margin, ROI, and live Agmarknet market prices.

> **Deployment note:** Fathom Layer runs as a sub-app mounted at `/fathom` inside the unified `ml_service` on port 8000. See `ml_service/README.md` for setup. Use standalone mode (port 8002) only for isolated development.

---

## 📐 Architecture Overview

```
fathom_layer/
├── app.py              # FastAPI sub-app — all HTTP endpoints
├── optimizer.py        # FathomOptimizer — inference + greedy allocation engine
├── train.py            # ModelTrainer — trains all 3 ML models
├── data_pipeline.py    # DataPipeline — 8-step data preprocessing pipeline
├── evaluate.py         # Model evaluation and report generation
├── market_service.py   # MarketService — live Agmarknet prices + geolocation
├── config.py           # FathomConfig — single source of truth for all constants
├── data/
│   ├── raw/            # Input CSVs (gitignored — download from Kaggle)
│   │   ├── crop_recommendation.csv
│   │   ├── fertilizer_prediction.csv
│   │   └── india_crop_yield.csv
│   └── processed/      # Auto-generated: train.csv, val.csv, test.csv (gitignored)
├── models/             # Auto-generated trained .joblib files (gitignored)
│   ├── yield_model.joblib
│   ├── margin_model.joblib
│   ├── suitability_model.joblib
│   ├── label_encoders.joblib
│   ├── scaler.joblib
│   ├── feature_lists.joblib
│   └── model_metadata.json
├── evaluation/         # Model reports and plots (gitignored)
└── tests/              # Unit and integration tests
```

---

## 🧠 How the System Works

The Fathom Layer operates in two phases: an **offline training pipeline** and an **online inference + optimisation engine**.

---

### Phase 1 — Offline: Data Pipeline + Model Training

#### Datasets Required

| File | Source | Contents |
|---|---|---|
| `crop_recommendation.csv` | [Kaggle](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset) | N, P, K, pH, rainfall, humidity, temperature, crop label |
| `fertilizer_prediction.csv` | [Kaggle](https://www.kaggle.com/datasets/gdabhishek/fertilizer-prediction) | Soil type, crop type, NPK values |
| `india_crop_yield.csv` | [Kaggle](https://www.kaggle.com/datasets/pyatakov/india-agriculture-crop-yield) | Historical crop yield by state/year (post-2010) |

Place all three files in `fathom_layer/data/raw/` before running the pipeline.

#### Data Pipeline — 8 Steps

```
Step 1 — Load & Audit
    Load all 3 CSVs, print shapes, null counts, class distributions

Step 2 — Clean
    ├─ Drop duplicates and Unnamed columns
    ├─ Rename columns (Nitrogen→N, phosphorous→P, potassium→K)
    ├─ Clip NPK/pH/rainfall to agronomic bounds
    ├─ Apply CROP_NAME_MAP (normalise, e.g. "Soyabean"→"Soybean")
    └─ Filter to 8 supported crops; clip yield outliers (mean ± 2.5σ per crop)

Step 3 — Infer Soil Type
    Rule-based assignment: Arid → Laterite → Black → Alluvial → Red → Mountain → Yellow

Step 4 — Soil Quality Score (0–100)
    N-score (20) + P-score (20) + K-score (20) + pH-score (20) + Humidity-score (20)

Step 5 — Financial Feature Engineering
    ├─ Yield (qtl/acre): India yield dataset median × quality_boost (0.8×–1.2×)
    ├─ Revenue = yield × MSP price (GoI 2023-24 rates)
    ├─ Cost = base_cost × quality_cost_multiplier
    └─ Margin % = (revenue − cost) / revenue × 100, capped at 75%

Step 6 — Suitability Label
    Binary label: soil_score (0/1/2) + quality_score (0/1) + margin_score (0/1) ≥ 2

Step 6b — Gaussian Noise Augmentation (8× expansion)
    7 synthetic copies per row with controlled Gaussian noise; targets recomputed

Step 6c — SMOTE
    Balances the suitability class distribution before train split

Step 7 — Interaction Features + Encode + Scale
    13 engineered features: NP_ratio, NK_ratio, PK_ratio, NPK_total,
    ph_rain_interact, humidity_temp_ratio, quality_yield_interact, aridity_index,
    nutrient_balance, ph_deviation, fertility_index, crop_yield_mean, crop_yield_std
    LabelEncoder on: soil_type, crop, season
    StandardScaler on all numerics (fit on train only)

Step 8 — Stratified Split & Save
    80% train / 10% val / 10% test (stratified by crop label)
```

#### Model Training — 3 Stacked Models

```
┌──────────────────────────────────────────────────────────────────┐
│                  Stacked ML Training Pipeline                     │
│                                                                   │
│  Input: 24 features (11 core + 13 interaction)                   │
│       ↓                                                           │
│  [Model 1] Random Forest Regressor — Yield Prediction            │
│       • 500 estimators, max_depth=20, min_samples_leaf=4          │
│       • 5-fold cross-validation                                   │
│       • Output: predicted_yield (qtl/acre)                        │
│       ↓ (adds predicted_yield → 25 total features)               │
│  [Model 2] XGBoost Regressor — Margin Prediction                 │
│       • 600 estimators, max_depth=6, lr=0.03                     │
│       • L1 + L2 regularisation, early stopping (patience=30)     │
│       • Output: predicted_margin (%)                              │
│       ↓ (adds predicted_margin + budget_per_acre → 27 total)     │
│  [Model 3] XGBoost Classifier — Suitability Classification       │
│       • 600 estimators, max_depth=6, gamma=0.1                   │
│       • scale_pos_weight for class imbalance                      │
│       • Output: suitability_probability (0.0–1.0)                │
└──────────────────────────────────────────────────────────────────┘
```

---

### Phase 2 — Online: Inference + Greedy Optimisation

```
Input: soil_type, soil_quality, land_acres, budget_inr, [lat, lon]
        │
        ▼
Step 0 — Resolve Location & Market Prices
        ├─ If lat/lon provided: reverse geocode → state + district (Nominatim)
        └─ Fetch Agmarknet mandi prices → crop→price dict
             └─ Fallback tier 1: state average
             └─ Fallback tier 2: Government MSP (2023-24)

Step 1 — Score All 8 Crops
    ├─ Build feature row (NPK heuristics + quality + season)
    ├─ Predict yield (RF), margin (XGB), suitability (XGB)
    ├─ Agronomic boost: +25% if crop is in best_soils for soil type
    ├─ Incompatibility penalty: ×0.2 if soil not in ok_soils
    ├─ Filter: skip if suitability_score < 0.30
    └─ Compute rank_score = profit_per_acre × utilization_penalty

Step 2 — Sort by Rank Score (descending)

Step 3 — Greedy Allocation Loop
    max_by_budget  = floor(remaining_budget / cost_per_acre / step) × step
    max_by_land    = remaining_steps × step
    max_by_diversity = floor(land × 60% / step) × step
    acres = min(all three); allocate; deduct from budget + land

Step 4 — 100% Land Utilisation Sweep
    If unplanted land remains: backfill cheapest crops until fully allocated

Step 5 — Return FathomResult
    Per-crop: crop, icon, color, acres, cost, revenue, profit, margin_pct,
              pct_of_land, market_price_qtl
    Totals: total_acres, total_cost, total_revenue, expected_profit, roi_pct,
            location_detected
```

---

## 📊 Supported Crops & MSP Prices (2023-24)

| Crop | Season | MSP (₹/qtl) | Best Soils |
|---|---|---|---|
| 🌾 Rice | Kharif | ₹2,183 | Alluvial, Yellow |
| 🌿 Wheat | Rabi | ₹2,275 | Alluvial, Black |
| 🌸 Cotton | Kharif | ₹6,620 | Black |
| 🫘 Soybean | Kharif | ₹4,600 | Black, Alluvial |
| 🌽 Maize | Kharif | ₹2,090 | Alluvial, Red |
| 🥜 Groundnut | Kharif | ₹6,377 | Red, Yellow, Arid |
| 🎋 Sugarcane | Annual | ₹315 | Alluvial, Black |
| 🫛 Lentils | Rabi | ₹6,425 | Alluvial, Black |

---

## 🔌 API Reference

When running inside the unified service, all routes are prefixed with `/fathom`.

### `POST /fathom/recommend`

**Request Body (JSON):**
```json
{
  "soil_type":    "Black_Soil",
  "soil_quality": 78.5,
  "land_acres":   5.0,
  "budget_inr":   150000,
  "lat":          18.52,
  "lon":          73.85
}
```

**Success Response (`200`):**
```json
{
  "allocations": [
    {
      "crop": "Cotton", "icon": "🌸", "color": "#60b4ff",
      "acres": 3.0, "cost": 96000, "revenue": 142800,
      "profit": 46800, "margin_pct": 32.8,
      "pct_of_land": 60.0, "market_price_qtl": 6750
    }
  ],
  "total_acres": 5.0, "total_cost": 140000,
  "total_revenue": 198500, "expected_profit": 58500,
  "roi_pct": 41.8, "soil_type": "Black_Soil",
  "soil_quality": 78.5, "budget_inr": 150000,
  "land_acres": 5.0, "location_detected": "Pune, Maharashtra"
}
```

### Other Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/fathom/soils` | All 7 soil types with boost multipliers and descriptions |
| `GET` | `/fathom/crops` | All 8 crops with cost, MSP, best/ok soils, season |
| `GET` | `/fathom/model-info` | Training timestamp, dataset sizes, and all evaluation metrics |
| `GET` | `/fathom/health` | `{ "status": "ok", "service": "fathom_layer" }` |
| `POST` | `/fathom/retrain` | Background retrain. Requires `X-Admin-Token` header. |

---

## 🚀 Setup & Running

### 1. Install Dependencies (shared with ml_service)
```powershell
cd ml_service
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Place Raw Data
Download the three Kaggle datasets and place in `fathom_layer/data/raw/`.

### 3. Run the Data Pipeline
```powershell
python -m fathom_layer.data_pipeline
```

### 4. Train the Models
```powershell
python -m fathom_layer.train
python -m fathom_layer.train --retrain   # Force retrain if models exist
```

### 5. Start Standalone (dev only)
```powershell
uvicorn fathom_layer.app:app --port 8002 --reload
```

Swagger UI: `http://localhost:8002/docs`

---

## ⚙️ Environment Variables

Read from shared `ml_service/.env`:

```env
AGMARKNET_API_KEY=your_api_key_here
AGMARKNET_RESOURCE_ID=9ef842fd-9a74-4050-a155-397d9013c4f9
FATHOM_ADMIN_TOKEN=your_admin_secret_here
```

---

## 🗂️ Configuration Reference (`config.py`)

| Constant | Value | Description |
|---|---|---|
| `TRAIN_RATIO` | 0.80 | Training split fraction |
| `MAX_SINGLE_CROP_PCT` | 0.60 | Max land fraction for one crop (diversification) |
| `ACRE_STEP` | 0.25 | Minimum allocation granularity (acres) |
| `MIN_SUITABILITY_SCORE` | 0.30 | Crops below this score are excluded |
| `OVERHEAD_PCT` | 0.25 | Post-harvest logistics overhead deducted from revenue |
| `MAX_POSSIBLE_MARGIN` | 0.40 | Profit margin capped at 40% for financial realism |
| `PRIORITIZE_UTILIZATION` | `True` | Ensures 100% land coverage even if budget is exhausted |

---

## 📦 Key Dependencies

| Package | Purpose |
|---|---|
| `fastapi` / `uvicorn` | Web framework + ASGI server |
| `scikit-learn` | Random Forest, StandardScaler, LabelEncoder, cross-validation |
| `xgboost` | Gradient Boosted Trees for margin and suitability models |
| `imbalanced-learn` | SMOTE for minority class oversampling |
| `joblib` | Model serialisation |
| `pandas` / `numpy` | Data manipulation |
| `pydantic` | Request/response validation |
| `python-dotenv` | Environment variable loading |
| `requests` | Agmarknet API + Nominatim geocoding |
