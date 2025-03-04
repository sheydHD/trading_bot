"""Configuration settings for the trading bot."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

# Risk Management Parameters
DEFAULT_STOP_LOSS = -0.30  # -30% stop loss
DEFAULT_RISK_REWARD_RATIO = 3.0  # 3:1 risk-reward ratio

# Scheduled Times
SCHEDULED_TIMES = [
    "08:00", "15:35", "16:00", "16:30", 
    "17:00", "18:00", "19:00", "20:00"
]

# Asset Lists
TOP_STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    # ... rest of the stocks ...
]

TOP_CRYPTOS = [
    "BTC", "ETH", "USDT", "BNB", "XRP",
    # ... rest of the cryptos ...
]

TOP_ASSETS = TOP_STOCKS + TOP_CRYPTOS

# Wallet Assets
WALLET_STOCKS = ["1810.HK", "BKNG", "CSCO", "CTAS", "CVX", "DE", "KO", "LRCX", "MSFT", "NVDA", "PDD", "SO", "TXN", "SPOT", "VOO", "XEL"]
WALLET_CRYPTOS = ["BTC", "DEGEN","JUP", "PEPE", "WIF", "XRP"] 