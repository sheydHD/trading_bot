# Frontend — Trading Dashboard

Single-page React application that visualises ML prediction results from
the backend API. Built with **React 18 + Vite 5 + Tailwind CSS 3**,
served in production via Docker (nginx:stable-alpine) on port 3000.

---

## Architecture (MVVM)

```
┌───────────────────────────────────────────────┐
│  View Layer                                   │
│  App.jsx → Header + Dashboard + Footer        │
│            Dashboard renders DataTable,        │
│            ProgressBar, SummaryCard            │
├───────────────────────────────────────────────┤
│  ViewModel                                    │
│  hooks/useDashboard.js                        │
│  – fetchLatest(), runAnalysis()               │
│  – status polling (3 s interval)              │
│  – derived counts (bullish / bearish / neutral)│
│  – auto-refresh every 5 min                   │
├───────────────────────────────────────────────┤
│  Model                                        │
│  services/api.js — Axios instance             │
│  (baseURL, API key, timeouts)                 │
└───────────────────────────────────────────────┘
```

All state and business logic lives in `useDashboard()`. The view layer
is purely presentational; components receive data via props or the
ViewModel return object.

---

## File Map

```
src/
├── App.jsx               Root layout: Header + Dashboard + Footer
├── main.jsx              Vite entry-point
├── index.css             Tailwind directives + minimal global styles
├── pages/
│   └── Dashboard.jsx     Main view — renders tables, progress, summary
├── hooks/
│   └── useDashboard.js   ViewModel — ALL business logic
├── components/
│   ├── DataTable.jsx     Sortable table (stock / crypto / portfolio variants)
│   ├── Header.jsx        Top nav bar
│   ├── Footer.jsx        Bottom bar with timestamp
│   ├── ProgressBar.jsx   Analysis progress indicator
│   └── ErrorBoundary.jsx React error boundary wrapper
├── services/
│   └── api.js            Axios instance (Model layer)
└── utils/
    └── format.js         num(), price(), pct(), changeColor(), etc.
```

---

## Data Flow

```
[Backend :5001]                    [Frontend :3000]
       │                                  │
       │  GET /api/analysis/latest        │  useDashboard: fetchLatest()
       │◄─────────────────────────────────│  on mount + every 5 min
       │  { stocks, cryptos, portfolio }  │
       │──────────────────────────────────►│  setData(res.data)
       │                                  │
       │  POST /api/analysis/run          │  useDashboard: runAnalysis()
       │◄─────────────────────────────────│  user clicks "Run Analysis"
       │  { success: true }               │
       │──────────────────────────────────►│
       │                                  │
       │  GET /api/analysis/status        │  poll every 3 s while running
       │◄─────────────────────────────────│  → ProgressBar display
       │  { step, total_steps, … }        │
       │──────────────────────────────────►│
```

---

## Component Reference

### `Dashboard.jsx`

Main page. Renders:

| Section | Component | Condition |
|---------|-----------|-----------|
| Top bar | Refresh + Run Analysis buttons | Always |
| Error | Red banner | `vm.error` truthy |
| Progress | `<ProgressBar>` | `vm.analyzing` |
| Summary | 4 × `<SummaryCard>` | Data loaded |
| Stocks | `<DataTable variant="stock">` | `stocks.length > 0` |
| Crypto | `<DataTable variant="crypto">` | `cryptos.length > 0` |
| Portfolio | `<DataTable variant="portfolio">` | Portfolio data present |
| Model info | Metadata footer | `vm.modelInfo` present |

### `DataTable.jsx`

Reusable sortable table configured via column definitions per variant:

- **stock**: 15 columns (symbol, name, sector, price, 1D/5D change,
  signal, confidence, score, tech/fund scores, RSI, P/E, MACD, accuracy)
- **crypto**: 10 columns (subset without fundamentals)
- **portfolio**: 10 columns (adds support/resistance levels)

Click any column header to sort ascending/descending.

### `useDashboard.js` (ViewModel)

Returned shape:

```typescript
{
  // Raw data
  stocks: Stock[];  cryptos: Crypto[];
  portfolio: { stocks: Stock[]; cryptos: Crypto[] };
  modelInfo: ModelInfo | null;
  // Meta
  loading: boolean;  error: string | null;
  analyzing: boolean;  status: AnalysisStatus;
  lastUpdated: Date | null;  execTime: number | null;
  // Derived
  bullishStocks: number;  bearishStocks: number;  neutralStocks: number;
  bullishCryptos: number;  bearishCryptos: number;  neutralCryptos: number;
  // Actions
  fetchLatest(): Promise<void>;
  runAnalysis(): Promise<void>;
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `""` | Backend base URL (empty uses `/api` relative) |
| `VITE_API_KEY` | `""` | API key sent as `X-API-Key` header |

In Docker, the nginx reverse-proxy handles `/api/` → `http://backend:5001`,
so `VITE_API_URL` is typically left empty.

---

## Development

```bash
# From project root
make dev-frontend      # pnpm dev on :3000 with API proxy

# Or directly
cd apps/frontend
pnpm install
pnpm dev               # Vite HMR on :3000, API proxied to :5001
```

`vite.config.js` proxies `/api` to `http://localhost:5001` in dev mode.

---

## Production Build

```bash
pnpm build             # Output in build/
```

Docker build:

```dockerfile
FROM node:20-alpine AS build
# pnpm install + vite build

FROM nginx:stable-alpine
# Copy build/ to /usr/share/nginx/html
# Copy nginx.conf with SPA fallback + /api/ reverse proxy
EXPOSE 3000
```

### nginx Configuration

- SPA fallback: all non-file routes → `index.html`
- `index.html` served with `Cache-Control: no-cache` (fresh bundle refs)
- `/api/` reverse-proxied to `backend:5001` with 600 s read timeout
- Static assets (`.css`, `.js`, images, fonts) cached 7 days with `immutable`

---

## Formatting Utilities (`utils/format.js`)

| Function | Purpose | Example |
|----------|---------|---------|
| `num(val, digits)` | Fixed decimal | `num(3.1415, 2)` → `"3.14"` |
| `price(val)` | Dollar format | `price(1234.5)` → `"$1,234.50"` |
| `pct(val)` | Percent with sign | `pct(2.3)` → `"+2.30%"` |
| `changeColor(val)` | Tailwind class | green/red/gray |
| `directionColor(dir)` | Tailwind class | UP=green, DOWN=red |
| `scoreBg(score)` | Badge bg class | ≥70 green, ≥50 yellow, <50 red |
| `elapsed(ms)` | Human duration | `elapsed(125000)` → `"2m 5s"` |
