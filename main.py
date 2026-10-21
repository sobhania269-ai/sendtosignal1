import os
import re
import asyncio
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from gemini_processor import process_batch_with_gemini, process_batch_translation_with_gemini

# متغیرهای اتصال تلگرام
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# کانال‌ها
SOURCE_CHANNEL_FA = "@chandsanieh_news"
SOURCES_EN = ["@ForexNewsNavigator_Official", "@cointelegraph"]

TARGET_CHANNELS_ALL = ["@isignal_ir", "@finsoph_news"]
TARGET_FINSOPH_ONLY = ["@finsoph_news"]

# ایموجی‌های پریمیوم
EMOJI_AHMAD_BULLET = "5958629062858514430"  # ایموجی سبز
EMOJI_ID = "5836782704686798781"            # ایموجی آیدی (مشترک)
EMOJI_LINK = "5271604874419647061"          # ایموجی پیوند (مشترک)
EMOJI_FINSOPH_BULLET = "5958661279408200638" # ایموجی نارنجی فینسوف

# کاراکترهای نامرئی برای کدگذاری شناسه پیام
ZW_0 = "\u200b"
ZW_1 = "\u200c"
ZW_SEP = "\u200d"

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def encode_id_invisible(channel_code: str, msg_id: int) -> str:
    """کدگذاری شناسه پیام همراه با کد منبع برای ردگیری تفکیک‌شده"""
    binary = bin(msg_id)[2:]
    invisible_str = "".join(ZW_1 if b == "1" else ZW_0 for b in binary)
    return f"{ZW_SEP}{channel_code}{invisible_str}{ZW_SEP}"

def decode_id_invisible(text: str, channel_code: str) -> int:
    """استخراج شناسه پیام بر اساس کد منبع"""
    if not text:
        return 0
    pattern = rf"{ZW_SEP}{channel_code}([{ZW_0}{ZW_1}]+){ZW_SEP}"
    match = re.search(pattern, text)
    if match:
        binary_str = "".join("1" if c == ZW_1 else "0" for c in match.group(1))
        try:
            return int(binary_str, 2)
        except ValueError:
            return 0
    return 0

