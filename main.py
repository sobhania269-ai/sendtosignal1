import os
import re
import asyncio
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from gemini_processor import process_batch_with_gemini

# متغیرهای اتصال تلگرام
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL") or "@chandsanieh_news"
TARGET_CHANNELS = ["@ahmadsobhani", "@finsoph_news"]

# ایموجی‌های پریمیوم
EMOJI_AHMAD_BULLET = "5958629062858514430"  # ایموجی ابتدای خطوط برای کانال شخصی
EMOJI_ID = "5836782704686798781"            # ایموجی آیدی (مشترک)
EMOJI_LINK = "5271604874419647061"          # ایموجی پیوند (مشترک)
EMOJI_FINSOPH_BULLET = "5958661279408200638" # ایموجی ابتدای خطوط فینسوف

# کاراکترهای نامرئی برای کدگذاری آیدی در انتهای پیام (برای چشم انسان کاملاً مخفی است)
ZW_0 = "\u200b"  # صفر
ZW_1 = "\u200c"  # یک
ZW_SEP = "\u200d" # جداکننده

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def encode_id_invisible(msg_id: int) -> str:
    """کدگذاری شناسه پیام به کاراکترهای کاملاً نامرئی در انتهای پست"""
    binary = bin(msg_id)[2:]
    invisible_str = "".join(ZW_1 if b == "1" else ZW_0 for b in binary)
    return ZW_SEP + invisible_str + ZW_SEP

def decode_id_invisible(text: str) -> int:
    """استخراج شناسه پیام از کاراکترهای نامرئی انتهای متن"""
    if not text:
        return 0
    pattern = rf"{ZW_SEP}([{ZW_0}{ZW_1}]+){ZW_SEP}"
    match = re.search(pattern, text)
    if match:
        binary_str = "".join("1" if c == ZW_1 else "0" for c in match.group(1))
        try:
            return int(binary_str, 2)
        except ValueError:
            return 0
    return 0

def format_news_text(raw_text: str) -> str:
    """پاک‌سازی لوزی‌های آبی، فرمت مارک‌داون و تضمین بولد بودن خط اول"""
    clean_text = re.sub(r'[🔹🔷]', '', raw_text).strip()
    lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
    if not lines:
        return ""

    first_line = lines[0]
    first_line = re.sub(r'</?b>', '', first_line)
    first_line = re.sub(r'\*\*(.*?)\*\*', r'\1', first_line).strip()
    lines[0] = f"<b>{first_line}</b>"

    for i in range(1, len(lines)):
        lines[i] = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', lines[i])

    return "\n\n".join(lines)

def prepare_caption_for_target(base_text: str, target: str, source_msg_id: int) -> str:
    """شخصی‌سازی متن، فوتر و تزریق آیدی نامرئی برای جلوگیری از تکرار"""
    paragraphs = base_text.split('\n\n')
    invisible_tag = encode_id_invisible(source_msg_id)

    if target == "@ahmadsobhani":
        formatted_paragraphs = [
            f'<tg-emoji emoji-id="{EMOJI_AHMAD_BULLET}">🟢</tg-emoji> {p}' for p in paragraphs
        ]
        body = '\n\n'.join(formatted_paragraphs)
        footer = (
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> {target}\n'
            f'<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> isignal.ir'
        )
        return f"{body}\n\n{footer}{invisible_tag}"

    elif target == "@finsoph_news":
        formatted_paragraphs = [
            f'<tg-emoji emoji-id="{EMOJI_FINSOPH_BULLET}">🔸</tg-emoji> {p}' for p in paragraphs
        ]
        body = '\n\n'.join(formatted_paragraphs)
        footer = (
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> @finsoph_news\n'
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> @fin_soph\n'
            f'<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> finsoph.ir'
        )
        return f"{body}\n\n{footer}{invisible_tag}"

    return f"{base_text}\n\n{target}{invisible_tag}"

