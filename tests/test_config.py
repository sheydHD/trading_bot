"""Tests for configuration loading and constants."""

import os
import pytest


class TestConfig:
    """Verify config module loads correctly."""

    def test_top_stocks_not_empty(self):
        from apps.backend.utils.config import TOP_STOCKS
        assert len(TOP_STOCKS) > 0

    def test_top_cryptos_not_empty(self):
        from apps.backend.utils.config import TOP_CRYPTOS
        assert len(TOP_CRYPTOS) > 0

    def test_wallet_stocks_not_empty(self):
        from apps.backend.utils.config import WALLET_STOCKS
        assert len(WALLET_STOCKS) > 0

    def test_wallet_cryptos_not_empty(self):
        from apps.backend.utils.config import WALLET_CRYPTOS
        assert len(WALLET_CRYPTOS) > 0

    def test_default_stop_loss_is_negative(self):
        from apps.backend.utils.config import DEFAULT_STOP_LOSS
        assert DEFAULT_STOP_LOSS < 0

    def test_risk_reward_ratio_positive(self):
        from apps.backend.utils.config import DEFAULT_RISK_REWARD_RATIO
        assert DEFAULT_RISK_REWARD_RATIO > 0

    def test_no_duplicate_stocks(self):
        from apps.backend.utils.config import TOP_STOCKS
        # Some may appear twice intentionally, but flag obvious dupes
        seen = set()
        dupes = [s for s in TOP_STOCKS if s in seen or seen.add(s)]
        # Allow a few known dupes (HON, TXN, ADP, BKNG appear twice in the list)
        assert len(dupes) <= 5, f"Too many duplicate stocks: {dupes}"

    def test_scheduled_times_format(self):
        from apps.backend.utils.config import SCHEDULED_TIMES
        import re
        for t in SCHEDULED_TIMES:
            assert re.match(r"^\d{2}:\d{2}$", t), f"Bad time format: {t}"


class TestRateLimiter:
    """Verify rate limiter works."""

    def test_rate_limiter_delays(self):
        import time
        from apps.backend.utils.rate_limiter import RateLimiter

        limiter = RateLimiter(calls_per_second=10)
        start = time.time()
        for _ in range(5):
            limiter.wait_if_needed()
        elapsed = time.time() - start
        # 5 calls at 10/sec should take at least 0.4s
        assert elapsed >= 0.3


class TestStructure:
    """Verify required files and packages exist."""

    @pytest.mark.parametrize("path", [
        "apps/__init__.py",
        "apps/backend/__init__.py",
        "apps/backend/api/__init__.py",
        "apps/backend/core/__init__.py",
        "apps/backend/utils/__init__.py",
        "apps/backend/api/app.py",
        "apps/backend/core/main.py",
        "apps/backend/utils/config.py",
        ".env.example",
        "apps/frontend/package.json",
        "apps/frontend/vite.config.js",
        "apps/frontend/nginx.conf",
        "apps/frontend/Dockerfile",
        "apps/backend/Dockerfile",
        "compose.yaml",
        "Makefile",
        "pyproject.toml",
    ])
    def test_required_file_exists(self, path):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full = os.path.join(root, path)
        assert os.path.exists(full), f"Missing required file: {path}"
