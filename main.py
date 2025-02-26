import os
import logging
import pandas as pd
import asyncio
import time
import json
from dotenv import load_dotenv

import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.error import TimedOut
from telegram import Bot
from tradingview_ta import TA_Handler, Interval

# -----------------------------------------------------------------------------
# Load environment variables from .env file
# -----------------------------------------------------------------------------
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
DEFAULT_RISK_REWARD_RATIO = 3.0  # 3:1 risk-reward ratio

# -----------------------------------------------------------------------------
# List of scheduled times
# -----------------------------------------------------------------------------
SCHEDULED_TIMES = [
    "08:00", "15:35", "16:00", "16:30", 
    "17:00", "18:00", "19:00", "20:00"
]

# -----------------------------------------------------------------------------
# Asset Lists
# -----------------------------------------------------------------------------
TOP_STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "AVGO", "COST",
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
WALLET_STOCKS = ["1810.HK", "BKNG", "CSCO", "CTAS", "CVX", "DE", "KO", "LRCX", "MSFT", "NVDA", "PDD", "SO", "TXN", "SPOT", "VOO", "XEL"]
WALLET_CRYPTOS = ["BTC", "DEGEN","JUP", "PEPE", "WIF", "XRP"]

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
            "indicators": analysis.indicators  # stored for fallback use in price fetching
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
    short_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_15_MINUTES)
    mid_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_HOUR)
    long_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_DAY)
    weekly_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_WEEK)
    
    short_score = evaluate_asset(short_analysis, None) if "error" not in short_analysis else 0
    mid_score   = evaluate_asset(mid_analysis, None) if "error" not in mid_analysis else 0
    long_score  = evaluate_asset(long_analysis, weekly_analysis) if "error" not in long_analysis else 0
    
    return short_score, mid_score, long_score

# -----------------------------------------------------------------------------
# Improved Current Price Function with Fallback
# -----------------------------------------------------------------------------
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

        # Get daily and weekly analysis
        daily_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_DAY)
        if "error" in daily_analysis:
            logging.error(f"Error fetching daily analysis for {asset}: {daily_analysis['error']}")
            continue

        weekly_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_WEEK)
        if "error" in weekly_analysis:
            logging.warning(f"Weekly analysis not available for {asset}. Using daily analysis only.")
            weekly_analysis = None

        # Compute overall score
        score = evaluate_asset(daily_analysis, weekly_analysis)
        rec = daily_analysis.get("recommendation", "N/A")
        rec_prio = rec_priority(rec)
        logging.info(f"Asset {asset}: Daily Recommendation: {rec}, Score: {score}")

        # Get multi-timeframe scores
        short_prob, mid_prob, long_prob = get_timeframe_scores(symbol, exchange, asset_type)
        horizons = {"Short": short_prob, "Mid": mid_prob, "Long": long_prob}
        recommended_horizon = max(horizons, key=horizons.get)

        # Prepare asset data dictionary.
        # Note: 'Indicators' are saved to be used as fallback for price fetching.
        data = {
            "Symbol": daily_analysis["symbol"],
            "Exchange": daily_analysis["exchange"],
            "Daily Recommendation": rec,
            "Weekly Recommendation": weekly_analysis["recommendation"] if weekly_analysis else "N/A",
            "RSI": daily_analysis["RSI"],
            "MACD_Hist": daily_analysis["MACD_hist"],
            "Score": score,
            "RecPriority": rec_prio,
            "Predicted Price": None,    # Removed linear regression prediction.
            "Current Price": None,
            "Model Accuracy": None,     # Removed model metrics.
            "Take Profit": None,
            "ATR": daily_analysis.get("indicators", {}).get("ATR", None),
            "Asset_Type": asset_type,
            "Source": "Top",
            "Short Probability": short_prob,
            "Mid Probability": mid_prob,
            "Long Probability": long_prob,
            "Recommended Horizon": recommended_horizon,
            "Indicators": daily_analysis.get("indicators")
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

    # Update top assets with current price and take profit calculations.
    for idx, row in top_stocks.iterrows():
        # Linear regression prediction removed; set as None.
        current_price = get_current_price(row["Symbol"], row["Asset_Type"], tv_indicators=row["Indicators"])
        top_stocks.at[idx, "Current Price"] = current_price
        if current_price is not None:
            if row.get("ATR") is not None:
                tp = calculate_take_profit_atr(current_price, row["ATR"], atr_stop_loss_multiplier=1.5, risk_reward_ratio=2.0)
            else:
                tp = calculate_take_profit(current_price, DEFAULT_STOP_LOSS, DEFAULT_RISK_REWARD_RATIO)
            top_stocks.at[idx, "Take Profit"] = tp

    for idx, row in top_cryptos.iterrows():
        current_price = get_current_price(row["Symbol"], row["Asset_Type"], tv_indicators=row["Indicators"])
        top_cryptos.at[idx, "Current Price"] = current_price
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
        current_price = get_current_price(symbol, "america", tv_indicators=daily_analysis.get("indicators"))
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
        current_price = get_current_price(symbol, "crypto", tv_indicators=daily_analysis.get("indicators"))
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
MESSAGE_LOG_FILE = "telegram_messages.json"

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

def load_message_ids():
    try:
        if os.path.exists(MESSAGE_LOG_FILE):
            with open(MESSAGE_LOG_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading message IDs: {e}")
        return []

async def delete_previous_messages():
    bot = Bot(token=BOT_TOKEN)
    message_ids = load_message_ids()
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
            await asyncio.sleep(0.5)
        except Exception as e:
            logging.warning(f"Could not delete message {msg_id}: {e}")
    with open(MESSAGE_LOG_FILE, "w") as f:
        json.dump([], f)

async def send_message_to_telegram(text: str, delete_old: bool = False):
    bot = Bot(token=BOT_TOKEN)
    if delete_old:
        await delete_previous_messages()
    max_length = 4096
    messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    try:
        for msg in messages:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=msg)
            save_message_id(sent_message.message_id)
            await asyncio.sleep(1)
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

    asyncio.run(send_message_to_telegram(main_message, delete_old=True))
    asyncio.run(send_message_to_telegram(wallet_message, delete_old=False))
    logging.info("Daily analysis job completed and messages sent.")

# -----------------------------------------------------------------------------
# Main Scheduler
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    # -----------------------------------------------------------------------------
    # APScheduler Setup
    # -----------------------------------------------------------------------------
    scheduler = BackgroundScheduler()

    # Schedule a job for each time with misfire handling.
    for t in SCHEDULED_TIMES:
        hour, minute = map(int, t.split(':'))
        trigger = CronTrigger(hour=hour, minute=minute)
        scheduler.add_job(
            daily_job,
            trigger,
            id=f"daily_job_{t}",
            misfire_grace_time=3600,  # Allows the job to run if delayed within 1 hour.
            coalesce=True           # If multiple runs are missed, only one execution occurs.
        )
        logging.info("Scheduled daily_job at %s", t)

    scheduler.start()
    logging.info("Scheduler started.")

    try:
        # Keep the main thread alive.
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logging.info("Scheduler shutdown.")