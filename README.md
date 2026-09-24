# 🌾 CropHub — Agricultural Intelligence Platform

CropHub is an end-to-end agricultural decision support system that combines computer vision (CV), machine learning (ML), and real-time market data to help farmers **analyze their soil**, **plan the most profitable crop mix**, and **find the best market to sell** — all in one integrated platform.

---

## 📐 System Architecture

CropHub is a **polyglot microservices monorepo** composed of four independently deployable layers that communicate over HTTP:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CropHub Platform                               │
│                                                                             │
│  ┌────────────┐    ┌────────────┐    ┌──────────────────────────────────┐  │
│  │   Client   │───▶│   Server   │───▶│     Unified ML Service           │  │
│  │ (React/TS) │    │ (Node.js / │    │     (FastAPI · Port 8000)        │  │
│  │ Port: 8080 │    │  Express)  │    │  ┌──────────────────────────┐   │  │
│  │            │    │ Port: 5000 │    │  │  /terra   — Terra Layer  │   │  │
│  └────────────┘    └────────────┘    │  │  /fathom  — Fathom Layer │   │  │
│                                      │  │  /logistics — Logistics  │   │  │
│                                      │  └──────────────────────────┘   │  │
│                                      └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Layer | Technology | Port | Responsibility |
|---|---|---|---|
| **Client** | React 18, TypeScript, Vite, Tailwind CSS | 8080 | User interface — soil analysis, crop recommendations, logistics planning |
| **Server** | Node.js, Express, MongoDB (Mongoose) | 5000 | Auth, persistence, secure API proxy to ML service |
| **Terra Layer** | Python, FastAPI, TensorFlow/Keras (MobileNetV2) | 8000 `/terra` | Soil image classification via hybrid CNN + GLCM texture analysis |
| **Fathom Layer** | Python, FastAPI, scikit-learn, XGBoost | 8000 `/fathom` | ML-driven crop mix optimisation and financial modelling |
| **Logistics Layer** | Python, FastAPI, Agmarknet API | 8000 `/logistics` | Real-time mandi discovery + market arbitrage profit optimisation |

> All three Python ML layers are unified into a **single FastAPI process** (`ml_service/main.py`) running on port 8000 to avoid port conflicts and simplify deployment.

---

## 🗂️ Directory Structure

```
CropHub/
├── client/             # React + Vite frontend application
├── server/             # Node.js / Express REST API + MongoDB integration
├── ml_service/         # Unified Python FastAPI service (Terra + Fathom + Logistics)
│   ├── main.py             # Root FastAPI app — mounts all three sub-apps
│   ├── requirements.txt    # Combined pip dependencies for all layers
│   ├── .env                # Unified environment variables
│   ├── terra_layer/        # Soil image CNN classification microservice
│   ├── fathom_layer/       # Crop recommendation + financial optimisation
│   └── logistics_layer/    # APMC mandi discovery + profit arbitrage engine
├── ARRANGEMENTS.md     # Real-world deployment checklist
└── README.md           # This file
```

---

## 🔄 End-to-End Data Flow

