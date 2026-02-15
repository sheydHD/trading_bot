import os
import logging
import pandas as pd
import asyncio
import time
import json
import concurrent.futures
import logging.handlers
import signal
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from pykalman import KalmanFilter
import requests
from textblob import TextBlob
import ta

import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.error import TimedOut
from telegram import Bot
from tradingview_ta import TA_Handler, Interval

from apps.backend.utils.analysis import rec_priority
from apps.backend.utils.telegram import (
    send_message_to_telegram as util_send_message_to_telegram,
    delete_previous_messages as util_delete_previous_messages,
)
from apps.backend.utils.config import (
    BOT_TOKEN, CHAT_ID,
    TOP_STOCKS, TOP_CRYPTOS, WALLET_STOCKS, WALLET_CRYPTOS,
    DEFAULT_STOP_LOSS, DEFAULT_RISK_REWARD_RATIO, SCHEDULED_TIMES
)
from apps.backend.utils.rate_limiter import rate_limited
from apps.backend.utils.cache import PersistentCache
from apps.backend.utils.email import send_email

# NOTE: Environment variables are loaded by utils.config on import.

# -----------------------------------------------------------------------------
# Runtime feature flags and resource limits (configurable via env)
# -----------------------------------------------------------------------------
ANALYSIS_MODE = os.getenv("ANALYSIS_MODE", "light").lower()  # light | full
ENABLE_SENTIMENT = os.getenv("ENABLE_SENTIMENT", "false").lower() == "true"
ENABLE_KALMAN = os.getenv("ENABLE_KALMAN", "false").lower() == "true"
ENABLE_ML = os.getenv("ENABLE_ML", "false").lower() == "true"
MAX_WORKERS = max(1, int(os.getenv("MAX_WORKERS", "3")))
MAX_STOCKS = int(os.getenv("MAX_STOCKS", "30")) if ANALYSIS_MODE == "light" else len(TOP_STOCKS)
MAX_CRYPTOS = int(os.getenv("MAX_CRYPTOS", "15")) if ANALYSIS_MODE == "light" else len(TOP_CRYPTOS)

# -----------------------------------------------------------------------------
# Define paths for logs and cache
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
CACHE_DIR = os.path.join(BASE_DIR, 'data', 'cache')

