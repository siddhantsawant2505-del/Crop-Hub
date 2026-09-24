# CropHub — Client

> React 18 · TypeScript 5.8 · Vite 5.4 · Tailwind CSS 3.4 · shadcn/ui

The **CropHub Client** is the full browser-based user interface for the CropHub agricultural intelligence platform. It guides a farmer through three connected analytical steps — soil analysis (Terra), crop planning (Fathom), and market routing (Logistics) — and communicates exclusively through the Node.js server at `http://localhost:5000/api`.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Routing](#routing)
4. [Authentication System](#authentication-system)
5. [Page Reference](#page-reference)
   - [Landing](#landing)
   - [Login & Signup](#login--signup)
   - [Dashboard](#dashboard)
   - [TerraLayer](#terralayer)
   - [FathomLayer](#fathomlayer)
   - [Logistics](#logistics)
6. [Component Library](#component-library)
7. [State Management](#state-management)
8. [HTTP Client & API Layer](#http-client--api-layer)
9. [Styling System](#styling-system)
10. [Environment Variables](#environment-variables)
11. [Scripts Reference](#scripts-reference)
12. [Testing](#testing)
13. [Full Dependency Reference](#full-dependency-reference)

---

## Tech Stack

| Category | Library | Version | Notes |
|---|---|---|---|
| Framework | React | 18.3.1 | Concurrent mode enabled |
| Language | TypeScript | 5.8.3 | Strict mode |
| Build tool | Vite + SWC | 5.4.19 | Sub-second HMR, SWC compiler |
| Styling | Tailwind CSS | 3.4.17 | JIT mode, custom design tokens |
| Component library | shadcn/ui | latest | Built on Radix UI primitives |
| Primitives | Radix UI | various | Accessible headless components |
| Animation | Framer Motion | 10.18.0 | Page transitions, micro-animations |
| Routing | React Router DOM | 6.30.1 | Client-side SPA routing |
| HTTP client | Axios | 1.13.6 | Interceptor-based auth attachment |
| Server state | TanStack Query | 5.83.0 | Cache, refetch, loading states |
| Forms | React Hook Form | 7.61.1 | Uncontrolled, performant |
| Validation | Zod | 3.25.76 | Schema-based form validation |
| Charts | Recharts | 2.15.4 | SVG-based crop allocation charts |
| Maps | pigeon-maps | 0.22.1 | Lightweight OpenStreetMap tiles |
| PDF export | jsPDF + jspdf-autotable | 4.2.1 | Client-side report generation |
| Icons | Lucide React | 0.462.0 | Pixel-aligned SVG icons |
| Toast | Sonner | 1.7.4 | Non-blocking notification toasts |
| Unit tests | Vitest | 3.2.4 | Vite-native test runner |
| Testing utils | @testing-library/react | 16.0.0 | DOM querying + assertions |
| E2E tests | Playwright | 1.57.0 | Full browser automation |

---

## Project Structure

```
client/
├── index.html                      # Vite HTML entry — injects <div id="root">
├── vite.config.ts                  # Vite config (SWC plugin, path aliases)
├── tailwind.config.ts              # Tailwind theme extensions + custom tokens
├── postcss.config.js               # PostCSS pipeline (autoprefixer)
├── tsconfig.json                   # Root TS config (references app + node)
├── tsconfig.app.json               # App TS config (strict, bundler module)
├── tsconfig.node.json              # Node config (for vite.config.ts itself)
├── components.json                 # shadcn/ui config (style, paths, aliases)
├── eslint.config.js                # ESLint with react-hooks + react-refresh
├── vitest.config.ts                # Vitest config (jsdom environment)
├── playwright.config.ts            # Playwright config (baseURL, browsers)
├── playwright-fixture.ts           # Playwright custom fixture definitions
│
└── src/
    ├── main.tsx                    # React DOM createRoot → <App />
    ├── App.tsx                     # BrowserRouter + all <Route> definitions
    ├── index.css                   # CSS custom properties (--surface, --on-surface, etc.)
    │
    ├── pages/
    │   ├── Landing.tsx             # Public hero / marketing page
    │   ├── Login.tsx               # JWT login form
    │   ├── Signup.tsx              # New user registration form
    │   ├── Dashboard.tsx           # Post-login overview + quick-action cards
    │   ├── TerraLayer.tsx          # 4-step soil image analysis wizard
    │   ├── FathomLayer.tsx         # Budget + land → crop-mix optimisation
    │   ├── Logistics.tsx           # Mandi discovery + arbitrage map
    │   └── NotFound.tsx            # 404 fallback page
    │
    ├── components/
    │   ├── AppLayout.tsx           # Sidebar nav + header shell (protected pages)
    │   ├── ProtectedRoute.tsx      # Auth guard HOC → redirect to /login
    │   └── ui/                     # shadcn/ui generated components
    │       ├── button.tsx
    │       ├── card.tsx
    │       ├── dialog.tsx
    │       ├── input.tsx
    │       ├── label.tsx
    │       ├── select.tsx
    │       ├── tabs.tsx
    │       ├── toast.tsx
    │       └── ...                 # (all other shadcn primitives)
    │
    ├── context/
    │   └── AuthContext.tsx         # createContext — token, user, login(), logout()
    │
    ├── hooks/                      # Custom React hooks (useAuth, etc.)
    └── lib/
        ├── axios.ts                # Axios instance with baseURL + auth interceptor
        └── utils.ts                # cn() — clsx + tailwind-merge helper
```

---

## Routing

Routing is configured in `src/App.tsx` using React Router DOM v6. The tree looks like this:

```
<BrowserRouter>
  <Routes>
    <Route path="/"           element={<Landing />} />
    <Route path="/login"      element={<Login />} />
    <Route path="/signup"     element={<Signup />} />

    <Route element={<ProtectedRoute />}>
      <Route element={<AppLayout />}>
        <Route path="/dashboard"  element={<Dashboard />} />
        <Route path="/terra"      element={<TerraLayer />} />
        <Route path="/fathom"     element={<FathomLayer />} />
        <Route path="/logistics"  element={<Logistics />} />
      </Route>
    </Route>

    <Route path="*" element={<NotFound />} />
  </Routes>
</BrowserRouter>
```

**`<ProtectedRoute>`** reads `token` from `AuthContext`. If falsy, it renders `<Navigate to="/login" replace />` before the child subtree can mount.

**`<AppLayout>`** renders the sidebar navigation and top header. The actual page content is injected via React Router's `<Outlet />`.

| Path | Component | Auth Required | Description |
|---|---|---|---|
| `/` | `Landing` | ❌ | Public marketing / hero page |
| `/login` | `Login` | ❌ | Email + password sign-in |
| `/signup` | `Signup` | ❌ | New account registration |
| `/dashboard` | `Dashboard` | ✅ | Overview + quick-action cards |
| `/terra` | `TerraLayer` | ✅ | Soil image upload + analysis |
| `/fathom` | `FathomLayer` | ✅ | Crop-mix financial optimiser |
| `/logistics` | `Logistics` | ✅ | Mandi discovery + profit map |
| `*` | `NotFound` | — | Catch-all 404 |

---

## Authentication System

Authentication is JWT-based and fully stateless on the server side.

### Login/Signup Flow

1. User submits credentials via the `Login` or `Signup` form.
2. A `POST` request is sent to `/api/auth/login` or `/api/auth/register`.
3. The server validates credentials, hashes passwords with bcryptjs, and returns a signed JWT (`JWT_SECRET`, expiry `30d`) + user object.
4. `AuthContext` stores the token in `localStorage` under the key `"token"` and sets the `user` context value.
5. The Axios instance in `src/lib/axios.ts` has a **request interceptor** that reads the token from `localStorage` on every call and attaches it as:
   ```
   Authorization: Bearer <token>
   ```
6. `<ProtectedRoute>` reads `token` from context. If the token is present, the child route renders. Otherwise, the user is redirected to `/login`.

### Logout Flow

1. `logout()` from `AuthContext` is called (e.g., from the sidebar).
2. It removes `"token"` from `localStorage`.
3. It sets `user` and `token` to `null` in context state.
4. React Router redirects to `/login`.

### AuthContext API

```typescript
interface AuthContextValue {
  user: User | null;
  token: string | null;
  login(token: string, user: User): void;
  logout(): void;
  isAuthenticated: boolean;
}
```

---

## Page Reference

### Landing

**Path:** `/`  
**Auth:** Public  

The public-facing marketing page. Introduces CropHub's three-layer system with animated sections. Contains calls-to-action linking to `/signup` and `/login`. Uses Framer Motion `staggerChildren` for section entrance animations.

---

### Login & Signup

**Paths:** `/login`, `/signup`  
**Auth:** Public (redirect to `/dashboard` if already authenticated)

Both pages use **React Hook Form** for uncontrolled form state and **Zod** for schema validation. On successful submission they call `login()` from `AuthContext` and `navigate('/dashboard')`.

---

### Dashboard

**Path:** `/dashboard`  
**Auth:** ✅ Protected

Overview panel showing the user's past soil analyses (fetched from `GET /api/soil/`) and quick-action cards linking to Terra, Fathom, and Logistics.

---

### TerraLayer

**Path:** `/terra`  
**Auth:** ✅ Protected

The most complex UI in the application. A **4-step wizard** that walks the farmer through soil image analysis.

#### Step 1 — Location Detection
- Uses `navigator.geolocation.getCurrentPosition()` to capture GPS coordinates (`lat`, `lon`).
- Coordinates are displayed and stored in component state.
- They are sent alongside the image to enable regional weather and soil profile lookups by the Terra Layer.

#### Step 2 — Soil Survey
- User fills a quick survey:
  - **Wetness** (slider, 1–10): how moist the soil feels.
  - **Texture** (select): Loamy / Sandy / Clayey / Silty / Peaty.
- This is serialised as a JSON string and sent as the `survey` form field.

#### Step 3 — Image Upload
- Accepts drag-and-drop or click-to-select.
- Client-side validation:
  - **Format:** JPEG, PNG, or WebP only.
  - **Size:** 10 KB minimum, 10 MB maximum.
  - **Dimensions:** At least 100 × 100 px (checked after loading the image into a `<canvas>`).
- On pass, sends `POST /api/soil/analyze` as `multipart/form-data` with:
  - `soilImage` — the image binary
  - `lat`, `lon` — GPS floats
  - `survey` — JSON string `{ "wetness": number, "texture": string }`

#### Step 4 — Report Display
Renders the Terra Layer response:

| Field | Rendered as |
|---|---|
| `soil_type_raw` | Formatted title (e.g., `"Black_Soil"` → `"Black Soil"`) |
| `confidence_percentage` | Progress bar with % label |
| `health_status` | Colour-coded badge (Optimal=green, Moderate=amber, Deficient=red) |
| `hydrology_alert` | Icon + label (Stable / Flood Risk / Drought Risk) |
| `workability_window` | Icon + label (Good / Clay-like / Too Sandy) |
| `ideal_crops` | Chip list of recommended crops |
| `warning_crop` | Red chip — crop to avoid |
| `soil_quality_score` | Large numeric display (0–100) |
| `action_plan` | Bulleted list of agronomic actions |

> The `soil_type_raw` and `soil_quality_score` are stored in React Router state and automatically pre-filled in the FathomLayer page when the user navigates to `/fathom`.

---

### FathomLayer

**Path:** `/fathom`  
**Auth:** ✅ Protected

Takes the Terra Layer soil context and generates a financially optimised crop allocation plan.

#### Inputs
| Field | Source | Description |
|---|---|---|
| Soil type | Auto-filled from router state or manual select | One of 7 soil types |
| Soil quality | Auto-filled from router state | 0–100 score |
| Land area | Manual input | Acres available for cultivation |
| Budget | Manual input | Total cultivation budget in INR (min ₹5,000) |
| GPS | Passed from Terra state | Optional — enables live Agmarknet prices |

#### API Call
```
POST http://localhost:5000/api/fathom/recommend
Content-Type: application/json

{
  "soil_type": "Black_Soil",
  "soil_quality": 78.5,
  "land_acres": 10,
  "budget_inr": 300000,
  "lat": 18.52,
  "lon": 73.85
}
```

#### Results Rendered
- **Animated stacked bar** — proportional land distribution across allocated crops. Each segment is colour-coded. Shows acreage labels if the crop takes ≥ 15% of land.
- **Per-crop cards** — one card per allocation showing: crop name + icon, margin % badge, live market price (if fetched), acres, cost, estimated revenue, and profit.
- **Financial summary panel** — total acres utilised / total land, total cost, total estimated revenue, expected profit, overall ROI %.
- **Price data origin** — shows the detected location (e.g., `"Pune, Maharashtra"`) used for Agmarknet price fetching.
- **"Proceed to Logistics Plan" button** — navigates to `/logistics` via `navigate('/logistics', { state: { fathomResult: result, lat, lon } })`. This passes the full allocation data to the next page without an extra API call.

---

### Logistics

**Path:** `/logistics`  
**Auth:** ✅ Protected

Takes the Fathom allocation result and finds the most profitable APMC mandi to sell each crop.

#### Dependency on Fathom Result
If the page is accessed without a Fathom result in router state, it shows an **empty state** with a button that redirects to `/fathom`. The `allocations` array from Fathom is required as the API request body.

#### Inputs
| Field | Default | Description |
|---|---|---|
| GPS location | From Fathom state or browser | Farm coordinates for distance calculation |
| Quantity per crop | 20 qtl | How many quintals to sell per crop |
| Search radius | 150 km | Radius to search for mandis |

#### API Call
```
POST http://localhost:5000/api/logistics/optimize
Content-Type: application/json

{
  "lat": 18.52,
  "lon": 73.85,
  "allocations": [ ... ],   // full FathomResult.allocations array
  "quantity_qtl": 20,
  "radius_km": 150
}
```

#### Results UI — Detailed Breakdown

**Crop tabs** — one tab per crop from the Fathom result. Switching tabs changes all result panels to show data for that crop.

**Interactive map** (pigeon-maps + OpenStreetMap tiles):
- White marker = your farm location.
- Green marker (larger) = best-ranked mandi for this crop.
- Grey markers (smaller) = all other mandis in range.
- Clicking any marker selects that mandi and populates the profit breakdown panel.

**Profit breakdown panel** (right of map):
Shown when a mandi is selected. Displays a waterfall breakdown:
```
+ Gross Revenue       = Live price × quantity_qtl
- Transport           = road_km × rate_per_km_per_qtl × qty (floored at minimum)
- Mandi Rent          = 1.5% of gross
- Commission          = 2.0% of gross
- Loading/Unloading   = ₹20 × qty
- Misc Fees           = ₹10 × qty
──────────────────────────────────────────
= True Net Profit
```
Also shows mandi contact info (phone number, address, operating hours).

**Ranked mandi cards** (grid below map):
Each card shows:
- Rank badge (circular, shows `#1`, `#2`, etc.)
- Mandi name + estimated road distance (km)
- ★ "Best Pick" badge for the #1-ranked mandi
- Live price per quintal
- Transport cost per quintal
- Combined fees + rent per quintal
- True net profit (large, colour-coded — green for #1)
- "Directions" button — opens Google Maps at `https://www.google.com/maps/search/?api=1&query=<lat>,<lon>`

**Full comparison table** (scrollable, below cards):
Columns: Mandi Name | Road Distance | Price/Qtl | Total Deductions | Net Profit | Actions  
The best mandi row shows a ★ star and green text. Each row has a Google Maps directions button.

---

## Component Library

The `src/components/ui/` folder is generated by **shadcn/ui** using:
```bash
npx shadcn-ui@latest add <component>
```

Components are fully owned source files (not a package dependency), so they can be customised directly. They are built on **Radix UI** primitives for accessibility (ARIA roles, keyboard navigation, focus management).

Key components used across pages:

| Component | Used in | Purpose |
|---|---|---|
| `Button` | All pages | Primary / secondary / ghost variants |
| `Card` | Dashboard, Fathom | Content containers |
| `Dialog` | Various | Modal overlays |
| `Input` | Login, Signup, Fathom | Controlled text inputs |
| `Label` | Forms | Accessible form labels |
| `Select` | TerraLayer survey | Soil texture dropdown |
| `Tabs` | Logistics | Per-crop tab switcher |
| `Toast` (Sonner) | All pages | Non-blocking notifications |

---

## State Management

CropHub uses a **minimal state architecture** — no Redux or Zustand. State lives in three places:

| Layer | What it manages |
|---|---|
| `AuthContext` | Global JWT token + user object. Persisted in `localStorage`. |
| React Router state | Data passed between pages (Terra → Fathom → Logistics) via `navigate(path, { state })` and `useLocation().state`. |
| Component `useState` | All local UI state (form values, API loading, results, selected mandi, etc.). |

**TanStack Query** (`@tanstack/react-query`) is available for any data fetching that needs cache management, but the primary three ML calls (analyze, recommend, optimize) are handled with raw `fetch` / Axios calls inside `handleSubmit` functions for full control over loading states.

---

## HTTP Client & API Layer

`src/lib/axios.ts` exports a configured Axios instance:

```typescript
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL, // http://localhost:5000/api
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

The Logistics page uses raw `fetch()` rather than the Axios instance (for direct control over the `multipart/form-data` encoding of the soil image upload). Both approaches target `http://localhost:5000`.

---

## Styling System

CSS custom properties are defined in `src/index.css` and used throughout all components via inline `style` props and Tailwind's `rgb(var(...))` syntax:

```css
:root {
  --surface:           /* dark background */
  --surface-container: /* slightly elevated card surface */
  --on-surface:        /* primary text colour */
}
```

The design uses a **dark theme** with:
- Accent green: `#00e87a` (CTA buttons, best-pick highlights, profit figures)
- Amber: `#ffb955` (Fathom / charts)
- Copper: `#c49a6c` (Logistics)
- Glassmorphism card borders: `rgba(0,232,122,0.08)`

All animations use Framer Motion with `staggerChildren` entrance variants and `whileHover` / `whileTap` for interactive elements.

---

## Environment Variables

Create a `.env` file in the `client/` directory (gitignored):

```env
VITE_API_BASE_URL=http://localhost:5000/api
```

This is the only variable consumed by the client. Vite exposes it as `import.meta.env.VITE_API_BASE_URL`.

> **Important:** All variables consumed by Vite at build time must be prefixed with `VITE_`. Variables without this prefix are not injected into the browser bundle.

---

## Scripts Reference

Run from the `client/` directory with `npm run <script>`:

| Script | Command | Description |
|---|---|---|
| `dev` | `vite` | Start dev server at `http://localhost:8080` with HMR |
| `build` | `vite build` | Production bundle → `dist/` |
| `build:dev` | `vite build --mode development` | Dev-mode bundle (unminified) |
| `preview` | `vite preview` | Serve `dist/` locally to test the production build |
| `lint` | `eslint .` | ESLint + TypeScript type-check |
| `test` | `vitest run` | Run all unit tests once (CI mode) |
| `test:watch` | `vitest` | Run unit tests in watch mode |

For E2E tests:
```bash
npx playwright test                   # headless
npx playwright test --headed          # visible browser
npx playwright show-report            # HTML report
```

---

## Testing

### Unit Tests (Vitest)

- **Runner:** Vitest 3.x (Vite-native, Jest-compatible API)
- **Environment:** jsdom (simulates browser DOM)
- **Utilities:** `@testing-library/react` for component rendering and querying
- **Config:** `vitest.config.ts`
- **Test files:** `src/**/*.test.tsx` or `src/**/*.spec.tsx`

### E2E Tests (Playwright)

- **Config:** `playwright.config.ts`
- **Base URL:** `http://localhost:8080` (dev server must be running)
- **Fixture:** `playwright-fixture.ts` defines any custom page helpers

---

## Full Dependency Reference

### Runtime Dependencies

| Package | Version | Purpose |
|---|---|---|
| `react` | 18.3.1 | Core UI framework |
| `react-dom` | 18.3.1 | DOM renderer |
| `react-router-dom` | 6.30.1 | Client-side routing + `useNavigate`, `useLocation` |
| `axios` | 1.13.6 | HTTP client with interceptors |
| `@tanstack/react-query` | 5.83.0 | Server state caching |
| `react-hook-form` | 7.61.1 | Form state management |
| `@hookform/resolvers` | 3.10.0 | Zod integration with RHF |
| `zod` | 3.25.76 | Schema validation |
| `framer-motion` | 10.18.0 | Animation library |
| `recharts` | 2.15.4 | SVG charts |
| `pigeon-maps` | 0.22.1 | Lightweight OpenStreetMap map |
| `lucide-react` | 0.462.0 | SVG icon library |
| `jspdf` | 4.2.1 | Client-side PDF generation |
| `jspdf-autotable` | 5.0.7 | Table plugin for jsPDF |
| `sonner` | 1.7.4 | Toast notification system |
| `clsx` | 2.1.1 | Conditional className helper |
| `tailwind-merge` | 2.6.0 | Merge Tailwind classes without conflicts |
| `class-variance-authority` | 0.7.1 | Variant-based component styling |
| `date-fns` | 3.6.0 | Date formatting utilities |
| `next-themes` | 0.3.0 | Theme switching utility |
| `cmdk` | 1.1.1 | Command palette component |
| `embla-carousel-react` | 8.6.0 | Touch carousel |
| `vaul` | 0.9.9 | Drawer component |
| `input-otp` | 1.4.2 | OTP input component |
| `react-resizable-panels` | 2.1.9 | Resizable panel layouts |
| `react-day-picker` | 8.10.1 | Date picker |
| `tailwindcss-animate` | 1.0.7 | CSS animation utilities |
| All `@radix-ui/*` | various | Headless accessible UI primitives |

### Dev Dependencies

| Package | Version | Purpose |
|---|---|---|
| `vite` | 5.4.19 | Build tool + dev server |
| `@vitejs/plugin-react-swc` | 3.11.0 | React + SWC compiler plugin |
| `typescript` | 5.8.3 | TypeScript compiler |
| `tailwindcss` | 3.4.17 | CSS utility framework |
| `autoprefixer` | 10.4.21 | CSS vendor prefix automation |
| `postcss` | 8.5.6 | CSS transformation pipeline |
| `eslint` | 9.32.0 | Linter |
| `eslint-plugin-react-hooks` | 5.2.0 | Hooks rules linting |
| `eslint-plugin-react-refresh` | 0.4.20 | HMR-safe component exports |
| `vitest` | 3.2.4 | Vite-native unit test runner |
| `@testing-library/react` | 16.0.0 | Component testing utilities |
| `@testing-library/jest-dom` | 6.6.0 | Custom DOM matchers |
| `jsdom` | 20.0.3 | DOM simulation for tests |
| `@playwright/test` | 1.57.0 | E2E browser automation |
| `puppeteer` | 24.40.0 | Headless browser (for test scripts) |
| `@tailwindcss/typography` | 0.5.16 | Prose typography plugin |
| `@types/react` | 18.3.23 | TypeScript types for React |
| `@types/react-dom` | 18.3.7 | TypeScript types for React DOM |
| `@types/node` | 22.16.5 | TypeScript types for Node.js |