```
USER UPLOADS SOIL IMAGE
        │
        ▼
   [Client: TerraLayer Page]
   Fills survey (wetness, texture), provides GPS location, uploads image
        │
        ▼ POST /api/soil/analyze (multipart/form-data)
   [Server: soilController]
   Proxies request → ml_service /terra/api/analyze
        │
        ▼
   [Terra Layer: TerraAnalyzer]
   1. Validates image (size, format, dimensions)
   2. Runs Hybrid CNN (MobileNetV2 + GLCM) → soil type + confidence
   3. Fetches Open-Meteo weather data in parallel
   4. Queries ISRIC SoilGrids for regional soil profile (clay%, pH, N)
   5. Returns report: soil type, health, quality score (0–100), crop hints
        │
        ▼ (soil_type + soil_quality_score carried to next step)
   [Client: FathomLayer Page]
   User inputs land area (acres) and budget (INR)
        │
        ▼ POST /api/fathom/recommend
   [Server: fathomController]
   Proxies request → ml_service /fathom/recommend
        │
        ▼
   [Fathom Layer: FathomOptimizer]
   1. Fetches live Agmarknet market prices (with MSP fallback)
   2. Runs stacked ML pipeline: Yield → Margin → Suitability models
   3. Greedy allocation respecting budget, land, and diversity constraints
   4. Returns per-crop allocation: acres, cost, revenue, profit, ROI
        │
        ▼ ("Proceed to Logistics Plan" button passes result via router state)
   [Client: Logistics Page]
   User detects GPS, sets quantity (qtl) and search radius
        │
        ▼ POST /api/logistics/optimize
   [Server: logisticsController]
   Proxies request → ml_service /logistics/optimize
        │
        ▼
   [Logistics Layer: run_optimization]
   1. Discovers nearby APMC mandis via Haversine (radius auto-relaxes)
   2. Fetches Agmarknet live prices per crop × mandi (concurrent)
   3. Computes True Net Profit: Gross − Transport − Rent − Commission − Labor
   4. Ranks mandis by net profit per crop; annotates best pick
   5. Returns ranked results + overall best crop + best mandi
        │
        ▼
   [Client: Interactive map + ranked mandi cards + full comparison table]
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Node.js | ≥ 18 | Server and Client |
| Python | ≥ 3.10 | Unified ML service |
| MongoDB Atlas | any | Database |
| npm / bun | latest | Client package management |

---

### 1. Clone and Install

```bash
git clone https://github.com/<your-org>/crophub.git
cd CropHub
```

**Client:**
```bash
cd client && npm install
```

**Server:**
```bash
cd server && npm install
```

**Unified ML Service:**
```bash
cd ml_service
python -m venv venv
.\venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

---

### 2. Environment Variables

Each layer requires its own `.env` file. See the individual `README.md` in each sub-folder for the full variable list.

| Layer | `.env` location |
|---|---|
| Server | `server/.env` |
| ML Service | `ml_service/.env` |

---

### 3. Train Models (First Run Only)

**Terra Layer** — place the CyAUG soil image dataset at `ml_service/terra_layer/dataset/CyAUG-Dataset/<ClassName>/`:
```bash
cd ml_service
.\venv\Scripts\activate
python terra_layer/train_model.py
```

**Fathom Layer** — place the three Kaggle CSVs at `ml_service/fathom_layer/data/raw/`:
```bash
python -m fathom_layer.data_pipeline
python -m fathom_layer.train
```

---

### 4. Start All Services

Open three terminals:

```bash
# Terminal 1 — Client (http://localhost:8080)
cd client && npm run dev

# Terminal 2 — Server (http://localhost:5000)
cd server && npm run dev

# Terminal 3 — Unified ML Service (http://localhost:8000)
cd ml_service
.\venv\Scripts\activate
uvicorn main:app --reload
```

Navigate to `http://localhost:8080`.

---

## 📡 API Summary

| Service | Base URL | Key Endpoints |
|---|---|---|
| Server | `http://localhost:5000/api` | `/auth`, `/soil`, `/crop`, `/market`, `/fathom`, `/logistics` |
| Terra Layer | `http://localhost:8000/terra` | `POST /api/analyze`, `GET /health` |
| Fathom Layer | `http://localhost:8000/fathom` | `POST /recommend`, `GET /soils`, `GET /crops`, `GET /model-info` |
| Logistics Layer | `http://localhost:8000/logistics` | `POST /optimize`, `POST /mandis/nearby`, `GET /crops`, `GET /config/fees` |
| ML Health | `http://localhost:8000/health` | Unified health check for all three layers |

---

## 🛠️ Tech Stack Summary

| Category | Technologies |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts, Framer Motion, pigeon-maps |
| Backend | Node.js, Express.js, MongoDB, Mongoose, JWT, Multer, Axios |
| ML / CV | TensorFlow/Keras, MobileNetV2, scikit-learn, XGBoost, imbalanced-learn, OpenCV, scikit-image |
| APIs | Open-Meteo (weather), ISRIC SoilGrids (soil profile), Agmarknet/data.gov.in (market prices) |
| DevTools | Nodemon, Uvicorn, Vite HMR, pytest, Playwright |
