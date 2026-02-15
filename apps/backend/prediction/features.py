"""Feature engineering for stock / crypto price prediction.

Computes technical indicators, macro-regime features, and momentum
metrics from raw OHLCV data downloaded via *yfinance*.

Design principles (v3):
- **Macro context**: VIX level, SPY momentum, and relative-strength vs
  SPY give the model market-regime awareness (5 extra features).
- **Noise-filtered target**: adaptive threshold removes tiny moves so the
  model trains only on significant directional changes.
- SMA100 (not SMA200) to keep 80 %+ of rows after warmup.
- Fundamentals feed scoring only (not ML).

Experimental utilities (available but not used in production):
- ``create_alpha_target``: excess-return target (stocks vs SPY).
  Ablation showed mixed results — helps some stocks, hurts others.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import ta
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_ohlcv(symbol: str, period: str = "5y") -> pd.DataFrame | None:
    """Download daily OHLCV data from Yahoo Finance.

    5-year default gives ~1250 rows — enough for robust walk-forward
    validation after the 99-row SMA100 warmup.
    """
    try:
        data = yf.download(
            symbol, period=period, interval="1d",
            progress=False, auto_adjust=True,
        )
        if data.empty:
            logger.warning("No OHLCV data for %s", symbol)
            return None
        # Flatten MultiIndex columns produced by newer yfinance versions
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as exc:
        logger.error("Failed to fetch OHLCV for %s: %s", symbol, exc)
        return None


def fetch_fundamentals(symbol: str) -> dict[str, Any]:
    """Fetch fundamental data via ``yf.Ticker(...).info``.

    Used by the *scoring* system, **not** by the ML model (fundamentals
    are point-in-time scalars — identical for every row, so they carry
    zero time-series signal).
    """
    try:
        info = yf.Ticker(symbol).info
        return {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "return_on_equity": info.get("returnOnEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "market_cap": info.get("marketCap"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector", "Unknown"),
            "short_name": info.get("shortName", symbol),
        }
    except Exception as exc:
        logger.error("Failed to fetch fundamentals for %s: %s", symbol, exc)
        return {"sector": "Unknown", "short_name": symbol}


# ---------------------------------------------------------------------------
# Market / macro context  (fetched ONCE per analysis run)
# ---------------------------------------------------------------------------

_market_cache: dict[str, Any] = {}


def fetch_market_context(period: str = "5y") -> dict[str, pd.Series]:
    """Download SPY and ^VIX once, cache for the session.

    Returns
    -------
    dict with keys ``spy_close`` and ``vix_close`` (pd.Series, DatetimeIndex).
    """
    if _market_cache:
        return _market_cache  # type: ignore[return-value]

    result: dict[str, pd.Series] = {}
    for ticker, key in [("SPY", "spy_close"), ("^VIX", "vix_close")]:
        try:
            raw = yf.download(
                ticker, period=period, interval="1d",
                progress=False, auto_adjust=True,
            )
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            if not raw.empty:
                result[key] = raw["Close"].squeeze()
                logger.info("Fetched %s: %d rows", ticker, len(raw))
        except Exception as exc:
            logger.warning("Could not fetch %s: %s", ticker, exc)

    _market_cache.update(result)
    return result


def clear_market_cache() -> None:
    """Clear the session cache (useful between analysis runs)."""
    _market_cache.clear()


def add_macro_features(
    df: pd.DataFrame,
    market: dict[str, pd.Series],
) -> pd.DataFrame:
    """Merge SPY / VIX macro features into a per-stock DataFrame.

    The macro series are reindexed to the stock's DatetimeIndex so that
    dates align correctly.  Missing values are forward-filled.
    """
    df = df.copy()
    close = df["Close"].squeeze()

    spy = market.get("spy_close")
    vix = market.get("vix_close")

    if spy is not None:
        spy = spy.reindex(df.index, method="ffill")
        df["spy_return_20d"] = spy.pct_change(20)
        df["spy_return_60d"] = spy.pct_change(60)
        stock_ret_20 = close.pct_change(20)
        df["relative_strength_20d"] = stock_ret_20 - df["spy_return_20d"]
    else:
        df["spy_return_20d"] = 0.0
        df["spy_return_60d"] = 0.0
        df["relative_strength_20d"] = 0.0

    if vix is not None:
        vix = vix.reindex(df.index, method="ffill")
        df["vix_level"] = vix / 100.0        # normalise: 20 → 0.20
        df["vix_delta_5"] = vix.diff(5) / 100.0
    else:
        df["vix_level"] = 0.0
        df["vix_delta_5"] = 0.0

    return df


# ---------------------------------------------------------------------------
# Technical indicator computation
# ---------------------------------------------------------------------------

# These columns are the ML feature vector.
# Carefully curated: trend → momentum → volatility → volume → returns → regime.
FEATURE_COLS: list[str] = [
    # Trend (6)
    "price_vs_sma20",
    "price_vs_sma50",
    "price_vs_sma100",
    "macd_norm",
    "macd_signal_norm",
    "macd_hist_norm",
    # Momentum (5)
    "rsi_14",
    "rsi_delta_5",              # 5-day rate-of-change of RSI
    "stoch_k",
    "stoch_d",
    "adx",
    # Volatility (3)
    "bb_pct",
    "atr_pct",                  # ATR as % of price (scale-invariant)
    "volatility_20d",
    # Volume (1)
    "volume_ratio",
    # Returns (5)
    "return_1d",
    "return_5d",
    "return_20d",
    "return_60d",
    "return_120d",              # 6-month momentum (Jegadeesh–Titman)
    # Regime / quality (4)
    "momentum_quality_60",      # fraction of positive days in 60 d
    "trend_strength_60",        # R² of price vs time over 60 d
    "range_position_60d",       # position within 60-day high-low range
    "up_days_ratio_20",         # fraction of up days in 20 d
]


def _rolling_r2(series: pd.Series, window: int = 60) -> pd.Series:
    """Rolling R² of *series* vs time — measures trend consistency.

    Returns a value between 0 (pure noise) and 1 (perfect straight line).
    """
    def _calc(arr):
        n = len(arr)
        if n < 10 or np.std(arr) < 1e-10:
            return 0.0
        corr = np.corrcoef(np.arange(n), arr)[0, 1]
        return corr ** 2 if np.isfinite(corr) else 0.0

    return series.rolling(window, min_periods=max(10, window // 2)).apply(
        _calc, raw=True,
    )


def compute_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Append technical-indicator columns to an OHLCV DataFrame (copy)."""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze().astype(float)

    # ---- Trend ----------------------------------------------------------
    sma20  = ta.trend.sma_indicator(close, window=20)
    sma50  = ta.trend.sma_indicator(close, window=50)
    sma100 = ta.trend.sma_indicator(close, window=100)

    df["sma_20"]  = sma20
    df["sma_50"]  = sma50
    df["sma_100"] = sma100

    df["price_vs_sma20"]  = (close - sma20)  / sma20
    df["price_vs_sma50"]  = (close - sma50)  / sma50
    df["price_vs_sma100"] = (close - sma100) / sma100

    macd_ind = ta.trend.MACD(close)
    # Normalise MACD by price → scale-invariant across stocks
    df["macd_norm"]        = macd_ind.macd()        / close
    df["macd_signal_norm"] = macd_ind.macd_signal() / close
    df["macd_hist_norm"]   = macd_ind.macd_diff()   / close

    # Raw MACD kept for display / scoring (NOT in FEATURE_COLS)
    df["macd"]        = macd_ind.macd()
    df["macd_signal"] = macd_ind.macd_signal()
    df["macd_hist"]   = macd_ind.macd_diff()

    adx_ind = ta.trend.ADXIndicator(high, low, close)
    df["adx"] = adx_ind.adx()

    # ---- Momentum -------------------------------------------------------
    df["rsi_14"] = ta.momentum.rsi(close, window=14)

    stoch = ta.momentum.StochasticOscillator(high, low, close)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # ---- Volatility -----------------------------------------------------
    bb = ta.volatility.BollingerBands(close)
    df["bb_high"] = bb.bollinger_hband()
    df["bb_low"]  = bb.bollinger_lband()
    df["bb_pct"]  = bb.bollinger_pband()

    atr_ind = ta.volatility.AverageTrueRange(high, low, close)
    df["atr_14"]  = atr_ind.average_true_range()
    df["atr_pct"] = df["atr_14"] / close      # scale-invariant

    # ---- Volume ---------------------------------------------------------
    vol_sma = ta.trend.sma_indicator(volume, window=20)
    df["volume_ratio"] = volume / vol_sma.replace(0, np.nan)

    # ---- Returns & realised volatility ----------------------------------
    df["return_1d"]      = close.pct_change(1)
    df["return_5d"]      = close.pct_change(5)
    df["return_20d"]     = close.pct_change(20)
    df["return_60d"]     = close.pct_change(60)
    df["return_120d"]    = close.pct_change(120)
    df["volatility_20d"] = close.pct_change().rolling(20).std()

    # ---- Regime / quality features -----------------------------------------
    pos_returns = (close.pct_change() > 0).astype(float)
    df["momentum_quality_60"] = pos_returns.rolling(60).mean()
    df["up_days_ratio_20"]    = pos_returns.rolling(20).mean()

    # RSI rate-of-change (momentum acceleration)
    df["rsi_delta_5"] = df["rsi_14"].diff(5)

    # Trend strength: R² of close vs time over 60 days
    df["trend_strength_60"] = _rolling_r2(close, window=60)

    # Position within 60-day high-low range (0 = at low, 1 = at high)
    high_60  = high.rolling(60).max()
    low_60   = low.rolling(60).min()
    range_60 = high_60 - low_60
    df["range_position_60d"] = (close - low_60) / range_60.replace(0, np.nan)

    return df


