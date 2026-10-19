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

# آیدی‌های اختصاصی ایموجی پریمیوم دریافتی
EMOJI_HEADER = "5958629062858514430"  # ایموجی ابتدای هر پیام
EMOJI_ID = "5836782704686798781"      # ایموجی کنار آیدی کانال
EMOJI_LINK = "5271604874419647061"    # ایموجی کنار لینک منبع

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def markdown_to_html_bold(text: str) -> str:
    """تبدیل دو ستاره مارک‌داون به تگ استاندارد HTML جهت بولد شدن قطعی"""
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

def build_channel_footer(target: str, source_msg_link: str) -> str:
    """ساخت فوتر اختصاصی شامل ایموجی‌های پریمیوم، آیدی و لینک منبع"""
    if target == "@ahmadsobhani":
        footer = f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> {target}'
        if source_msg_link:
            footer += f'\n<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> <a href="{source_msg_link}">منبع خبر</a>'
        return footer
    else:
        # برای بقیه کانال‌ها مثل finsoph_news
        return f"{target}"

async def fetch_and_process_messages():
    await client.start()
    print(f"اتصال تلگرام برقرار شد.\nمبدأ: {SOURCE_CHANNEL}\nمقاصد: {TARGET_CHANNELS}")

    time_limit = datetime.now(timezone.utc) - timedelta(minutes=18)
    grouped_posts = {}

    print("در حال خواندن پیام‌های کانال مبدأ...")
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
        print("پیام جدیدی در این بازه زمانی یافت نشد.")
        await client.disconnect()
        return

    sorted_groups = sorted(grouped_posts.values(), key=lambda group: min(m.id for m in group))

    # به دست آوردن نام کاربری کانال مبدا برای ساخت لینک پیام
    source_username = SOURCE_CHANNEL.replace("@", "")

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
        print(f"ارسال متن پست شناسه {first_id} به جمینای...")

        processed_text = process_text_with_gemini(text_content)
        await asyncio.sleep(4)

        if processed_text == "SKIP" or not processed_text.strip():
            print(f"پست {first_id} رد شد (SKIP).")
            continue

        # تبدیل ** به <b>
        processed_text = markdown_to_html_bold(processed_text)

        # ساخت لینک پیام اصلی در مبدأ
        source_msg_link = f"https://t.me/{source_username}/{first_id}"

        # ارسال به کانال‌های مقصد
        for target in TARGET_CHANNELS:
            footer = build_channel_footer(target, source_msg_link)
            
            # افزودن ایموجی پریمیوم به اول پیام برای کانال ahmadsobhani
            if target == "@ahmadsobhani":
                full_caption = f'<tg-emoji emoji-id="{EMOJI_HEADER}">🔹</tg-emoji> {processed_text}\n\n{footer}'
            else:
                full_caption = f"{processed_text}\n\n{footer}"

            try:
                media_messages = [m for m in group if m.media]

                if len(media_messages) > 1:
                    peer = await client.get_input_entity(target)
                    multi_media = []

                    for idx, msg in enumerate(media_messages):
                        cap = full_caption if idx == 0 else ""
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
                    await client.send_message(
                        target,
                        full_caption,
                        file=media_messages[0].media,
                        parse_mode="html"
                    )
                    print(f"✅ پست تک‌مدیا {first_id} به {target} ارسال شد.")
                else:
                    await client.send_message(
                        target,
                        full_caption,
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
