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

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL") or "@chandsanieh_news"
TARGET_CHANNELS = ["@ahmadsobhani", "@finsoph_news"]

# شناسه‌های ایموجی‌های پریمیوم
# کانال احمد سبحانی
EMOJI_AHMAD_BULLET = "5958629062858514430"  # ایموجی ابتدای خطوط برای کانال شخصی
EMOJI_ID = "5836782704686798781"            # ایموجی آیدی (مشترک)
EMOJI_LINK = "5271604874419647061"          # ایموجی پیوند (مشترک)

# کانال فینسوف نیوز
EMOJI_FINSOPH_BULLET = "5958661279408200638" # ایموجی ابتدای خطوط برای فینسوف

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def format_news_text(raw_text: str) -> str:
    """پاک‌سازی متن، حذف ایموجی‌های نامطلوب، و بولد کردن قطعی خط اول"""
    clean_text = re.sub(r'[🔹🔷]', '', raw_text).strip()
    
    lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
    if not lines:
        return ""

    # اطمینان از بولد بودن سطر اول (تیتر)
    first_line = lines[0]
    first_line = re.sub(r'</?b>', '', first_line)
    first_line = re.sub(r'\*\*(.*?)\*\*', r'\1', first_line).strip()
    lines[0] = f"<b>{first_line}</b>"

    # تبدیل ستاره‌های بقیه خطوط به بولد استاندارد HTML
    for i in range(1, len(lines)):
        lines[i] = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', lines[i])

    return "\n\n".join(lines)

def prepare_caption_for_target(base_text: str, target: str) -> str:
    """شخصی‌سازی متن، ایموجی خطوط و فوتر برای هر کانال به صورت جداگانه"""
    paragraphs = base_text.split('\n\n')

    if target == "@ahmadsobhani":
        # ایموجی سبز در ابتدای تمام پاراگراف‌ها
        formatted_paragraphs = [
            f'<tg-emoji emoji-id="{EMOJI_AHMAD_BULLET}">🟢</tg-emoji> {p}' for p in paragraphs
        ]
        body = '\n\n'.join(formatted_paragraphs)
        
        # فوتر اختصاصی کانال احمد سبحانی
        footer = (
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> {target}\n'
            f'<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> isignal.ir'
        )
        return f"{body}\n\n{footer}"

    elif target == "@finsoph_news":
        # ایموجی اختصاصی فینسوف در ابتدای تمام پاراگراف‌ها
        formatted_paragraphs = [
            f'<tg-emoji emoji-id="{EMOJI_FINSOPH_BULLET}">🔸</tg-emoji> {p}' for p in paragraphs
        ]
        body = '\n\n'.join(formatted_paragraphs)

        # فوتر اختصاصی فینسوف شامل دو کانال و وب‌سایت رسمی
        footer = (
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> @finsoph_news\n'
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> @fin_soph\n'
            f'<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> finsoph.ir'
        )
        return f"{body}\n\n{footer}"

    else:
        return f"{base_text}\n\n{target}"

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
        print(f"ارسال متن پست شناسه {first_id} به جمینای...")

        processed_text = process_text_with_gemini(text_content)
        await asyncio.sleep(4)

        if processed_text == "SKIP" or not processed_text.strip():
            print(f"پست {first_id} رد شد (SKIP).")
            continue

        # اعمال قالب‌بندی و بولد کردن خط اول
        base_formatted_text = format_news_text(processed_text)
        if not base_formatted_text:
            continue

        # ارسال به هر دو کانال به صورت کاملاً مجزا
        for target in TARGET_CHANNELS:
            caption = prepare_caption_for_target(base_formatted_text, target)

            try:
                media_messages = [m for m in group if m.media]

                if len(media_messages) > 1:
                    peer = await client.get_input_entity(target)
                    multi_media = []

                    for idx, msg in enumerate(media_messages):
                        cap = caption if idx == 0 else ""
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
                        caption,
                        file=media_messages[0].media,
                        parse_mode="html",
                        link_preview=False
                    )
                    print(f"✅ پست تک‌مدیا {first_id} به {target} ارسال شد.")
                else:
                    await client.send_message(
                        target,
                        caption,
                        parse_mode="html",
                        link_preview=False
                    )
                    print(f"✅ پست متنی {first_id} به {target} ارسال شد.")

                await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ خطا در ارسال به {target}: {e}")

    await client.disconnect()
    print("پایان عملیات.")

if __name__ == "__main__":
    asyncio.run(fetch_and_process_messages())
