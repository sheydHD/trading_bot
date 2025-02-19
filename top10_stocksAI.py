import os
import joblib
import logging
import numpy as np
import pandas as pd
import asyncio
import schedule
import time
import json
from dotenv import load_dotenv

import yfinance as yf
from datetime import timedelta
from telegram.error import TimedOut
from telegram import Bot
from tradingview_ta import TA_Handler, Interval
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# Load environment variables from .env file
load_dotenv()

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# -----------------------------------------------------------------------------
# Bot Configuration (from .env)
# -----------------------------------------------------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

# -----------------------------------------------------------------------------
# Global Risk Management Parameters
# -----------------------------------------------------------------------------
DEFAULT_STOP_LOSS = -0.30  # -30% stop loss
DEFAULT_RISK_REWARD_RATIO = 2.0  # 2:1 risk-reward ratio

# -----------------------------------------------------------------------------
# Asset Lists
# -----------------------------------------------------------------------------
TOP_STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "AVGO", "COST"
    "NFLX", "ASML", "TMUS", "CSCO", "AZN", "LIN", "PEP", "ADBE", "QCOM", "AMD",
    "INTU", "ARM", "TXN", "BKNG", "MRVL", "CEG", "MSTR", "INTC", "TEAM", "ABNB",
    "CDNS", "CTAS", "MAR", "PLTR", "ADP", "ATVI", "BIDU", "BIIB", "BMRN", "CDW",
    "CERN", "CHKP", "CMCSA", "CPRT", "CRWD", "CSX", "DDOG", "DXCM", "EA", "EBAY",
    "EXC", "FAST", "FISV", "FTNT", "GILD", "HON", "IDXX", "ILMN", "JD", "KDP",
    "KLAC", "LRCX", "LULU", "MELI", "MNST", "MU", "NTES", "NXPI", "OKTA", "ORLY",
    "PANW", "PAYX", "PDD", "PYPL", "REGN", "ROST", "SBUX", "SNPS", "SPLK", "SWKS",
    "TTWO", "VRSK", "VRTX", "WDAY", "XEL", "ZM", "ZS", "ZBRA", "ZTO", "ZTS",
    "BRK.B", "V", "JPM", "UNH", "HD", "PG", "MA", "DIS", "BAC", "XOM",
    "KO", "PFE", "ABBV", "TMO", "ABT", "ACN", "CVX", "NKE", "MRK", "WMT",
    "LLY", "DHR", "MCD", "NEE", "PM", "IBM", "MDT", "ORCL", "HON", "AMGN",
    "TXN", "CAT", "GS", "BLK", "SPGI", "MS", "ISRG", "NOW", "LMT", "BA",
    "GE", "DE", "SCHW", "MMM", "ADP", "BKNG", "SYK", "CI", "CB", "C",
    "USB", "T", "LOW", "MO", "BMY", "UNP", "RTX", "DUK", "SO", "APD"
]

TOP_CRYPTOS = [
    "BTC", "ETH", "USDT", "BNB", "XRP", "SOL", "USDC", "ADA", "DOGE", "TRX"
    "TON", "DOT", "MATIC", "DAI", "AVAX", "SHIB", "LTC", "WBTC", "BCH", "LINK",
    "UNI", "ICP", "LEO", "ETC", "XLM", "XMR", "FIL", "LDO", "OKB", "CRO",
    "ATOM", "HBAR", "APT", "VET", "QNT", "NEAR", "MKR", "GRT", "AAVE", "RETH",
    "ALGO", "STX", "EGLD", "XDC", "IMX", "SAND", "FTM", "XTZ", "MANA", "THETA",
    "LEO", "BGB", "BNB"
]

TOP_ASSETS = TOP_STOCKS + TOP_CRYPTOS

# --- Wallet Assets (always displayed after the top recommendations) ---
WALLET_STOCKS = ["SPX500", "PDD", "SPOT", "1810.HK", "NVDA", "6055.HK", "9988.HK", "BABA", "CSCO", "PANW", "CPRT", "HFG", "PG", "DDOG", "XEL", "KO"]
WALLET_CRYPTOS = ["SOL", "LTC", "XRP", "ONDO", "DOGE", "BTC", "BNB"]

