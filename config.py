import os
import sys
from dotenv import load_dotenv

# Cấu hình encoding UTF-8 cho console tránh lỗi hiển thị tiếng Việt trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Tải cấu hình từ file .env
load_dotenv()

PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
PASSWORD = os.getenv("PASSWORD", "")
IMEI = os.getenv("IMEI")
COOKIE = os.getenv("COOKIE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Kiểm tra cấu hình bắt buộc
if not COOKIE or COOKIE == "YOUR_COOKIE_HERE":
    print("[CẢNH BÁO] Bạn chưa cấu hình COOKIE Zalo Web trong file .env")
if not IMEI or IMEI == "YOUR_IMEI_HERE":
    print("[CẢNH BÁO] Bạn chưa cấu hình IMEI Zalo Web trong file .env")