# ---------------------------------------------------------------------------
# Target variable
# ---------------------------------------------------------------------------

def create_target(
    df: pd.DataFrame,
    horizon: int = 5,
    noise_filter: bool = True,
) -> pd.Series:
    """Binary target for direction prediction.

    Parameters
    ----------
    horizon : int
        Number of trading days to look ahead.
    noise_filter : bool
        If *True*, exclude tiny moves (mark as ``NaN``) so the model
        trains only on significant price changes.  The adaptive
        threshold is ``0.2 × realised-vol × √horizon``, floored at 0.2 %.
    """
    close = df["Close"].squeeze()
    future_return = close.shift(-horizon) / close - 1

    if noise_filter:
        vol = close.pct_change().rolling(20).std() * np.sqrt(horizon)
        threshold = (vol * 0.2).clip(lower=0.002)
        target = pd.Series(np.nan, index=df.index, name="target")
        target[future_return > threshold] = 1.0
        target[future_return < -threshold] = 0.0
    else:
        target = (future_return > 0).astype(float)

    return target


def create_alpha_target(
    df: pd.DataFrame,
    spy_close: pd.Series,
    horizon: int = 5,
    noise_filter: bool = True,
) -> pd.Series:
    """Binary target based on *excess return over SPY* (alpha).

    This isolates stock-specific signal from market-beta noise.  If the
    market rises 3 % and the stock rises 2 %, that is alpha = −1 %
    (bearish).  The noise threshold is slightly tighter (0.15 × vol)
    because alpha returns have lower variance than absolute returns.
    """
    close = df["Close"].squeeze()
    spy = spy_close.reindex(df.index, method="ffill")

    stock_ret = close.shift(-horizon) / close - 1
    spy_ret = spy.shift(-horizon) / spy - 1
    excess_return = stock_ret - spy_ret

    if noise_filter:
        vol = close.pct_change().rolling(20).std() * np.sqrt(horizon)
        threshold = (vol * 0.15).clip(lower=0.0015)
        target = pd.Series(np.nan, index=df.index, name="target")
        target[excess_return > threshold] = 1.0
        target[excess_return < -threshold] = 0.0
    else:
        target = (excess_return > 0).astype(float)
        target[future_return.isna()] = np.nan
        target.name = "target"

    return target
