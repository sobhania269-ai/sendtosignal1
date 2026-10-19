import modal
import subprocess
import os

# تعریف محیط اجرایی مودال و پکیج‌های مورد نیاز
image = (
    modal.Image.debian_slim()
    .pip_install("telethon", "google-genai", "python-dotenv")
)

app = modal.App("telegram-bot-cron")

# ولوم ابری برای اینکه فایل last_msg_id.txt همیشه حفظ شود و پاک نشود
volume = modal.Volume.from_name("bot-data-volume", create_if_missing=True)
DATA_DIR = "/data"

@app.function(
    image=image,
    secret=modal.Secret.from_name("telegram-secrets"), # متغیرهای محیطی در مودال
    volumes={DATA_DIR: volume},
    schedule=modal.Cron("*/15 * * * *"), # تنظیم اجرای خودکار هر ۱۵ دقیقه
)
def run_main_script():
    print("شروع اجرای کرون‌جاب مودال روی main.py...")
    
    # اجرای فایل اصلی شما
    result = subprocess.run(["python", "main.py"], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("خطاها:", result.stderr)
        
    # ذخیره تغییرات فایل آیدی‌ها در ولوم ابری
    volume.commit()
    print("پایان اجرای کرون‌جاب.")
