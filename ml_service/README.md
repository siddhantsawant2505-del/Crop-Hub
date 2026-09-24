# CropHub — ML Service

The unified **Python FastAPI** backend for CropHub. All three ML/data layers run as a **single process on port 8000**, mounted as sub-applications under one FastAPI app.

> Previously each layer ran on its own port (8000–8002). They were consolidated to eliminate port conflicts, share one virtual environment, and simplify deployment.

---

## Layers

| Mount path | Layer | What it does |
|---|---|---|
| `/terra` | **Terra Layer** | Accepts a soil photograph. Runs a hybrid MobileNetV2 + GLCM neural network to classify soil type, computes a quality score (0–100), and returns a full agronomic report. |
| `/fathom` | **Fathom Layer** | Accepts soil context + land area + budget. Runs a stacked ML pipeline (Random Forest → XGBoost × 2) and a greedy allocator to return a financially-optimised crop-mix plan. |
| `/logistics` | **Logistics Layer** | Accepts GPS + Fathom crop allocations. Discovers nearby APMC mandis, fetches live Agmarknet prices, and returns each mandi ranked by true net profit after all deductions. |

Each layer has its own subfolder with an internal `README.md` for detailed technical documentation.

---

## Project Structure

```
ml_service/
├── main.py                    # Root FastAPI app — mounts /terra, /fathom, /logistics
├── requirements.txt           # Unified pip dependencies for all three layers
├── .env                       # Shared environment variables (gitignored)
├── .gitignore
│
├── terra_layer/
│   ├── main.py                # FastAPI sub-app
│   ├── analyzer.py            # TerraAnalyzer — core inference engine
│   ├── train_model.py         # Full MobileNetV2 + GLCM training pipeline
│   ├── fit_scaler_only.py     # Refit StandardScaler without full retrain
│   ├── clean_dataset.py       # Dataset audit and cleanup utilities
│   ├── model.keras            # Trained hybrid model          [gitignored]
│   ├── specialist_laterite_red.keras  # Binary specialist model [gitignored]
│   ├── scaler.pkl             # Fitted StandardScaler          [gitignored]
│   └── dataset/               # Training images                [gitignored]
│
├── fathom_layer/
│   ├── app.py                 # FastAPI sub-app
│   ├── optimizer.py           # FathomOptimizer — inference + greedy allocation
│   ├── train.py               # Trains all 3 stacked ML models
│   ├── data_pipeline.py       # 8-step data preprocessing pipeline
│   ├── evaluate.py            # Model evaluation + report generation
│   ├── market_service.py      # Live Agmarknet prices + Nominatim geocoding
│   ├── config.py              # FathomConfig dataclass — all constants
│   ├── data/                  # Raw CSVs + processed splits  [gitignored]
│   └── models/                # Trained .joblib model files   [gitignored]
│
└── logistics_layer/
    ├── app.py                 # FastAPI sub-app
    ├── optimizer.py           # Async profit optimization pipeline
    ├── market_fetcher.py      # Agmarknet API client + 3-tier fallback + cache
    ├── mandi_discovery.py     # Haversine filter + progressive radius relaxation
    ├── distance_service.py    # Haversine formula + road-correction factor
    ├── schemas.py             # Pydantic v2 request/response models
    ├── config.py              # LogisticsConfig dataclass — all constants
    └── data/
        └── mandis_india.json  # Curated APMC mandi dataset    [tracked in git]
```

---

## Quick Start

### 1. Create the virtual environment

```powershell
cd ml_service
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create `ml_service/.env` (gitignored):

```env
# Agmarknet live prices  (data.gov.in — register for a free key)
AGMARKNET_API_KEY=your_key_here
AGMARKNET_RESOURCE_ID=9ef842fd-9a74-4050-a155-397d9013c4f9

# Admin tokens
FATHOM_ADMIN_TOKEN=your_fathom_admin_token
LOGISTICS_ADMIN_TOKEN=your_logistics_admin_token

