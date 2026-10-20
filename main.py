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

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

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

def prepare_caption_for_target(base_text: str, target: str) -> str:
    """شخصی‌سازی متن و فوتر برای هر کانال به صورت کاملاً مجزا"""
    paragraphs = base_text.split('\n\n')

    if target == "@ahmadsobhani":
        formatted_paragraphs = [
            f'<tg-emoji emoji-id="{EMOJI_AHMAD_BULLET}">🟢</tg-emoji> {p}' for p in paragraphs
        ]
        body = '\n\n'.join(formatted_paragraphs)
        footer = (
            f'<tg-emoji emoji-id="{EMOJI_ID}">🆔</tg-emoji> {target}\n'
            f'<tg-emoji emoji-id="{EMOJI_LINK}">🔗</tg-emoji> isignal.ir'
        )
        return f"{body}\n\n{footer}"

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
        return f"{body}\n\n{footer}"

    return f"{base_text}\n\n{target}"

async def get_last_processed_id_from_channel(channel_username: str, source_user: str) -> int:
    """جلوگیری قطعی از تکرار: خواندن آخرین پست ارسال‌شده در کانال جهت استخراج آخرین شناسه پیام"""
    try:
        async for msg in client.iter_messages(channel_username, limit=10):
            text = msg.text or msg.message or ""
            # جستجوی الگوی شناسه پیام مبدأ در صورت وجود یا خواندن پیام
            match = re.search(rf't\.me/{source_user}/(\d+)', text)
            if match:
                return int(match.group(1))
    except Exception as e:
        print(f"اطلاع: امکان خواندن تاریخچه پیام‌های کانال مقصد نبود: {e}")
    return 0

async def fetch_and_process_messages():
    await client.start()
    print(f"اتصال تلگرام برقرار شد.\nمبدأ: {SOURCE_CHANNEL}\nمقاصد: {TARGET_CHANNELS}")

    source_username = SOURCE_CHANNEL.replace("@", "")

    # ۱. جلوگیری از ارسال تکراری بر اساس آخرین پیام ثبت شده در کانال مقصد
    last_sent_id = await get_last_processed_id_from_channel(TARGET_CHANNELS[0], source_username)
    time_limit = datetime.now(timezone.utc) - timedelta(minutes=20)
    
    if last_sent_id > 0:
        print(f"آخرین شناسه ارسال‌شده قبلی: {last_sent_id} (پیام‌های جدیدتر از این بررسی خواهند شد)")

    grouped_posts = {}

    print("در حال بررسی پیام‌های کانال مبدأ...")
    async for message in client.iter_messages(SOURCE_CHANNEL, limit=35):
        # شرط توقف: اگر به پیام‌های قدیمی‌تر از بازه ۲۰ دقیقه یا آخرین پیام ارسالی رسیدیم
        if message.id <= last_sent_id or message.date < time_limit:
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

    # مرتب‌سازی پست‌ها از قدیمی به جدید
    sorted_groups = sorted(grouped_posts.values(), key=lambda group: min(m.id for m in group))

    # ۲. آماده‌سازی دسته جمعی پست‌ها برای هوش مصنوعی
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

    # ۳. ارسال همه پست‌ها به جمینای تنها در ۱ درخواست
    print(f"🚀 ارسال یکجای {len(batch_for_gemini)} پست به جمینای...")
    processed_results = process_batch_with_gemini(batch_for_gemini)

    # ۴. ارسال خروجی‌های تاییدشده به کانال‌ها
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
            caption = prepare_caption_for_target(base_formatted_text, target)

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