# Create directories if they don't exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# File paths
LOG_FILE = os.path.join(LOG_DIR, 'trading_bot.log')
TELEGRAM_MESSAGES_FILE = os.path.join(CACHE_DIR, 'telegram_messages.json')
ANALYSIS_CACHE_FILE = os.path.join(CACHE_DIR, 'analysis_cache.json')

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
def setup_logging():
    """Configure logging with rotation and proper formatting."""
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s')
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5*1024*1024, backupCount=5
    )
    file_handler.setFormatter(log_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

# BOT_TOKEN, CHAT_ID, WALLET_STOCKS, WALLET_CRYPTOS imported from utils.config
TOP_ASSETS = TOP_STOCKS + TOP_CRYPTOS

# -----------------------------------------------------------------------------
# Global Cache for TradingView Analysis (for improved performance)
# -----------------------------------------------------------------------------
analysis_cache = PersistentCache(cache_file=ANALYSIS_CACHE_FILE, expiry_seconds=3600)

# rec_priority() imported from utils.analysis

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
def detect_crypto_exchange(symbol: str):
    exchanges = ["BINANCE", "COINBASE", "KRAKEN", "BYBIT"]
    # Check cache first
    cached = analysis_cache.get(("exchange", symbol, "crypto"))
    if cached:
        return cached.get("tv_symbol"), cached.get("exchange")
    for exchange in exchanges:
        try:
            test_symbol = symbol.upper() + "USDT"
            # Use "crypto" as the screener for all crypto assets
            test_analysis = get_tradingview_analysis(test_symbol, exchange, "crypto", interval=Interval.INTERVAL_1_DAY)
            if "error" not in test_analysis:
                analysis_cache.set(("exchange", symbol, "crypto"), {"tv_symbol": test_symbol, "exchange": exchange})
                return test_symbol, exchange
        except Exception as e:
            logging.debug(f"Exchange {exchange} test failed for {symbol}: {e}")
    return None, None

def detect_stock_exchange(symbol: str):
    """Detects the correct exchange for a given stock symbol."""
    
    screener_map = {
        "HK": "hongkong",
        "L": "uk",
        "T": "japan",
        "AX": "australia",
        "CN": "canada",
        "PA": "france",
        "DE": "germany",
        "NS": "india",
        "JK": "indonesia",
        "TA": "israel",
        "MI": "italy",
        "KL": "malaysia",
        "MX": "mexico",
        "NZ": "newzealand",
        "QA": "qatar",
        "SA": "saudiarabia",
        "SG": "singapore",
        "KS": "southkorea",
        "MC": "spain",
        "ST": "sweden",
        "SW": "switzerland",
        "TW": "taiwan",
        "BK": "thailand",
        "IS": "turkey",
        "AE": "uae",
        "VN": "vietnam"
    }
    
    screener = "america"
    if "." in symbol:
        suffix = symbol.split('.')[-1]
        screener = screener_map.get(suffix, "america")

    exchanges = {
        "america": ["NASDAQ", "NYSE", "AMEX"],
        "hongkong": ["HKEX"],
        "uk": ["LSE"],
        "japan": ["TSE"],
        "australia": ["ASX"],
        "canada": ["TSX", "TSXV"],
        "france": ["EURONEXT"],
        "germany": ["XETRA", "FWB"],
        "india": ["NSE", "BSE"],
        "indonesia": ["IDX"],
        "israel": ["TASE"],
        "italy": ["MIL"],
        "malaysia": ["MYX"],
        "mexico": ["BMV"],
        "newzealand": ["NZX"],
        "qatar": ["QSE"],
        "saudiarabia": ["TADAWUL"],
        "singapore": ["SGX"],
        "southkorea": ["KRX"],
        "spain": ["BME"],
        "sweden": ["OMXSTO"],
        "switzerland": ["SIX"],
        "taiwan": ["TWSE"],
        "thailand": ["SET"],
        "turkey": ["BIST"],
        "uae": ["DFM", "ADX"],
        "vietnam": ["HOSE", "HNX"]
    }.get(screener, [])
    
    cached = analysis_cache.get(("exchange", symbol, "stock"))
    if cached:
        return symbol, cached.get("exchange"), screener

    for exchange in exchanges:
        try:
            test_analysis = get_tradingview_analysis(symbol, exchange, screener, interval=Interval.INTERVAL_1_DAY)
            if "error" not in test_analysis:
                analysis_cache.set(("exchange", symbol, "stock"), {"exchange": exchange})
                return symbol, exchange, screener
        except Exception as e:
            logging.debug(f"Exchange {exchange} test failed for {symbol}: {e}")
            
    return None, None, None

@rate_limited(calls_per_second=1)  # Limit to 1 call per second
def get_tradingview_analysis(symbol: str, exchange: str, screener: str, interval=Interval.INTERVAL_1_DAY) -> dict:
    """
    Retrieve TradingView analysis for the specified asset.
    Uses a persistent cache to reduce repeated API calls.
    """
    key = (symbol.upper(), exchange, screener, interval)
    
    # Check cache first
    cached_result = analysis_cache.get(key)
    if cached_result:
        return cached_result
    
    for attempt in range(3):
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
            
            # Store in cache
            analysis_cache.set(key, result)
            return result
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait_time = 2 ** attempt
                logging.warning(f"Rate limited. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                analysis_cache.set(key, {"error": str(e)}, expiry_seconds=300) # Cache errors for 5 minutes
                return {"symbol": symbol.upper(), "exchange": exchange, "error": str(e)}
    return {"symbol": symbol.upper(), "exchange": exchange, "error": "Max retries exceeded"}

def evaluate_asset(daily_analysis: dict, weekly_analysis: dict = None) -> int:
    """
    Enhanced evaluation for an asset using multiple methods.
    Uses recommendation, advanced indicators, sentiment, ML and statistical validation.
    Returns a score from 0 to 100.
    """
    score = 50  # Base score

    # 1. TradingView Recommendation (25% of score)
    rec = daily_analysis.get("recommendation", "NEUTRAL").upper()
    rec_adjustment = {"STRONG_BUY": 20, "BUY": 10, "NEUTRAL": 0, "SELL": -10, "STRONG_SELL": -20}
    score += rec_adjustment.get(rec, 0) * 0.25

    # 2. Enhanced Technical Analysis (25% of score)
    # RSI adjustment with zone awareness
    rsi = daily_analysis.get("RSI", 50)
    # Handle overbought and oversold conditions with more nuance
    if rsi > 70:  # Overbought
        rsi_adjustment = -10
    elif rsi < 30:  # Oversold
        rsi_adjustment = 10
    else:  # Look for momentum in the middle zone
        rsi_momentum = daily_analysis.get("indicators", {}).get("RSI[1]", rsi) - rsi
        rsi_adjustment = 5 * (1 if rsi_momentum > 0 else -1 if rsi_momentum < 0 else 0)
    score += rsi_adjustment

    # MACD with signal line crossover detection
    macd = daily_analysis.get("indicators", {}).get("MACD.macd", 0)
    macd_signal = daily_analysis.get("indicators", {}).get("MACD.signal", 0)
    macd_hist = daily_analysis.get("MACD_hist", macd - macd_signal)
    macd_hist_prev = daily_analysis.get("indicators", {}).get("MACD.hist[1]", macd_hist)
    
    # Detect crossover (more powerful signal)
    if macd_hist > 0 and macd_hist_prev < 0:  # Bullish crossover
        score += 15
    elif macd_hist < 0 and macd_hist_prev > 0:  # Bearish crossover
        score -= 15
    elif macd_hist > 0:  # Positive but no crossover
        score += 5
    elif macd_hist < 0:  # Negative but no crossover
        score -= 5
    
    # 3. Volume analysis (new addition)
    volume = daily_analysis.get("indicators", {}).get("volume", 0)
    volume_ma = daily_analysis.get("indicators", {}).get("volume_ma", 0)
    if volume > volume_ma * 1.5:  # Significant volume spike
        # Volume confirms price direction
        if macd_hist > 0:  # Bullish with high volume
            score += 10
        elif macd_hist < 0:  # Bearish with high volume
            score -= 10
    
    # 4. Trend strength analysis (new addition)
    adx = daily_analysis.get("indicators", {}).get("ADX", 0)
    if adx > 25:  # Strong trend
        if macd_hist > 0:  # Strong bullish trend
            score += 10
        elif macd_hist < 0:  # Strong bearish trend
            score -= 10
    
    # Weekly analysis adjustment with more weight
    if weekly_analysis and "error" not in weekly_analysis:
        weekly_rec = weekly_analysis.get("recommendation", "NEUTRAL").upper()
        weekly_adjustment = {"STRONG_BUY": 15, "BUY": 10, "NEUTRAL": 0, "SELL": -10, "STRONG_SELL": -15}
        score += weekly_adjustment.get(weekly_rec, 0)
        
        # Multi-timeframe confluence check
        if (weekly_rec in ["STRONG_BUY", "BUY"] and 
            rec in ["STRONG_BUY", "BUY"]):
            score += 10  # Extra points for multi-timeframe confluence
    
    # Ensure score is between 0 and 100
    return max(0, min(100, int(score)))

def get_sentiment_score(symbol: str) -> float:
    """
    Get market sentiment for a symbol from news articles and social media.
    Returns a score between -1 (very negative) and 1 (very positive).
    """
    try:
        # Try to get news from a financial news API (implement your API key)
        news_endpoint = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={symbol}&limit=10&apikey=YOUR_API_KEY"
        response = requests.get(news_endpoint)
        if response.status_code == 200:
            news_data = response.json()
            sentiment_scores = []
            for article in news_data:
                title = article.get('title', '')
                if title:
                    blob = TextBlob(title)
                    sentiment_scores.append(blob.sentiment.polarity)
            
            # Return average sentiment if we have scores
            if sentiment_scores:
                return sum(sentiment_scores) / len(sentiment_scores)
        
        # Default neutral sentiment if API fails
        return 0.0
    except Exception as e:
        logging.warning(f"Error getting sentiment for {symbol}: {e}")
        return 0.0  # Neutral sentiment as fallback

def apply_kalman_filter(symbol: str, exchange: str, asset_type: str) -> dict:
    """
    Apply Kalman filter for statistical validation and noise reduction in price prediction.
    Returns a dict with filtered price and volatility estimates.
    """
    try:
        # Get historical data - you'll need to implement your data source
        if asset_type == "crypto":
            # Use your existing crypto data fetching method
            data = fetch_crypto_historical(symbol, days=30)
        else:
            # Use your existing stock data fetching method
            data = fetch_stock_historical(symbol, days=30)
        
        if data is None or len(data) < 10:
            return {"filtered_price": None, "volatility": None}
        
        # Extract closing prices
        prices = data['close'].values
        
        # Initialize Kalman Filter
        kf = KalmanFilter(
            initial_state_mean=prices[0],
            initial_state_covariance=1.0,
            observation_covariance=0.1,
            transition_covariance=0.01
        )
        
        # Apply filter
        filtered_state_means, filtered_state_covariances = kf.filter(prices)
        
        return {
            "filtered_price": filtered_state_means[-1][0],
            "volatility": np.sqrt(filtered_state_covariances[-1][0][0])
        }
    except Exception as e:
        logging.warning(f"Error applying Kalman filter for {symbol}: {e}")
        return {"filtered_price": None, "volatility": None}

def generate_ml_prediction(symbol: str, days_ahead=5) -> dict:
    """
    Generate machine learning prediction for price movement.
    Uses Random Forest regressor with technical indicators as features.
    """
    try:
        # Fetch historical data - implement your data source
        historical_data = fetch_historical_data(symbol, days=120)
        if historical_data is None or len(historical_data) < 60:
            return {"prediction": None, "confidence": 0}
        
        # Create features using the TA library
        df = historical_data.copy()
        
        # Add technical indicators as features
        df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
        
        # Price-based features
        df['return_1d'] = df['close'].pct_change(1)
        df['return_5d'] = df['close'].pct_change(5)
        df['volatility'] = df['return_1d'].rolling(window=20).std()
        
        # Create target: future price change
        df['target'] = df['close'].shift(-days_ahead) / df['close'] - 1
        
        # Drop NaN and prepare datasets
        df = df.dropna()
        if len(df) < 30:
            return {"prediction": None, "confidence": 0}
        
        # Prepare features and target
        features = ['rsi', 'macd', 'macd_signal', 'macd_diff', 'atr', 'return_1d', 'return_5d', 'volatility']
        X = df[features]
        y = df['target']
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        # Standardize features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train_scaled, y_train)
        
        # Make prediction
        predicted_return = model.predict(X_test_scaled[-1:])
        confidence = model.score(X_test_scaled, y_test)
        
        return {
            "prediction": float(predicted_return[0]),
            "confidence": confidence
        }
    except Exception as e:
        logging.warning(f"Error generating ML prediction for {symbol}: {e}")
        return {"prediction": None, "confidence": 0}

def get_timeframe_scores(symbol: str, exchange: str, asset_type: str):
    """
    Get scores for short, mid, and long timeframes.
    Short: 15-minute interval; Mid: 1-hour interval; Long: daily (with weekly bonus).
    Returns a tuple: (short_score, mid_score, long_score)
    """
    short_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_15_MINUTES) if ANALYSIS_MODE == "full" else {"recommendation": "NEUTRAL", "indicators": {}}
    mid_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_HOUR) if ANALYSIS_MODE == "full" else {"recommendation": "NEUTRAL", "indicators": {}}
    long_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_DAY)
    weekly_analysis = get_tradingview_analysis(symbol, exchange, asset_type, interval=Interval.INTERVAL_1_WEEK) if ANALYSIS_MODE == "full" else None
    
    short_score = evaluate_asset(short_analysis, None) if "error" not in short_analysis else 0
    mid_score   = evaluate_asset(mid_analysis, None) if "error" not in mid_analysis else 0
    long_score  = evaluate_asset(long_analysis, weekly_analysis) if "error" not in long_analysis else 0
    
    return short_score, mid_score, long_score

