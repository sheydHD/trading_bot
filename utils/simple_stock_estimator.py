import pandas as pd
from datetime import datetime
from tradingview_ta import TA_Handler, Interval

# Function to get TradingView analysis dynamically
def get_tradingview_analysis(symbol, exchange, screener, interval=Interval.INTERVAL_1_DAY):
    try:
        handler = TA_Handler(
            symbol=symbol.upper(),  # Ensures symbol is always uppercase
            screener=screener,
            exchange=exchange,
            interval=interval
        )

        analysis = handler.get_analysis()
        
        return {
            "symbol": symbol.upper(),
            "exchange": exchange,
            "timeframe": interval,
            "recommendation": analysis.summary.get("RECOMMENDATION", "N/A"),
            "oscillators": analysis.oscillators.get("RECOMMENDATION", "N/A"),
            "moving_averages": analysis.moving_averages.get("RECOMMENDATION", "N/A"),
            "indicators": analysis.indicators
        }
    
    except Exception as e:
        return {"symbol": symbol.upper(), "exchange": exchange, "error": str(e)}

# Function to detect whether the asset is a stock (US, EU, UK) or crypto
def detect_exchange(symbol):
    symbol = symbol.upper().strip()  # Ensure uppercase

    # **Check if it's a cryptocurrency**
    crypto_exchanges = ["BINANCE", "COINBASE", "KRAKEN"]
    if symbol in ["BTC", "ETH", "SOL", "DOGE", "BNB", "ADA", "XRP", "DOT", "SHIB"]:
        return symbol + "USDT", "BINANCE", "crypto"

    # **Mapping for European, UK, and US stocks**
    exchange_mapping = {
        "NASDAQ": "america", "NYSE": "america",
        "XETRA": "europe", "EURONEXT": "europe",
        "LSE": "uk", "TSE": "japan"
    }
    possible_exchanges = ["NASDAQ", "NYSE", "XETRA", "EURONEXT", "LSE"]

    # **Test each exchange**
    for exchange in possible_exchanges:
        screener = exchange_mapping[exchange]
        try:
            test_analysis = get_tradingview_analysis(symbol, exchange, screener)
            if "error" not in test_analysis:
                return symbol, exchange, screener
        except:
            continue

    return None, None, None  # If no valid exchange is found

# Function to analyze any stock or crypto dynamically
def analyze_asset(symbol):
    symbol, exchange, screener = detect_exchange(symbol.upper())  # Ensure uppercase

    if not symbol or not exchange:
        print(f"❌ Error: Could not determine the exchange for {symbol}. It may not be listed.")
        return

    # Get analysis from TradingView
    analysis_result = get_tradingview_analysis(symbol, exchange, screener)

    if "error" in analysis_result:
        print(f"❌ Error fetching {symbol}: {analysis_result['error']}")
        return

    # Print results
    print("\n🔹 TradingView Analysis for", symbol)
    print(f"Symbol: {analysis_result['symbol']} ({analysis_result['exchange']})")
    print(f"Overall Recommendation: {analysis_result['recommendation']}")
    print(f"Oscillators Signal: {analysis_result['oscillators']}")
    print(f"Moving Averages Signal: {analysis_result['moving_averages']}")

    # Save results to CSV
    result_data = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Symbol": analysis_result["symbol"],
        "Exchange": analysis_result["exchange"],
        "Timeframe": analysis_result["timeframe"],
        "Overall Recommendation": analysis_result["recommendation"],
        "Oscillators Signal": analysis_result["oscillators"],
        "Moving Averages Signal": analysis_result["moving_averages"],
        **analysis_result.get("indicators", {})  # Save all indicators
    }

    # Convert to DataFrame and save
    df = pd.DataFrame([result_data])
    filename = "asset_analysis.csv"
    df.to_csv(filename, mode='a', index=False, header=not pd.io.common.file_exists(filename))

    print(f"\n📊 Analysis saved to {filename} ✅")

    # 🚀 Final Recommendation
    print("\n🚀 FINAL DECISION:")
    if analysis_result["recommendation"] in ["STRONG_BUY", "BUY"]:
        print("✅ RECOMMENDATION: BUY 📈")
    elif analysis_result["recommendation"] in ["STRONG_SELL", "SELL"]:
        print("❌ RECOMMENDATION: SELL 📉")
    else:
        print("⚖️ RECOMMENDATION: HOLD/NEUTRAL ⏳")

# 🏆 User Input for Any Stock or Crypto (Automatically handles lowercase input)
user_asset = input("Enter any stock or crypto symbol (e.g., AAPL, TSLA, BTC, SOL, ZAL, WIZZ): ").strip().upper()
analyze_asset(user_asset)
