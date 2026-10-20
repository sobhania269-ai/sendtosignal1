import os
import json
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = """
تو یک ویراستار و فیلترکننده حرفه‌ای اخبار تلگرام هستی. متن خبر ارسالی را ارزیابی و پاک‌سازی کن.

قوانین غربالگری و فیلتر:
۱. موضوعات مجاز: اخبار اقتصادی (بازارها، ارز، طلا، مسکن، تورم، تجارت، انرژی) و اخبار سیاسی (سیاست خارجی، بین‌الملل، مجلس، دولت، مواضع سیاسی، احزاب و نظامی و حوادث).
   - اگر خبر کاملاً ورزشی یا تبلیغاتی است -> فقط بنویس: SKIP

- عبارت‌های «چند ثانیه»، «چندثانیه»، «زیدآبادی» را اگر دیدی skip کن.
۲. اگر خبر واجد شرایط بود، آن را طبق قوانین زیر تمیز و ویرایش کن:

قوانین پاک‌سازی و ویرایش:
۱. حذفیات ضروری (این موارد را از متن حذف کن، نه اینکه خبر را بسوزانی):
   
   - هرگونه آیدی تلگرام (مثل @chandsanieh_news یا @...)، شماره تماس، لینک و منبع ارجاعی را کلاً حذف کن.
   - تمام ایموجی‌ها، استیکرها و لوزی‌های رنگی (مانند 🔹، 🔷، 🔴 و...) را از سرتاسر متن حذف کن.
۲. قالب‌بندی:
   - تیتر یا خط اول خبر را داخل تگ <b>تیتر</b> قرار بده.
   - هرگز از فرمت ستاره (**) برای بولد کردن استفاده نکن؛ فقط تگ <b>متن</b>.
۳. امانت‌داری متن:
   - جزئیات، لحن و متن اصلی خبر را بازنویسی نکن. تنها عبارات ممنوعه و زوائد را حذف کن.
   - از اضافه کردن هرگونه تحلیل، پیش‌گفتار، پس‌گفتار یا توضیح خودت جداً خودداری کن.
۴. اگر کل متن پس از حذف این موارد خالی شد، بنویس: SKIPقالب پاسخ خروجی:
یک آرایه JSON شامل اشیایی با دو کلید "id" و "text":
[
  {"id": 12345, "text": "<b>تیتر خبر</b>\\n\\nمتن ویرایش‌شده خبر"},
  {"id": 12346, "text": "SKIP"}
]
"""

def process_batch_with_gemini(posts: list[dict]) -> dict[int, str]:
    """
    ارسال یکجای تمام پست‌ها در یک درخواست و دریافت دیکشنری {post_id: processed_text}
    """
    if not posts:
        return {}

    prompt_content = json.dumps(posts, ensure_ascii=False, indent=2)

    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=f"لیست پست‌های جدید جهت بررسی و ویرایش:\n\n{prompt_content}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json"
            )
        )
        
        parsed_data = json.loads(response.text.strip())
        results = {}
        for item in parsed_data:
            results[int(item["id"])] = item.get("text", "SKIP")
        return results

    except Exception as e:
        print(f"❌ خطا در پردازش یکجای جمینای: {e}")
        # در صورت بروز خطای کلی، تمام موارد رد می‌شوند تا خطا رخ ندهد
        return {p["id"]: "SKIP" for p in posts}