# -----------------------------------------------------------------------------
# Main Analysis Function (includes wallet assets and multi-timeframe evaluation)
# -----------------------------------------------------------------------------
def analyze_assets(send_messages=False):
    """
    Main analysis function used by both command line and API.
    
    Args:
        send_messages: Whether to send Telegram/email messages (True for CLI, False for API)
    
    Returns:
        Tuple of DataFrames containing analysis results
    """
    print("Starting analysis process...")
    stock_results = []
    crypto_results = []

    # Process assets in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Process TOP_ASSETS
        futures = []
        limited_assets = TOP_STOCKS[:MAX_STOCKS] + TOP_CRYPTOS[:MAX_CRYPTOS]
        for asset in limited_assets:
            futures.append(executor.submit(analyze_single_asset, asset))
        
        # Collect results
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                if result["Asset_Type"] == "crypto":
                    crypto_results.append(result)
                else:
                    stock_results.append(result)

    # Build DataFrames and sort by Score (highest first)
    df_stocks = pd.DataFrame(stock_results)
    df_cryptos = pd.DataFrame(crypto_results)
    
    # Handle empty dataframes
    if df_stocks.empty:
        logging.warning("No stock results found. Creating empty DataFrame.")
        df_stocks = pd.DataFrame(columns=["Symbol", "Exchange", "Score", "Asset_Type"])
    
    if df_cryptos.empty:
        logging.warning("No crypto results found. Creating empty DataFrame.")
        df_cryptos = pd.DataFrame(columns=["Symbol", "Exchange", "Score", "Asset_Type"])
    
    # Filter and sort by Score
    df_stocks_filtered = df_stocks[df_stocks["Score"] > 0].sort_values(by="Score", ascending=False) if not df_stocks.empty else df_stocks
    df_cryptos_filtered = df_cryptos[df_cryptos["Score"] > 0].sort_values(by="Score", ascending=False) if not df_cryptos.empty else df_cryptos

    top_stocks = df_stocks_filtered.head(10).copy() if not df_stocks_filtered.empty else pd.DataFrame()
    top_cryptos = df_cryptos_filtered.head(10).copy() if not df_cryptos_filtered.empty else pd.DataFrame()
    best_stocks = top_stocks.head(6) if not top_stocks.empty else pd.DataFrame()
    best_cryptos = top_cryptos.head(6) if not top_cryptos.empty else pd.DataFrame()

    # Update top assets with current price and take profit calculations
    if not top_stocks.empty:
        for idx, row in top_stocks.iterrows():
            try:
                # Get current price using our enhanced method
                symbol = row["Symbol"]
                exchange = row["Exchange"]
                asset_type = row["Asset_Type"]
                
                # Make sure we have Indicators to pass
                indicators = row.get("Indicators", {})
                if not isinstance(indicators, dict):
                    indicators = {}
                
                # Get current price using TV indicators as a fallback
                current_price = get_current_price(symbol, exchange, asset_type, tv_indicators=indicators)
                top_stocks.at[idx, "Current Price"] = current_price
                
                if current_price is not None:
                    if row.get("ATR") is not None:
                        tp = calculate_take_profit_atr(current_price, row["ATR"], atr_stop_loss_multiplier=1.5, risk_reward_ratio=2.0)
                    else:
                        tp = calculate_take_profit(current_price, DEFAULT_STOP_LOSS, DEFAULT_RISK_REWARD_RATIO)
                    top_stocks.at[idx, "Take Profit"] = tp
            except Exception as e:
                logging.warning(f"Error updating price for {row['Symbol']}: {e}")
                continue

    if not top_cryptos.empty:
        for idx, row in top_cryptos.iterrows():
            try:
                # Get current price using our enhanced method
                symbol = row["Symbol"]
                exchange = row["Exchange"]
                asset_type = row["Asset_Type"]
                
                # Make sure we have Indicators to pass
                indicators = row.get("Indicators", {})
                if not isinstance(indicators, dict):
                    indicators = {}
                
                # Get current price using TV indicators as a fallback
                current_price = get_current_price(symbol, exchange, asset_type, tv_indicators=indicators)
                top_cryptos.at[idx, "Current Price"] = current_price
                
                if current_price is not None:
                    if row.get("ATR") is not None:
                        tp = calculate_take_profit_atr(current_price, row["ATR"], atr_stop_loss_multiplier=1.5, risk_reward_ratio=2.0)
                    else:
                        tp = calculate_take_profit(current_price, DEFAULT_STOP_LOSS, DEFAULT_RISK_REWARD_RATIO)
                    top_cryptos.at[idx, "Take Profit"] = tp
            except Exception as e:
                logging.warning(f"Error updating price for {row['Symbol']}: {e}")
                continue

    # Process Wallet Assets (separately)
    wallet_stocks_list = []
    wallet_cryptos_list = []
    
    # Process wallet stocks
    for asset in WALLET_STOCKS[:10] if ANALYSIS_MODE == "light" else WALLET_STOCKS:
        try:
            symbol, exchange, screener = detect_stock_exchange(asset)
            if not symbol or not exchange:
                logging.warning(f"Skipping wallet stock {asset}: Could not determine exchange/screener.")
                continue
                
            daily_analysis = get_tradingview_analysis(symbol, exchange, screener, interval=Interval.INTERVAL_1_DAY)
            if "error" in daily_analysis:
                logging.warning(f"Skipping wallet stock {symbol}: {daily_analysis['error']}")
                continue
                
            # Get current price with fallbacks
            current_price = get_current_price(symbol, exchange, "stock", tv_indicators=daily_analysis.get("indicators", {}))
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
        except Exception as e:
            logging.warning(f"Error processing wallet stock {asset}: {e}")
            continue
    
    # Process wallet cryptos
    for asset in WALLET_CRYPTOS[:10] if ANALYSIS_MODE == "light" else WALLET_CRYPTOS:
        try:
            symbol, exchange = detect_crypto_exchange(asset)
            if not symbol or not exchange:
                logging.warning(f"Skipping wallet crypto {asset}: Could not determine exchange/screener.")
                continue
                
            daily_analysis = get_tradingview_analysis(symbol, exchange, "crypto", interval=Interval.INTERVAL_1_DAY)
            if "error" in daily_analysis:
                logging.warning(f"Skipping wallet crypto {symbol}: {daily_analysis['error']}")
                continue
                
            # Get current price with fallbacks
            current_price = get_current_price(symbol, exchange, "crypto", tv_indicators=daily_analysis.get("indicators", {}))
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
        except Exception as e:
            logging.warning(f"Error processing wallet crypto {asset}: {e}")
            continue
    
    # Create DataFrames from the lists
    wallet_stocks = pd.DataFrame(wallet_stocks_list).sort_values(by="RecPriority", ascending=True) if wallet_stocks_list else pd.DataFrame()
    wallet_cryptos = pd.DataFrame(wallet_cryptos_list).sort_values(by="RecPriority", ascending=True) if wallet_cryptos_list else pd.DataFrame()

    # Improved logging of results
    logging.info(f"Analysis completed. Found {len(best_stocks)} best stocks, {len(best_cryptos)} best cryptos")
    logging.info(f"Wallet contains {len(wallet_stocks)} stocks and {len(wallet_cryptos)} cryptos")
    
    if not best_stocks.empty:
        logging.debug(f"Best stocks: {', '.join(best_stocks['Symbol'].tolist())}")
    if not best_cryptos.empty:
        logging.debug(f"Best cryptos: {', '.join(best_cryptos['Symbol'].tolist())}")
    
    # Return all DataFrames for web UI
    return best_stocks, top_stocks, best_cryptos, top_cryptos, wallet_stocks, wallet_cryptos

