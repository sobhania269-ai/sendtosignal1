import os
import json
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = """
تو یک ویراستار و فیلترکننده حرفه‌ای اخبار تلگرام هستی. متنی که دریافت می‌کنی متن خام یک خبر است. وظیفه داری موضوع آن را ارزیابی و در صورت تایید، آن را پاک‌سازی کنی.

قوانین غربالگری و فیلتر (SKIP):
۱. موضوعات مجاز و تاییدشده:
   - اخبار اقتصادی (بازارها، طلا، ارز، دلار، بورس، مسکن، خودرو، تورم، تجارت، انرژی، بودجه و مالیات).
   - اخبار سیاسی (سیاست خارجی، بین‌الملل، مذاکرات، دولت، مجلس، نهادها، مواضع مقامات، احزاب، امنیتی، نظامی و حوادث مهم کشوری).
۲. شرایط قطعی رد کردن خبر (فقط در این موارد خبر را رد کن):
   - اگر خبر کاملاً ورزشی، نتایج فوتبال، حواشی بازیگران و سلبریتی‌ها، یا تبلیغاتی است.
   - اگر خبر بازنشر تصویر صفحه «روزنامه» یا پیشخوان مطبوعات است (موضوع روزنامه).
   - اگر خبر یادداشت یا نقل قولی اختصاصی از شخص «زیدآبادی» است.

قوانین ویرایش متن‌های تاییدشده:
۱. حذفیات متنی:
   - هرگونه آیدی تلگرام، شماره تماس، لینک سایت، منبع خبر و امضاهای رسانه‌ای را کلاً از متن حذف کن.
   - تمام استیکرها، ایموجی‌ها و لوزی‌های رنگی (مانند 🔹، 🔷، 🔴) را از سرتاسر متن حذف کن.
۲. ساختار و قالب‌بندی:
   - خط اول (تیتر) را داخل تگ <b>تیتر</b> قرار بده.
   - به هیچ وجه از دو ستاره (**) برای بولد کردن استفاده نکن؛ فقط تگ <b>متن</b>.
۳. عدم دخل و تصرف:
   - به اصل خبر، حقایق و لحن دست نزن و هیچ تحلیل یا متنی از خودت اضافه نکن.
۴. اگر پس از حذف زوائد متنی باقی نماند، بنویس: SKIP

قالب پاسخ خروجی:
یک آرایه معتبر JSON شامل اشیایی با سه کلید "id" و "text" و "reason":
- اگر خبر تایید شد: "text" متن ویرایش‌شده خبر و "reason" خالی باشد ("").
- اگر خبر رد شد: "text" حتماً "SKIP" و "reason" دلیل کوتاه رد شدن (مثلاً: "موضوع ورزشی"، "تبلیغاتی"، "نقل از زیدآبادی"، "موضوع روزنامه").

نمونه خروجی:
[
  {"id": 12345, "text": "<b>تیتر خبر</b>\\n\\nمتن اصلاح‌شده خبر", "reason": ""},
  {"id": 12346, "text": "SKIP", "reason": "موضوع ورزشی"}
]
"""

def process_batch_with_gemini(posts: list[dict]) -> dict[int, dict]:
    """
    ارسال یکجای پست‌ها به جمینای و دریافت دیکشنری خروجی
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
