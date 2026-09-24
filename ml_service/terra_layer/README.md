# 🌍 Terra Layer — Soil Intelligence Microservice

The **Terra Layer** is a Python-based FastAPI microservice responsible for **soil image classification** and **soil health reporting**. It is the first analytical step in the CropHub pipeline — a farmer uploads a photo of their soil, and Terra Layer returns a structured report including the detected soil type, health status, quality score (0–100), and crop recommendations. This output is then consumed by the **Fathom Layer** for crop-mix optimisation.

> **Deployment note:** Terra Layer runs as a sub-app mounted at `/terra` inside the unified `ml_service` on port 8000. See `ml_service/README.md` for setup. Use standalone mode (port 8001) only for isolated development.

---

## 📐 Architecture Overview

```
terra_layer/
├── main.py                         # FastAPI sub-app — exposes POST /api/analyze
├── analyzer.py                     # TerraAnalyzer class — core inference engine
├── train_model.py                  # Full training pipeline (MobileNetV2 + GLCM)
├── fit_scaler_only.py              # Utility: refit StandardScaler without retraining
├── clean_dataset.py                # Dataset audit and cleanup utilities
├── model.keras                     # Trained hybrid CNN (gitignored — large binary)
├── specialist_laterite_red.keras   # Binary specialist: Laterite vs Red Soil (gitignored)
├── scaler.pkl                      # Fitted StandardScaler for GLCM features (gitignored)
├── dataset/                        # Training data (gitignored)
│   └── CyAUG-Dataset/
│       ├── Alluvial_Soil/
│       ├── Arid_Soil/
│       ├── Black_Soil/
│       ├── Laterite_Soil/
│       ├── Mountain_Soil/
│       ├── Red_Soil/
│       └── Yellow_Soil/
└── evaluation/                     # Training evaluation outputs (gitignored)
    ├── confusion_matrix_hybrid.png
    ├── classification_report_hybrid.txt
    └── confidence_distribution.png
```

---

## 🧠 How the Soil Classification Works

Terra Layer uses a **dual-input hybrid neural network** that fuses deep visual features from `MobileNetV2` with handcrafted texture statistics computed using **Gray-Level Co-occurrence Matrix (GLCM)** analysis. This combination is significantly more robust than a standard CNN alone — particularly for distinguishing visually similar soils such as **Laterite** and **Red Soil**.

### Inference Pipeline (per request)

```
Incoming Image (JPEG/PNG/WebP/BMP)
        │
        ▼
1. File Validation
   ├─ Size check: 10KB – 10MB
   ├─ Format check: JPEG, PNG, BMP, GIF, WEBP
   └─ Dimension check: min 100 × 100 px
        │
        ▼ (validation passed)
2. Parallel Execution (ThreadPoolExecutor, 3 workers)
   ├─ Branch A: Image Analysis (main thread)
   │   ├─ Load image as RGB via PIL
   │   ├─ Convert to BGR for OpenCV HSV analysis
   │   ├─ Resize to 224×224 for model input
   │   ├─ Extract GLCM Texture Features (4 values):
   │   │     contrast, homogeneity, energy, correlation
   │   │     (distances=[1,3], angles=[0°, 45°, 90°])
   │   ├─ Scale GLCM features using fitted StandardScaler (scaler.pkl)
   │   ├─ Feed dual inputs to Hybrid CNN:
   │   │     [image_array (1,224,224,3)] + [texture_vector (1,4)]
   │   ├─ Apply softmax → 7-class probability vector
   │   ├─ Check confidence ≥ 65% threshold
   │   │     └─ If below → raise ValueError (not a soil image)
   │   └─ Return predicted soil class + confidence score
   │
   ├─ Branch B: Weather Fetch (executor thread)
   │   └─ GET open-meteo.com → current temperature (°C) + precipitation (mm)
   │
   └─ Branch C: Regional Soil Profile (executor thread)
       └─ GET ISRIC SoilGrids API → clay %, sand %, silt %, pH, nitrogen (0–5cm)
        │
        ▼
3. Report Assembly
   ├─ Health Status (Optimal / Moderate / Deficient)
   ├─ Soil Quality Score (0–100)
   │     Optimal → 85 + (confidence × 10)
   │     Moderate → 65 + (confidence × 5)
   │     Deficient → 40 + (confidence × 5)
   ├─ Hydrology Alert: Stable / Flood Risk / Drought Risk
   ├─ Workability Window: Good / Clay-like / Too Sandy
   ├─ Recommended Crops (based on soil type rule matrix)
   ├─ Warning Crop (crop to avoid for this soil type)
   └─ Action Plan (weather context + texture survey + regional data)
        │
        ▼
4. Return JSON Report
```

---

## 🏗️ Model Architecture — Hybrid MobileNetV2 + Texture

### Inputs
| Branch | Input Shape | Description |
|---|---|---|
| `image_input` | `(224, 224, 3)` | RGB soil photograph |
| `texture_input` | `(4,)` | Scaled GLCM feature vector |

### Network Structure
```
image_input (224,224,3)                texture_input (4,)
     │                                       │
     │ Rescaling: [0,255] → [-1, 1]          │
     │                                       │
     ▼                                       ▼
MobileNetV2 (ImageNet weights)         Dense(16, relu)
     │ GlobalAveragePooling2D               │
     ▼                                       │
Dense(512, relu)                            │
     │                                       │
     └──────────────── Concatenate ──────────┘
                             │
                        Dense(64, relu)
                             │
                         Dropout(0.3)
                             │
                     Dense(7, softmax)
                             │
                      7 Soil Classes
```

