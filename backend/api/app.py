"""Flask API for the trading bot analysis."""

import os
import sys
import json
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import pandas as pd
import time

# Add the parent directory to the Python path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary utilities from backends
from utils.analysis import analyze_assets, fetch_stock_data, fetch_crypto_data, analyze_data
from utils.cache import PersistentCache

# Import your main analysis function
# Update this import to use the correct module path
from core.main import analyze_assets as main_analyze_assets

# Load environment variables
load_dotenv()

# Get the location of frontend build files
BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'build'))
if not os.path.exists(BUILD_DIR):
    # Fallback to Docker environment where build is at the app root
    BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..', 'build'))
    if not os.path.exists(BUILD_DIR):
        print(f"WARNING: Build directory not found at {BUILD_DIR}. Trying root app directory...")
        BUILD_DIR = os.path.abspath('/app/build')

# Initialize Flask app with the appropriate static folder
app = Flask(__name__, static_folder=BUILD_DIR)
CORS(app, supports_credentials=True)  # Enable CORS for all routes

print(f"Static folder set to: {BUILD_DIR}")
print(f"Static folder exists: {os.path.exists(BUILD_DIR)}")
if os.path.exists(BUILD_DIR):
    print(f"Build directory contents: {os.listdir(BUILD_DIR)}")
else:
    print("WARNING: Build directory does not exist. Frontend will not be served correctly!")

# Authentication (Simple API key for demonstration)
API_KEY = os.getenv("API_KEY", "your-secret-api-key")

# Storage for analysis history
analysis_history = []

# Set up cache file in the appropriate location
if os.path.exists('/app/backend/data'):
    analysis_cache_file = "/app/backend/data/cache/analysis_cache.json"
else:
    analysis_cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache", "analysis_cache.json")

# Ensure directory exists
os.makedirs(os.path.dirname(analysis_cache_file), exist_ok=True)

# Load existing cache data if it exists
if os.path.exists(analysis_cache_file):
    try:
        with open(analysis_cache_file, 'r') as f:
            cached_data = json.load(f)
            analysis_cache = PersistentCache(cache_file=analysis_cache_file, initial_data=cached_data)
            print(f"Loaded analysis cache from {analysis_cache_file}")
    except Exception as e:
        print(f"Error loading cache: {e}")
        analysis_cache = PersistentCache(cache_file=analysis_cache_file)
else:
    analysis_cache = PersistentCache(cache_file=analysis_cache_file)
    print(f"Created new analysis cache at {analysis_cache_file}")

# Global variables to track analysis status
analysis_status = {
    "is_running": False,
    "start_time": None,
    "current_step": 0,
    "total_steps": 5,
    "current_step_name": "",
    "logs": []
}

def authenticate(request):
    """Simple API key authentication."""
    # For development, allow requests without authentication
    if os.getenv("FLASK_ENV") == "development":
        return True
        
    api_key = request.headers.get('X-API-Key')
    return api_key == API_KEY