def analyze_single_asset(asset):
    
    if asset in TOP_CRYPTOS or asset in WALLET_CRYPTOS:
        asset_type = "crypto"
        symbol, exchange = detect_crypto_exchange(asset)
        screener = "crypto"
        if not symbol:
            logging.warning(f"Skipping {asset}: Not found on supported crypto exchanges.")
            return None
    else:
        asset_type = "stock"
        symbol, exchange, screener = detect_stock_exchange(asset)
        if not symbol:
            logging.warning(f"Skipping {asset}: Not found on supported stock exchanges.")
            return None

    # Get daily (and weekly in full mode) analysis
    daily_analysis = get_tradingview_analysis(symbol, exchange, screener, interval=Interval.INTERVAL_1_DAY)
    if "error" in daily_analysis:
        logging.error(f"Error fetching daily analysis for {asset}: {daily_analysis['error']}")
        return None

    weekly_analysis = None
    if ANALYSIS_MODE == "full":
        weekly = get_tradingview_analysis(symbol, exchange, screener, interval=Interval.INTERVAL_1_WEEK)
        if "error" not in weekly:
            weekly_analysis = weekly

    # Get sentiment analysis (new)
    sentiment_score = get_sentiment_score(symbol) if ENABLE_SENTIMENT else 0.0
    
    # Apply Kalman filter for statistical validation (new)
    kalman_results = apply_kalman_filter(symbol, exchange, asset_type) if ENABLE_KALMAN else {"filtered_price": None, "volatility": None}
    
    # Generate ML predictions (new)
    ml_prediction = generate_ml_prediction(symbol) if ENABLE_ML else {"prediction": None, "confidence": 0}
    
    # Compute enhanced overall score
    basic_score = evaluate_asset(daily_analysis, weekly_analysis)
    
    # Adjust score based on new analysis methods
    final_score = basic_score
    
    # Sentiment adjustment (up to 10 points)
    if sentiment_score > 0.2:  # Positive sentiment
        final_score += min(10, sentiment_score * 20)
    elif sentiment_score < -0.2:  # Negative sentiment
        final_score -= min(10, abs(sentiment_score * 20))
    
    # ML prediction adjustment (up to 15 points)
    if ml_prediction["prediction"] is not None and ml_prediction.get("confidence", 0) > 0.6:
        if ml_prediction["prediction"] > 0.02:  # Predicted 2%+ gain
            final_score += min(15, ml_prediction["prediction"] * 300)
        elif ml_prediction["prediction"] < -0.02:  # Predicted 2%+ loss
            final_score -= min(15, abs(ml_prediction["prediction"] * 300))
    
    # Ensure score is between 0 and 100
    final_score = max(0, min(100, int(final_score)))
    
    rec = daily_analysis.get("recommendation", "N/A")
    rec_prio = rec_priority(rec)
    logging.info(f"Asset {asset}: Daily Recommendation: {rec}, Enhanced Score: {final_score}")

    # Get multi-timeframe scores
    short_prob, mid_prob, long_prob = get_timeframe_scores(symbol, exchange, asset_type)
    horizons = {"Short": short_prob, "Mid": mid_prob, "Long": long_prob}
    recommended_horizon = max(horizons, key=horizons.get)

    # Prepare asset data dictionary with enhanced information
    data = {
        "Symbol": daily_analysis["symbol"],
        "Exchange": daily_analysis["exchange"],
        "Daily Recommendation": rec,
        "Weekly Recommendation": weekly_analysis["recommendation"] if weekly_analysis else "N/A",
        "RSI": daily_analysis["RSI"],
        "MACD_Hist": daily_analysis["MACD_hist"],
        "Basic Score": basic_score,
        "Score": final_score,
        "RecPriority": rec_prio,
        "Sentiment": sentiment_score,
        "ML_Prediction": ml_prediction["prediction"],
        "ML_Confidence": ml_prediction["confidence"],
        "Kalman_Price": kalman_results["filtered_price"],
        "Kalman_Volatility": kalman_results["volatility"],
        "Current Price": None,
        "Take Profit": None,
        "ATR": daily_analysis.get("indicators", {}).get("ATR", None),
        "Asset_Type": asset_type,
        "Source": "Top",
        "Short_Term": short_prob,
        "Mid_Term": mid_prob,
        "Long_Term": long_prob,
        "Recommended_Horizon": recommended_horizon,
        "Indicators": daily_analysis.get("indicators", {})
    }
    
    # Try to get current price
    try:
        data["Current Price"] = get_current_price(symbol, exchange, asset_type)
        
        # Calculate take profit level if price and ATR are available
        if data["Current Price"] and data["ATR"]:
            data["Take Profit"] = calculate_take_profit_atr(
                data["Current Price"], 
                data["ATR"]
            )
    except Exception as e:
        logging.warning(f"Could not get price for {symbol}: {e}")
        
    return data