# FOR TESTING
# TOP_STOCKS = ["AAPL"]
# TOP_CRYPTOS = ["BTC"]
# TOP_ASSETS = TOP_STOCKS + TOP_CRYPTOS
# WALLET_STOCKS = ["PDD"]
# WALLET_CRYPTOS = ["SOL"]


# -----------------------------------------------------------------------------
# Global Cache for TradingView Analysis (for improved performance)
# -----------------------------------------------------------------------------
analysis_cache = {}

# -----------------------------------------------------------------------------
# Helper: Recommendation Priority (for secondary sorting)
# -----------------------------------------------------------------------------
def rec_priority(rec: str) -> int:
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

# -----------------------------------------------------------------------------
# Take-Profit Calculation Functions
# -----------------------------------------------------------------------------
def calculate_take_profit(entry_price, stop_loss_percent=DEFAULT_STOP_LOSS, risk_reward_ratio=DEFAULT_RISK_REWARD_RATIO):
    risk = abs(stop_loss_percent)
    target_profit_percent = risk * risk_reward_ratio
    return entry_price * (1 + target_profit_percent)

def calculate_take_profit_atr(entry_price, atr_value, atr_stop_loss_multiplier=1.5, risk_reward_ratio=2.0):
    risk_amount = atr_stop_loss_multiplier * atr_value
    return entry_price + (risk_reward_ratio * risk_amount)

# -----------------------------------------------------------------------------
# Utility Functions for Technical Analysis
# -----------------------------------------------------------------------------
def detect_asset_type(symbol: str) -> str:
    return "crypto" if symbol in TOP_CRYPTOS else "america"

def detect_crypto_exchange(symbol: str):
    exchanges = ["BINANCE", "COINBASE", "KRAKEN"]
    for exchange in exchanges:
        try:
            test_symbol = symbol.upper() + "USDT"
            test_analysis = get_tradingview_analysis(test_symbol, exchange, "crypto", interval=Interval.INTERVAL_1_DAY)
            if "error" not in test_analysis:
                return test_symbol, exchange
        except Exception as e:
            logging.debug(f"Exchange {exchange} test failed for {symbol}: {e}")
    return None, None

def detect_stock_exchange(symbol: str):
    exchanges = ["NASDAQ", "NYSE", "AMEX"]
    for exchange in exchanges:
        try:
            test_analysis = get_tradingview_analysis(symbol, exchange, "america", interval=Interval.INTERVAL_1_DAY)
            if "error" not in test_analysis:
                return symbol, exchange
        except Exception as e:
            logging.debug(f"Exchange {exchange} test failed for {symbol}: {e}")
    return None, None

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

def evaluate_asset(daily_analysis: dict, weekly_analysis: dict = None) -> int:
    """
    Evaluate an asset and return a score from 0 to 100.
    Uses recommendation, RSI, MACD histogram, moving averages, and ATR.
    """
    score = 50  # Base score

    # Recommendation adjustment
    rec = daily_analysis.get("recommendation", "NEUTRAL").upper()
    rec_adjustment = {"STRONG_BUY": 20, "BUY": 10, "NEUTRAL": 0, "SELL": -10, "STRONG_SELL": -20}
    score += rec_adjustment.get(rec, 0)

    # RSI adjustment: best is near 50
    rsi = daily_analysis.get("RSI", 50)
    rsi_adjustment = 10 - abs(rsi - 50) * 0.5
    score += rsi_adjustment

    # MACD histogram adjustment
    macd_hist = daily_analysis.get("MACD_hist", 0)
    if macd_hist > 0:
        score += 10
    elif macd_hist < 0:
        score -= 10

    # Moving averages signal
    ma_signal = daily_analysis.get("moving_averages", "NEUTRAL").upper()
    if ma_signal in ["BUY", "STRONG_BUY"]:
        score += 10
    elif ma_signal in ["SELL", "STRONG_SELL"]:
        score -= 10

    # Volatility adjustment (using ATR)
    atr = daily_analysis.get("indicators", {}).get("ATR", None)
    if atr is not None:
        if atr < 1:
            score += 5
        elif atr > 2:
            score -= 5

    # Weekly analysis adjustment (if provided)
    if weekly_analysis and "error" not in weekly_analysis:
        weekly_rec = weekly_analysis.get("recommendation", "NEUTRAL").upper()
        weekly_adjustment = {"STRONG_BUY": 10, "BUY": 5, "NEUTRAL": 0, "SELL": -5, "STRONG_SELL": -10}
        score += weekly_adjustment.get(weekly_rec, 0)

    # Ensure score is between 0 and 100
    return max(0, min(100, int(score)))

