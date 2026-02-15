"""TradingView technical-analysis helpers.

Wrappers around ``tradingview_ta`` for fetching summary recommendations,
oscillator/MA ratings, RSI, and MACD for arbitrary assets.
Results are cached in-memory to reduce redundant API calls within a
single analysis run.
"""

import logging

from tradingview_ta import TA_Handler, Interval

from apps.backend.utils.rate_limiter import rate_limited

# Global cache for TradingView Analysis
analysis_cache = {}

def rec_priority(rec: str) -> int:
    """Map a TradingView recommendation string to a sort-priority int.

    Lower is more bullish: STRONG_BUY=1, BUY=2, …, STRONG_SELL=5.
    Unknown values return 6.
    """
    mapping = {
        "STRONG_BUY": 1,
        "BUY": 2,
        "NEUTRAL": 3,
        "SELL": 4,
        "STRONG_SELL": 5
    }
    if rec:
        return mapping.get(rec.upper(), 6)
    return 6

@rate_limited(calls_per_second=2)
def get_tradingview_analysis(
    symbol: str,
    exchange: str,
    screener: str,
    interval=Interval.INTERVAL_1_DAY,
) -> dict:
    """Fetch TradingView technical analysis for one asset.

    Results are cached in the module-level ``analysis_cache`` dict
    (keyed by ``(symbol, exchange, screener, interval)``) so repeated
    calls within the same process return instantly.

    Args:
        symbol: Ticker symbol (uppercase).
        exchange: Exchange identifier (e.g. ``"NASDAQ"``).
        screener: TradingView screener (e.g. ``"america"``, ``"crypto"``).
        interval: Time-frame (default: 1-day).

    Returns:
        Dict with ``recommendation``, ``oscillators``, ``moving_averages``,
        ``RSI``, ``MACD_hist``, and full ``indicators``.
    """
    key = (symbol.upper(), exchange, screener, interval)
    if key in analysis_cache:
        return analysis_cache[key]
    try:
        handler = TA_Handler(
            symbol=symbol.upper(),
            screener=screener,
            exchange=exchange,
            interval=interval
        )
        analysis = handler.get_analysis()
        result = {
            "symbol": symbol.upper(),
            "exchange": exchange,
            "timeframe": interval,
            "recommendation": analysis.summary.get("RECOMMENDATION", "N/A"),
            "oscillators": analysis.oscillators.get("RECOMMENDATION", "N/A"),
            "moving_averages": analysis.moving_averages.get("RECOMMENDATION", "N/A"),
            "RSI": analysis.indicators.get("RSI", 50),
            "MACD_hist": analysis.indicators.get("MACD.macd", 0) - analysis.indicators.get("MACD.signal", 0),
            "indicators": analysis.indicators
        }
        analysis_cache[key] = result
        return result
    except Exception as e:
        return {"symbol": symbol.upper(), "exchange": exchange, "error": str(e)}
