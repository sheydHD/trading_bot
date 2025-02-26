import pandas as pd
import logging
import numpy as np
from datetime import datetime
from tradingview_ta import TA_Handler, Interval
import yfinance as yf

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# -----------------------------------------------------------------------------
# Asset Lists
# -----------------------------------------------------------------------------
TOP_STOCKS = ["BABA"]

# TOP_STOCKS = ["1810.HK", "BKNG", "CSCO", "CTAS", "CVX", "DE", "KO", "LRCX", "MSFT", "NVDA", "PDD", "SO", "TXN", "SPOT", "VOO", "XEL"]
TOP_CRYPTOS = ["BTC", "DEGEN","JUP", "PEPE", "WIF", "XRP"]
TOP_ASSETS = TOP_STOCKS + TOP_CRYPTOS

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def get_tradingview_analysis(symbol, exchange, screener, interval=Interval.INTERVAL_1_DAY):
    """
    Fetch TradingView technical analysis using tradingview_ta.
    Returns a dict with recommendation, RSI, MACD_hist, and all indicators.
    """
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener=screener,
            exchange=exchange,
            interval=interval
        )
        analysis = handler.get_analysis()
        return {
            "symbol": symbol,
            "exchange": exchange,
            "recommendation": analysis.summary.get("RECOMMENDATION", "N/A"),
            "oscillators": analysis.oscillators.get("RECOMMENDATION", "N/A"),
            "moving_averages": analysis.moving_averages.get("RECOMMENDATION", "N/A"),
            "RSI": analysis.indicators.get("RSI", 50),
            "MACD_hist": analysis.indicators.get("MACD.macd", 0)
                         - analysis.indicators.get("MACD.signal", 0),
            "indicators": analysis.indicators,  # keep entire set for fallback usage
        }
    except Exception as e:
        logging.error(f"Error fetching TradingView analysis for {symbol}: {e}")
        return {"symbol": symbol, "exchange": exchange, "error": str(e)}

def get_current_price(yf_symbol):
    """
    Fetch the latest close price from Yahoo Finance (period=1d).
    Returns None if no data is found or an error occurs.
    """
    try:
        data = yf.download(yf_symbol, period="1d", interval="1d", progress=False)
        if not data.empty:
            return float(data['Close'][-1])
        else:
            logging.warning(f"No current price found for {yf_symbol} on Yahoo Finance.")
            return None
    except Exception as e:
        logging.error(f"Error fetching current price for {yf_symbol}: {e}")
        return None

def get_price_with_fallback(yf_symbol, tv_indicators):
    """
    1) Attempt to get the price from Yahoo Finance using 'yf_symbol'.
    2) If that fails, attempt to use TradingView's 'close' price from 'tv_indicators'.
    3) Returns None if both fail.
    """
    # 1) Primary source: Yahoo Finance
    price = get_current_price(yf_symbol)
    if price is not None:
        return price

    # 2) Fallback: TradingView's "close" (daily candle)
    if tv_indicators:
        tv_close = tv_indicators.get("close")
        if tv_close is not None:
            logging.info(f"Using TradingView close price as fallback for {yf_symbol}.")
            return float(tv_close)

    return None

