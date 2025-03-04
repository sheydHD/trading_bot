#!/usr/bin/env python3
"""
Entry point for the trading bot application.
This script imports and runs the necessary functions from the backend core module,
and also starts the Flask API server for the web UI.
"""

import os
import sys
import threading
import logging

# Add the backend directory to the Python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import the setup_logging and daily_job functions from the core module
from backend.core.main import setup_logging, daily_job, reset_telegram_messages
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import time
from backend.utils.config import SCHEDULED_TIMES

# Import Flask app to run the web server
from backend.api.app import app as flask_app

def run_flask_app():
    """Run the Flask API server in a separate thread"""
    flask_app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

def run_trading_scheduler():
    """Run the trading bot scheduler"""
    # Set up the scheduler
    scheduler = BackgroundScheduler()
    
    # Schedule jobs
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
    
    # Run the daily job immediately (optional)
    daily_job()
    
    # Start the scheduler
    scheduler.start()
    logging.info("Scheduler started.")
    
    return scheduler

if __name__ == "__main__":
    # Set up logging
    setup_logging()
    
    # Reset telegram messages (optional, uncomment if needed)
    # reset_telegram_messages()
    
    # Start Flask API in a separate thread
    logging.info("Starting Flask API server for web UI...")
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start trading scheduler
    logging.info("Starting trading scheduler...")
    scheduler = run_trading_scheduler()
    
    # Keep the script running
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down scheduler...")
        scheduler.shutdown()
        logging.info("Application shut down.") 