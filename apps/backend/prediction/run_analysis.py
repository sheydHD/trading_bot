"""Standalone entry-point for running prediction analysis.

Launched as a **subprocess** by the Flask API so that the heavy ML work
does not block the uvicorn event-loop / server thread:

    python -m apps.backend.prediction.run_analysis \
        --cache-file /path/to/analysis_cache.json \
        --status-file /path/to/analysis_status.json

Progress is written to *status-file* as JSON.
Final results are saved via :class:`PersistentCache` to *cache-file*.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _write_status(path: str, status: dict) -> None:
    """Atomically update the status JSON file."""
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(status, f)
        os.replace(tmp, path)
    except Exception as exc:
        logger.error("Failed to write status file: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run prediction analysis")
    parser.add_argument("--cache-file", required=True, help="Path to analysis cache JSON")
    parser.add_argument("--status-file", required=True, help="Path to status JSON")
    args = parser.parse_args()

    cache_file: str = args.cache_file
    status_file: str = args.status_file

    start_time = datetime.now().isoformat()

    def _update_status(*, step: int = 0, total: int = 4,
                       step_name: str = "", log_msg: str = "",
                       running: bool = True) -> None:
        """Helper to push a status update."""
        current = {}
        try:
            if os.path.exists(status_file):
                with open(status_file, "r") as f:
                    current = json.load(f)
        except Exception:
            current = {}

        logs = current.get("logs", [])
        if log_msg:
            logs.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": log_msg,
                "type": "info",
            })

        _write_status(status_file, {
            "is_running": running,
            "start_time": start_time,
            "current_step": step,
            "total_steps": total,
            "current_step_name": step_name,
            "logs": logs[-100:],   # cap log length
        })

    def _progress_callback(step: int, total: int, message: str) -> None:
        """Called by ``run_prediction_analysis`` to report progress."""
        _update_status(step=step, total=total, step_name=message,
                       log_msg=message, running=True)

    try:
        _update_status(step=0, step_name="Initialising", log_msg="Subprocess started")

        # Import here (after logging is configured)
        from apps.backend.prediction.analyzer import run_prediction_analysis
        from apps.backend.utils.cache import PersistentCache

        result = run_prediction_analysis(
            progress_callback=_progress_callback,
            enable_tuning=False,
        )

        # Persist results via PersistentCache
        cache = PersistentCache(cache_file=cache_file)
        cache.set("latest_prediction", result)
        logger.info("Analysis results cached to %s", cache_file)

        _update_status(step=4, total=4, step_name="Complete",
                       log_msg="Analysis finished successfully", running=False)

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Analysis failed:\n%s", tb)
        _update_status(step=0, step_name="Error",
                       log_msg=f"Analysis failed: {exc}", running=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
