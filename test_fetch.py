import asyncio
import logging
from dotenv import load_dotenv
import os

load_dotenv()
from main import fetch_post_details, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD

logging.basicConfig(level=logging.INFO)

async def test():
    print(f"Username loaded: {INSTAGRAM_USERNAME}")
    print(f"Session file exists? {os.path.exists(f'session-{INSTAGRAM_USERNAME}')}")
    try:
        details = await asyncio.to_thread(fetch_post_details, "https://www.instagram.com/reel/DNa1kuCz9JI/")
        print("Details:", details)
    except Exception as e:
        print("Failed to fetch details:", e)

if __name__ == "__main__":
    asyncio.run(test())
