"""Central configuration — environment variables, asset lists, and constants.

Loads a single ``.env`` file from the project root (three directories above
this file).  All modules import symbols directly from here rather than
reading ``os.getenv`` themselves, ensuring a single source of truth.

Sections:
    - Telegram credentials (``BOT_TOKEN``, ``CHAT_ID``)
    - Risk management defaults
    - Scheduled alert times
    - Asset universes: ``TOP_STOCKS``, ``TOP_CRYPTOS`` (broad),
      ``PREDICTION_STOCKS/CRYPTOS`` (ML), ``WALLET_STOCKS/CRYPTOS`` (portfolio)
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load environment variables
# Single .env at project root (FAANG convention)
# ---------------------------------------------------------------------------
_ROOT_DIR = Path(__file__).resolve().parents[3]  # …/trading
_ENV_FILE = _ROOT_DIR / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)
else:
    load_dotenv()  # fall back to python-dotenv's default search

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
_chat_id_raw = os.getenv("TELEGRAM_CHAT_ID")
CHAT_ID: int | None = int(_chat_id_raw) if _chat_id_raw else None
if CHAT_ID is None:
    logger.warning("TELEGRAM_CHAT_ID is not set – Telegram messaging disabled")

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
    "BTC", "ETH", "USDT", "BNB", "XRP", "SOL", "USDC", "ADA", "DOGE", "TRX",
    "TON", "DOT", "MATIC", "DAI", "AVAX", "SHIB", "LTC", "WBTC", "BCH", "LINK",
    "UNI", "ICP", "LEO", "ETC", "XLM", "XMR", "FIL", "LDO", "OKB", "CRO",
    "ATOM", "HBAR", "APT", "VET", "QNT", "NEAR", "MKR", "GRT", "AAVE", "RETH",
    "ALGO", "STX", "EGLD", "XDC", "IMX", "SAND", "FTM", "XTZ", "MANA", "THETA",
    "BGB"
]

TOP_ASSETS = TOP_STOCKS + TOP_CRYPTOS

# ---------------------------------------------------------------------------
# Prediction engine – curated high-liquidity universe
# 20 large-cap stocks (sector-diversified) + 10 major cryptos
# Fewer symbols → better data quality, faster analysis, less rate-limiting
# ---------------------------------------------------------------------------
PREDICTION_STOCKS = [
    "AAPL",   # Tech – Consumer Electronics
    "MSFT",   # Tech – Software
    "GOOGL",  # Communication – Search & Cloud
    "AMZN",   # Consumer Discretionary – E-commerce & Cloud
    "NVDA",   # Semiconductors
    "META",   # Communication – Social Media
    "TSLA",   # Auto / Clean Energy
    "JPM",    # Financials – Banking
    "V",      # Financials – Payments
    "UNH",    # Healthcare – Insurance
    "XOM",    # Energy – Oil & Gas
    "PG",     # Consumer Staples
    "HD",     # Retail – Home Improvement
    "MA",     # Financials – Payments
    "AVGO",   # Semiconductors
    "COST",   # Retail – Wholesale
    "ABBV",   # Healthcare – Pharma
    "LLY",    # Healthcare – Pharma
    "MRK",    # Healthcare – Pharma
    "WMT",    # Retail – Grocery
]

PREDICTION_CRYPTOS = [
    "BTC",    # Bitcoin
    "ETH",    # Ethereum
    "SOL",    # Solana
    "BNB",    # Binance Coin
    "XRP",    # Ripple
    "ADA",    # Cardano
    "DOGE",   # Dogecoin
    "AVAX",   # Avalanche
    "LINK",   # Chainlink
    "DOT",    # Polkadot
]

# Wallet Assets
WALLET_STOCKS = ["1810.HK", "BKNG", "CSCO", "CTAS", "CVX", "DE", "KO", "LRCX", "MSFT", "NVDA", "PDD", "SO", "TXN", "SPOT", "VOO", "XEL"]
WALLET_CRYPTOS = ["BTC", "DEGEN","JUP", "PEPE", "WIF", "XRP"] 