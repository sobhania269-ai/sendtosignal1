import os
import json
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = """
تو یک ویراستار و فیلترکننده حرفه‌ای اخبار تلگرام هستی. متن خبر ارسالی را ارزیابی و پاک‌سازی کن.

قوانین غربالگری و فیلتر:
۱. موضوعات مجاز: اخبار اقتصادی (بازارها، ارز، طلا، مسکن، تورم، تجارت، انرژی) و اخبار سیاسی (سیاست خارجی، بین‌الملل، مجلس، دولت، مواضع سیاسی، احزاب، نظامی و حوادث مهم).
   - اگر خبر کاملاً ورزشی، تبلیغاتی، زرد، سینمایی یا بی‌معنی است -> رد کن (SKIP).
   - عبارت‌های «چند ثانیه»، «چندثانیه»، «زیدآبادی» یا «روزنامه» را اگر دیدی -> رد کن (SKIP).

قوانین ویرایش متن‌های تاییدشده:
۱. حذفیات ضروری:
   - هرگونه آیدی تلگرام، شماره تماس، لینک و منبع ارجاعی را کلاً حذف کن.
   - تمام ایموجی‌ها، استیکرها و لوزی‌های رنگی (مانند 🔹، 🔷، 🔴 و...) را از سرتاسر متن حذف کن.
۲. قالب‌بندی:
   - تیتر یا خط اول خبر را حتماً داخل تگ <b>تیتر</b> قرار بده.
   - هرگز از فرمت ستاره (**) برای بولد کردن استفاده نکن؛ فقط تگ <b>متن</b>.
۳. امانت‌داری متن:
   - جزئیات، لحن و متن اصلی خبر را بازنویسی نکن. تنها عبارات ممنوعه و زوائد را حذف کن.
   - هیچ تحلیل، مقدمه، توضیح یا متنی از خودت اضافه نکن.
۴. اگر کل متن پس از حذف زوائد خالی شد -> رد کن (SKIP).

قالب پاسخ خروجی:
یک آرایه JSON شامل اشیایی با سه کلید "id" و "text" و "reason":
- اگر تایید شد: "text" متن خبر است و "reason" خالی باشد ("").
- اگر رد شد: "text" حتماً دقیقاً برابر "SKIP" باشد و "reason" دلیل خیلی کوتاه رد شدن (حداکثر ۴ یا ۵ کلمه فارسی، مثل: "موضوع ورزشی"، "تبلیغاتی"، "وجود کلمه چندثانیه"، "خبر زرد").

نمونه خروجی:
[
  {"id": 12345, "text": "<b>تیتر خبر</b>\\n\\nمتن ویرایش‌شده خبر", "reason": ""},
  {"id": 12346, "text": "SKIP", "reason": "حاوی کلمه روزنامه"}
]
"""

def process_batch_with_gemini(posts: list[dict]) -> dict[int, dict]:
    """
    ارسال یکجای پست‌ها و دریافت دیکشنری:
    {post_id: {"text": str, "reason": str}}
    """
    if not posts:
        return {}

    prompt_content = json.dumps(posts, ensure_ascii=False, indent=2)

    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=f"لیست پست‌های جدید جهت بررسی و ویرایش:\n\n{prompt_content}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json"
            )
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed_data = json.loads(raw_text)
        results = {}
        for item in parsed_data:
            results[int(item["id"])] = {
                "text": item.get("text", "SKIP"),
                "reason": item.get("reason", "")
            }
        return results

    except Exception as e:
        print(f"❌ خطا در پردازش یکجای جمینای: {e}")
        return {p["id"]: {"text": "SKIP", "reason": f"خطای ارتباطی: {e}"} for p in posts}
