import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from gemini_processor import process_text_with_gemini

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "@chandsanieh_news")
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL", "@finsoph_news")

LAST_MSG_FILE = "last_msg_id.txt"

def get_last_processed_id() -> int:
    if os.path.exists(LAST_MSG_FILE):
        try:
            with open(LAST_MSG_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0

def save_last_processed_id(msg_id: int):
    with open(LAST_MSG_FILE, "w") as f:
        f.write(str(msg_id))

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def fetch_and_process_messages():
    await client.start()
    print("اتصال به تلگرام برقرار شد. در حال بررسی پیام‌های ۱۵ دقیقه اخیر...")

    last_id = get_last_processed_id()
    new_highest_id = last_id
    messages_to_process = []
    
    # خواندن پیام‌های جدیدتر از آخرین آیدی ثبت‌شده (تا ۱۵ پیام اخیر در هر اجرا)
    async for message in client.iter_messages(SOURCE_CHANNEL, min_id=last_id, limit=15):
        if message.id > new_highest_id:
            new_highest_id = message.id
        messages_to_process.append(message)

    if not messages_to_process:
        print("پیام جدیدی در این بازه یافت نشد.")
        return

    # مرتب‌سازی از قدیمی‌ترین به جدیدترین برای حفظ ترتیب زمانی
    messages_to_process.reverse()

    for message in messages_to_process:
        # ۱. فیلتر استیکر
        if message.sticker:
            print(f"پیام {message.id} استیکر است -> رد شد.")
            continue

        # ۲. فیلتر پست‌های بدون متن
        text = message.text
        if not text:
            print(f"پیام {message.id} بدون متن یا کپشن است -> رد شد.")
            continue

        print(f"در حال پردازش پیام ID: {message.id}")

        # ۳. ارسال به جمینای برای بررسی شرایط
        processed_text = process_text_with_gemini(text)

        if processed_text == "SKIP" or not processed_text.strip():
            print(f"پیام {message.id} توسط جمینای رد شد (SKIP).")
            continue

        # ۴. ارسال جداگانه پیام مفید به کانال مقصد
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
            print(f"✅ پیام مفید {message.id} با موفقیت به صورت جداگانه ارسال شد!")
        except Exception as e:
            print(f"❌ خطا در ارسال پیام {message.id}: {e}")

    # به‌روزرسانی بالاترین آیدی پردازش‌شده
    if new_highest_id > last_id:
        save_last_processed_id(new_highest_id)

if __name__ == "__main__":
    import asyncio
    asyncio.run(fetch_and_process_messages())
