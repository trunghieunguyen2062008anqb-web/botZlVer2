import os
import json

STATE_FILE = "bot_state.json"
GROUPS_FILE = "groups.txt"

def load_state():
    """Tải trạng thái cấu hình từ file JSON hoặc khởi tạo mặc định"""
    default_state = {
        "auto_reply_enabled": True,
        "auto_send_enabled": False,
        "random_delay_enabled": False,
        "delay_between_groups": 30,
        "auto_send_interval": 900,
        "auto_send_messages": [
            "✨ HIẾU CHÁY STORE ✨\nThu mua Zalo GDTG\nLiên hệ: 0562437403",
            "✨ HIẾU CHÁY STORE ✨\nNhận làm Web / Bot Telegram\nLiên hệ: 0562437403",
            "✨ HIẾU CHÁY STORE ✨\nBán YouTube Premium / Netflix giá rẻ\nLiên hệ: 0562437403",
            "✨ HIẾU CHÁY STORE ✨\nNhận tăng tương tác TikTok / YouTube\nLiên hệ: 0562437403",
            "✨ HIẾU CHÁY STORE ✨\nNhóm giao lưu MMO: https://zalo.me/g/bcuisd3btxjopjqfnhnt"
        ],
        "auto_send_message": "✨ HIẾU CHÁY STORE ✨\nThu mua Zalo GDTG\nLiên hệ: 0562437403",
        "auto_send_groups": [],
        "blacklisted_groups": [],
        "known_joined_groups": []
    }
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                
                # Khởi tạo danh sách đen nếu chưa có
                if "blacklisted_groups" not in state:
                    state["blacklisted_groups"] = []
                
                # Giữ nguyên danh sách tin nhắn động, lọc bỏ tin nhắn trống
                msgs = state.get("auto_send_messages", [])
                if not msgs or not isinstance(msgs, list):
                    msgs = default_state["auto_send_messages"]
                msgs = [m for m in msgs if m and m.strip()]
                state["auto_send_messages"] = msgs
                
                return state
        except Exception as e:
            print(f"❌ Lỗi đọc file bot_state.json: {e}")
            
    return default_state

def save_state(state):
    """Lưu trạng thái cấu hình vào file JSON"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ Lỗi ghi file bot_state.json: {e}")

def save_groups_to_txt(groups):
    """Lưu danh sách ID nhóm vào file groups.txt để hiển thị thủ công"""
    try:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            f.write("# Danh sách ID nhóm rải tin nhắn (mỗi dòng 1 ID, dòng bắt đầu bằng # sẽ bị bỏ qua)\n")
            for g_id in groups:
                f.write(f"{g_id}\n")
    except Exception as e:
        print(f"❌ Lỗi ghi file groups.txt: {e}")

def write_env_file(cookie, imei, phone, password):
    """Ghi đè lại các thông tin cấu hình vào file .env"""
    from dotenv import load_dotenv
    load_dotenv(override=True)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write("# Cấu hình tài khoản Zalo cá nhân\n")
            f.write(f"PHONE_NUMBER={phone}\n")
            f.write(f"PASSWORD={password}\n")
            f.write(f"IMEI={imei}\n")
            f.write(f"COOKIE={cookie}\n\n")
            f.write("# API Key của Gemini AI\n")
            f.write(f"GEMINI_API_KEY={GEMINI_API_KEY or ''}\n\n")
            f.write("# Cấu hình Telegram Bot\n")
            f.write(f"TELEGRAM_BOT_TOKEN={TELEGRAM_BOT_TOKEN or ''}\n")
            f.write(f"TELEGRAM_CHAT_ID={TELEGRAM_CHAT_ID or ''}\n")
        return True
    except Exception as e:
        print(f"❌ Lỗi ghi file .env: {e}")
        return False