def get_timeframe_scores(symbol: str, exchange: str, asset_type: str):
    """
    Get scores for short, mid, and long timeframes.
    Short: 15-minute interval; Mid: 1-hour interval; Long: daily (with weekly bonus).
    Returns a tuple: (short_score, mid_score, long_score)
    """
    short_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_15_MINUTES)  # ✅ Fixed
    mid_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_HOUR)  # ✅ Fixed
    long_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_DAY)
    weekly_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_WEEK)
    
    short_score = evaluate_asset(short_analysis, None) if "error" not in short_analysis else 0
    mid_score   = evaluate_asset(mid_analysis, None) if "error" not in mid_analysis else 0
    long_score  = evaluate_asset(long_analysis, weekly_analysis) if "error" not in long_analysis else 0
    
    return short_score, mid_score, long_score

# -----------------------------------------------------------------------------
# Improved Current Price Function with Timeframe Fallback
# -----------------------------------------------------------------------------
def get_current_price(symbol: str, asset_type: str, timeframe: str = "short"):
    """
    Retrieve the current price using different intervals based on the trading timeframe.
    timeframe: 'short', 'mid', or 'long'
    """
    try:
        yf_symbol = symbol.replace("USDT", "-USD") if asset_type == "crypto" and symbol.endswith("USDT") else symbol
        
        if timeframe == "short":
            # Intraday: try 1m; if empty, try 5m
            df = yf.download(yf_symbol, period="1d", interval="1m")
            if df.empty or df['Close'].dropna().empty:
                df = yf.download(yf_symbol, period="1d", interval="5m")
        elif timeframe == "mid":
            # Use hourly data for swing trading
            df = yf.download(yf_symbol, period="7d", interval="60m")
        else:  # long-term
            # Use daily data
            df = yf.download(yf_symbol, period="1mo", interval="1d")
        
        if not df.empty and 'Close' in df.columns:
            last_price = df['Close'].dropna().iloc[-1]
            return float(last_price)
        logging.warning(f"No price data returned for {symbol} with timeframe '{timeframe}'.")
        return None
    except Exception as e:
        logging.error(f"Error retrieving current price for {symbol}: {e}")
        return None

# -----------------------------------------------------------------------------
# Price Prediction Function (Unchanged)
# -----------------------------------------------------------------------------
def train_and_predict_price(symbol: str, asset_type: str, period: str = "1y"):
    try:
        yf_symbol = symbol.replace("USDT", "-USD") if asset_type == "crypto" and symbol.endswith("USDT") else symbol
        df = yf.download(yf_symbol, period=period, interval='1d')
        if df.empty or 'Close' not in df.columns:
            logging.warning(f"No valid historical data found for {yf_symbol}.")
            return None, None
        df = df.reset_index()
        df['DateOrdinal'] = df['Date'].apply(lambda x: x.toordinal())
        df['SMA_7'] = df['Close'].rolling(window=7, min_periods=1).mean()
        df['Volume'] = df.get('Volume', 0).fillna(0)
        features = ['DateOrdinal', 'SMA_7', 'Volume']
        X = df[features].values
        y = df['Close'].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = LinearRegression()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        logging.info(f"Trained model for {symbol}: MSE = {mse:.2f}, R2 = {r2:.2f}")
        os.makedirs("models", exist_ok=True)
        model_filename = os.path.join("models", f"{symbol}_linear_regression.joblib")
        joblib.dump(model, model_filename)
        logging.info(f"Saved model to {model_filename}")
        last_row = df.iloc[-1]
        tomorrow_ordinal = last_row['DateOrdinal'] + 1
        feature_vector = np.array([[tomorrow_ordinal, last_row['SMA_7'], last_row['Volume']]])
        predicted_price = model.predict(feature_vector)[0]
        return predicted_price, r2
    except Exception as e:
        logging.error(f"Error training model for {symbol}: {e}")
        return None, None

