# CropHub — Server

The central **Node.js / Express** REST API for CropHub. Handles user authentication, MongoDB persistence, image uploads, and acts as a **secure proxy** to the unified Python ML service (`ml_service/`).

---

## Tech Stack

| Package | Version | Purpose |
|---|---|---|
| `express` | 4.18 | HTTP framework |
| `mongoose` | 8.0 | MongoDB ODM |
| `jsonwebtoken` | 9.0 | JWT creation + verification |
| `bcryptjs` | 2.4 | Password hashing |
| `multer` | 1.4 | Multipart image upload (in-memory) |
| `axios` | 1.6 | HTTP proxy calls to ML service |
| `cors` | 2.8 | Cross-origin request control |
| `helmet` | 7.1 | Secure HTTP headers |
| `express-rate-limit` | 7.1 | Per-IP rate limiting |
| `express-validator` | 7.0 | Request input validation |
| `morgan` | 1.10 | HTTP request logging (dev) |
| `aws-sdk` | 2.x | Optional S3 image storage |
| `dotenv` | 16.x | Environment variable loading |
| `nodemon` | 3.0 | Dev auto-reload |

---

## Project Structure

```
server/
├── package.json
└── src/
    ├── server.js                   # App factory + startup (port 5000)
    ├── config/
    │   └── db.js                   # Mongoose connection to MongoDB Atlas
    ├── routes/
    │   ├── authRoutes.js           # /api/auth
    │   ├── soilRoutes.js           # /api/soil
    │   ├── cropRoutes.js           # /api/crop
    │   ├── marketRoutes.js         # /api/market
    │   ├── fathomRoutes.js         # /api/fathom
    │   └── logisticsRoutes.js      # /api/logistics
    ├── controllers/
    │   ├── authController.js       # Register, login, JWT issuance
    │   ├── soilController.js       # Image proxy → Terra Layer + DB persistence
    │   ├── cropController.js       # Crop metadata queries
    │   ├── marketController.js     # Market price lookups
    │   ├── fathomController.js     # Proxy → /fathom/recommend
    │   └── logisticsController.js  # Proxy → /logistics/optimize, /mandis/nearby
    ├── middleware/
    │   ├── auth.js                 # protect() — JWT verification middleware
    │   ├── upload.js               # Multer config (memoryStorage)
    │   ├── validation.js           # express-validator rule chains
    │   └── errorHandler.js         # Centralised JSON error formatter
    ├── models/                     # Mongoose schemas (User, SoilAnalysis)
    ├── services/                   # Business logic helpers
    ├── utils/                      # Shared utility functions
    └── scripts/
        └── initDb.js               # Database seeding
```

---

## API Reference

### `GET /api/health`
Returns server status and timestamp. No auth required.

---

### Authentication — `/api/auth`

| Method | Endpoint | Auth | Body / Notes |
|---|---|---|---|
| `POST` | `/api/auth/register` | ❌ | `{ name, email, password }` → returns JWT + user |
| `POST` | `/api/auth/login` | ❌ | `{ email, password }` → returns JWT |
| `POST` | `/api/auth/logout` | ✅ | Clears session |

Passwords hashed with **bcryptjs** (salt rounds = 10). Tokens signed with `JWT_SECRET`, expire after `JWT_EXPIRE` (default `30d`).

---

### Soil Analysis — `/api/soil`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/soil/analyze` | ❌ | `multipart/form-data`: `soilImage` file + `lat`, `lon`, `survey` JSON |
| `GET` | `/api/soil/` | ✅ | All past analyses for the authenticated user |
| `GET` | `/api/soil/:id` | ✅ | Single analysis by MongoDB `_id` |

**Proxy flow:** Multer reads the image into memory → `soilController` builds a `FormData` payload → `axios.post` to `TERRA_LAYER_URL/api/analyze` → response returned directly to client.

---

### Fathom — `/api/fathom`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/fathom/recommend` | ❌ | `{ soil_type, soil_quality, land_acres, budget_inr, lat?, lon? }` |

**Proxy flow:** `fathomController` → `axios.post` to `FATHOM_LAYER_URL/recommend`.

---

### Logistics — `/api/logistics`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/logistics/optimize` | ❌ | `{ lat, lon, allocations, quantity_qtl, radius_km }` — full mandi arbitrage |
| `POST` | `/api/logistics/mandis/nearby` | ❌ | `{ lat, lon, radius_km }` — map pin data only |
| `GET` | `/api/logistics/crops` | ❌ | Supported crops + Agmarknet commodity names + MSP prices |
| `GET` | `/api/logistics/fees` | ❌ | Fee structure (transport rate, commission %, etc.) |

**Proxy flow:** `logisticsController` → `axios` to `LOGISTICS_LAYER_URL/*`. Wraps response in `{ success: true, data: ... }`.

---

### Market & Crop Metadata

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/market/` | Live crop market prices (Agmarknet or MSP fallback) |
| `GET` | `/api/crop/` | Supported crops with cost, soil compatibility, season |

---

## Middleware Stack

The following middleware is applied globally to every `app.use('/api/', ...)` request, in order:

```
Request
  → helmet()               — secure HTTP headers
  → rateLimit()            — 100 req / 15 min per IP
  → cors()                 — origin check (CORS_ORIGIN env var)
  → express.json()         — JSON body parsing
  → morgan('dev')          — request logging (dev only)
  → [route handler]
  → errorHandler()         — catch-all JSON error formatter
```

Protected routes additionally call `protect()` before the controller, which verifies the `Authorization: Bearer <token>` header.

---

## Environment Variables

Create `server/.env` (never commit — gitignored):

```env
# Server
NODE_ENV=development
PORT=5000

# MongoDB
MONGODB_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/crophub

# JWT
JWT_SECRET=your_long_random_secret_here
JWT_EXPIRE=30d

# Encryption (AES-256-CBC — used for sensitive field encryption)
ENCRYPTION_KEY=your_64_char_hex_key
ENCRYPTION_IV=your_32_char_hex_iv

# CORS
CORS_ORIGIN=http://localhost:8080

# AWS S3 (optional — for image storage)
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-south-1
AWS_S3_BUCKET=your-bucket-name

# Unified ML Service URLs
TERRA_LAYER_URL=http://localhost:8000/terra
FATHOM_LAYER_URL=http://localhost:8000/fathom
LOGISTICS_LAYER_URL=http://localhost:8000/logistics
```

---

## Scripts

```bash
npm install            # install dependencies

npm run dev            # start with nodemon (auto-reload)
npm start              # start without auto-reload (production)
npm run seed           # seed the database (runs initDb.js)
npm run init-db        # alias for seed
```

Server listens on `http://localhost:5000`.  
Health check: `GET http://localhost:5000/api/health`
