import os
from dotenv import load_dotenv
from telethon import TelegramClient, events
from gemini_processor import process_text_with_gemini

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "@chandsanieh_news")
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL", "@finsoph_news")

# ساخت کلاینت Telethon
client = TelegramClient('userbot_session', API_ID, API_HASH)

@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def message_handler(event):
    message = event.message

    # ۱. فیلتر استیکر
    if message.sticker:
        print("پست دریافتی استیکر است -> نادیده گرفته شد.")
        return

    # ۲. فیلتر پست‌های بدون متن (مثل عکس یا ویدئوی بدون کپشن)
    text = message.text or message.caption
    if not text:
        print("پست بدون متن یا کپشن است -> نادیده گرفته شد.")
        return

    print(f"پیام جدید از کانال مبدأ دریافت شد:\n{text[:60]}...")

    # ۳. ارسال متن به جمینای برای بررسی و ویرایش
    processed_text = process_text_with_gemini(text)

    # ۴. اگر جمینای تشخیص داد پیام نباید ارسال شود یا خروجی SKIP داد
    if processed_text == "SKIP" or not processed_text.strip():
        print("پیام توسط جمینای فیلتر یا رد شد (تبلیغاتی/غیر مرتبط/مبهم/استیکر).")
        return

    # ۵. ارسال به کانال مقصد (اگر همراه با عکس/ویدئو بود، رسانه هم ارسال می‌شود)
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
        print(f"❌ خطا در ارسال پیام به کانال مقصد: {e}")

async def main():
    print("ربات فعال شد و در حال گوش دادن به کانال مبدأ است...")
    await client.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
