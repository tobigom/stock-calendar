"""
Telegram login script - sends code and signs in
"""
import os
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = 26220720
API_HASH = "778b9252849089d2b872061e9044e9ed"
PHONE_NUMBER = "821012345678"
CODE = "81147"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
session_file = os.path.join(BASE_DIR, "telegram_session")

async def main():
    client = TelegramClient(session_file, API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(PHONE_NUMBER)
            try:
                await client.sign_in(PHONE_NUMBER, CODE)
            except SessionPasswordNeededError:
                print("2FA password required - please enter your cloud password")
                return
        print("SUCCESS: Telegram login successful! Session file created.")
        me = await client.get_me()
        print(f"Logged in as: {me.phone}")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await client.disconnect()

asyncio.run(main())
