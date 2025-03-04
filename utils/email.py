"""Email sending utilities."""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def send_email(subject, content, recipient=None):
    """
    Send an email using SMTP.
    
    Args:
        subject: Email subject
        content: Email body content (can be HTML)
        recipient: Override recipient email (optional)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Check if email is enabled
    if os.getenv("EMAIL_ENABLED", "false").lower() != "true":
        logging.info("Email forwarding is disabled. Set EMAIL_ENABLED=true to enable.")
        return False
        
    email_address = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    email_recipient = recipient or os.getenv("EMAIL_RECIPIENT")
    
    if not all([email_address, email_password, email_recipient]):
        logging.error("Email configuration is incomplete. Check your .env file.")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = email_address
        msg["To"] = email_recipient
        msg["Subject"] = subject
        
        # Convert plain text to simple HTML for better formatting
        html_content = f"""
        <html>
            <head></head>
            <body>
                <div style="font-family: Arial, sans-serif; line-height: 1.5;">
                    <h2 style="color: #333;">{subject}</h2>
                    <div style="white-space: pre-wrap;">{content}</div>
                    <p style="color: #777; margin-top: 20px; font-size: 12px;">
                        Sent by Trading Bot on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, "html"))
        
        # Connect to Gmail SMTP server
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
            
        logging.info(f"Email sent successfully to {email_recipient}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        return False 