# -----------------------------------------------------------------------------
# Main Analysis Function (includes wallet assets and multi-timeframe evaluation)
# -----------------------------------------------------------------------------
def analyze_assets():
    stock_results = []
    crypto_results = []

    # Process TOP_ASSETS
    for asset in TOP_ASSETS:
        asset_type = detect_asset_type(asset)
        if asset_type == "crypto":
            symbol, exchange = detect_crypto_exchange(asset)
            if not symbol:
                logging.warning(f"Skipping {asset}: Not found on supported crypto exchanges.")
                continue
        else:
            symbol, exchange = detect_stock_exchange(asset)
            if not symbol:
                logging.warning(f"Skipping {asset}: Not found on supported stock exchanges.")
                continue

        # Get long-term daily and weekly analysis as before:
        daily_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_DAY)
        if "error" in daily_analysis:
            logging.error(f"Error fetching daily analysis for {asset}: {daily_analysis['error']}")
            continue

        weekly_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_WEEK)
        if "error" in weekly_analysis:
            logging.warning(f"Weekly analysis not available for {asset}. Using daily analysis only.")
            weekly_analysis = None

        # Compute overall score as before
        score = evaluate_asset(daily_analysis, weekly_analysis)
        rec = daily_analysis.get("recommendation", "N/A")
        rec_prio = rec_priority(rec)
        logging.info(f"Asset {asset}: Daily Recommendation: {rec}, Score: {score}")

        # Get multi-timeframe scores
        short_prob, mid_prob, long_prob = get_timeframe_scores(symbol, exchange, asset_type)
        # Recommend the horizon with the highest probability
        horizons = {"Short": short_prob, "Mid": mid_prob, "Long": long_prob}
        recommended_horizon = max(horizons, key=horizons.get)

        # Prepare asset data dictionary
        data = {
            "Symbol": daily_analysis["symbol"],
            "Exchange": daily_analysis["exchange"],
            "Daily Recommendation": rec,
            "Weekly Recommendation": weekly_analysis["recommendation"] if weekly_analysis else "N/A",
            "RSI": daily_analysis["RSI"],
            "MACD_Hist": daily_analysis["MACD_hist"],
            "Score": score,
            "RecPriority": rec_prio,
            "Predicted Price": None,
            "Current Price": None,
            "Model Accuracy": None,
            "Take Profit": None,
            "ATR": daily_analysis.get("indicators", {}).get("ATR", None),
            "Asset_Type": asset_type,
            "Source": "Top",
            "Short Probability": short_prob,
            "Mid Probability": mid_prob,
            "Long Probability": long_prob,
            "Recommended Horizon": recommended_horizon
        }
        if asset_type == "crypto":
            crypto_results.append(data)
        else:
            stock_results.append(data)

    # Build DataFrames and sort by Score (highest first)
    df_stocks = pd.DataFrame(stock_results)
    df_cryptos = pd.DataFrame(crypto_results)
    df_stocks_filtered = df_stocks[df_stocks["Score"] > 0].sort_values(by="Score", ascending=False)
    df_cryptos_filtered = df_cryptos[df_cryptos["Score"] > 0].sort_values(by="Score", ascending=False)

    top_stocks = df_stocks_filtered.head(10).copy()
    top_cryptos = df_cryptos_filtered.head(10).copy()
    best_stocks = top_stocks.head(5)
    best_cryptos = top_cryptos.head(5)

    # Run predictions and TP calculations for top assets
    for idx, row in top_stocks.iterrows():
        predicted_price, model_accuracy = train_and_predict_price(row["Symbol"], row["Asset_Type"], period="1y")
        # Use the recommended horizon for current price
        current_price = get_current_price(row["Symbol"], row["Asset_Type"], timeframe=row["Recommended Horizon"].lower())
        top_stocks.at[idx, "Predicted Price"] = predicted_price
        top_stocks.at[idx, "Current Price"] = current_price
        top_stocks.at[idx, "Model Accuracy"] = model_accuracy
        if current_price is not None:
            if row.get("ATR") is not None:
                tp = calculate_take_profit_atr(current_price, row["ATR"], atr_stop_loss_multiplier=1.5, risk_reward_ratio=2.0)
            else:
                tp = calculate_take_profit(current_price, DEFAULT_STOP_LOSS, DEFAULT_RISK_REWARD_RATIO)
            top_stocks.at[idx, "Take Profit"] = tp

    for idx, row in top_cryptos.iterrows():
        predicted_price, model_accuracy = train_and_predict_price(row["Symbol"], row["Asset_Type"], period="1y")
        current_price = get_current_price(row["Symbol"], row["Asset_Type"], timeframe=row["Recommended Horizon"].lower())
        top_cryptos.at[idx, "Predicted Price"] = predicted_price
        top_cryptos.at[idx, "Current Price"] = current_price
        top_cryptos.at[idx, "Model Accuracy"] = model_accuracy
        if current_price is not None:
            if row.get("ATR") is not None:
                tp = calculate_take_profit_atr(current_price, row["ATR"], atr_stop_loss_multiplier=1.5, risk_reward_ratio=2.0)
            else:
                tp = calculate_take_profit(current_price, DEFAULT_STOP_LOSS, DEFAULT_RISK_REWARD_RATIO)
            top_cryptos.at[idx, "Take Profit"] = tp

    # Process Wallet Assets (separately)
    wallet_stocks_list = []
    wallet_cryptos_list = []
    for asset in WALLET_STOCKS:
        symbol, exchange = detect_stock_exchange(asset)
        if not symbol or not exchange:
            logging.warning(f"Skipping wallet stock {asset}: Could not determine exchange/screener.")
            continue
        daily_analysis = get_tradingview_analysis(symbol, exchange, "america", interval=Interval.INTERVAL_1_DAY)
        if "error" in daily_analysis:
            logging.warning(f"Skipping wallet stock {symbol}: {daily_analysis['error']}")
            continue
        current_price = get_current_price(symbol, "america", timeframe="long")
        rec = daily_analysis.get("recommendation", "N/A")
        wallet_stocks_list.append({
            "Symbol": symbol,
            "Exchange": exchange,
            "Daily Recommendation": rec,
            "RSI": daily_analysis.get("RSI", 50),
            "MACD_Hist": daily_analysis.get("MACD_hist", 0),
            "Current Price": current_price,
            "RecPriority": rec_priority(rec),
            "Source": "Wallet"
        })

    for asset in WALLET_CRYPTOS:
        symbol, exchange = detect_crypto_exchange(asset)
        if not symbol or not exchange:
            logging.warning(f"Skipping wallet crypto {asset}: Could not determine exchange/screener.")
            continue
        daily_analysis = get_tradingview_analysis(symbol, exchange, "crypto", interval=Interval.INTERVAL_1_DAY)
        if "error" in daily_analysis:
            logging.warning(f"Skipping wallet crypto {symbol}: {daily_analysis['error']}")
            continue
        current_price = get_current_price(symbol, "crypto", timeframe="short")
        rec = daily_analysis.get("recommendation", "N/A")
        wallet_cryptos_list.append({
            "Symbol": symbol,
            "Exchange": exchange,
            "Daily Recommendation": rec,
            "RSI": daily_analysis.get("RSI", 50),
            "MACD_Hist": daily_analysis.get("MACD_hist", 0),
            "Current Price": current_price,
            "RecPriority": rec_priority(rec),
            "Source": "Wallet"
        })

    wallet_stocks_df = pd.DataFrame(wallet_stocks_list).sort_values(by="RecPriority", ascending=True)
    wallet_cryptos_df = pd.DataFrame(wallet_cryptos_list).sort_values(by="RecPriority", ascending=True)

    return best_stocks, top_stocks, best_cryptos, top_cryptos, wallet_stocks_df, wallet_cryptos_df

