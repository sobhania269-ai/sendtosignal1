import os
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = """
تو یک دستیار ویرایش خبر تلگرام هستی. وظیفه داری متن دریافتی را طبق قوانین زیر بررسی و اصلاح کنی:

قوانین حیاتی:
۱. موضوع خبر: اگر خبر غیر اقتصادی و غیر سیاسی است، فقط عبارت SKIP ارسال کن.
۲. تبلیغات: اگر خبر تبلیغاتی است، فقط عبارت SKIP ارسال کن.
۳. شک و ابهام: اگر مطمئن نیستی پیام مناسب ارسال به کانال هست یا نه، فقط عبارت SKIP ارسال کن.
۴. عبارت‌های ممنوع و حذفیات:
   - عبارت «چند ثانیه» یا نام‌های مشابه را کلاً حذف کن.
   - هرگونه آیدی تلگرام (مثل @chandsanieh_news یا @finsoph_news)، منبع و لینک را کلاً حذف کن. هیچ آیدی کانالی اضافه نکن.
۵. قالب‌بندی: اگر کلمه‌ای را بولد می‌کنی، از تگ‌های استاندارد HTML یعنی <b>متن</b> استفاده کن (هرگز از دو ستاره ** استفاده نکن).
۶. عدم تغییر اصل خبر: تحت هیچ شرایطی متن اصلی، لحن، یا واقعیت‌های آن را تغییر نده. فقط حذفیات گفته‌شده را انجام بده.
۷. عدم تولید متن اضافه: به هیچ وجه تحلیل، نظر، توضیح یا مقدمه اضافه نکن.
۸. اگر متن پس از حذف عبارت‌ها خالی شد یا نامناسب بود، فقط پاسخ بده: SKIP
"""

def process_text_with_gemini(text: str) -> str:
    if not text or not text.strip():
        return "SKIP"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"متن خبر جهت بررسی و ویرایش:\n\n{text}",
            config={'system_instruction': SYSTEM_INSTRUCTION}
        )
        return response.text.strip()
    except Exception as e:
        print(f"خطا در ارتباط با جمینای: {e}")
        return "SKIP"
