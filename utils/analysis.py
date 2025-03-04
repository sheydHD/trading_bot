"""Analysis utilities for the trading bot."""

import logging
import pandas as pd
from tradingview_ta import TA_Handler, Interval

from utils.price import get_current_price
from utils.rate_limiter import rate_limited
from utils.config import (
    TOP_STOCKS, TOP_CRYPTOS, DEFAULT_STOP_LOSS, DEFAULT_RISK_REWARD_RATIO
)

# Global cache for TradingView Analysis
analysis_cache = {}

def rec_priority(rec: str) -> int:
    """Helper: Recommendation Priority (for secondary sorting)"""
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
def get_tradingview_analysis(symbol: str, exchange: str, screener: str, interval=Interval.INTERVAL_1_DAY) -> dict:
    """
    Retrieve TradingView analysis for the specified asset.
    Uses a simple in-memory cache to reduce repeated API calls.
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

def analyze_assets():
    """Main analysis function that processes all assets and returns results."""
    # Implementation would go here - this is a placeholder
    # You should move the analyze_assets function from main.py to here
    logging.info("Analyzing assets...")
    # Return empty DataFrames as placeholders
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame() 