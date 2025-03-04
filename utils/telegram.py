"""Telegram messaging utilities."""

import os
import json
import asyncio
import logging
from telegram.error import TimedOut
from telegram import Bot

from utils.config import BOT_TOKEN, CHAT_ID

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
    bot = Bot(token=BOT_TOKEN)
    if delete_old:
        await delete_previous_messages()
    max_length = 4096
    messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    try:
        for msg in messages:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=msg)
            save_message_id(sent_message.message_id)
            await asyncio.sleep(1)
    except TimedOut:
        logging.error("Telegram API request timed out. Retrying in 10 seconds...")
        await asyncio.sleep(10)
        for msg in messages:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=msg)
            save_message_id(sent_message.message_id)
            await asyncio.sleep(1) 