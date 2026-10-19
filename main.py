import os
import re
import asyncio
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import InputSingleMedia
from telethon.tl.functions.messages import SendMultiMediaRequest
from gemini_processor import process_text_with_gemini

# متغیرهای اتصال تلگرام
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# کانال‌های مبدا و مقصد
SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL") or "@chandsanieh_news"
TARGET_CHANNELS = ["@ahmadsobhani", "@finsoph_news"]

# ایموجی پریمیوم (اختیاری)
PREMIUM_EMOJI_ID = os.environ.get("PREMIUM_EMOJI_ID") or ""

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def markdown_to_html_bold(text: str) -> str:
    """تبدیل خودکار دو ستاره مارک‌داون به تگ استاندارد HTML جهت بولد شدن قطعی"""
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

async def fetch_and_process_messages():
    await client.start()
    print(f"اتصال تلگرام برقرار شد.\nمبدأ: {SOURCE_CHANNEL}\nمقاصد: {TARGET_CHANNELS}")

    # بررسی پیام‌های حدود ۱۸ دقیقه اخیر
    time_limit = datetime.now(timezone.utc) - timedelta(minutes=18)
    grouped_posts = {}

    print("در حال خواندن پیام‌های کانال مبدأ...")
    async for message in client.iter_messages(SOURCE_CHANNEL, limit=25):
        if message.date < time_limit:
            break
        
        # نادیده گرفتن استیکرها یا پیام‌های سیستمی
        if message.sticker or message.action:
            continue

        if message.grouped_id:
            if message.grouped_id not in grouped_posts:
                grouped_posts[message.grouped_id] = []
            grouped_posts[message.grouped_id].append(message)
        else:
            grouped_posts[f"single_{message.id}"] = [message]

    if not grouped_posts:
        print("پیام جدیدی در این بازه زمانی یافت نشد.")
        await client.disconnect()
        return

    # مرتب‌سازی گروه‌ها از قدیمی به جدید
    sorted_groups = sorted(grouped_posts.values(), key=lambda group: min(m.id for m in group))

    for group in sorted_groups:
        # استخراج کپشن متنی از میان پیام‌های گروه
        text_content = ""
        for msg in group:
            caption = msg.text or msg.message
            if caption and caption.strip():
                text_content = caption.strip()
                break

        # فیلتر اولیه: تنها در صورتی که متن وجود داشته باشد به جمینای می‌رود
        if not text_content:
            continue

        first_id = group[0].id
        print(f"ارسال متن پست شناسه {first_id} به جمینای...")

        processed_text = process_text_with_gemini(text_content)
        
        # تاخیر برای رعایت محدودیت درخواست در دقیقه جمینای
        await asyncio.sleep(4)

        if processed_text == "SKIP" or not processed_text.strip():
            print(f"پست {first_id} مرتبط تشخیص داده نشد یا حذف شد (SKIP).")
            continue

        # اصلاح ساختار بولد
        processed_text = markdown_to_html_bold(processed_text)

        # ارسال جداگانه به هر دو کانال
        for target in TARGET_CHANNELS:
            caption_with_id = f"{processed_text}\n\n{target}"

            if PREMIUM_EMOJI_ID:
                caption_with_id = f'<tg-emoji emoji-id="{PREMIUM_EMOJI_ID}">🔹</tg-emoji> {caption_with_id}'

            try:
                media_messages = [m for m in group if m.media]

                if len(media_messages) > 1:
                    # ارسال چندرسانه‌ای به صورت اسلایدی/آلبوم ورق‌خور
                    peer = await client.get_input_entity(target)
                    multi_media = []

                    for idx, msg in enumerate(media_messages):
                        # اختصاص کپشن تنها به اسلاید اول
                        cap = caption_with_id if idx == 0 else ""
                        input_media = await client.get_input_media(msg.media)

                        multi_media.append(
                            InputSingleMedia(
                                media=input_media,
                                random_id=client.rnd_id(),
                                message=cap,
                                parse_mode="html"
                            )
                        )

                    await client(SendMultiMediaRequest(
                        peer=peer,
                        multi_media=multi_media
                    ))
                    print(f"✅ آلبوم اسلایدی پست {first_id} به {target} ارسال شد.")

                elif len(media_messages) == 1:
                    # تک‌مدیا با کپشن
                    await client.send_message(
                        target,
                        caption_with_id,
                        file=media_messages[0].media,
                        parse_mode="html"
                    )
                    print(f"✅ پست تک‌مدیا {first_id} به {target} ارسال شد.")
                else:
                    # متن خالص
                    await client.send_message(
                        target,
                        caption_with_id,
                        parse_mode="html"
                    )
                    print(f"✅ پست متنی {first_id} به {target} ارسال شد.")

                await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ خطا در ارسال به {target}: {e}")

    await client.disconnect()
    print("پایان عملیات.")

if __name__ == "__main__":
    asyncio.run(fetch_and_process_messages())