def add_log(message, log_type="info"):
    """Add a log message to the status logs."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    analysis_status["logs"].append({
        "timestamp": timestamp,
        "message": message,
        "type": log_type
    })
    # Keep only the last 100 logs
    if len(analysis_status["logs"]) > 100:
        analysis_status["logs"].pop(0)

@app.route('/api/analysis/latest', methods=['GET'])
def get_latest_analysis():
    """Get the latest analysis results."""
    if not authenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Try to get cached result first
    cached = analysis_cache.get("latest_analysis")
    if cached:
        return jsonify(cached)
    
    # Run analysis (or get from your database/cache)
    try:
        best_stocks, top_stocks, best_cryptos, top_cryptos, wallet_stocks, wallet_cryptos = analyze_assets()
        
        # Convert DataFrames to dict for JSON serialization
        result = {
            "timestamp": datetime.now().isoformat(),
            "best_stocks": best_stocks.to_dict(orient="records") if not best_stocks.empty else [],
            "top_stocks": top_stocks.to_dict(orient="records") if not top_stocks.empty else [],
            "best_cryptos": best_cryptos.to_dict(orient="records") if not best_cryptos.empty else [],
            "top_cryptos": top_cryptos.to_dict(orient="records") if not top_cryptos.empty else [],
            "wallet_stocks": wallet_stocks.to_dict(orient="records") if not wallet_stocks.empty else [],
            "wallet_cryptos": wallet_cryptos.to_dict(orient="records") if not wallet_cryptos.empty else []
        }
        
        # Save to cache
        analysis_cache.set("latest_analysis", result)
        
        # Save to history (limited to last 10 analyses)
        analysis_history.append(result)
        if len(analysis_history) > 10:
            analysis_history.pop(0)
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis/history', methods=['GET'])
def get_analysis_history():
    """Get historical analysis results."""
    if not authenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Ensure analysis_history is a list
    safe_history = analysis_history if isinstance(analysis_history, list) else []
    
    # Return the last 10 analyses
    return jsonify(safe_history)

@app.route('/api/analysis/status', methods=['GET'])
def get_analysis_status():
    """Get the current status of any running analysis."""
    if not authenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Calculate elapsed time if analysis is running
    elapsed_time = None
    if analysis_status["is_running"] and analysis_status["start_time"]:
        elapsed_time = (datetime.now() - analysis_status["start_time"]).total_seconds() * 1000
    
    return jsonify({
        "is_running": analysis_status["is_running"],
        "current_step": analysis_status["current_step"],
        "total_steps": analysis_status["total_steps"],
        "current_step_name": analysis_status["current_step_name"],
        "elapsed_time": elapsed_time,
        "logs": analysis_status["logs"]
    })

@app.route('/api/analysis/run', methods=['POST'])
def run_analysis():
    """Run a new analysis."""
    if not authenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    if analysis_status["is_running"]:
        return jsonify({
            "success": False, 
            "error": "Analysis is already running",
            "status": analysis_status
        })
    
    try:
        # Reset status
        analysis_status["is_running"] = True
        analysis_status["start_time"] = datetime.now()
        analysis_status["current_step"] = 1
        analysis_status["current_step_name"] = "Initializing data fetching"
        analysis_status["logs"] = []
        
        add_log("Starting new analysis run")
        
        # Step 1: Initialize
        add_log("Initializing data fetching")
        time.sleep(1)  # Simulate initialization work
        
        # Capture all output from main.py
        import io
        import sys
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Use your actual analysis function from main.py
            add_log("Running main analysis code...")
            
            # Step 2-4: Run the actual analysis from main.py
            analysis_status["current_step"] = 2
            analysis_status["current_step_name"] = "Running complete analysis"
            best_stocks, top_stocks, best_cryptos, top_cryptos, wallet_stocks, wallet_cryptos = main_analyze_assets(send_messages=True)
            
            # Add debug logging
            add_log(f"Processing results - best_stocks: {best_stocks.shape if not best_stocks.empty else 'empty'}")
            add_log(f"Processing results - best_cryptos: {best_cryptos.shape if not best_cryptos.empty else 'empty'}")
            
            # Get output from main.py and add to logs
            output = captured_output.getvalue()
            for line in output.strip().split('\n'):
                if line:
                    add_log(f"MAIN: {line}")
        finally:
            # Restore stdout
            sys.stdout = old_stdout
        
        # Step 5: Finalizing
        analysis_status["current_step"] = 5
        analysis_status["current_step_name"] = "Finalizing results"
        add_log("Preparing final results")
        
        # Normalize DataFrame columns for consistent frontend handling
        def normalize_df(df):
            if df.empty:
                return df
                
            # Replace spaces with underscores in column names
            df.columns = [col.replace(' ', '_') for col in df.columns]
            return df
        
        # Normalize all DataFrames before converting to dict
        best_stocks = normalize_df(best_stocks)
        top_stocks = normalize_df(top_stocks)
        best_cryptos = normalize_df(best_cryptos)
        top_cryptos = normalize_df(top_cryptos)
        wallet_stocks = normalize_df(wallet_stocks)
        wallet_cryptos = normalize_df(wallet_cryptos)
        
        # Create result dict
        result = {
            "timestamp": datetime.now().isoformat(),
            "best_stocks": best_stocks.to_dict(orient="records") if not best_stocks.empty else [],
            "top_stocks": top_stocks.to_dict(orient="records") if not top_stocks.empty else [],
            "best_cryptos": best_cryptos.to_dict(orient="records") if not best_cryptos.empty else [],
            "top_cryptos": top_cryptos.to_dict(orient="records") if not top_cryptos.empty else [],
            "wallet_stocks": wallet_stocks.to_dict(orient="records") if not wallet_stocks.empty else [],
            "wallet_cryptos": wallet_cryptos.to_dict(orient="records") if not wallet_cryptos.empty else []
        }
        
        # Log the size of each result component
        add_log(f"Result JSON sizes - best_stocks: {len(result['best_stocks'])}, best_cryptos: {len(result['best_cryptos'])}")
        
        # Calculate execution time
        end_time = datetime.now()
        execution_time = (end_time - analysis_status["start_time"]).total_seconds()
        add_log(f"Analysis completed in {execution_time:.2f} seconds")
        
        # Set an environment variable to tell the app not to clear cache on restart
        os.environ["PRESERVE_ANALYSIS_CACHE"] = "true"
        
        # Make sure to cache the results properly
        analysis_cache.set("latest_analysis", result, expiry_seconds=86400)  # Cache for 24 hours
        
        # Print debug info about cache
        add_log(f"Cached analysis results (cache size: {len(json.dumps(result))} bytes)")
        
        # Save to history (limited to last 10 analyses)
        analysis_history.append(result)
        if len(analysis_history) > 10:
            analysis_history.pop(0)
        
        # Update status    
        analysis_status["is_running"] = False
        
        # Debug column names
        for df_name, df in [
            ("best_stocks", best_stocks), 
            ("top_stocks", top_stocks),
            ("best_cryptos", best_cryptos),
            ("top_cryptos", top_cryptos),
            ("wallet_stocks", wallet_stocks),
            ("wallet_cryptos", wallet_cryptos)
        ]:
            if not df.empty:
                add_log(f"{df_name} columns: {list(df.columns)}")
            else:
                add_log(f"{df_name} is empty")
        
        return jsonify({
            "success": True, 
            "message": f"Analysis completed in {execution_time:.2f} seconds", 
            "data": result,
            "execution_time": execution_time,
            "logs": analysis_status["logs"]
        })
    except Exception as e:
        error_message = str(e)
        add_log(f"Error during analysis: {error_message}", "error")
        analysis_status["is_running"] = False
        return jsonify({
            "success": False, 
            "error": error_message,
            "logs": analysis_status["logs"]
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker."""
    return jsonify({"status": "healthy"}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve frontend static files or fall back to index.html for SPA routing"""
    if path != "" and os.path.exists(os.path.join(BUILD_DIR, path)):
        # Serve static files directly if they exist
        print(f"Serving static file: {path}")
        return send_from_directory(BUILD_DIR, path)
    
    # For any other route, serve the index.html to enable SPA routing
    print(f"Requested path: {path}, serving index.html (SPA routing)")
    return send_from_directory(BUILD_DIR, 'index.html')

# Before the app.run() line, add this for debugging
print(f"Looking for static files in: {BUILD_DIR}")
print(f"Directory exists: {os.path.exists(BUILD_DIR)}")
if os.path.exists(BUILD_DIR):
    print(f"Contents: {os.listdir(BUILD_DIR)}")

# Add alias routes without the /api prefix for compatibility
@app.route('/analysis/latest', methods=['GET'])
def get_latest_analysis_alias():
    return get_latest_analysis()

@app.route('/analysis/history', methods=['GET'])
def get_analysis_history_alias():
    return get_analysis_history()

@app.route('/analysis/status', methods=['GET'])
def get_analysis_status_alias():
    return get_analysis_status()

@app.route('/analysis/run', methods=['POST'])
def run_analysis_alias():
    return run_analysis()

@app.route('/api/analysis/example', methods=['GET'])
def get_example_analysis():
    """Return example analysis data for testing."""
    if not authenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Create example data that matches the format expected by the frontend
    example_data = {
        "timestamp": datetime.now().isoformat(),
        "best_stocks": [
            {"Symbol": "AAPL", "Daily_Recommendation": "STRONG_BUY", "Current_Price": 150.0, "Take_Profit": 175.0, "Score": 92},
            {"Symbol": "MSFT", "Daily_Recommendation": "BUY", "Current_Price": 300.0, "Take_Profit": 350.0, "Score": 88}
        ],
        "top_stocks": [
            {"Symbol": "AAPL", "Daily_Recommendation": "STRONG_BUY", "Current_Price": 150.0, "Take_Profit": 175.0, "Score": 92},
            {"Symbol": "MSFT", "Daily_Recommendation": "BUY", "Current_Price": 300.0, "Take_Profit": 350.0, "Score": 88},
            {"Symbol": "GOOGL", "Daily_Recommendation": "NEUTRAL", "Current_Price": 2800.0, "Take_Profit": 3000.0, "Score": 75}
        ],
        "best_cryptos": [
            {"Symbol": "BTC", "Daily_Recommendation": "STRONG_BUY", "Current_Price": 50000.0, "Take_Profit": 60000.0, "Score": 95},
            {"Symbol": "ETH", "Daily_Recommendation": "BUY", "Current_Price": 3000.0, "Take_Profit": 4000.0, "Score": 90}
        ],
        "top_cryptos": [
            {"Symbol": "BTC", "Daily_Recommendation": "STRONG_BUY", "Current_Price": 50000.0, "Take_Profit": 60000.0, "Score": 95},
            {"Symbol": "ETH", "Daily_Recommendation": "BUY", "Current_Price": 3000.0, "Take_Profit": 4000.0, "Score": 90},
            {"Symbol": "SOL", "Daily_Recommendation": "NEUTRAL", "Current_Price": 100.0, "Take_Profit": 120.0, "Score": 80}
        ],
        "wallet_stocks": [
            {"Symbol": "TSLA", "Daily_Recommendation": "NEUTRAL", "Current_Price": 800.0, "RecPriority": 3},
            {"Symbol": "AMZN", "Daily_Recommendation": "BUY", "Current_Price": 3500.0, "RecPriority": 2}
        ],
        "wallet_cryptos": [
            {"Symbol": "ADA", "Daily_Recommendation": "NEUTRAL", "Current_Price": 2.5, "RecPriority": 3},
            {"Symbol": "XRP", "Daily_Recommendation": "SELL", "Current_Price": 1.2, "RecPriority": 4}
        ]
    }
    
    # Cache this example data so it's available via the normal endpoint too
    analysis_cache.set("latest_analysis", example_data)
    
    return jsonify(example_data)

@app.route('/api/analysis/debug', methods=['GET'])
def get_analysis_debug():
    """Return debug information about the latest analysis."""
    if not authenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    latest = analysis_cache.get("latest_analysis")
    if not latest:
        return jsonify({"error": "No analysis data available"})
    
    # Extract column names from each DataFrame
    sample_data = {}
    for key in ["best_stocks", "top_stocks", "best_cryptos", "top_cryptos", "wallet_stocks", "wallet_cryptos"]:
        if key in latest and latest[key] and len(latest[key]) > 0:
            sample_data[key] = {
                "columns": list(latest[key][0].keys()),
                "sample": latest[key][0]
            }
    
    return jsonify({
        "cache_status": "available",
        "sample_data": sample_data
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 