def detect_exchange(asset):
    """
    Dynamically detect the correct TradingView (symbol, exchange, screener)
    and also produce a best-guess Yahoo Finance symbol (yf_symbol).
    
    Approach:
      1) Hardcoded overrides (SPX500, 1810.HK, or any others).
      2) If recognized as crypto, return BINANCE/crypto + 'symbol-USD' for YF.
      3) Otherwise, loop major stock exchanges to see if TradingView recognizes the symbol.
    """
    asset = asset.upper().strip()

    # -------------------------------------------------------------------------
    # 1) HARDCODED OVERRIDES FOR SPECIAL CASES
    # -------------------------------------------------------------------------
    # Adjust the symbol/exchange/screener as needed for your TradingView plan.
    # Format: { "input": (tv_symbol, tv_exchange, tv_screener, yf_symbol) }
    special_map = {
        # If 'SPX500USD' on 'OANDA' doesn't work for you, try 'US500' on 'TVC' with screener='index'.
        "SPX500": ("SPX500USD", "OANDA", "cfd", "^GSPC"),
        "1810.HK": ("1810", "HKEX", "hongkong", "1810.HK"),
        "6055.HK": ("6055", "HKEX", "hongkong", "6055.HK"),

        # You can force certain stocks here if auto-detection fails:
        # "PLTR": ("PLTR", "NYSE", "america", "PLTR"),
        # "SPOT": ("SPOT", "NYSE", "america", "SPOT"),
        # "ARM": ("ARM", "NASDAQ", "america", "ARM"),
        # "JD": ("JD", "NASDAQ", "america", "JD"),
        # "CSCO": ("CSCO", "NASDAQ", "america", "CSCO"),
    }
    if asset in special_map:
        return special_map[asset]

    # -------------------------------------------------------------------------
    # 2) CRYPTO HANDLING
    # -------------------------------------------------------------------------
    crypto_list = ["BTC", "ETH", "SOL", "SUI", "XRP", "ONDO", "DOGE", "BNB", "ADA", "DOT", "SHIB"]
    if asset in crypto_list:
        tv_symbol = asset + "USDT"
        tv_exchange = "BINANCE"
        tv_screener = "crypto"
        yf_symbol = asset + "-USD"  # e.g. 'BTC' -> 'BTC-USD'
        return (tv_symbol, tv_exchange, tv_screener, yf_symbol)

    # -------------------------------------------------------------------------
    # 3) FALLBACK: TRY MULTIPLE MAJOR STOCK EXCHANGES
    # -------------------------------------------------------------------------
    possible_exchanges = [
        "NASDAQ", "NYSE", "XETRA", "EURONEXT", "LSE", "HKEX", "TSE", "INDEX"
    ]
    exchange_mapping = {
        "NASDAQ": "america",
        "NYSE": "america",
        "XETRA": "europe",
        "EURONEXT": "europe",
        "LSE": "uk",
        "HKEX": "hongkong",
        "TSE": "japan",
        "INDEX": "america",
    }

    for ex in possible_exchanges:
        screener = exchange_mapping[ex]
        test_analysis = get_tradingview_analysis(asset, ex, screener)
        if "error" not in test_analysis:
            # Found a valid exchange for TradingView
            yf_symbol = asset  # default for US
            if ex == "HKEX":
                yf_symbol = asset + ".HK"
            elif ex == "LSE":
                yf_symbol = asset + ".L"
            elif ex == "TSE":
                yf_symbol = asset + ".T"
            return (asset, ex, screener, yf_symbol)

    return (None, None, None, None)

# -----------------------------------------------------------------------------
# Main Analysis Function
# -----------------------------------------------------------------------------
def analyze_assets():
    """
    Analyze all assets:
      1) Detect (symbol, exchange, screener) for TradingView + Yahoo symbol.
      2) Fetch TradingView technical analysis.
      3) Fetch current price:
         - Attempt Yahoo Finance
         - Fallback to TradingView's close (if available)
      4) Print & save results.
    """
    results = []

    for asset in TOP_ASSETS:
        tv_symbol, tv_exchange, tv_screener, yf_symbol = detect_exchange(asset)
        if not tv_symbol or not tv_exchange:
            logging.warning(f"Skipping {asset}: Could not determine exchange/screener.")
            continue

        # 1) TradingView Analysis
        daily_analysis = get_tradingview_analysis(tv_symbol, tv_exchange, tv_screener)
        if "error" in daily_analysis:
            logging.warning(f"Skipping {tv_symbol}: {daily_analysis['error']}")
            continue

        # 2) Get price with fallback
        current_price = get_price_with_fallback(yf_symbol, daily_analysis.get("indicators"))

        # 3) Collect results
        result = {
            "Asset": asset,
            "TV_Symbol": tv_symbol,
            "Exchange": tv_exchange,
            "TV_Recommendation": daily_analysis.get("recommendation"),
            "RSI": daily_analysis.get("RSI"),
            "MACD_Hist": daily_analysis.get("MACD_hist"),
            "Current_Price": current_price,
        }
        results.append(result)

    # Convert results to DataFrame
    df_results = pd.DataFrame(results)
    df_results.to_csv("asset_analysis.csv", index=False)
    logging.info("Analysis complete. Results saved to asset_analysis.csv.")
    print(df_results)

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    analyze_assets()