# -----------------------------------------------------------------------------
# Telegram Messaging Function
# -----------------------------------------------------------------------------
# Store message IDs in a JSON file
MESSAGE_LOG_FILE = "telegram_messages.json"

# Function to save message IDs
def save_message_id(message_id):
    try:
        if os.path.exists(MESSAGE_LOG_FILE):
            with open(MESSAGE_LOG_FILE, "r") as f:
                data = json.load(f)
        else:
            data = []

        data.append(message_id)

        with open(MESSAGE_LOG_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Error saving message ID: {e}")

# Function to load stored message IDs
def load_message_ids():
    try:
        if os.path.exists(MESSAGE_LOG_FILE):
            with open(MESSAGE_LOG_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading message IDs: {e}")
        return []

# Function to delete previous messages
async def delete_previous_messages():
    bot = Bot(token=BOT_TOKEN)
    message_ids = load_message_ids()

    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
            await asyncio.sleep(0.5)  # Prevent API spam
        except Exception as e:
            logging.warning(f"Could not delete message {msg_id}: {e}")

    # Clear message log after deletion
    with open(MESSAGE_LOG_FILE, "w") as f:
        json.dump([], f)

# Function to send a new message and store its ID
async def send_message_to_telegram(text: str, delete_old: bool = False):
    bot = Bot(token=BOT_TOKEN)

    # Delete previous messages if delete_old is True
    if delete_old:
        await delete_previous_messages()

    max_length = 4096  # Telegram message length limit
    messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]

    try:
        for msg in messages:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=msg)
            save_message_id(sent_message.message_id)
            await asyncio.sleep(1)  # Small delay to avoid rate limits
    except TimedOut:
        logging.error("Telegram API request timed out. Retrying in 10 seconds...")
        await asyncio.sleep(10)
        for msg in messages:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=msg)
            save_message_id(sent_message.message_id)
            await asyncio.sleep(1)

