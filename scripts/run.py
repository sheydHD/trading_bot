#!/usr/bin/env python3
"""
Run script to start the web API and scheduler.

This script simply delegates to the existing `run.py` at repo root, while
ensuring the right working directory and optional virtualenv activation.

Usage:
  python scripts/run.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    os.chdir(ROOT_DIR)
    # If a venv exists, try to use its python
    venv_py = ROOT_DIR / ".venv" / "bin" / "python"
    if not venv_py.exists():
        venv_py = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_py) if venv_py.exists() else sys.executable
    # Prefer uvicorn ASGI for backend only, else fallback to legacy run.py if present
    try:
        subprocess.run([python_exe, "-m", "uvicorn", "apps.backend.api.app:asgi_app", "--host", "0.0.0.0", "--port", "5001", "--reload"], check=True)
    except subprocess.CalledProcessError as e:
        # If uvicorn fails or not found, surface the error
        raise


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


