# AI Trading Chatbot for Stock and Cryptocurrency Analysis

This repository contains a Python-based AI trading chatbot that provides **technical analysis** and **Telegram messaging** functionalities for popular stocks and cryptocurrencies. The bot:

- Gathers technical analysis data from [TradingView](https://tradingview.com) via the `tradingview_ta` library.
- Retrieves market data from [Yahoo Finance](https://finance.yahoo.com) with the `yfinance` library.
- Sends automated analysis reports and target price updates via Telegram.
- Uses schedule-based tasks to execute daily or multiple times a day.

---

## Table of Contents

1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Installation and Setup](#installation-and-setup)
5. [Environment Variables](#environment-variables)
6. [Running the Bot](#running-the-bot)
7. [Configuring the Scheduler](#configuring-the-scheduler)
8. [How the Bot Works](#how-the-bot-works)
9. [Risk Management Parameters](#risk-management-parameters)
10. [Logging](#logging)
11. [Maintenance and Troubleshooting](#maintenance-and-troubleshooting)
12. [License](#license)

---

## 1. Features

1. **Technical Analysis**: Fetches signals (e.g., RSI, MACD histogram, and moving averages) from TradingView for stocks and cryptocurrencies.
2. **Risk Management**: Provides default stop-loss and risk/reward settings for each asset.
3. **Multiple Assets**: Supports top stocks (like AAPL, MSFT, NVDA) and top cryptocurrencies (like BTC, ETH, BNB).
4. **Automated Telegram Alerts**: Sends consolidated analysis reports to a Telegram channel.
5. **Scheduling**: Uses the `schedule` library to automate analysis at specific times during the day.

---

## 2. Prerequisites

Make sure you have the following tools installed:

- Python 3.7+
- Pip (Python package manager)
- A [Telegram Bot](https://core.telegram.org/bots#6-botfather) with an active bot token
- [TradingView](https://tradingview.com) account (for the `tradingview_ta` library)
- Node.js and npm (for the frontend)

---

## 3. Project Structure

The project has been organized into a clean, modular structure:

```
.
├── backend/                # Backend Python code
│   ├── api/                # API endpoints
│   ├── config/             # Configuration files (.env, requirements)
│   ├── core/               # Core application files
│   ├── data/               # Data storage
│   │   └── cache/          # Cache files (JSON)
│   ├── logs/               # Log files
│   └── utils/              # Utility modules
│       ├── analysis.py     # Technical analysis functions
│       ├── cache.py        # Caching utilities
│       ├── config.py       # Configuration constants
│       ├── email.py        # Email notification utilities
│       ├── price.py        # Price data functions
│       ├── rate_limiter.py # Rate limiting utilities
│       └── telegram.py     # Telegram bot utilities
│
├── docker/                 # Docker configuration
│   ├── Dockerfile          # Docker configuration
│   ├── docker-compose.yml  # Docker Compose configuration
│   ├── docker-entrypoint.sh # Docker entrypoint script
│   └── .dockerignore       # Docker ignore file
│
├── frontend/               # Frontend React application
│   ├── config/             # Frontend configuration
│   │   ├── package.json    # NPM package definition
│   │   ├── postcss.config.js # PostCSS configuration
│   │   └── tailwind.config.js # Tailwind CSS configuration
│   ├── public/             # Static assets
│   └── src/                # React source code
│       ├── components/     # React components
│       ├── context/        # React context providers
│       ├── pages/          # Page components
│       ├── services/       # API service functions
│       └── utils/          # Frontend utilities
│
├── scripts/                # Utility scripts
│   ├── cleanup.sh          # Cleanup script for removing redundant files
│   └── setup.sh            # Setup script for initializing the project
│
├── run.py                  # Entry point script
├── setup.sh -> scripts/setup.sh        # Symlink to setup script
├── cleanup.sh -> scripts/cleanup.sh    # Symlink to cleanup script
├── LICENSE                 # License file
└── README.md               # Project documentation
```

---

## 4. Installation and Setup

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/sheydHD/trading_bot.git
   cd <your_repo_folder>
   ```

2. **Run the Setup Script**:

   ```bash
   ./setup.sh
   ```

   This script will:

   - Create necessary directories
   - Copy environment configuration files
   - Install Python dependencies
   - Set up the frontend (if applicable)

3. **Configure Environment Variables**:

   Edit the environment file with your API keys and configuration:

   ```bash
   nano backend/config/.env
   ```

---

## 5. Environment Variables

| Variable             | Type    | Description                                              |
| -------------------- | ------- | -------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | string  | Your Telegram bot token obtained from BotFather          |
| `TELEGRAM_CHAT_ID`   | integer | The chat ID (or channel ID) where the bot sends messages |

The environment variables are stored in:

- `backend/config/.env` for development
- `backend/config/.env.production` for production

> **Note**: Keep these files secret and avoid committing them to version control.

---

## 6. Running the Bot

Run the backend script:

```bash
./run.py
```

For the frontend (if applicable):

```bash
cd frontend
npm start
```

### Using Docker (optional)

To run the application with Docker:

```bash
cd docker
docker-compose up
```

---

## 7. Configuring the Scheduler

The scheduler configuration is in `backend/core/main.py`. By default, it schedules tasks at 08:00 and 16:00:

```python
schedule.every().day.at("08:00").do(daily_job)
schedule.every().day.at("16:00").do(daily_job)
```

You can easily change or add more triggers. For example:

```python
# Every 2 hours
schedule.every(2).hours.do(daily_job)

# Every Monday at 9:15 AM
schedule.every().monday.at("09:15").do(daily_job)
```

For more scheduling options, refer to the [schedule library docs](https://github.com/dbader/schedule).

---

## 8. How the Bot Works

1. **Analyze Stocks & Cryptos**: The `analyze_assets()` function loops through defined `TOP_STOCKS` and `TOP_CRYPTOS`.
   - Detects if each symbol is for stocks (`america`) or crypto.
   - Fetches daily & weekly `tradingview_ta` signals.
   - Evaluates each asset with a scoring system (`evaluate_asset`).
   - Builds DataFrames for stocks and cryptos.
2. **Send Telegram Messages**: Summarizes top 5 stocks, top 5 cryptos, and also displays wallet assets. Messages are sent to Telegram via the `python-telegram-bot` library.
3. **Cleanup**: Old Telegram messages are deleted to keep the chat tidy.

---

## 9. Risk Management Parameters

- `DEFAULT_STOP_LOSS = -0.30` (–30%)
- `DEFAULT_RISK_REWARD_RATIO = 2.0`

**Take-Profit Calculation**:

1. `calculate_take_profit()`: If the asset drops 30%, the risk is 30%. With a 2:1 ratio, the take-profit is +60% from entry.
2. `calculate_take_profit_atr()`: Alternative method using [ATR (Average True Range)](https://www.investopedia.com/terms/a/atr.asp) for volatility-based stop loss.

---

## 10. Logging

The bot uses Python's built-in `logging` module:

```python
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
```

Logs are displayed on the console by default. Adjust the logging level or add file handlers as needed.

---

## 11. Maintenance and Troubleshooting

### 11.1 Updating the Symbol Lists

- **Stock Symbols**: Update `TOP_STOCKS` or `WALLET_STOCKS` lists.
- **Crypto Symbols**: Update `TOP_CRYPTOS` or `WALLET_CRYPTOS` lists.

### 11.2 Common Issues

1. **TradingView API Errors**: `tradingview_ta` might fail if the symbol or exchange is incorrect.
2. **Telegram Rate Limits**: Keep messages under 4096 characters and pace your sends.
3. **No Data from Yahoo Finance**: Ensure the symbol is valid (especially for cryptos, e.g., use `BTC-USD`).

### 11.3 Keep Libraries Updated

- `pip install --upgrade tradingview_ta yfinance python-dotenv python-telegram-bot`

---

## 12. License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). Feel free to customize or extend.
