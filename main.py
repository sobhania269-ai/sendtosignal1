import os
import asyncio
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from gemini_processor import process_text_with_gemini

# تنظیمات و متغیرهای محیطی
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL") or "@chandsanieh_news"
# کانال مقصد موقت طبق درخواست
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL") or "@ahmadsobhani"
PREMIUM_EMOJI_ID = os.environ.get("PREMIUM_EMOJI_ID") or ""

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def fetch_and_process_messages():
    await client.start()
    print(f"اتصال برقرار شد.\nمبدأ: {SOURCE_CHANNEL} | مقصد: {TARGET_CHANNEL}")

    time_limit = datetime.now(timezone.utc) - timedelta(minutes=18)
    
    # دیکشنری برای دسته‌بندی آلبوم‌ها بر اساس grouped_id
    # فرمت: {grouped_id: [messages...]} یا {f"single_{id}": [message]}
    grouped_posts = {}

    print("در حال بررسی پیام‌های کانال مبدأ...")
    async for message in client.iter_messages(SOURCE_CHANNEL, limit=25):
        if message.date < time_limit:
            break
        
        # رد کردن استیکر و پیام‌های سرویسی تلگرام
        if message.sticker or message.action:
            continue

        if message.grouped_id:
            if message.grouped_id not in grouped_posts:
                grouped_posts[message.grouped_id] = []
            grouped_posts[message.grouped_id].append(message)
        else:
            grouped_posts[f"single_{message.id}"] = [message]

    if not grouped_posts:
        print("پیام جدیدی در ۱۵ دقیقه اخیر یافت نشد.")
        await client.disconnect()
        return

    # مرتب‌سازی پست‌ها از قدیمی به جدید بر اساس شناسه پیام اول گروه
    sorted_groups = sorted(grouped_posts.values(), key=lambda group: min(m.id for m in group))

    for group in sorted_groups:
        # در تلگرام معمولاً اولین یا آخرین قطعه آلبوم حاوی کپشن متنی است
        text_content = ""
        for msg in group:
            caption = msg.text or msg.message
            if caption and caption.strip():
                text_content = caption.strip()
                break

        # فیلتر: اگر هیچ متنی وجود نداشت، به جمینای فرستاده نمی‌شود
        if not text_content:
            first_id = group[0].id
            print(f"پست شناسه {first_id} (تعداد اسلاید: {len(group)}) بدون کپشن است -> رد شد.")
            continue

        first_id = group[0].id
        print(f"پست شناسه {first_id} دارای کپشن است. ارسال به جمینای...")

        # ارسال متن به جمینای
        processed_text = process_text_with_gemini(text_content)
        
        # وقفه ۴ ثانیه‌ای برای عدم برخورد با محدودیت ۱۵ درخواست در دقیقه
        await asyncio.sleep(4)

        if processed_text == "SKIP" or not processed_text.strip():
            print(f"پست {first_id} مرتبط با موضوعات اقتصادی/سیاسی تشخیص داده نشد (SKIP).")
            continue

        # افزودن ایموجی پریمیوم در صورت تنظیم بودن
        final_caption = processed_text
        if PREMIUM_EMOJI_ID:
            final_caption = f'<tg-emoji emoji-id="{PREMIUM_EMOJI_ID}">🔹</tg-emoji> {processed_text}'

        # ارسال به مقصد
        try:
            # بررسی آلبوم (چند عکسه/اسلایدی)
            media_list = [m.media for m in group if m.media]

            if len(media_list) > 1:
                # ارسال به عنوان آلبوم اسلایدی
                print(f"ارسال آلبوم شامل {len(media_list)} مدیا...")
                await client.send_file(
                    TARGET_CHANNEL,
                    file=media_list,
                    caption=final_caption,
                    parse_mode="html"
                )
            elif len(media_list) == 1:
                # تک‌مدیا همراه با کپشن
                await client.send_message(
                    TARGET_CHANNEL,
                    final_caption,
                    file=media_list[0],
                    parse_mode="html"
                )
            else:
                # پست صرفاً متنی
                await client.send_message(
                    TARGET_CHANNEL,
                    final_caption,
                    parse_mode="html"
                )
            
            print(f"✅ پست با موفقیت به کانال مقصد ارسال شد.")

        except Exception as e:
            print(f"❌ خطا در ارسال پست {first_id}: {e}")

    await client.disconnect()
    print("عملیات پایان یافت.")

if __name__ == "__main__":
    asyncio.run(fetch_and_process_messages())
