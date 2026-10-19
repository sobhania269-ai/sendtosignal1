import os
import asyncio
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from gemini_processor import process_text_with_gemini

# متغیرهای محیطی
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "@chandsanieh_news")
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL", "@finsoph_news")

# آیدی عددی ایموجی پریمیوم مورد نظر (در صورت تمایل جایگزین کنید)
# نمونه: 5368324170671202286
PREMIUM_EMOJI_ID = os.environ.get("PREMIUM_EMOJI_ID", "")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def fetch_and_process_messages():
    await client.start()
    print("اتصال به تلگرام برقرار شد. در حال بررسی پیام‌های ۱۵ دقیقه اخیر...")

    # بازه زمانی: فقط پیام‌های ۱۵ دقیقه گذشته (با ۲ دقیقه حاشیه اطمینان)
    time_limit = datetime.now(timezone.utc) - timedelta(minutes=17)
    
    messages_to_process = []

    # خواندن پیام‌های اخیر
    async for message in client.iter_messages(SOURCE_CHANNEL, limit=20):
        if message.date < time_limit:
            break
        messages_to_process.append(message)

    if not messages_to_process:
        print("پیام جدیدی در بازه زمانی ۱۵ دقیقه اخیر یافت نشد.")
        await client.disconnect()
        return

    # حفظ ترتیب زمانی (از قدیمی به جدید)
    messages_to_process.reverse()

    for message in messages_to_process:
        # ۱. فیلتر استیکر و سرویس مسیج‌ها
        if message.sticker or message.action:
            continue

        # ۲. بررسی وجود متن یا کپشن
        text = message.text or message.message
        if not text:
            print(f"پیام {message.id} فاقد متن است -> رد شد.")
            continue

        print(f"در حال پردازش پیام ID: {message.id} با جمینای...")

        # ۳. ارسال به جمینای
        processed_text = process_text_with_gemini(text)

        if processed_text == "SKIP" or not processed_text.strip():
            print(f"پیام {message.id} توسط فیلتر رد شد (SKIP).")
            continue

        # افزودن ایموجی پریمیوم در صورت تنظیم بودن ID
        final_caption = processed_text
        if PREMIUM_EMOJI_ID:
            final_caption = f'<tg-emoji emoji-id="{PREMIUM_EMOJI_ID}">🔹</tg-emoji> {processed_text}'

        # ۴. ارسال به کانال مقصد بدون دانلود و آپلود مجدد فایل روی سرور
        try:
            if message.media:
                # ارسال همان مدیا به صورت ارجاع سروری به همراه کپشن جدید
                await client.send_message(
                    TARGET_CHANNEL,
                    final_caption,
                    file=message.media,
                    parse_mode="html"
                )
            else:
                await client.send_message(
                    TARGET_CHANNEL,
                    final_caption,
                    parse_mode="html"
                )
            print(f"✅ پیام {message.id} با موفقیت ارسال شد.")
        except Exception as e:
            print(f"❌ خطا در ارسال پیام {message.id}: {e}")

    # قطع ارتباط و خروج تمیز از برنامه
    await client.disconnect()
    print("عملیات با موفقیت پایان یافت.")

if __name__ == "__main__":
    asyncio.run(fetch_and_process_messages())