# New utility functions for fetching historical data
def fetch_historical_data(symbol, days=120):
    """Fetch historical market data for a symbol."""
    try:
        if symbol in TOP_CRYPTOS or symbol in WALLET_CRYPTOS:
            return fetch_crypto_historical(symbol, days)
        else:
            return fetch_stock_historical(symbol, days)
    except Exception as e:
        logging.error(f"Error fetching historical data for {symbol}: {e}")
        return None

def fetch_stock_historical(symbol, days=120):
    """Fetch historical stock data using yfinance."""
    try:
        import yfinance as yf
        stock = yf.Ticker(symbol)
        df = stock.history(period=f"{days}d")
        if df.empty:
            return None
        return df.rename(columns={
            'Open': 'open', 
            'High': 'high', 
            'Low': 'low', 
            'Close': 'close', 
            'Volume': 'volume'
        })
    except Exception as e:
        logging.error(f"Error fetching stock historical data for {symbol}: {e}")
        return None

def fetch_crypto_historical(symbol, days=120):
    """Fetch historical cryptocurrency data with multiple fallback options."""
    try:
        # Try different symbol formats for Yahoo Finance
        symbol_formats = [
            symbol,  # Original format
            symbol.replace("USDT", "-USD"),  # Convert BTCUSDT to BTC-USD format
            symbol.split("USDT")[0] + "-USD" if "USDT" in symbol else symbol  # Alternative format
        ]
        
        # Try each format with Yahoo Finance
        for sym_format in symbol_formats:
            try:
                import yfinance as yf
                logging.debug(f"Trying Yahoo Finance with symbol: {sym_format}")
                stock = yf.Ticker(sym_format)
                df = stock.history(period=f"{days}d")
                if not df.empty:
                    logging.info(f"Successfully fetched data for {symbol} using format {sym_format}")
                    return df.rename(columns={
                        'Open': 'open', 
                        'High': 'high', 
                        'Low': 'low', 
                        'Close': 'close', 
                        'Volume': 'volume'
                    })
            except Exception as e:
                logging.debug(f"Failed to fetch {sym_format} from Yahoo Finance: {e}")
                continue
        
        # If Yahoo Finance fails for all formats, try CCXT
        logging.info(f"Falling back to CCXT for {symbol}")
        try:
            import ccxt
            exchange = ccxt.binance()
            timeframe = '1d'
            limit = days
            symbol_ccxt = symbol if "USDT" in symbol else f"{symbol}/USDT"
            ohlcv = exchange.fetch_ohlcv(symbol_ccxt, timeframe, limit=limit)
            
            if ohlcv and len(ohlcv) > 0:
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                logging.info(f"Successfully fetched {symbol} data from CCXT")
                return df
        except Exception as e:
            logging.warning(f"CCXT fallback failed for {symbol}: {e}")
        
        # Last resort - try to generate dummy data for testing purposes
        logging.warning(f"All data sources failed for {symbol}. Using dummy data for testing.")
        dates = pd.date_range(end=pd.Timestamp.now(), periods=days)
        dummy_data = {
            'open': [100] * days,
            'high': [105] * days,
            'low': [95] * days,
            'close': [101] * days,
            'volume': [1000000] * days
        }
        return pd.DataFrame(dummy_data, index=dates)
        
    except Exception as e:
        logging.error(f"All methods failed to fetch historical data for {symbol}: {e}")
        return None

