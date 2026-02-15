"""Flask API for the trading-bot prediction engine.

Frontend is served by nginx (see ``apps/frontend/nginx.conf``).
This module only exposes ``/api/*`` endpoints.

The analysis run is dispatched to a **separate subprocess** so that
uvicorn can keep serving health-check and status requests while the
heavy ML work is in progress.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

from apps.backend.utils.cache import PersistentCache

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__)

_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
]
if _allowed_origins:
    CORS(app, resources={r"/api/*": {"origins": _allowed_origins}}, supports_credentials=True)
elif os.getenv("FLASK_ENV") == "development":
    CORS(app, supports_credentials=True)

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "your-secret-api-key")

# ---------------------------------------------------------------------------
# Persistent cache
# ---------------------------------------------------------------------------
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
_CACHE_FILE = os.path.join(_CACHE_DIR, "analysis_cache.json")

if os.path.exists(_CACHE_FILE):
    try:
        with open(_CACHE_FILE, "r") as _f:
            analysis_cache = PersistentCache(cache_file=_CACHE_FILE, initial_data=json.load(_f))
            logger.info("Loaded analysis cache from %s", _CACHE_FILE)
    except Exception as exc:
        logger.warning("Cache load failed (%s) – starting fresh", exc)
        analysis_cache = PersistentCache(cache_file=_CACHE_FILE)
else:
    analysis_cache = PersistentCache(cache_file=_CACHE_FILE)
    logger.info("Created new analysis cache at %s", _CACHE_FILE)

# ---------------------------------------------------------------------------
# Analysis status tracking  (shared via a tiny JSON file so the subprocess
# and the main uvicorn process can both read/write it).
# ---------------------------------------------------------------------------
_STATUS_FILE = os.path.join(_CACHE_DIR, "analysis_status.json")

_DEFAULT_STATUS = {
    "is_running": False,
    "start_time": None,
    "current_step": 0,
    "total_steps": 4,
    "current_step_name": "",
    "logs": [],
}

# Subprocess handle
_analysis_proc: subprocess.Popen | None = None


def _read_status() -> dict:
    """Read analysis status from the shared JSON file.

    The file is written by the analysis subprocess and read by the
    Flask API to serve ``/api/analysis/status`` responses.

    Returns:
        Status dict with keys: ``is_running``, ``start_time``,
        ``current_step``, ``total_steps``, ``current_step_name``, ``logs``.
    """
    try:
        if os.path.exists(_STATUS_FILE):
            with open(_STATUS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {**_DEFAULT_STATUS}


def _write_status(status: dict) -> None:
    """Persist analysis status to the shared JSON file."""
    try:
        with open(_STATUS_FILE, "w") as f:
            json.dump(status, f)
    except Exception:
        pass


def _authenticate() -> bool:
    """Verify ``X-API-Key`` header.  Bypassed when ``FLASK_ENV=development``."""
    if os.getenv("FLASK_ENV") == "development":
        return True
    return request.headers.get("X-API-Key") == API_KEY


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health_check():
    """Liveness probe — always returns ``{"status": "healthy"}``."""
    return jsonify({"status": "healthy"}), 200


@app.route("/api/analysis/status", methods=["GET"])
def get_analysis_status():
    """Return current analysis progress.

    Reads the status JSON file written by the subprocess and enriches
    it with elapsed-time computation.  Also detects when the subprocess
    has terminated and clears a stale ``is_running`` flag.
    """
    if not _authenticate():
        return jsonify({"error": "Unauthorized"}), 401

    global _analysis_proc
    status = _read_status()

    # Check if subprocess finished but status file not yet updated
    if _analysis_proc is not None and _analysis_proc.poll() is not None:
        _analysis_proc = None
        status = _read_status()
        if status.get("is_running"):
            status["is_running"] = False
            _write_status(status)

    elapsed_time = None
    if status.get("is_running") and status.get("start_time"):
        try:
            start = datetime.fromisoformat(status["start_time"])
            elapsed_time = (datetime.now() - start).total_seconds() * 1000
        except Exception:
            pass

    return jsonify({
        "is_running": status.get("is_running", False),
        "current_step": status.get("current_step", 0),
        "total_steps": status.get("total_steps", 4),
        "current_step_name": status.get("current_step_name", ""),
        "elapsed_time": elapsed_time,
        "logs": status.get("logs", []),
    })


@app.route("/api/analysis/latest", methods=["GET"])
def get_latest_analysis():
    """Return the most recent cached prediction results.

    Calls ``cache.reload()`` first to pick up any data written by
    an analysis subprocess since the last request.

    Returns:
        200 with the full analysis payload, or 404 if no results
        have been cached yet.
    """
    if not _authenticate():
        return jsonify({"error": "Unauthorized"}), 401

    # Re-load cache from disk (the subprocess may have written new data)
    analysis_cache.reload()
    cached = analysis_cache.get("latest_prediction")
    if cached:
        return jsonify(cached)

    return jsonify({"error": "No analysis available. Trigger a run first."}), 404


@app.route("/api/analysis/run", methods=["POST"])
def run_analysis():
    """Trigger a fresh prediction analysis in a background subprocess.

    Returns immediately with ``{"success": true}``.
    Poll ``/api/analysis/status`` for progress.
    """
    if not _authenticate():
        return jsonify({"error": "Unauthorized"}), 401

    global _analysis_proc
    status = _read_status()
    if status.get("is_running"):
        # Double-check: if subprocess died, clear stale status
        if _analysis_proc is None or _analysis_proc.poll() is not None:
            status["is_running"] = False
            _write_status(status)
        else:
            return jsonify({
                "success": False,
                "error": "Analysis already running",
            })

    # Write initial status
    _write_status({
        "is_running": True,
        "start_time": datetime.now().isoformat(),
        "current_step": 0,
        "total_steps": 4,
        "current_step_name": "Starting",
        "logs": [{"timestamp": datetime.now().strftime("%H:%M:%S"),
                  "message": "Starting prediction analysis", "type": "info"}],
    })

    # Find project root (parent of apps/)
    project_root = os.path.dirname(  # /app
        os.path.dirname(             # /app/apps
            os.path.dirname(         # /app/apps/backend
                os.path.dirname(__file__)  # /app/apps/backend/api
            )
        )
    )

    # Launch analysis as a separate process
    _analysis_proc = subprocess.Popen(
        [sys.executable, "-m", "apps.backend.prediction.run_analysis",
         "--cache-file", _CACHE_FILE,
         "--status-file", _STATUS_FILE],
        cwd=project_root,
    )

    return jsonify({
        "success": True,
        "message": "Analysis started – poll /api/analysis/status for progress",
    })


# ---------------------------------------------------------------------------
# ASGI wrapper – uvicorn targets  apps.backend.api.app:asgi_app
# ---------------------------------------------------------------------------
from asgiref.wsgi import WsgiToAsgi  # type: ignore  # noqa: E402

asgi_app = WsgiToAsgi(app)
