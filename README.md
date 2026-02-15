# Trading Bot

AI-powered stock and cryptocurrency analysis platform. Combines **technical
indicators**, **XGBoost + Logistic Regression ensemble ML**, and **fundamental
scoring** to produce directional predictions for 34 stocks and 14
cryptocurrencies. Results are served via a REST API and rendered in a React
dashboard.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Makefile Commands](#makefile-commands)
- [API Reference](#api-reference)
- [Prediction Engine](#prediction-engine)
- [Frontend Dashboard](#frontend-dashboard)
- [Testing](#testing)
- [Deployment](#deployment)
- [License](#license)

---

## Architecture Overview

```
┌──────────────┐   HTTP :3000    ┌─────────────────────────┐
│              │ ◄──────────────►│   React + Vite + TW     │
│   Browser    │                 │   (nginx SPA)           │
│              │   /api/* proxy  │   apps/frontend/        │
└──────────────┘ ──────────────► └────────────┬────────────┘
                                              │ reverse proxy
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Flask + uvicorn        │
                                 │   (WsgiToAsgi)          │
                                 │   apps/backend/api/     │
                                 │   :5001                 │
                                 └────────────┬────────────┘
                                              │ subprocess
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Prediction Engine      │
                                 │   apps/backend/          │
                                 │     prediction/          │
                                 │   • features.py          │
                                 │   • model.py             │
                                 │   • scoring.py           │
                                 │   • analyzer.py          │
                                 └────────────┬────────────┘
                                              │ yfinance
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Yahoo Finance API      │
                                 │   (OHLCV + fundamentals) │
                                 └─────────────────────────┘
```

**Key design decisions:**

| Decision | Rationale |
|---|---|
| Subprocess-based analysis | Heavy ML training (~6 min) runs in a child process so uvicorn stays responsive to health checks and status polling. |
| XGBoost + LR ensemble | XGBoost captures non-linear patterns; Logistic Regression regularises and reduces overfitting. 60/40 soft-vote average. |
| Walk-forward validation | Expanding-window with 5-day purge gap prevents look-ahead bias. Each fold ≈ 3 months of test data. |
| NEUTRAL predictions | Stocks with calibrated confidence < 52% are labelled NEUTRAL rather than forcing a weak directional call. |
| Noise-filtered targets | Adaptive threshold (0.2 × realised vol × √horizon) filters out insignificant price moves during training. |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/sheydHD/trading_bot.git
cd trading_bot

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set API_KEY

# 3. Build & launch
make build
make up

# 4. Verify
curl http://localhost:5001/api/health     # → {"status": "healthy"}
open http://localhost:3000                 # Dashboard
```

The frontend serves at **http://localhost:3000**, the API at **http://localhost:5001**.

---

## Project Structure

```
trading_bot/
├── .env.example              # Environment template (copy to .env)
├── compose.yaml              # Docker Compose — backend + frontend services
├── Makefile                  # All project commands (make help)
├── pyproject.toml            # Python project config, deps (Poetry)
├── poetry.lock               # Locked dependency versions
│
├── apps/
│   ├── backend/              # Python API + analysis engine
│   │   ├── Dockerfile        # python:3.10-slim, uvicorn CMD
│   │   ├── api/
│   │   │   └── app.py        # Flask REST API (4 routes)
│   │   ├── core/
│   │   │   └── main.py       # Legacy CLI analysis engine
│   │   ├── prediction/       # ML prediction engine ← see prediction/README.md
│   │   │   ├── analyzer.py   #   Orchestrator: fetch → features → model → score
│   │   │   ├── features.py   #   24 technical features + target creation
│   │   │   ├── model.py      #   XGBoost + LR ensemble, walk-forward CV
│   │   │   ├── scoring.py    #   Multi-factor 0–100 scoring
│   │   │   └── run_analysis.py  # Subprocess entry-point
│   │   ├── utils/
│   │   │   ├── analysis.py   #   TradingView helpers
│   │   │   ├── cache.py      #   PersistentCache (JSON, thread-safe)
│   │   │   ├── config.py     #   Env vars, asset lists, constants
│   │   │   ├── email.py      #   Gmail SMTP notifications
│   │   │   ├── price.py      #   Yahoo Finance price fetcher
│   │   │   ├── rate_limiter.py  # Rate-limiting decorator
│   │   │   └── telegram.py   #   Telegram bot messaging
│   │   ├── data/cache/       # Runtime cache (gitignored)
│   │   └── logs/             # Log files (gitignored)
│   │
│   └── frontend/             # React 18 + Vite 5 + Tailwind 3
│       ├── Dockerfile        # Multi-stage: node build → nginx serve
│       ├── nginx.conf        # SPA routing + /api reverse proxy
│       └── src/
│           ├── App.jsx       # Root layout
│           ├── pages/
│           │   └── Dashboard.jsx     # Main dashboard view
│           ├── hooks/
│           │   └── useDashboard.js   # ViewModel (MVVM)
│           ├── services/
│           │   └── api.js            # Axios client
│           ├── components/
│           │   ├── DataTable.jsx     # Sortable table (3 presets)
│           │   ├── Header.jsx        # Nav + status indicator
│           │   ├── Footer.jsx        # Copyright
│           │   ├── ProgressBar.jsx   # Analysis progress
│           │   └── ErrorBoundary.jsx # Error boundary
│           └── utils/
│               └── format.js         # Number/colour formatters
│
├── scripts/
│   ├── run.py                # Local dev: uvicorn with hot-reload
│   └── setup.py              # Full project setup (Poetry + pnpm)
│
└── tests/                    # pytest suite (45 tests)
    ├── conftest.py
    ├── test_api.py           # 9 tests
    ├── test_cache.py         # 8 tests
    ├── test_config.py        # 17 tests
    └── test_email.py         # 11 tests
```

---

## Environment Variables

Copy `.env.example` → `.env` and configure:

### Required

| Variable | Description | Example |
|---|---|---|
| `API_KEY` | Authentication key for protected endpoints | `my-secret-key-123` |

### Notifications (optional)

| Variable | Description | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) | — |
| `TELEGRAM_CHAT_ID` | Target chat / channel ID | — |
| `EMAIL_ENABLED` | Enable email alerts | `false` |
| `EMAIL_ADDRESS` | Sender Gmail address | — |
| `EMAIL_PASSWORD` | Gmail [app password](https://support.google.com/accounts/answer/185833) | — |
| `EMAIL_RECIPIENT` | Recipient email address | — |

### Application

| Variable | Description | Default |
|---|---|---|
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:3000` |
| `FLASK_ENV` | `production` or `development` | `production` |
| `ANALYSIS_MODE` | Legacy engine mode (`light` / `full`) | `full` |
| `VITE_API_URL` | Frontend API base URL (build-time) | `/api` |
| `VITE_API_KEY` | Frontend API key (build-time) | — |

---

## Makefile Commands

Run `make help` for the full list.

### Docker (production)

| Command | Description |
|---|---|
| `make build` | Build all Docker images |
| `make up` | Start all services (detached) |
| `make down` | Stop and remove containers |
| `make logs` | Tail logs from all containers |
| `make restart` | Restart all services |
| `make up-backend` | Start backend only |
| `make up-frontend` | Start frontend only |
| `make restart-backend` | Restart backend only |
| `make restart-frontend` | Restart frontend only |

### Local development

| Command | Description |
|---|---|
| `make setup` | Full local setup (Poetry + pnpm) |
| `make dev` | Run backend + frontend locally |
| `make dev-backend` | uvicorn with hot-reload (:5001) |
| `make dev-frontend` | Vite dev server (:3000) |

### Quality

| Command | Description |
|---|---|
| `make lint` | Run ruff linter |
| `make test` | Run pytest suite |
| `make clean` | Remove build artifacts and caches |

---

## API Reference

Base URL: `http://localhost:5001`

All endpoints except `/api/health` require the `X-API-Key` header (or run
in `FLASK_ENV=development` for unauthenticated access).

### `GET /api/health`

Health check. No authentication.

```json
{ "status": "healthy" }
```

### `POST /api/analysis/run`

Start a new analysis. Returns immediately; work runs in a subprocess.

```bash
curl -X POST -H "X-API-Key: $API_KEY" http://localhost:5001/api/analysis/run
```

```json
{ "success": true, "message": "Analysis started – poll /api/analysis/status for progress" }
```

### `GET /api/analysis/status`

Poll analysis progress.

```json
{
  "is_running": true,
  "current_step": 2,
  "total_steps": 4,
  "current_step_name": "Analyzing stocks",
  "elapsed_time": 45.2,
  "logs": [
    { "timestamp": "14:30:01", "type": "info", "message": "Fetching fundamental data" }
  ]
}
```

### `GET /api/analysis/latest`

Retrieve cached results from the most recent analysis run.

<details>
<summary>Response shape (abbreviated)</summary>

```json
{
  "timestamp": "2026-02-15T14:35:29",
  "stocks": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "sector": "Technology",
      "price": 245.12,
      "prediction": "DOWN",
      "confidence": 0.627,
      "score": 46,
      "model_accuracy": 0.556
    }
  ],
  "cryptos": [ { "symbol": "BTC", "prediction": "UP", "confidence": 0.537 } ],
  "portfolio": { "stocks": [], "cryptos": [] },
  "model_info": {
    "avg_accuracy": 0.503,
    "stocks_analyzed": 34,
    "cryptos_analyzed": 14,
    "prediction_horizon": "5 trading days",
    "method": "XGBoost + LR Ensemble + Multi-Factor Scoring",
    "features_used": 24
  }
}
```

</details>

---

## Prediction Engine

The ML pipeline lives in `apps/backend/prediction/`. See
[apps/backend/prediction/README.md](apps/backend/prediction/README.md) for
detailed methodology and technical documentation.

**Pipeline:**

```
Yahoo Finance OHLCV (5 years, daily)
        │
        ▼
  compute_technical_features()    24 features across 6 categories
        │
        ▼
  create_target()                 noise-filtered binary classification
        │
        ▼
  walk_forward_validate()         expanding window, 63-day folds, 5-day purge
        │
        ▼
  train()                         XGBoost + Logistic Regression ensemble
        │
        ▼
  predict()                       calibrated probability → UP / DOWN / NEUTRAL
        │
        ▼
  compute_overall_score()         weighted blend: tech + fundamentals + ML
```

---

## Frontend Dashboard

React 18 SPA with MVVM architecture. See
[apps/frontend/README.md](apps/frontend/README.md) for component documentation.

```
App
├── Header          nav bar + live backend status indicator
├── Dashboard       summary cards + data tables + progress
│   ├── SummaryCard ×4
│   ├── DataTable   sortable, 3 column presets (stock / crypto / portfolio)
│   └── ProgressBar analysis progress
└── Footer
```

---

## Testing

```bash
make test
```

45 tests across 4 files:

| File | Tests | Scope |
|---|---|---|
| `test_api.py` | 9 | Health, status, CORS, SPA routing |
| `test_cache.py` | 8 | Get/set, expiry, atomic writes, reload |
| `test_config.py` | 17 | Env loading, defaults, asset list integrity |
| `test_email.py` | 11 | Email formatting, SMTP, enable/disable |

---

## Deployment

### Docker (recommended)

```bash
make build && make up
```

Two containers:
- **backend** — `python:3.10-slim`, uvicorn on `:5001`, healthcheck every 30s
- **frontend** — `nginx:stable-alpine`, SPA on `:3000`, reverse-proxies `/api` to backend

### Manual

```bash
make setup    # Install Poetry deps + pnpm build
make dev      # Start both services locally
```

Requires: Python ≥ 3.10, Node.js ≥ 18, pnpm ≥ 9.

---

## License

[MIT](LICENSE)
