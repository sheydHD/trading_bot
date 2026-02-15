"""Shared pytest fixtures."""

import os
import json
import tempfile
import pytest

# Ensure env vars are set before importing app modules
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


@pytest.fixture()
def app():
    """Create a Flask test app."""
    from apps.backend.api.app import app as flask_app

    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def tmp_cache_file(tmp_path):
    """Return a path to a temporary JSON cache file."""
    return str(tmp_path / "test_cache.json")
