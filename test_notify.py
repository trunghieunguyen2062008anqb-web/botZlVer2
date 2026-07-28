import sys
from config import PHONE_NUMBER, PASSWORD, IMEI, COOKIE
from zlapi import ZaloAPI
from zlapi.models import Message, ThreadType

def parse_cookie_string(cookie_str):
    cookies = {}
    if not cookie_str or cookie_str.strip() == "" or cookie_str == "YOUR_COOKIE_HERE":
        return cookies
    try:
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                k, v = item.split('=', 1)
                cookies[k] = v
    except Exception as e:
        print(f"Lỗi: {e}")
    return cookies

def main():
    cookies_dict = parse_cookie_string(COOKIE)
    try:
        bot = ZaloAPI(
            phone=PHONE_NUMBER if PHONE_NUMBER != "YOUR_PHONE_NUMBER_HERE" else "",
            password=PASSWORD if PASSWORD != "YOUR_PASSWORD_HERE" else "",
            imei=IMEI,
            cookies=cookies_dict
        )
        my_uid = bot.uid() if callable(bot.uid) else bot.uid
        print(f"🟢 Kết nối thành công! UID của bạn: {my_uid}")
        
        test_text = (
            "🔔 [ZALO BOT - KIỂM TRA THÔNG BÁO TỪ HỆ THỐNG]\n"
            "🟢 Gửi thử nghiệm thành công trực tiếp vào mục My Documents (Cloud của tôi)!\n"
            "🚀 Trạng thái: Hoạt động hoàn hảo."
        )
        bot.send(Message(text=test_text), thread_id=my_uid, thread_type=ThreadType.USER)
        print("✅ Đã gửi thành công tin nhắn kiểm tra vào mục My Documents của bạn!")
    except Exception as e:
        print(f"❌ Lỗi khi gửi tin kiểm tra: {e}")

if __name__ == "__main__":
    main()
