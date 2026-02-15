# Backend — Trading Bot API & Analysis Engine

Flask REST API serving prediction results to the frontend, with a
subprocess-based ML pipeline that runs XGBoost + Logistic Regression
ensemble models on 5 years of daily OHLCV data.

---

## Module Map

```
apps/backend/
├── api/
│   └── app.py               Flask application, 4 REST endpoints
├── core/
│   └── main.py              Legacy CLI analysis engine (TradingView-based)
├── prediction/              ML prediction engine (see prediction/README.md)
│   ├── analyzer.py          Orchestrator
│   ├── features.py          Feature engineering (24 features)
│   ├── model.py             XGBoost + LR ensemble
│   ├── scoring.py           Multi-factor scoring (0–100)
│   └── run_analysis.py      Subprocess entry-point
├── utils/
│   ├── analysis.py          TradingView analysis helpers
│   ├── cache.py             PersistentCache (JSON, thread-safe)
│   ├── config.py            Central config — env vars, asset lists
│   ├── email.py             Gmail SMTP notifications
│   ├── price.py             Yahoo Finance price fetcher
│   ├── rate_limiter.py      Rate-limiting decorator
│   └── telegram.py          Telegram bot messaging
├── data/cache/              Runtime cache files (gitignored)
└── logs/                    Application logs (gitignored)
```

---

## API Layer (`api/app.py`)

The Flask application is wrapped with `asgiref.WsgiToAsgi` to run under
uvicorn. Analysis runs are dispatched to a child process via
`subprocess.Popen` so the server remains responsive during the ~6-minute
ML workload.

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | No | `{"status": "healthy"}` |
| `POST` | `/api/analysis/run` | Yes | Start analysis subprocess |
| `GET` | `/api/analysis/status` | Yes | Poll progress (step, logs) |
| `GET` | `/api/analysis/latest` | Yes | Cached prediction results |

### Authentication

Protected endpoints require `X-API-Key` header matching the `API_KEY`
environment variable. In `FLASK_ENV=development`, authentication is
bypassed.

### Inter-Process Communication

```
Flask API                          Subprocess
─────────                          ──────────
POST /api/analysis/run
  │  Popen("python -m apps.backend.prediction.run_analysis")
  │  ──────────────────────────────► main()
  │                                    │
  │  GET /api/analysis/status          │ _write_status(path, {...})
  │  ◄── reads status.json ───────────│
  │                                    │
  │                                    │ cache.set("analysis_results", data)
  │  GET /api/analysis/latest          │
  │  ◄── cache.reload() + get() ──────│
  ▼                                    ▼
```

- **Status file**: JSON written atomically by the subprocess, read by the
  API on each `/status` poll.
- **Results cache**: `PersistentCache` (JSON file with expiry). The API
  calls `cache.reload()` before reading to pick up subprocess writes.

---

## Utilities (`utils/`)

### `config.py` — Central Configuration

Loads `.env` from project root. Defines:

- **Asset lists**: `PREDICTION_STOCKS` (20), `PREDICTION_CRYPTOS` (10),
  `WALLET_STOCKS` (16), `WALLET_CRYPTOS` (6), `TOP_STOCKS` (150),
  `TOP_CRYPTOS` (51)
- **Risk params**: `DEFAULT_STOP_LOSS = -0.30`, `DEFAULT_RISK_REWARD_RATIO = 3.0`
- **Schedule**: 8 daily times for Telegram alerts

### `cache.py` — PersistentCache

Thread-safe JSON cache with TTL expiry and atomic writes.

```python
cache = PersistentCache("results.json", expiry_seconds=3600)
cache.set("key", {"data": 42})
cache.get("key")     # → {"data": 42}
cache.reload()       # Re-read from disk (for subprocess updates)
```

### `rate_limiter.py` — Rate Limiting

Decorator and class for controlling API call frequency.

```python
@rate_limited(calls_per_second=2)
def fetch_data(symbol):
    ...
```

### `email.py` — Email Notifications

Gmail SMTP with HTML formatting. Disabled by default (`EMAIL_ENABLED=false`).

### `telegram.py` — Telegram Messaging

Async message sending with old-message deletion and message-ID tracking.

### `price.py` — Price Fetching

Yahoo Finance primary, TradingView fallback.

---

## Legacy Engine (`core/main.py`)

The original 1267-line monolithic analysis module. Uses TradingView
signals, Kalman filtering, TextBlob sentiment, and Random Forest ML.
Scheduled via APScheduler; sends results via Telegram/email.

> **Note**: The newer prediction engine in `prediction/` supersedes
> this module for ML predictions. `core/main.py` is retained for
> TradingView-based scoring and scheduled alert delivery.

---

## Docker

```dockerfile
FROM python:3.10-slim
# ... install deps from pyproject.toml via Poetry export
EXPOSE 5001
CMD ["uvicorn", "apps.backend.api.app:asgi_app", "--host", "0.0.0.0", "--port", "5001"]
```

Health check: `curl -f http://localhost:5001/api/health` every 30 seconds.

---

## Development

```bash
# From project root
make dev-backend    # uvicorn with --reload on :5001
```

Or directly:

```bash
poetry run uvicorn apps.backend.api.app:asgi_app --host 0.0.0.0 --port 5001 --reload
```
