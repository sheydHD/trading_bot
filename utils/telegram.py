"""Telegram messaging utilities."""

import os
import json
import asyncio
import logging
from telegram.error import TimedOut
from telegram import Bot

from utils.config import BOT_TOKEN, CHAT_ID
from utils.email import send_email  # Import the email function

MESSAGE_LOG_FILE = "telegram_messages.json"

def save_message_id(message_id):
    try:
        if os.path.exists(MESSAGE_LOG_FILE):
            with open(MESSAGE_LOG_FILE, "r") as f:
                data = json.load(f)
        else:
            data = []
        data.append(message_id)
        with open(MESSAGE_LOG_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Error saving message ID: {e}")

def load_message_ids():
    try:
        if os.path.exists(MESSAGE_LOG_FILE):
            with open(MESSAGE_LOG_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading message IDs: {e}")
        return []

async def delete_previous_messages():
    bot = Bot(token=BOT_TOKEN)
    message_ids = load_message_ids()
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=msg_id)
            await asyncio.sleep(0.5)
        except Exception as e:
            logging.warning(f"Could not delete message {msg_id}: {e}")
    with open(MESSAGE_LOG_FILE, "w") as f:
        json.dump([], f)

async def send_message_to_telegram(text: str, delete_old: bool = False):
    """
    Sends a message to Telegram chat and optionally deletes old messages.
    
    Args:
        text: The message text to send
        delete_old: Whether to delete previous messages before sending
    
    Returns:
        The message ID of the sent message
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logging.warning("Telegram credentials not found in environment variables")
        return None
    
    try:
        bot = Bot(token=bot_token)
        
        # Delete old messages if requested
        if delete_old:
            # Read message IDs from file
            messages_file = "telegram_messages.json"
            message_ids = []
            
            if os.path.exists(messages_file):
                try:
                    with open(messages_file, 'r') as f:
                        message_ids = json.load(f)
                        logging.info(f"Loaded {len(message_ids)} message IDs from {messages_file}")
                except Exception as e:
                    logging.error(f"Error reading message IDs: {e}")
                    message_ids = []
            
            # Delete messages
            if message_ids:
                logging.info(f"Attempting to delete {len(message_ids)} previous messages: {message_ids}")
                for msg_id in message_ids:
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                        logging.info(f"Successfully deleted message ID: {msg_id}")
                    except Exception as e:
                        logging.warning(f"Could not delete message {msg_id}: {e}")
        
        # Send new message
        message = await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        logging.info(f"Sent telegram message with ID: {message.message_id}")
        
        # Update message ID in file
        messages_file = "telegram_messages.json"
        message_ids = []
        
        # Read existing IDs if file exists
        if os.path.exists(messages_file):
            try:
                with open(messages_file, 'r') as f:
                    message_ids = json.load(f)
            except Exception:
                message_ids = []
        
        # Add new message ID
        message_ids.append(message.message_id)
        
        # Keep only the last 2 messages
        if len(message_ids) > 2:
            message_ids = message_ids[-2:]
        
        # Write IDs back to file
        with open(messages_file, 'w') as f:
            json.dump(message_ids, f)
            logging.info(f"Updated message IDs file with: {message_ids}")
        
        return message.message_id
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")
        return None

async def send_email_async(subject, content):
    """Run the email sending function asynchronously."""
    loop = asyncio.get_event_loop()
    # Run the email function in a thread pool since it's a blocking operation
    await loop.run_in_executor(None, lambda: send_email(subject, content)) 