# -----------------------------------------------------------------------------
# Telegram Messaging Function
# -----------------------------------------------------------------------------
MESSAGE_LOG_FILE = TELEGRAM_MESSAGES_FILE

def save_message_id(message_id):
    """Save the Telegram message ID to a JSON file."""
    message_ids = load_message_ids()
    message_ids.append(message_id)
    
    with open(TELEGRAM_MESSAGES_FILE, 'w') as f:
        json.dump(message_ids, f)

def load_message_ids():
    """Load the saved Telegram message IDs from a JSON file."""
    try:
        with open(TELEGRAM_MESSAGES_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def delete_previous_messages():
    if BOT_TOKEN is None or CHAT_ID is None:
        logging.warning("Telegram bot is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables to enable messaging.")
        return

    bot = Bot(token=BOT_TOKEN)
    message_ids = load_message_ids()
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
            await asyncio.sleep(0.5)
        except Exception as e:
            logging.warning(f"Could not delete message {msg_id}: {e}")
    with open(TELEGRAM_MESSAGES_FILE, "w") as f:
        json.dump([], f)

async def send_message_to_telegram(text: str, delete_old: bool = False):
    if BOT_TOKEN is None or CHAT_ID is None:
        logging.warning("Telegram bot is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables to enable messaging.")
        return None
        
    bot = Bot(token=BOT_TOKEN)
    if delete_old:
        await delete_previous_messages()
    max_length = 4096
    messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    sent_message_ids = []
    try:
        for msg in messages:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=msg)
            sent_message_ids.append(sent_message.message_id)
            save_message_id(sent_message.message_id)
            await asyncio.sleep(1)
        logging.info(f"Successfully sent {len(messages)} message(s) to Telegram")
        return sent_message_ids
    except TimedOut:
        logging.error("Telegram API request timed out. Retrying in 10 seconds...")
        await asyncio.sleep(10)
        sent_message_ids = []
        for msg in messages:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=msg)
            sent_message_ids.append(sent_message.message_id)
            save_message_id(sent_message.message_id)
            await asyncio.sleep(1)
        logging.info(f"Successfully sent {len(messages)} message(s) to Telegram after retry")
        return sent_message_ids
    except Exception as e:
        logging.error(f"Error sending Telegram message: {str(e)}")
        return []

