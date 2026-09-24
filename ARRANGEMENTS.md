# CropHub — Real-World Deployment Checklist

This document tracks all the manual steps required to bring CropHub from development to a fully operational state. The ML service has been consolidated into a single unified FastAPI process (`ml_service/`) covering Terra, Fathom, and Logistics layers.

---

## 1. Machine Learning Assets

### Terra Layer
- [ ] **Soil Image Dataset**: Download the [CyAUG Soil Types Dataset](https://www.kaggle.com/datasets) and place images under `ml_service/terra_layer/dataset/CyAUG-Dataset/<ClassName>/` with exactly 7 class folder names: `Alluvial_Soil`, `Arid_Soil`, `Black_Soil`, `Laterite_Soil`, `Mountain_Soil`, `Red_Soil`, `Yellow_Soil`.
- [ ] **Train the Hybrid CNN**: Run `python terra_layer/train_model.py` from inside the activated `ml_service/` virtual environment. This trains the MobileNetV2 + GLCM model, fits the `StandardScaler`, and saves `model.keras`, `specialist_laterite_red.keras`, and `scaler.pkl`.
- [ ] **Verify model accuracy**: Check `terra_layer/evaluation/classification_report_hybrid.txt` — target ≥ 85% overall accuracy before deploying.

### Fathom Layer
- [ ] **Download Kaggle Datasets**: Place the following three CSVs inside `ml_service/fathom_layer/data/raw/`:
  - `crop_recommendation.csv` — [Kaggle link](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset)
  - `fertilizer_prediction.csv` — [Kaggle link](https://www.kaggle.com/datasets/gdabhishek/fertilizer-prediction)
  - `india_crop_yield.csv` — [Kaggle link](https://www.kaggle.com/datasets/pyatakov/india-agriculture-crop-yield)
- [ ] **Run the Data Pipeline**: `python -m fathom_layer.data_pipeline` (from `ml_service/` with venv active).
- [ ] **Train the Models**: `python -m fathom_layer.train`. Produces three `.joblib` files in `fathom_layer/models/`.
- [ ] **Verify model quality**: Check `fathom_layer/evaluation/` for R² (yield/margin) and ROC-AUC (suitability) — target R² ≥ 0.80 and AUC ≥ 0.85.

### Logistics Layer
- [ ] **No training required**. The Logistics Layer uses the curated static dataset `logistics_layer/data/mandis_india.json` (already tracked in git) and calls the live Agmarknet API for prices.
- [ ] **Get an Agmarknet API Key**: Register at [data.gov.in](https://data.gov.in) → My Account → API Keys. Add the key to `ml_service/.env` as `AGMARKNET_API_KEY`. Without this, the system falls back to MSP ± jitter (demo mode).

---

## 2. Environment Variables

- [ ] **`ml_service/.env`** — Create this file (gitignored). Required keys:
  ```env
  AGMARKNET_API_KEY=your_data_gov_in_key
  AGMARKNET_RESOURCE_ID=9ef842fd-9a74-4050-a155-397d9013c4f9
  FATHOM_ADMIN_TOKEN=your_secure_token
  LOGISTICS_ADMIN_TOKEN=your_secure_token
  ```

- [ ] **`server/.env`** — Create this file (gitignored). Required keys:
  ```env
  NODE_ENV=production
  PORT=5000
  MONGODB_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/crophub
  JWT_SECRET=your_long_random_secret
  JWT_EXPIRE=30d
  CORS_ORIGIN=https://your-frontend-domain.com
  TERRA_LAYER_URL=http://localhost:8000/terra
  FATHOM_LAYER_URL=http://localhost:8000/fathom
  LOGISTICS_LAYER_URL=http://localhost:8000/logistics
  ```

- [ ] **`client/.env`** — Create this file (gitignored):
  ```env
  VITE_API_BASE_URL=http://localhost:5000/api
  ```

---

## 3. Cloud Accounts & Infrastructure

### MongoDB Atlas
- [ ] Create a cluster on [MongoDB Atlas](https://cloud.mongodb.com).
- [ ] In **Network Access**, whitelist your backend server's IP address (or `0.0.0.0/0` for initial testing).
- [ ] In **Database Access**, create a user with `readWrite` on the `crophub` database.
- [ ] Copy the connection string into `server/.env` as `MONGODB_URI`.

### AWS S3 (Optional — Image Storage)
- [ ] Create an S3 Bucket and configure CORS to allow `PUT`/`POST` from your frontend domain.
- [ ] Create an IAM User with `AmazonS3FullAccess` (or bucket-scoped policy).
- [ ] Copy `Access Key ID` and `Secret Access Key` into `server/.env` as `AWS_ACCESS_KEY` and `AWS_SECRET_KEY`.

---

## 4. Starting All Services (Development)

Open three terminal windows from the project root:

```powershell
# Terminal 1 — Unified ML Service (Terra + Fathom + Logistics)
cd ml_service
.\venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Node.js Server
cd server
npm run dev

# Terminal 3 — React Client
cd client
npm run dev
```

Navigate to `http://localhost:8080`.

**Health checks:**
- ML Service: `http://localhost:8000/health`
- Terra: `http://localhost:8000/terra/health`
- Fathom: `http://localhost:8000/fathom/health`
- Logistics: `http://localhost:8000/logistics/health`
- Server: `http://localhost:5000/api/health`

---

## 5. Production Deployment

- [ ] **SSL & HTTPS**: The browser Geolocation API and Camera API require HTTPS in production. Use a domain with a TLS certificate (Let's Encrypt via Nginx, Vercel, or Railway).
- [ ] **Reverse proxy**: Configure Nginx to proxy `/api` → Node.js (port 5000) and serve the React build as static files.
- [ ] **ML service process manager**: Use `gunicorn` with `uvicorn` workers, or a systemd service, to keep the Python ML service alive:
  ```bash
  gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
  ```
- [ ] **Environment separation**: Set `NODE_ENV=production` in the server `.env`. Disable Vite HMR and use `npm run build` for the client.

---

## 6. UI/UX & Legal Compliance

- [ ] **Geolocation Consent**: Add clear copy in the Terra and Logistics pages explaining why GPS is needed (e.g., *"CropHub needs your location to provide accurate regional weather, soil, and market data."*).
- [ ] **Agronomic Liability Disclaimer**: Add a disclaimer at the bottom of the Terra analysis report and Fathom recommendations (e.g., *"These recommendations are AI-generated estimates. Consult a local agronomist before making cultivation decisions."*).
- [ ] **Market Price Disclaimer**: Add a note on the Logistics page that prices are fetched from Agmarknet and may have up to 12-hour cache lag.
- [ ] **3D Assets & Animations**: Export `.spline` or Lottie `.json` formats and place them in `client/public/` for landing page animations.

---

## 7. Known Limitations & TODOs

| Area | Limitation | Resolution |
|---|---|---|
| Logistics price data | Falls back to MSP ± jitter when Agmarknet key is missing or API is down | Obtain an API key from data.gov.in |
| Fathom models | Models are trained offline; market prices used for training are static MSP values | Re-run `train.py` periodically with updated MSP rates |
| Terra confidence | Images with < 65% model confidence are rejected as "not soil" | Expand training dataset; lower threshold cautiously |
| Mandi dataset | `mandis_india.json` is a curated static snapshot | Periodically refresh from official APMC sources |
| Authentication | JWT stored in `localStorage` (vulnerable to XSS) | Migrate to `httpOnly` cookie-based auth for production |
