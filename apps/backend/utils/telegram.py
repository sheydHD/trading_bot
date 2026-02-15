"""Telegram bot messaging with old-message cleanup.

Sends Markdown-formatted messages via ``python-telegram-bot`` and
manages a local JSON file of message IDs so that previous messages
can be deleted before sending new ones (keeps the chat tidy).

Required env vars:
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import json
import asyncio
import logging
from telegram.error import TimedOut
from telegram import Bot

from apps.backend.utils.config import BOT_TOKEN, CHAT_ID
from apps.backend.utils.email import send_email

# Use a consistent absolute cache path under backend/data/cache
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
MESSAGE_LOG_FILE = os.path.join(CACHE_DIR, "telegram_messages.json")

def save_message_id(message_id: int) -> None:
    """Append a Telegram message ID to the local log file."""
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

def load_message_ids() -> list[int]:
    """Load previously-sent Telegram message IDs from disk."""
    try:
        if os.path.exists(MESSAGE_LOG_FILE):
            with open(MESSAGE_LOG_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading message IDs: {e}")
        return []

async def delete_previous_messages() -> None:
    """Delete all previously-tracked messages from the Telegram chat."""
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

async def send_message_to_telegram(text: str, delete_old: bool = False) -> int | None:
    """Send a Markdown message to the configured Telegram chat.

    Optionally deletes previously-sent messages first to keep the
    chat clean.  The new message ID is appended to the local log
    (capped at 2 entries).

    Args:
        text: Markdown-formatted message body.
        delete_old: If ``True``, delete tracked messages before sending.

    Returns:
        The Telegram message ID of the sent message, or ``None`` on
        failure.
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
            message_ids = []
            try:
                if os.path.exists(MESSAGE_LOG_FILE):
                    with open(MESSAGE_LOG_FILE, 'r') as f:
                        message_ids = json.load(f)
                        logging.info(f"Loaded {len(message_ids)} message IDs from {MESSAGE_LOG_FILE}")
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
        message_ids = []
        try:
            if os.path.exists(MESSAGE_LOG_FILE):
                with open(MESSAGE_LOG_FILE, 'r') as f:
                    message_ids = json.load(f)
        except Exception:
            message_ids = []
        
        # Add new message ID
        message_ids.append(message.message_id)
        
        # Keep only the last 2 messages
        if len(message_ids) > 2:
            message_ids = message_ids[-2:]
        
        # Write IDs back to file
        with open(MESSAGE_LOG_FILE, 'w') as f:
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