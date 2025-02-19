import pandas as pd
import matplotlib.pyplot as plt

# Define CSV file location
csv_file = "stock_analysis.csv"

# Load CSV file
try:
    df = pd.read_csv(csv_file)
    print(f"✅ Loaded {csv_file} successfully!")
except FileNotFoundError:
    print(f"❌ Error: The file '{csv_file}' was not found. Run the analysis script first.")
    exit()

# Convert 'Date' column to datetime format
df["Date"] = pd.to_datetime(df["Date"])

# Unique stocks in the dataset
stocks = df["Symbol"].unique()

# Define available indicators based on CSV headers
available_indicators = {
    "RSI": "RSI",
    "MACD": "MACD.macd",
    "MACD Signal": "MACD.signal",
    "EMA 20": "EMA20",
    "SMA 50": "SMA50",
    "ADX": "ADX",
    "CCI20": "CCI20",
    "Stochastic K": "Stoch.K",
    "Stochastic D": "Stoch.D",
}

# 📊 Plot indicators for each stock separately
for stock in stocks:
    stock_df = df[df["Symbol"] == stock]

    # Create a figure with subplots
    plt.figure(figsize=(12, 8))
    plt.suptitle(f"📈 Technical Analysis for {stock}", fontsize=14, fontweight="bold")

    # Plot RSI
    if "RSI" in df.columns:
        plt.subplot(3, 1, 1)
        plt.plot(stock_df["Date"], stock_df["RSI"], marker="o", linestyle="-", label="RSI", color="blue")
        plt.axhline(y=70, color="r", linestyle="--", label="Overbought (70)")
        plt.axhline(y=30, color="g", linestyle="--", label="Oversold (30)")
        plt.title("RSI Indicator")
        plt.xlabel("Date")
        plt.ylabel("RSI")
        plt.legend()
        plt.grid()

    # Plot MACD
    if "MACD.macd" in df.columns and "MACD.signal" in df.columns:
        plt.subplot(3, 1, 2)
        plt.plot(stock_df["Date"], stock_df["MACD.macd"], marker="s", linestyle="-", label="MACD", color="purple")
        plt.plot(stock_df["Date"], stock_df["MACD.signal"], marker="x", linestyle="--", label="MACD Signal", color="orange")
        plt.axhline(y=0, color="gray", linestyle="--", label="Zero Line")
        plt.title("MACD Indicator")
        plt.xlabel("Date")
        plt.ylabel("MACD")
        plt.legend()
        plt.grid()

    # Plot EMA & SMA
    if "EMA20" in df.columns and "SMA50" in df.columns:
        plt.subplot(3, 1, 3)
        plt.plot(stock_df["Date"], stock_df["EMA20"], marker="o", linestyle="-", label="EMA 20", color="blue")
        plt.plot(stock_df["Date"], stock_df["SMA50"], marker="s", linestyle="--", label="SMA 50", color="orange")
        plt.title("Moving Averages (EMA 20 & SMA 50)")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        plt.grid()

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()