# Optional — override defaults
DEFAULT_SEARCH_RADIUS_KM=150
TRANSPORT_RATE_PER_KM_PER_QTL=8.5
```

### 3. Train models (first run only)

**Terra Layer** — place the CyAUG soil image dataset at `terra_layer/dataset/CyAUG-Dataset/<ClassName>/`:
```powershell
python terra_layer/train_model.py
```

**Fathom Layer** — place the three Kaggle CSVs at `fathom_layer/data/raw/`:
```powershell
python -m fathom_layer.data_pipeline
python -m fathom_layer.train
```

**Logistics Layer** — no training step required.

### 4. Start the server

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Health Checks

| URL | Description |
|---|---|
| `http://localhost:8000/health` | Root — all three layers loaded |
| `http://localhost:8000/terra/health` | Terra Layer |
| `http://localhost:8000/fathom/health` | Fathom Layer |
| `http://localhost:8000/logistics/health` | Logistics Layer + API key status |

---

## API Reference

### Terra Layer — `/terra`

| Method | Path | Description |
|---|---|---|
| `POST` | `/terra/api/analyze` | `multipart/form-data`: image + lat, lon, survey JSON → full soil report |
| `GET` | `/terra/health` | Health check |
| `GET` | `/terra/docs` | Swagger UI |

---

### Fathom Layer — `/fathom`

| Method | Path | Description |
|---|---|---|
| `POST` | `/fathom/recommend` | `{ soil_type, soil_quality, land_acres, budget_inr, lat?, lon? }` → crop allocation plan |
| `GET` | `/fathom/soils` | All 7 supported soil types with boost multipliers |
| `GET` | `/fathom/crops` | All 8 supported crops with MSP prices and soil compatibility |
| `GET` | `/fathom/model-info` | Training metadata + evaluation metrics for all 3 models |
| `POST` | `/fathom/retrain` | Background retrain — requires `X-Admin-Token` header |
| `GET` | `/fathom/health` | Health check |
| `GET` | `/fathom/docs` | Swagger UI |

---

### Logistics Layer — `/logistics`

| Method | Path | Description |
|---|---|---|
| `POST` | `/logistics/optimize` | `{ lat, lon, allocations, quantity_qtl, radius_km }` → ranked mandis per crop |
| `POST` | `/logistics/mandis/nearby` | `{ lat, lon, radius_km }` → nearby mandi list (map pins) |
| `GET` | `/logistics/crops` | Supported crops + Agmarknet commodity name mapping + MSP |
| `GET` | `/logistics/config/fees` | Fee structure (transport rate, commission %, rent %, etc.) |
| `GET` | `/logistics/health` | Health check + Agmarknet key status |
| `GET` | `/logistics/docs` | Swagger UI |

---

## Dependencies

```
# Core
fastapi >= 0.110.0
uvicorn[standard] >= 0.27.0
pydantic >= 2.6.0
python-dotenv >= 1.0.1
httpx >= 0.27.0
requests >= 2.31.0
python-multipart >= 0.0.9

# Terra Layer
tensorflow >= 2.16.1
keras >= 3.0.0
pillow >= 10.2.0
numpy >= 1.26.0
opencv-python >= 4.10.0
scikit-image >= 0.23.0

# Fathom Layer
scikit-learn >= 1.4.0
xgboost >= 2.0.0
imbalanced-learn >= 0.12.0
pandas >= 2.2.0
joblib >= 1.3.0
matplotlib >= 3.8.0
seaborn >= 0.13.0

# Testing
pytest >= 8.0.0
pytest-asyncio >= 0.23.0
```

---

## Standalone Development

Each sub-app can be run independently for isolated development:

```powershell
# Terra only (port 8001)
uvicorn terra_layer.main:app --port 8001 --reload

# Fathom only (port 8002)
uvicorn fathom_layer.app:app --port 8002 --reload

# Logistics only (port 8003)
uvicorn logistics_layer.app:app --port 8003 --reload
```

> When running standalone, update the corresponding `*_LAYER_URL` env var in `server/.env` to point at the correct port.
