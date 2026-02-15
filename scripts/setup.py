#!/usr/bin/env python3
"""
Project setup script using Poetry for Python dependency management.

This script:
- Ensures required directories exist
- Ensures root .env exists (creates from .env.example if missing)
- Installs Python dependencies via Poetry
- Installs and builds the frontend (pnpm/npm)

Usage:
  python scripts/setup.py

Optional env vars:
  SKIP_FRONTEND=true  # Skip frontend install/build
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "apps" / "backend"
FRONTEND_DIR = ROOT_DIR / "apps" / "frontend"
DATA_CACHE_DIR = BACKEND_DIR / "data" / "cache"
LOGS_DIR = BACKEND_DIR / "logs"
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE = ROOT_DIR / ".env.example"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)


def ensure_poetry() -> None:
    """Ensure the poetry CLI is available."""
    if shutil.which("poetry"):
        return
    print("poetry not found. Installing via pip...")
    subprocess.run([sys.executable, "-m", "pip", "install", "poetry"], check=True)
    if not shutil.which("poetry"):
        raise RuntimeError(
            "poetry is required but could not be installed automatically. "
            "Install poetry from https://python-poetry.org/docs/ and re-run."
        )


def ensure_dirs() -> None:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        print(f"Env file exists: {ENV_FILE}")
        return
    if ENV_EXAMPLE.exists():
        ENV_FILE.write_text(ENV_EXAMPLE.read_text())
    else:
        ENV_FILE.write_text(
            "# Copy .env.example to .env and fill in your values\n"
        )
    print(f"Created env file: {ENV_FILE}")


def setup_python() -> None:
    ensure_poetry()
    run(["poetry", "install", "--no-interaction"], cwd=ROOT_DIR)


def setup_frontend() -> None:
    if os.environ.get("SKIP_FRONTEND", "false").lower() == "true":
        print("Skipping frontend setup (SKIP_FRONTEND=true)")
        return
    if not FRONTEND_DIR.exists():
        print("No frontend directory found. Skipping frontend setup.")
        return
    if shutil.which("pnpm"):
        if (FRONTEND_DIR / "pnpm-lock.yaml").exists():
            run(["pnpm", "install", "--frozen-lockfile"], cwd=FRONTEND_DIR)
        else:
            run(["pnpm", "install"], cwd=FRONTEND_DIR)
        run(["pnpm", "build"], cwd=FRONTEND_DIR)
    else:
        if (FRONTEND_DIR / "package-lock.json").exists():
            run(["npm", "ci", "--no-fund", "--no-audit"], cwd=FRONTEND_DIR)
        else:
            run(["npm", "install"], cwd=FRONTEND_DIR)
        run(["npm", "run", "build"], cwd=FRONTEND_DIR)


def main() -> None:
    print("Starting setup...")
    ensure_dirs()
    ensure_env_file()
    setup_python()
    setup_frontend()
    print("\nSetup complete!")
    print("  Local dev:  make dev")
    print("  Docker:     make up")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