# -----------------------------------------------------------------------------
# Scheduled Job: Build and Send the Message
# -----------------------------------------------------------------------------
def daily_job():
    logging.info("Starting daily analysis job...")
    best_stocks, top_stocks, best_cryptos, top_cryptos, wallet_stocks, wallet_cryptos = analyze_assets()

    # Build the main message (without wallet assets)
    main_lines = [
        "📊 Daily Market Analysis 📊",
        "----------------------------------------",
        ""
    ]
    # --- Best Picks Section ---
    main_lines.append("🔥 Best Stock Picks (Top 5) 🔥")
    main_lines.append("")
    if not best_stocks.empty:
        for _, row in best_stocks.iterrows():
            symbol = row["Symbol"]
            rec = row["Daily Recommendation"]
            curr = row["Current Price"] or 0
            tp = row["Take Profit"] or 0
            score = row["Score"]
            probabilities = f"Short: {row['Short Probability']}% | Mid: {row['Mid Probability']}% | Long: {row['Long Probability']}%"
            rec_horizon = row["Recommended Horizon"]
            line = (f"• {symbol}: `Rec={rec}` | 📈 `Curr=${curr:,.2f}` | 🎯 `TP=${tp:,.2f}` | `Score={score}`\n"
                    f"   ➜ {probabilities} | Recommended: {rec_horizon}-term")
            main_lines.append(line)
            main_lines.append("")
    else:
        main_lines.append("No bullish stocks found. 😔")
        main_lines.append("")

    main_lines.append("🏢 Other Top Stocks")
    main_lines.append("")
    if not top_stocks.empty:
        for _, row in top_stocks.iterrows():
            if row["Symbol"] in best_stocks["Symbol"].values:
                continue
            symbol = row["Symbol"]
            rec = row["Daily Recommendation"]
            curr = row["Current Price"] or 0
            tp = row["Take Profit"] or 0
            score = row["Score"]
            probabilities = f"Short: {row['Short Probability']}% | Mid: {row['Mid Probability']}% | Long: {row['Long Probability']}%"
            rec_horizon = row["Recommended Horizon"]
            line = (f"• {symbol}: `Rec={rec}` | 📈 `Curr=${curr:,.2f}` | 🎯 `TP=${tp:,.2f}` | `Score={score}`\n"
                    f"   ➜ {probabilities} | Recommended: {rec_horizon}-term")
            main_lines.append(line)
            main_lines.append("")
    else:
        main_lines.append("No additional bullish stocks found. 😔")
        main_lines.append("")

    main_lines.append("🔥 Best Crypto Picks (Top 5) 🔥")
    main_lines.append("")
    if not best_cryptos.empty:
        for _, row in best_cryptos.iterrows():
            symbol = row["Symbol"]
            rec = row["Daily Recommendation"]
            curr = row["Current Price"] or 0
            tp = row["Take Profit"] or 0
            score = row["Score"]
            probabilities = f"Short: {row['Short Probability']}% | Mid: {row['Mid Probability']}% | Long: {row['Long Probability']}%"
            rec_horizon = row["Recommended Horizon"]
            line = (f"• {symbol}: `Rec={rec}` | 📈 `Curr=${curr:,.2f}` | 🎯 `TP=${tp:,.2f}` | `Score={score}`\n"
                    f"   ➜ {probabilities} | Recommended: {rec_horizon}-term")
            main_lines.append(line)
            main_lines.append("")
    else:
        main_lines.append("No bullish cryptos found. 😔")
        main_lines.append("")

    main_message = "\n".join(main_lines)

    # Build the wallet assets message separately
    wallet_lines = []
    wallet_lines.append("👜 My Stocks Wallet")
    wallet_lines.append("")
    if not wallet_stocks.empty:
        for _, row in wallet_stocks.iterrows():
            symbol = row["Symbol"]
            rec = row["Daily Recommendation"]
            curr = row["Current Price"] or 0
            line = f"• {symbol}: `Rec={rec}` | 📈 `Curr=${curr:,.2f}`"
            wallet_lines.append(line)
            wallet_lines.append("")
    else:
        wallet_lines.append("No wallet stocks data available. 😔")
        wallet_lines.append("")

    wallet_lines.append("👜 My Cryptos Wallet")
    wallet_lines.append("")
    if not wallet_cryptos.empty:
        for _, row in wallet_cryptos.iterrows():
            symbol = row["Symbol"]
            rec = row["Daily Recommendation"]
            curr = row["Current Price"] or 0
            line = f"• {symbol}: `Rec={rec}` | 📈 `Curr=${curr:,.2f}`"
            wallet_lines.append(line)
            wallet_lines.append("")
    else:
        wallet_lines.append("No wallet cryptos data available. 😔")
        wallet_lines.append("")

    wallet_message = "\n".join(wallet_lines)

    # Send the two messages separately:
    asyncio.run(send_message_to_telegram(main_message, delete_old=True))
    asyncio.run(send_message_to_telegram(wallet_message, delete_old=False))
    logging.info("Daily analysis job completed and messages sent.")

# -----------------------------------------------------------------------------
# Main Scheduler
# -----------------------------------------------------------------------------
def main():
    schedule.every().day.at("08:00").do(daily_job)
    schedule.every().day.at("16:00").do(daily_job)
    daily_job()  # Optional immediate run
    # Uncomment below to enable continuous scheduling:
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)

if __name__ == "__main__":
    main()
