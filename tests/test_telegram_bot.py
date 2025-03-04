# Fetch Bot Information
# import requests

# BOT_TOKEN = "7361081528:AAElCFMcnNH3D7NWKZfiAjS-YDDsxkHG84Y"

# response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates")
# print(response.json())

import asyncio
from telegram import Bot

# Bot token and chat ID
BOT_TOKEN = "7361081528:AAElCFMcnNH3D7NWKZfiAjS-YDDsxkHG84Y"
CHAT_ID = 6998039575  # Your chat ID
MESSAGE = "Hello, Antoni! Your bot is ready to go. 🚀"

# Define an asynchronous function to send the message
async def send_message():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=MESSAGE)

# Run the async function
asyncio.run(send_message())