### Training Strategy
**Phase 1 — Head Training** (MobileNetV2 base frozen):
- Optimizer: Adam (lr = 1e-3) · Epochs: up to 25 · EarlyStopping (patience=5 on val_accuracy)

**Phase 2 — Fine-Tuning** (top 30 MobileNetV2 layers unfrozen):
- Optimizer: Adam (lr = 1e-5) · Epochs: up to 10 · EarlyStopping (patience=5)

**Specialist Model** — Binary MobileNetV2 for Laterite vs Red Soil:
- Binary cross-entropy · up to 15 epochs · Trained on Laterite + Red subset only

### Augmentation (training only)
Random horizontal + vertical flip · Rotation ±30° · Brightness ±20% · Contrast ±20% · Zoom ±10%

---

## 🌿 Soil Classification — 7 Classes

| Class | Characteristics | Key Compatible Crops |
|---|---|---|
| `Alluvial_Soil` | Fertile river deposits, high P, mildly acidic | Rice, Wheat, Sugarcane, Jute |
| `Black_Soil` | High clay, moisture-retentive, neutral-alkaline | Cotton, Soybean, Wheat |
| `Red_Soil` | Iron-rich, low N+P, well-drained | Groundnut, Millets, Pulses |
| `Yellow_Soil` | Moderate fertility, moderate drainage | Groundnut, Potato, Rice |
| `Laterite_Soil` | Highly acidic, leached, high rainfall | Plantation crops |
| `Mountain_Soil` | Shallow, organic-rich, lower temperatures | Tea, Coffee, Spices |
| `Arid_Soil` | Dry, sandy, low moisture, high potassium | Bajra, Jowar, Barley |

---

## 🔌 API Reference

When running inside the unified service, all routes are prefixed with `/terra`.

### `POST /terra/api/analyze`

Accepts `multipart/form-data`.

| Field | Type | Required | Description |
|---|---|---|---|
| `lat` | `float` (form) | ✅ | GPS latitude |
| `lon` | `float` (form) | ✅ | GPS longitude |
| `survey` | `string` (JSON) | ✅ | `{ "wetness": 1–10, "texture": "Loamy" \| "Sandy" \| ... }` |
| `image` | `file` | ✅ | Soil photo (JPEG/PNG/BMP/WebP, max 10MB, min 100×100 px) |

**Success Response (`200`):**
```json
{
  "success": true,
  "status": "analysis_v2_active",
  "report": {
    "health_status": "Optimal",
    "key_interpretation": "Soil detected as Black Soil (Confidence: 92.4%).",
    "hydrology_alert": "Stable",
    "workability_window": "Good",
    "ideal_crops": ["Cotton", "Soybean", "Wheat"],
    "warning_crop": "Rice",
    "action_plan": ["Detected: Black Soil", "Texture Survey: Loamy | Wetness: 7/10"],
    "soil_type_raw": "Black_Soil",
    "soil_quality_score": 94.2,
    "soil_type_confidence": 0.9241,
    "confidence_percentage": 92.41,
    "validation_status": "validated"
  }
}
```

**Error Responses:**
- `400` — Not a soil image / confidence below threshold / invalid format
- `500` — Internal processing error

### `GET /terra/health`
```json
{ "status": "healthy", "service": "terra_layer" }
```

---

## 🔬 Training the Model

### Dataset Setup
```
ml_service/terra_layer/dataset/CyAUG-Dataset/<ClassName>/<image_files>
```
Each class folder must match one of the 7 class names exactly.

### Run Training
```powershell
cd ml_service
.\venv\Scripts\activate
python terra_layer/train_model.py
```

This will:
1. Audit dataset class distribution and compute class weights
2. Extract GLCM texture features for all images
3. Fit and save `StandardScaler` → `scaler.pkl`
4. Train Phase 1 (frozen) and Phase 2 (fine-tuned) with EarlyStopping
5. Save hybrid model → `model.keras`
6. Train and save specialist model → `specialist_laterite_red.keras`
7. Generate evaluation outputs in `evaluation/`

### Refit Scaler Only
```powershell
python terra_layer/fit_scaler_only.py
```

---

## ⚙️ Environment Variables

Terra Layer reads from the shared `ml_service/.env`. AWS S3 variables are optional:

```env
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_S3_BUCKET=your_bucket_name
AWS_REGION=ap-south-1
```

---

## 🚀 Running Standalone

> In production, Terra runs as part of the unified ML service. Use this only for isolated development.

```powershell
cd ml_service
.\venv\Scripts\activate
uvicorn terra_layer.main:app --port 8001 --reload
```

Swagger UI: `http://localhost:8001/docs`

---

## 📦 Key Dependencies

| Package | Purpose |
|---|---|
| `fastapi` / `uvicorn` | Web framework + ASGI server |
| `tensorflow` / `keras` | MobileNetV2 model inference and training |
| `opencv-python` | Image preprocessing, HSV analysis, Laplacian graininess |
| `scikit-image` | GLCM texture feature extraction |
| `scikit-learn` | StandardScaler for texture normalisation |
| `joblib` | Scaler serialisation |
| `Pillow` | Image loading and format validation |
| `requests` | Open-Meteo weather API + ISRIC SoilGrids API |
| `numpy` | Numerical operations |
| `matplotlib` | Evaluation plots |