async def get_last_processed_id_from_channel(channel_username: str) -> int:
    """خواندن آخرین آیدی ارسال‌شده با بررسی کاراکتر نامرئی آخرین پیام‌های کانال"""
    try:
        async for msg in client.iter_messages(channel_username, limit=10):
            text = msg.text or msg.message or ""
            msg_id = decode_id_invisible(text)
            if msg_id > 0:
                return msg_id
    except Exception as e:
        print(f"اطلاع: خطا در خواندن آخرین پیام کانال مقصد: {e}")
    return 0

async def fetch_and_process_messages():
    await client.start()
    print(f"اتصال تلگرام برقرار شد.\nمبدأ: {SOURCE_CHANNEL}\nمقاصد: {TARGET_CHANNELS}")

    # ۱. بازیابی آخرین آیدی پیام فوروارد شده از کانال مقصد
    last_sent_id = await get_last_processed_id_from_channel(TARGET_CHANNELS[0])
    
    # دقیقاً ۱۵ دقیقه اخیر (حذف همپوشانی زمان‌ها)
    time_limit = datetime.now(timezone.utc) - timedelta(minutes=15)
    
    if last_sent_id > 0:
        print(f"🔍 آخرین شناسه پردازش‌شده در کانال: {last_sent_id} (پیام‌های قدیمی‌تر از این رد می‌شوند)")
    else:
        print("🔍 سابقه قبلی در کانال یافت نشد؛ پیام‌های ۱۵ دقیقه گذشته بررسی می‌شوند.")

    grouped_posts = {}

    print("در حال بررسی پیام‌های کانال مبدأ...")
    async for message in client.iter_messages(SOURCE_CHANNEL, limit=35):
        # شرط توقف قطعی: پیام‌های مساوی یا قدیمی‌تر از آخرین آیدی ثبت‌شده
        if last_sent_id > 0 and message.id <= last_sent_id:
            break
        # در صورت نبود آیدی قبلی، بر اساس زمان ۱۵ دقیقه متوقف می‌شود
        if last_sent_id == 0 and message.date < time_limit:
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
        print("هیچ پیام جدیدی برای پردازش یافت نشد.")
        await client.disconnect()
        return

    # مرتب‌سازی از قدیمی به جدید
    sorted_groups = sorted(grouped_posts.values(), key=lambda group: min(m.id for m in group))

    # ۲. آماده‌سازی دسته جمعی برای جمینای
    batch_for_gemini = []
    groups_by_first_id = {}

    for group in sorted_groups:
        text_content = ""
        for msg in group:
            caption = msg.text or msg.message
            if caption and caption.strip():
                text_content = caption.strip()
                break

        if not text_content:
            continue

        first_id = min(m.id for m in group)
        groups_by_first_id[first_id] = group
        batch_for_gemini.append({
            "id": first_id,
            "text": text_content
        })

    if not batch_for_gemini:
        print("هیچ پست متنی واجد شرایطی یافت نشد.")
        await client.disconnect()
        return

    # ۳. یک درخواست تکی به جمینای برای تمام پست‌ها
    print(f"🚀 ارسال یکجای {len(batch_for_gemini)} پست به جمینای...")
    processed_results = process_batch_with_gemini(batch_for_gemini)

    # ۴. ارسال خروجی‌ها به کانال‌ها
    for first_id, raw_processed_text in processed_results.items():
        if raw_processed_text == "SKIP" or not raw_processed_text.strip():
            print(f"پست شناسه {first_id} رد شد (SKIP).")
            continue

        base_formatted_text = format_news_text(raw_processed_text)
        if not base_formatted_text:
            continue

        group = groups_by_first_id[first_id]
        media_messages = [m for m in group if m.media]

        for target in TARGET_CHANNELS:
            caption = prepare_caption_for_target(base_formatted_text, target, first_id)

            try:
                if len(media_messages) > 1:
                    files_to_send = [m.media for m in media_messages]
                    await client.send_file(
                        target,
                        file=files_to_send,
                        caption=caption,
                        parse_mode="html"
                    )
                    print(f"✅ آلبوم چندرسانه‌ای {first_id} به {target} ارسال شد.")

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
                print(f"❌ خطا در ارسال پست {first_id} به {target}: {e}")

    await client.disconnect()
    print("پایان عملیات.")

if __name__ == "__main__":
    asyncio.run(fetch_and_process_messages())
