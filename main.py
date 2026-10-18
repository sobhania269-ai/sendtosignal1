import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from gemini_processor import process_text_with_gemini

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")
SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "@chandsanieh_news")
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL", "@finsoph_news")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def check_latest_message():
    await client.start()
    print("اتصال به تلگرام برقرار شد...")

    # گرفتن آخرین پیام از کانال مبدأ
    async for message in client.iter_messages(SOURCE_CHANNEL, limit=1):
        if not message:
            print("پیامی یافت نشد.")
            return

        # ۱. فیلتر استیکر
        if message.sticker:
            print("آخرین پست استیکر است -> رد شد.")
            return

        # ۲. فیلتر پست‌های بدون متن
        text = message.text or message.caption
        if not text:
            print("پست بدون متن است -> رد شد.")
            return

        print(f"بررسی آخرین پیام:\n{text[:50]}...")

        # ۳. پردازش با جمینای
        processed_text = process_text_with_gemini(text)

        if processed_text == "SKIP" or not processed_text.strip():
            print("پیام توسط جمینای فیلتر یا رد شد (SKIP).")
            return

        # ۴. ارسال به کانال مقصد
        try:
            if message.media and not message.sticker:
                await client.send_file(
                    TARGET_CHANNEL,
                    file=message.media,
                    caption=processed_text
                )
            else:
                await client.send_message(
                    TARGET_CHANNEL,
                    processed_text
                )
            print("✅ پیام با موفقیت به کانال مقصد ارسال شد!")
        except Exception as e:
            print(f"❌ خطا در ارسال پیام: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_latest_message())