def pre_clean_source_text(raw_text: str) -> str:
    """حذف نام و لینک کانال چندثانیه از پیام فارسی"""
    if not raw_text:
        return ""
    cleaned = re.sub(r'چند[\s\u200c]*ثانیه(\s*آنلاین)?', '', raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'https?://t\.me/chandsanieh_news\S*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'@chandsanieh_news', '', cleaned, flags=re.IGNORECASE)
    lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
    return "\n\n".join(lines)

def format_news_text(raw_text: str) -> str:
    """پاک‌سازی لوزی‌های آبی و بولد کردن خط اول"""
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

def prepare_caption(base_text: str, target: str, channel_code: str, source_msg_id: int) -> str:
    """شخصی‌سازی ظاهر، فوتر و تگ نامرئی بر اساس کانال مقصد"""
    paragraphs = base_text.split('\n\n')
    invisible_tag = encode_id_invisible(channel_code, source_msg_id)

    if target == "@isignal_ir":
        formatted_paragraphs = [
            f'<tg-emoji emoji-id="{EMOJI_AHMAD_BULLET}">🟢</tg-emoji> {p}' for p in paragraphs
        ]
        body = '\n\n'.join(formatted_paragraphs)
        footer = (
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> {target}\n'
            f'<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> <a href="https://isignal.ir">isignal.ir</a>'
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
            f'<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> <a href="https://finsoph.ir">finsoph.ir</a>'
        )
        return f"{body}\n\n{footer}{invisible_tag}"

    return f"{base_text}\n\n{target}{invisible_tag}"

async def get_last_processed_id(channel_username: str, channel_code: str) -> int:
    """خواندن شناسه آخرین پیام پردازش‌شده از کانال مقصد"""
    try:
        async for msg in client.iter_messages(channel_username, limit=15):
            text = msg.text or msg.message or ""
            msg_id = decode_id_invisible(text, channel_code)
            if msg_id > 0:
                return msg_id
    except Exception as e:
        print(f"خطا در خواندن پیام‌های {channel_username}: {e}")
    return 0

async def process_channel(source_channel: str, targets: list[str], channel_code: str, is_translation: bool = False):
    """پردازش یک کانال مبدأ و ارسال به مقاصد تعیین‌شده"""
    print(f"\n==============================")
    print(f"📥 شروع بررسی کانال مبدأ: {source_channel}")
    
    last_sent_id = await get_last_processed_id(targets[0], channel_code)
    time_limit = datetime.now(timezone.utc) - timedelta(minutes=15)

    if last_sent_id > 0:
        print(f"🔍 آخرین پیام ثبت‌شده از {source_channel}: {last_sent_id}")
    else:
        print(f"🔍 پیام قبلی یافت نشد؛ پیام‌های ۱۵ دقیقه گذشته بررسی می‌شوند.")

    grouped_posts = {}
    async for message in client.iter_messages(source_channel, limit=30):
        if last_sent_id > 0 and message.id <= last_sent_id:
            break
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
        print(f"پیام جدیدی در {source_channel} یافت نشد.")
        return

    sorted_groups = sorted(grouped_posts.values(), key=lambda group: min(m.id for m in group))
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

        if not is_translation:
            text_content = pre_clean_source_text(text_content)

        if text_content:
            batch_for_gemini.append({"id": first_id, "text": text_content})

    if not batch_for_gemini:
        return

    print(f"🚀 ارسال {len(batch_for_gemini)} پست از {source_channel} به جمینای ({'ترجمه' if is_translation else 'ویرایش'})...")
    
    if is_translation:
        results = process_batch_translation_with_gemini(batch_for_gemini)
    else:
        results = process_batch_with_gemini(batch_for_gemini)

    for first_id, item_data in results.items():
        raw_text = item_data.get("text", "SKIP")
        skip_reason = item_data.get("reason", "").strip()

        if raw_text == "SKIP" or not raw_text.strip():
            reason_msg = f" (علت: {skip_reason})" if skip_reason else ""
            print(f"⛔ پست {first_id} از {source_channel} رد شد{reason_msg}")
            continue

        formatted_text = format_news_text(raw_text)
        if not formatted_text:
            continue

        group = groups_by_first_id[first_id]
        media_messages = [m for m in group if m.media]

        for target in targets:
            caption = prepare_caption(formatted_text, target, channel_code, first_id)
            try:
                if len(media_messages) > 1:
                    files_to_send = [m.media for m in media_messages]
                    await client.send_file(target, file=files_to_send, caption=caption, parse_mode="html")
                    print(f"✅ آلبوم چندرسانه‌ای {first_id} به {target} ارسال شد.")
                elif len(media_messages) == 1:
                    await client.send_message(target, caption, file=media_messages[0].media, parse_mode="html", link_preview=False)
                    print(f"✅ پست تک‌مدیا {first_id} به {target} ارسال شد.")
                else:
                    await client.send_message(target, caption, parse_mode="html", link_preview=False)
                    print(f"✅ پست متنی {first_id} به {target} ارسال شد.")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"❌ خطا در ارسال به {target}: {e}")

async def main():
    await client.start()
    print("اتصال تلگرام برقرار شد.")

    # ۱. کانال فارسی (ارسال به هر دو کانال: آی‌سیگنال و فینسوف)
    await process_channel(
        source_channel=SOURCE_CHANNEL_FA,
        targets=TARGET_CHANNELS_ALL,
        channel_code="FA_",
        is_translation=False
    )

    # ۲. کانال فارکس انگلیسی (ترجمه و ارسال فقط به فینسوف)
    await process_channel(
        source_channel=SOURCES_EN[0],
        targets=TARGET_FINSOPH_ONLY,
        channel_code="FX_",
        is_translation=True
    )

    # ۳. کانال کریپتو انگلیسی (ترجمه و ارسال فقط به فینسوف)
    await process_channel(
        source_channel=SOURCES_EN[1],
        targets=TARGET_FINSOPH_ONLY,
        channel_code="CT_",
        is_translation=True
    )

    await client.disconnect()
    print("\n🏁 تمام عملیات با موفقیت به پایان رسید.")

if __name__ == "__main__":
    asyncio.run(main())