# -----------------------------------------------------------------------------
# Scheduled Job: Build and Send the Message
# -----------------------------------------------------------------------------
def daily_job():
    try:
        logging.info("Starting daily analysis job...")
        best_stocks, top_stocks, best_cryptos, top_cryptos, wallet_stocks, wallet_cryptos = analyze_assets(send_messages=True)

        main_lines = [
            "📊 Daily Market Analysis 📊",
            "----------------------------------------",
            ""
        ]
        # --- Best Picks Section ---
        main_lines.append("🔥 Best Stock Picks (Top 6) 🔥")
        main_lines.append("")
        if not best_stocks.empty:
            for _, row in best_stocks.iterrows():
                try:
                    line = format_asset_line(row)
                    main_lines.append(line)
                    main_lines.append("")
                except Exception as e:
                    logging.error(f"Error formatting stock {row.get('Symbol', 'unknown')}: {e}")
                    main_lines.append(f"• {row.get('Symbol', 'unknown')}: Error displaying data")
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
                try:
                    line = format_asset_line(row)
                    main_lines.append(line)
                    main_lines.append("")
                except Exception as e:
                    logging.error(f"Error formatting stock {row.get('Symbol', 'unknown')}: {e}")
                    main_lines.append(f"• {row.get('Symbol', 'unknown')}: Error displaying data")
                    main_lines.append("")
        else:
            main_lines.append("No additional bullish stocks found. 😔")
            main_lines.append("")

        main_lines.append("🔥 Best Crypto Picks (Top 6) 🔥")
        main_lines.append("")
        if not best_cryptos.empty:
            for _, row in best_cryptos.iterrows():
                try:
                    line = format_asset_line(row)
                    main_lines.append(line)
                    main_lines.append("")
                except Exception as e:
                    logging.error(f"Error formatting crypto {row.get('Symbol', 'unknown')}: {e}")
                    main_lines.append(f"• {row.get('Symbol', 'unknown')}: Error displaying data")
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
                try:
                    line = format_asset_line(row)
                    wallet_lines.append(line)
                    wallet_lines.append("")
                except Exception as e:
                    logging.error(f"Error formatting wallet stock {row.get('Symbol', 'unknown')}: {e}")
                    wallet_lines.append(f"• {row.get('Symbol', 'unknown')}: Error displaying data")
                    wallet_lines.append("")
        else:
            wallet_lines.append("No wallet stocks data available. 😔")
            wallet_lines.append("")

        wallet_lines.append("👜 My Cryptos Wallet")
        wallet_lines.append("")
        if not wallet_cryptos.empty:
            for _, row in wallet_cryptos.iterrows():
                try:
                    line = format_asset_line(row)
                    wallet_lines.append(line)
                    wallet_lines.append("")
                except Exception as e:
                    logging.error(f"Error formatting wallet crypto {row.get('Symbol', 'unknown')}: {e}")
                    wallet_lines.append(f"• {row.get('Symbol', 'unknown')}: Error displaying data")
                    wallet_lines.append("")
        else:
            wallet_lines.append("No wallet cryptos data available. 😔")
            wallet_lines.append("")

        wallet_message = "\n".join(wallet_lines)

        # Send to Telegram
        asyncio.run(util_send_message_to_telegram(main_message, delete_old=True))
        asyncio.run(util_send_message_to_telegram(wallet_message, delete_old=False))
        
        # Send directly to email
        if os.getenv("EMAIL_ENABLED", "false").lower() == "true":
            # Extract subject from first line
            first_line = main_lines[0] if main_lines else "Trading Bot Update"
            subject = first_line[:50] + "..." if len(first_line) > 50 else first_line
            
            # Combine messages for email
            full_content = main_message + "\n\n" + wallet_message
            
            # Send email directly
            send_email(subject, full_content)
        
        logging.info("Daily analysis job completed and messages sent.")
    except Exception as e:
        error_message = f"❌ Error in daily analysis job: {str(e)}"
        logging.error(error_message, exc_info=True)
        asyncio.run(util_send_message_to_telegram(error_message, delete_old=False))

