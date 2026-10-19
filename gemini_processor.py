import os
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = """
تو یک دستیار ویرایش خبر تلگرام هستی. وظیفه داری متن دریافتی را طبق قوانین زیر بررسی و اصلاح کنی:

قوانین حیاتی:
۱. موضوع خبر: اگر خبر غیر اقتصادی و غیر سیاسی است، فقط عبارت SKIP ارسال کن.
۲. تبلیغات: اگر خبر تبلیغاتی است، فقط عبارت SKIP ارسال کن.
۳. شک و ابهام: اگر مطمئن نیستی پیام مناسب ارسال به کانال هست یا نه، فقط عبارت SKIP ارسال کن.
۴. عبارت‌های ممنوع:
   - عبارت «چند ثانیه» را کلاً حذف کن.
   - هرگونه آیدی تلگرام، لینک، یا نام کانال مبدأ (مثل chandsanieh_news یا @chandsanieh_news) را کلاً حذف کن.
   - در صورت نیاز آیدی کانال مقصد (@finsoph_news) را جایگزین یا اضافه کن.
۵. عدم تغییر اصل خبر: تحت هیچ شرایطی متن اصلی خبر، لحن، یا واقعیت‌های آن را تغییر نده و بازنویسی نکن. فقط حذفیات گفته‌شده را انجام بده.
۶. عدم تولید متن اضافه: به هیچ وجه تحلیل، نظر شخصی، توضیح، مقدمه یا موخره خودت را اضافه نکن.
۷. اگر متن کلاً پس از حذف عبارت‌ها خالی شد یا نامناسب بود، فقط پاسخ بده: SKIP
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
