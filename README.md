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
3. [Installation and Setup](#installation-and-setup)
4. [Directory Structure](#directory-structure)
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

---

## 3. Installation and Setup

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/sheydHD/trading_bot.git
   cd <your_repo_folder>
   ```

2. **Install Requirements**:

   ```bash
   pip install -r requirements.txt
   ```

   Typically, `requirements.txt` would include:

   ```text
   python-dotenv
   schedule
   yfinance
   pandas
   numpy
   tradingview_ta
   python-telegram-bot==20.0
   ```

   _(Adjust package versions as needed.)_

3. **Create a `.env` File**:

   Create an `.env` file in the root of your project to store environment variables (see [Environment Variables](#environment-variables)).

---

## 4. Directory Structure

```bash
.
├── main.py                # Or whichever name you use for the entry point script
├── telegram_messages.json  # JSON file storing Telegram message IDs
├── .env                   # Environment variables file (not committed)
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

_(You can adjust as needed for your project.)_

---

## 5. Environment Variables

| Variable             | Type    | Description                                              |
| -------------------- | ------- | -------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | string  | Your Telegram bot token obtained from BotFather          |
| `TELEGRAM_CHAT_ID`   | integer | The chat ID (or channel ID) where the bot sends messages |

**Example `.env` File:**

```ini
TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUV
TELEGRAM_CHAT_ID=123456789
```

> **Note**: Keep this file secret and avoid committing it to version control.

---

## 6. Running the Bot

Run the script (e.g., `main.py`) directly:

```bash
python main.py
```

By default, the script contains a `main()` function that:

1. Schedules tasks (analysis, reporting) at specific times (e.g., 08:00 and 16:00).
2. Invokes `daily_job()` immediately for an optional immediate run.
3. (Commented out) Continues scheduling in a `while True` loop.

If you want the bot to continuously run, make sure you uncomment the `while True:` block:

```python
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 7. Configuring the Scheduler

Currently, the code schedules tasks at 08:00 and 16:00 by default:

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

The bot uses Python’s built-in `logging` module:

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