def format_asset_line(row):
    """Format a single asset line for the Telegram message."""
    symbol = row.get("Symbol", "Unknown")
    rec = row.get("Daily Recommendation", "N/A")
    curr = row.get("Current Price", 0) or 0
    
    # Basic line for all assets
    line = f"• {symbol}: `Rec={rec}` | 📈 `Curr=${curr:,.2f}`"
    
    # Add take profit and score for top assets
    if "Score" in row:
        score = row.get("Score", "N/A")
        tp = row.get("Take Profit", 0) or 0
        line += f" | 🎯 `TP=${tp:,.2f}` | `Score={score}`"
        
        # Check for both old and new probability field names
        probability_fields = [
            ["Short_Term", "Mid_Term", "Long_Term"],  # New field names
            ["Short Probability", "Mid Probability", "Long Probability"]  # Old field names
        ]
        
        for fields in probability_fields:
            if all(k in row for k in fields):
                # Use the matched field set
                short_prob = row[fields[0]]
                mid_prob = row[fields[1]]
                long_prob = row[fields[2]]
                probabilities = f"Short: {short_prob}% | Mid: {mid_prob}% | Long: {long_prob}%"
                
                # Check for both old and new recommended horizon field names
                if "Recommended_Horizon" in row:
                    rec_horizon = row.get("Recommended_Horizon", "N/A")
                elif "Recommended Horizon" in row:
                    rec_horizon = row.get("Recommended Horizon", "N/A")
                else:
                    rec_horizon = "N/A"
                    
                line += f"\n   ➜ {probabilities} | Recommended: {rec_horizon}-term"
                break  # Found a matching set, no need to check others
        
        # Add ML prediction info if available
        if "ML_Prediction" in row and row["ML_Prediction"] is not None:
            pred = row["ML_Prediction"] * 100  # Convert to percentage
            confidence = row.get("ML_Confidence", 0) * 100  # Convert to percentage
            prediction_text = f"Up {pred:.1f}%" if pred > 0 else f"Down {abs(pred):.1f}%"
            line += f"\n   🤖 ML Prediction: `{prediction_text}` (Confidence: {confidence:.0f}%)"
        
        # Add sentiment score if available and significant
        if "Sentiment" in row and abs(row["Sentiment"]) > 0.1:
            sentiment = row["Sentiment"]
            sentiment_emoji = "😀" if sentiment > 0.3 else "🙂" if sentiment > 0 else "😐" if sentiment > -0.3 else "😕"
            line += f"\n   {sentiment_emoji} Sentiment: {sentiment:.2f}"
    
    # For wallet assets, add simple RSI if available
    elif "RSI" in row and "Source" in row and row.get("Source") == "Wallet":
        rsi = row.get("RSI", 50)
        rsi_emoji = "🔥" if rsi < 30 else "🥶" if rsi > 70 else "🧊" 
        line += f" | RSI: `{rsi:.1f}` {rsi_emoji}"
    
    return line

def signal_handler(sig, frame):
    """Handle termination signals gracefully."""
    logging.info("Received termination signal. Shutting down...")
    scheduler.shutdown()
    logging.info("Scheduler shutdown complete.")
    sys.exit(0)

def reset_telegram_messages():
    try:
        if os.path.exists(MESSAGE_LOG_FILE):
            with open(MESSAGE_LOG_FILE, "r") as f:
                data = json.load(f)
            # Remove the last 2 message IDs
            data = data[:-2] if len(data) >= 2 else []
            with open(MESSAGE_LOG_FILE, "w") as f:
                json.dump(data, f)
            logging.info(f"Removed last 2 message IDs from {MESSAGE_LOG_FILE}")
        else:
            logging.warning(f"{MESSAGE_LOG_FILE} does not exist")
    except Exception as e:
        logging.error(f"Error updating message IDs: {e}")

def get_current_price(symbol, exchange, asset_type, tv_indicators=None):
    """
    Enhanced current price fetching with multiple fallbacks.
    It tries methods one by one and returns as soon as one is successful.
    
    Args:
        symbol: Asset symbol
        exchange: Exchange name
        asset_type: 'crypto' or 'stock'
        tv_indicators: TradingView indicators (optional fallback)
        
    Returns:
        Current price as float or None if not available
    """
    
    # Method 1: Use cached TradingView close price if available
    if tv_indicators and isinstance(tv_indicators, dict):
        tv_close = tv_indicators.get("close")
        if tv_close is not None:
            logging.info(f"SUCCESS (source: TradingView cache) - Found price for {symbol}: {tv_close}")
            return float(tv_close)

    # For crypto assets, try CCXT then Yahoo Finance
    if asset_type == "crypto":
        # Method 2 (Crypto): Try CCXT
        try:
            import ccxt
            exchange_obj = ccxt.binance()
            symbol_ccxt = symbol if "USDT" in symbol else f"{symbol}/USDT"
            ticker = exchange_obj.fetch_ticker(symbol_ccxt)
            if ticker and 'last' in ticker:
                price = float(ticker['last'])
                logging.info(f"SUCCESS (source: CCXT) - Found price for {symbol}: {price}")
                return price
        except Exception as e:
            logging.debug(f"INFO (source: CCXT) - Could not fetch {symbol}: {e}")

        # Method 3 (Crypto): Try Yahoo Finance with different formats
        for sym_format in [symbol.replace("USDT", "-USD"), symbol.split("USDT")[0] + "-USD" if "USDT" in symbol else symbol]:
            try:
                import yfinance as yf
                data = yf.download(sym_format, period="1d", interval="1m", auto_adjust=False, progress=False)
                if not data.empty and 'Close' in data.columns:
                    price = float(data['Close'].values.flat[-1])
                    logging.info(f"SUCCESS (source: yfinance) - Found price for {sym_format}: {price}")
                    return price
            except Exception as e:
                logging.debug(f"INFO (source: yfinance) - Could not fetch {sym_format}: {e}")
                continue # continue to next format
        
    # For stock assets, try Yahoo Finance
    elif asset_type == "stock":
        # Method 2 (Stock): Try Yahoo Finance
        try:
            import yfinance as yf
            data = yf.download(symbol, period="1d", interval="1m", auto_adjust=False, progress=False)
            if not data.empty and 'Close' in data.columns:
                price = float(data['Close'].values.flat[-1])
                logging.info(f"SUCCESS (source: yfinance) - Found price for {symbol}: {price}")
                return price
        except Exception as e:
            logging.debug(f"INFO (source: yfinance) - Could not fetch {symbol}: {e}")

    logging.warning(f"FAILED (all sources) - Could not get current price for {symbol}")
    return None

if __name__ == '__main__':
    setup_logging()
    # Remove the last 2 message IDs from telegram_messages.json
    reset_telegram_messages()
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
    
    daily_job()
    scheduler.start()
    logging.info("Scheduler started.")

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Keep the main thread alive.
        while True:
            time.sleep(60)
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
        scheduler.shutdown()
        logging.info("Scheduler shutdown due to error.")
        sys.exit(1)