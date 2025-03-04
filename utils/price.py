"""Price fetching utilities."""

import logging
import yfinance as yf

def get_current_price(symbol: str, asset_type: str, tv_indicators=None):
    """
    Fetch the latest closing price from Yahoo Finance using a daily interval.
    If no data is returned, fall back to TradingView's "close" price from tv_indicators.
    """
    try:
        # Determine the Yahoo Finance symbol.
        if asset_type == "crypto":
            yf_symbol = symbol.replace("USDT", "-USD")
        else:
            yf_symbol = symbol
        # Always use daily data.
        data = yf.download(yf_symbol, period="1d", interval="1d", progress=False)
        if not data.empty and 'Close' in data.columns:
            price = float(data['Close'].iloc[-1])
            return price
        logging.warning(f"No current price found for {yf_symbol} on Yahoo Finance.")
        # Fallback: use TradingView's close if available.
        if tv_indicators:
            tv_close = tv_indicators.get("close")
            if tv_close is not None:
                logging.info(f"Using TradingView close price as fallback for {yf_symbol}.")
                return float(tv_close)
        return None
    except Exception as e:
        logging.error(f"Error fetching current price for {yf_symbol}: {e}")
        return None 