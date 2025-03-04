"""Test script for email functionality."""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Add parent directory to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
load_dotenv()

# Import the email function
from utils.email import send_email

def test_email():
    """Test sending an email with the configured settings."""
    
    # Print configuration (with password hidden)
    email_address = os.getenv("EMAIL_ADDRESS")
    email_recipient = os.getenv("EMAIL_RECIPIENT")
    email_enabled = os.getenv("EMAIL_ENABLED")
    
    logging.info(f"Email configuration:")
    logging.info(f"  EMAIL_ENABLED: {email_enabled}")
    logging.info(f"  EMAIL_ADDRESS: {email_address}")
    logging.info(f"  EMAIL_RECIPIENT: {email_recipient}")
    logging.info(f"  EMAIL_PASSWORD: {'*' * 8} (hidden)")
    
    # Send a test email
    subject = "Email Test - Trading Bot"
    content = """
    This is a test email from your Trading Bot.
    
    If you're seeing this message, your email configuration is working properly!
    
    You can now proceed with the full implementation.
    """
    
    logging.info("Attempting to send test email...")
    result = send_email(subject, content)
    
    if result:
        logging.info("✅ Success! Test email sent successfully.")
        logging.info(f"Please check {email_recipient} for the test message.")
    else:
        logging.error("❌ Failed to send test email. Check the logs for more details.")

if __name__ == "__main__":
    test_email() 