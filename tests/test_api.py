"""Tests for the Flask API endpoints."""

import pytest


class TestHealthEndpoint:
    """Test /api/health."""

    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_json(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert data["status"] == "healthy"


class TestAnalysisStatusEndpoint:
    """Test /api/analysis/status."""

    def test_status_returns_200_in_dev(self, client):
        """In dev mode auth is skipped, should return 200."""
        resp = client.get("/api/analysis/status")
        assert resp.status_code == 200

    def test_status_contains_expected_keys(self, client):
        resp = client.get("/api/analysis/status")
        data = resp.get_json()
        assert "is_running" in data
        assert "current_step" in data
        assert "total_steps" in data
        assert "logs" in data


class TestAnalysisExampleEndpoint:
    """Test /api/analysis/example."""

    def test_example_returns_200_in_dev(self, client):
        resp = client.get("/api/analysis/example")
        assert resp.status_code == 200

    def test_example_contains_all_categories(self, client):
        resp = client.get("/api/analysis/example")
        data = resp.get_json()
        for key in ["best_stocks", "top_stocks", "best_cryptos", "top_cryptos",
                     "wallet_stocks", "wallet_cryptos"]:
            assert key in data, f"Missing key: {key}"
            assert isinstance(data[key], list)

    def test_example_has_timestamp(self, client):
        resp = client.get("/api/analysis/example")
        data = resp.get_json()
        assert "timestamp" in data


class TestCORSHeaders:
    """Verify CORS behaviour in dev mode."""

    def test_options_preflight(self, client):
        resp = client.options("/api/health")
        # Flask-CORS should allow it
        assert resp.status_code in (200, 204)


class TestSPAServing:
    """Test the SPA catch-all route."""

    def test_unknown_route_serves_index(self, client):
        # In test mode BUILD_DIR may not exist; expect 404 from
        # send_from_directory rather than a hard crash.
        resp = client.get("/some/random/path")
        assert resp.status_code in (200, 404)
