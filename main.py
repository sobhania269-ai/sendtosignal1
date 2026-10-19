import os
import re
import asyncio
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from gemini_processor import process_text_with_gemini

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL") or "@chandsanieh_news"

# لیست کانال‌های مقصد
TARGET_CHANNELS = ["@ahmadsobhani", "@finsoph_news"]

PREMIUM_EMOJI_ID = os.environ.get("PREMIUM_EMOJI_ID") or ""

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def markdown_to_html_bold(text: str) -> str:
    """تبدیل خودکار دو ستاره مارک‌داون به تگ‌های HTML جهت بولد شدن قطعی"""
    # تبدیل **متن** به <b>متن</b>
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

async def fetch_and_process_messages():
    await client.start()
    print(f"اتصال برقرار شد.\nمبدأ: {SOURCE_CHANNEL}\nمقصدها: {TARGET_CHANNELS}")

    time_limit = datetime.now(timezone.utc) - timedelta(minutes=18)
    grouped_posts = {}

    print("در حال بررسی پیام‌های کانال مبدأ...")
    async for message in client.iter_messages(SOURCE_CHANNEL, limit=25):
        if message.date < time_limit:
            break
        
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

    sorted_groups = sorted(grouped_posts.values(), key=lambda group: min(m.id for m in group))

    for group in sorted_groups:
        text_content = ""
        for msg in group:
            caption = msg.text or msg.message
            if caption and caption.strip():
                text_content = caption.strip()
                break

        if not text_content:
            continue

        first_id = group[0].id
        print(f"ارسال متن پست {first_id} به جمینای...")

        processed_text = process_text_with_gemini(text_content)
        await asyncio.sleep(4)

        if processed_text == "SKIP" or not processed_text.strip():
            print(f"پست {first_id} رد شد (SKIP).")
            continue

        # اصلاح فرمت بولد (تبدیل ** به <b>)
        processed_text = markdown_to_html_bold(processed_text)

        # ارسال به هر دو کانال مقصد
        for target in TARGET_CHANNELS:
            # افزودن آیدی همان کانال در انتهای متن
            caption_with_id = f"{processed_text}\n\n{target}"

            # افزودن ایموجی پریمیوم (در صورت وجود)
            if PREMIUM_EMOJI_ID:
                caption_with_id = f'<tg-emoji emoji-id="{PREMIUM_EMOJI_ID}">🔹</tg-emoji> {caption_with_id}'

            try:
                media_list = [m.media for m in group if m.media]

                if len(media_list) > 1:
                    await client.send_file(
                        target,
                        file=media_list,
                        caption=caption_with_id,
                        parse_mode="html"
                    )
                elif len(media_list) == 1:
                    await client.send_message(
                        target,
                        caption_with_id,
                        file=media_list[0],
                        parse_mode="html"
                    )
                else:
                    await client.send_message(
                        target,
                        caption_with_id,
                        parse_mode="html"
                    )
                
                print(f"✅ پست {first_id} به کانال {target} ارسال شد.")
                await asyncio.sleep(1) # وقفه کوتاه بین ارسال‌ها

            except Exception as e:
                print(f"❌ خطا در ارسال به {target}: {e}")

    await client.disconnect()
    print("عملیات با موفقیت پایان یافت.")

if __name__ == "__main__":
    asyncio.run(fetch_and_process_messages())
