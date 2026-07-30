import asyncio
import sys
import io
import json
import os
import time
import threading
import google.generativeai as genai
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify

# Cấu hình encoding UTF-8 cho console tránh lỗi hiển thị tiếng Việt trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Import config ban đầu
import config
from config import PHONE_NUMBER, PASSWORD, IMEI, COOKIE, GEMINI_API_KEY
from zlapi import ZaloAPI
from zlapi.models import Message, ThreadType

# Khởi tạo ứng dụng Web Control Panel (Flask)
app = Flask(__name__)

# Tên file lưu trạng thái cấu hình của bot
STATE_FILE = "bot_state.json"
GROUPS_FILE = "groups.txt"

# Các biến trạng thái toàn cục của Bot
bot_instance = None
bot_status = "DISCONNECTED"  # CONNECTED, CONNECTING, DISCONNECTED, ERROR
bot_error_message = ""
bot_thread = None
auto_send_started = False

def load_state():
    """Tải trạng thái cấu hình từ file JSON hoặc khởi tạo mặc định"""
    default_state = {
        "auto_reply_enabled": True,
        "auto_send_enabled": False,
        "random_delay_enabled": False,  # Tắt giãn cách ngẫu nhiên mặc định
        "delay_between_groups": 30,  # Giãn cách giữa mỗi nhóm (giây) - Mặc định 30 giây
        "auto_send_interval": 1800,  # Thời gian chờ sau mỗi chu kỳ (giây) - Mặc định 30 phút
        "auto_send_messages": [
            (
                "┌─────────────────────────────┐\n"
                "  ✨ HCS-BOT [ AUTO ODER] ✨\n"
                "  🔥 Uy Tín Đổi Trả 100% 🔥\n"
                "└─────────────────────────────┘\n\n"
                "⚡ GÓI ACCOUNT HẤP DẪN:\n"
                "━━━━━━━━━━━━━━━━━\n"
                "✦ TikTok Clone Reg (>7 ngày) ───> 900đ\n"
                "✦ Gemini Slot (1 năm):\n"
                "  • Gói 1 tháng ───> 25K\n"
                "  • Gói 3 tháng ───> 75K\n"
                "  • Gói 6 tháng ───> 150K\n"
                "━━━━━━━━━━━━━━━━━\n"
                "💳 Quét mã QR thanh toán tự động nhận hàng trong 30s.\n"
                "✉️ Liên hệ mua hàng: https://t.me/hieuchaystore_bot"
            ),
            (
                "┌─────────────────────────────┐\n"
                "  ✨ HCS-BOT [ AUTO ODER] ✨\n"
                "  🔥 Giải trí không giới hạn 🔥\n"
                "└─────────────────────────────┘\n\n"
                "⚡ DỊCH VỤ YOUTUBE PREMIUM:\n"
                "━━━━━━━━━━━━━━━━━\n"
                "✦ YouTube Premium (1 tháng) ───> 15.000đ\n"
                "  • Xem video không quảng cáo\n"
                "  • Phát nhạc trong nền/tắt màn hình\n"
                "  • Tải video xem offline cực tiện lợi\n"
                "━━━━━━━━━━━━━━━━━\n"
                "💳 Thanh toán tự động - Nhận tài khoản ngay trong 30s.\n"
                "✉️ Liên hệ mua hàng: https://t.me/hieuchaystore_bot"
            ),
            (
                "┌─────────────────────────────┐\n"
                "  ✨ HCS-BOT [ AUTO ODER] ✨\n"
                "  🔥 Giải pháp bán hàng tự động 🔥\n"
                "└─────────────────────────────┘\n\n"
                "⚡ NHẬN LÀM BOT TELEGRAM:\n"
                "━━━━━━━━━━━━━━━━━\n"
                "✦ Thiết kế Bot Telegram bán hàng ───> 150.000đ\n"
                "  • Quản lý đơn hàng tự động 24/7\n"
                "  • Tích hợp thanh toán quét mã QR\n"
                "  • Thống kê doanh thu chi tiết\n"
                "━━━━━━━━━━━━━━━━━\n"
                "💳 Nâng tầm kinh doanh - Chi phí tối ưu nhất.\n"
                "✉️ Liên hệ mua hàng: https://t.me/hieuchaystore_bot"
            )
        ],
        "current_message_index": 0,
        "auto_send_message": "",
        "auto_send_groups": [],       # Danh sách ID nhóm nhận tin nhắn tự động
        "last_reply_timestamps": {}   # Lưu mốc thời gian đã tự động trả lời để tránh spam khi bot restart
    }
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Gộp cấu hình mặc định để đảm bảo đầy đủ các trường mới thêm
                for k, v in default_state.items():
                    if k not in loaded:
                        loaded[k] = v
                return loaded
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

def load_groups_from_txt():
    """Đọc danh sách ID nhóm từ file groups.txt"""
    groups = []
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        groups.append(line)
        except Exception as e:
            print(f"❌ Lỗi khi đọc file groups.txt: {e}")
    return groups

def save_groups_to_txt(group_list):
    """Ghi danh sách ID nhóm vào file groups.txt"""
    try:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            f.write("# Hãy nhập các ID nhóm Zalo (mỗi dòng 1 ID) bạn muốn rải tin vào đây.\n")
            f.write("# Cách lấy ID nhóm: Chạy list_groups.py hoặc xem trực tiếp trên Web Dashboard\n")
            for g_id in group_list:
                f.write(f"{g_id}\n")
    except Exception as e:
        print(f"❌ Lỗi ghi file groups.txt: {e}")

def parse_cookie_string(cookie_str):
    """Phân tích chuỗi cookie dạng raw từ trình duyệt thành dictionary"""
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
        print(f"❌ Lỗi phân tích chuỗi Cookie: {e}")
    return cookies

# Cấu hình Gemini AI (Tùy chọn)
use_gemini = False
ai_model = None

if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel("gemini-1.5-flash")
        use_gemini = True
        print("🤖 Gemini AI đã được cấu hình thành công! Sẵn sàng xử lý tin nhắn tự động.")
    except Exception as e:
        print(f"❌ Không thể cấu hình Gemini AI: {e}")


def send_telegram_notification(text):
    """Gửi thông báo tin nhắn mới qua Telegram nếu người dùng cấu hình Token và Chat ID trong file .env"""
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id and token != "YOUR_TELEGRAM_BOT_TOKEN_HERE" and chat_id != "YOUR_TELEGRAM_CHAT_ID_HERE":
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text
            }
            requests.post(url, json=payload, timeout=5)
            print("📤 Đã gửi thông báo qua Telegram thành công.")
        except Exception as e:
            print(f"❌ Không thể gửi thông báo qua Telegram: {e}")


class PersonalZaloBot(ZaloAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = load_state()
        self.existing_groups = set()
        
    def onMessage(self, mid, author_id, message, message_object, thread_id, thread_type):
        my_uid = self.uid() if callable(self.uid) else self.uid
        
        # Tránh tự trả lời tin nhắn của chính mình (nhưng vẫn cho phép gõ lệnh điều khiển bằng dấu '.')
        if author_id == my_uid:
            if message and isinstance(message, str) and message.strip().startswith("."):
                pass
            else:
                # Đồng bộ trực tiếp vào state và lưu file
                timestamps = self.state.get("last_reply_timestamps", {})
                timestamps[thread_id] = time.time()
                self.state["last_reply_timestamps"] = timestamps
                save_state(self.state)
                return

        # Tự động nhận diện nhóm mới gia nhập
        if thread_type == ThreadType.GROUP:
            if hasattr(self, 'existing_groups') and thread_id not in self.existing_groups:
                self.existing_groups.add(thread_id)
                if thread_id not in self.state["auto_send_groups"]:
                    self.state["auto_send_groups"].append(thread_id)
                    save_state(self.state)
                    save_groups_to_txt(self.state["auto_send_groups"])
                    print(f"🆕 [TỰ ĐỘNG] Phát hiện nhóm mới gia nhập: {thread_id}. Đã tự động thêm vào groups.txt và đồng bộ state!")

        # Chỉ xử lý tin nhắn dạng chữ
        if not message or not isinstance(message, str):
            return

        message = message.strip()

        # 1. Xử lý các lệnh cấu hình bắt đầu bằng dấu chấm '.'
        if message.startswith("."):
            print(f"📩 [LỆNH CHẠY] {author_id}: {message}")
            self.handle_command(message, thread_id, thread_type, author_id)
            return

        # 2. Xử lý tự động phản hồi khi không online (nếu bật)
        if self.state.get("auto_reply_enabled", True):
            # KHÔNG tự động phản hồi trong bất kỳ nhóm chat nào (ThreadType.GROUP) để tránh làm phiền nhóm.
            # Chỉ tự động trả lời tin nhắn riêng tư (ThreadType.USER).
            if thread_type == ThreadType.GROUP:
                return
            
            # Đối với chat cá nhân (USER)
            if thread_type == ThreadType.USER:
                current_time = time.time()
                
                # --- PHẦN GỬI THÔNG BÁO CHO CHỦ SHop ---
                try:
                    # Lấy tên của khách hàng
                    sender_name = "Người lạ"
                    try:
                        info = self.fetchUserInfo(thread_id)
                        if info:
                            sender_name = getattr(info, 'name', 'Người lạ')
                    except:
                        pass
                    
                    notify_text = (
                        f"🔔 [ZALO BOT - TIN NHẮN MỚI]\n"
                        f"👤 Khách hàng: {sender_name} (ID: {thread_id})\n"
                        f"💬 Nội dung: \"{message}\"\n"
                        f"🔗 Hãy mở Zalo để phản hồi khách hàng!"
                    )
                    
                    # 1. Gửi tin nhắn đến Cloud của tôi (Truyền File) để tạo dấu chấm đỏ báo hiệu trên ứng dụng điện thoại
                    self.send(Message(text=notify_text), thread_id=my_uid, thread_type=ThreadType.USER)
                    
                    # 2. Gửi qua Telegram (nếu có cấu hình trong .env)
                    send_telegram_notification(notify_text)
                except Exception as e:
                    print(f"⚠️ Lỗi gửi thông báo tin nhắn mới: {e}")
                # --------------------------------------
                
                # Kiểm tra giãn cách 2 tiếng (7200 giây) kể từ lần trả lời tự động trước
                timestamps = self.state.get("last_reply_timestamps", {})
                last_time = timestamps.get(thread_id, 0)
                if current_time - last_time < 7200:
                    # Chưa đủ 2 tiếng, không rep tự động tiếp để tránh spam
                    return
                # Đánh dấu thời gian đã phản hồi và lưu lại
                timestamps[thread_id] = current_time
                self.state["last_reply_timestamps"] = timestamps
                save_state(self.state)
            
            # Chỉ in log tin nhắn nếu là chat riêng
            print(f"📩 [{thread_type.name}] {author_id}: {message}")
            self.generate_and_send_reply(message, thread_id, thread_type)

    def handle_command(self, cmd_text, thread_id, thread_type, author_id):
        """Xử lý các câu lệnh cấu hình của Bot"""
        parts = cmd_text.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        print(f"🛠️ Thực thi lệnh: {cmd} {args}")

        if cmd == ".ping":
            self.send(Message(text="🏓 Pong! Zalo Bot của bạn vẫn đang hoạt động ổn định 24/24."), thread_id, thread_type)
            
        elif cmd == ".id":
            self.send(Message(text=f"🆔 ID của cuộc hội thoại này là: {thread_id}"), thread_id, thread_type)
            return
            
        elif cmd == ".test":
            try:
                my_uid = self.uid() if callable(self.uid) else self.uid
                test_text = (
                    "🔔 [ZALO BOT - THỬ NGHIỆM THÔNG BÁO]\n"
                    "⚙️ Đây là tin nhắn thử nghiệm gửi đến mục My Documents của bạn.\n"
                    "🟢 Hệ thống thông báo đẩy đã hoạt động hoàn hảo!"
                )
                self.send(Message(text=test_text), thread_id=my_uid, thread_type=ThreadType.USER)
                self.send(Message(text="✅ Đã gửi tin nhắn test vào mục My Documents của bạn. Hãy mở My Documents kiểm tra!"), thread_id, thread_type)
            except Exception as e:
                self.send(Message(text=f"❌ Lỗi gửi test: {e}"), thread_id, thread_type)
            return
            
        elif cmd == ".help":
            help_msg = (
                "🤖 HƯỚNG DẪN CẤU HÌNH ZALO SELF-BOT:\n"
                "===================================\n"
                "👉 .ping - Kiểm tra trạng thái hoạt động\n"
                "👉 .reply [on/off] - Bật/Tắt tự động trả lời tin nhắn\n"
                "👉 .autosend [on/off] - Bật/Tắt tự động gửi tin nhắn nhóm định kỳ\n"
                "👉 .addgroup - Thêm nhóm hiện tại vào danh sách gửi tin nhắn định kỳ\n"
                "👉 .delgroup - Xóa nhóm hiện tại khỏi danh sách gửi định kỳ\n"
                "👉 .groups - Xem danh sách nhóm đã đăng ký\n"
                "👉 .autosend msg [nội dung] - Cài đặt tin nhắn định kỳ\n"
                "👉 .autosend time [số giây] - Cài đặt khoảng thời gian gửi (ví dụ: 1800 cho 30 phút)"
            )
            self.send(Message(text=help_msg), thread_id, thread_type)

        elif cmd == ".reply":
            if args.lower() == "on":
                self.state["auto_reply_enabled"] = True
                save_state(self.state)
                self.send(Message(text="✅ Đã BẬT tự động phản hồi tin nhắn."), thread_id, thread_type)
            elif args.lower() == "off":
                self.state["auto_reply_enabled"] = False
                save_state(self.state)
                self.send(Message(text="🛑 Đã TẮT tự động phản hồi tin nhắn."), thread_id, thread_type)

        elif cmd == ".autosend":
            if not args:
                return
            subparts = args.split(" ", 1)
            subcmd = subparts[0].lower()
            subargs = subparts[1].strip() if len(subparts) > 1 else ""

            if subcmd == "on":
                self.state["auto_send_enabled"] = True
                save_state(self.state)
                self.send(Message(text="✅ Đã BẬT tính năng gửi tin nhắn nhóm định kỳ."), thread_id, thread_type)
            elif subcmd == "off":
                self.state["auto_send_enabled"] = False
                save_state(self.state)
                self.send(Message(text="🛑 Đã TẮT tính năng gửi tin nhắn nhóm định kỳ."), thread_id, thread_type)
            elif subcmd == "msg":
                if subargs:
                    self.state["auto_send_message"] = subargs
                    save_state(self.state)
                    self.send(Message(text=f"✅ Đã cập nhật tin nhắn định kỳ thành: '{subargs}'"), thread_id, thread_type)
            elif subcmd == "time":
                try:
                    seconds = int(subargs)
                    if seconds >= 10:
                        self.state["auto_send_interval"] = seconds
                        save_state(self.state)
                        self.send(Message(text=f"✅ Đã cập nhật khoảng thời gian gửi định kỳ thành {seconds} giây."), thread_id, thread_type)
                except ValueError:
                    pass

        elif cmd == ".addgroup":
            if thread_type == ThreadType.GROUP:
                if thread_id not in self.state["auto_send_groups"]:
                    self.state["auto_send_groups"].append(thread_id)
                    save_state(self.state)
                    save_groups_to_txt(self.state["auto_send_groups"])
                    self.send(Message(text=f"✅ Đã thêm nhóm này vào danh sách rải tin."), thread_id, thread_type)

        elif cmd == ".delgroup":
            if thread_type == ThreadType.GROUP:
                if thread_id in self.state["auto_send_groups"]:
                    self.state["auto_send_groups"].remove(thread_id)
                    save_state(self.state)
                    save_groups_to_txt(self.state["auto_send_groups"])
                    self.send(Message(text="✅ Đã xóa nhóm này khỏi danh sách rải tin."), thread_id, thread_type)

        elif cmd == ".groups":
            groups = self.state.get("auto_send_groups", [])
            if not groups:
                self.send(Message(text="ℹ️ Danh sách nhóm đăng ký tự động gửi đang trống."), thread_id, thread_type)
            else:
                msg = "📋 DANH SÁCH NHÓM ĐÃ ĐĂNG KÝ:\n"
                for idx, g_id in enumerate(groups, 1):
                    msg += f"{idx}. ID: {g_id}\n"
                self.send(Message(text=msg), thread_id, thread_type)

    def generate_and_send_reply(self, incoming_msg, thread_id, thread_type):
        """Xử lý sinh phản hồi tự động bằng AI hoặc mẫu mặc định và gửi lại"""
        if use_gemini and ai_model:
            try:
                prompt = (
                    "Bạn là trợ lý ảo cá nhân tự động đại diện cho chủ tài khoản Zalo. "
                    "Hãy trả lời tin nhắn của bạn bè/đối tác một cách lịch sự, tự nhiên, ngắn gọn (dưới 3 câu) bằng tiếng Việt. "
                    f"Tin nhắn nhận được: '{incoming_msg}'"
                )
                response = ai_model.generate_content(prompt)
                reply_text = response.text.strip()
            except Exception as e:
                print(f"❌ Lỗi gọi Gemini AI: {e}")
                reply_text = "Chào bạn! Tôi là bot hỗ trợ tự động của Hiếu. Hiếu đang bận nên chưa thể phản hồi ngay được. Vui lòng để lại lời nhắn hoặc gọi điện trực tiếp nếu có việc gấp nhé. Cảm ơn bạn!"
        else:
            reply_text = "Chào bạn! Tôi là bot hỗ trợ tự động của Hiếu. Hiếu đang bận nên chưa thể phản hồi ngay được. Vui lòng để lại lời nhắn hoặc gọi điện trực tiếp nếu có việc gấp nhé. Cảm ơn bạn!"

        try:
            self.send(Message(text=reply_text), thread_id, thread_type)
            print(f"📤 Đã gửi phản hồi tự động đến {thread_id}")
        except Exception as e:
            print(f"❌ Lỗi gửi tin nhắn phản hồi: {e}")

def is_silent_hours():
    """Kiểm tra xem hiện tại có nằm trong khung giờ nghỉ đêm từ 22h tối đến 7h sáng hôm sau (giờ Việt Nam - GMT+7) không"""
    # Lấy thời gian UTC hiện tại, sau đó cộng thêm 7 tiếng để ra giờ Việt Nam chính xác bất kể timezone của VPS
    utc_now = datetime.now(timezone.utc)
    vn_now = utc_now + timedelta(hours=7)
    current_hour = vn_now.hour
    
    # Khung giờ nghỉ: từ 22h tối (>= 22) HOẶC trước 7h sáng (< 7)
    if current_hour >= 22 or current_hour < 7:
        return True
    return False


def auto_send_thread_worker():
    """Luồng chạy nền xử lý việc tự động gửi tin nhắn định kỳ vào các nhóm đã đăng ký"""
    global bot_instance, bot_status, bot_error_message
    print("🚀 Bắt đầu luồng kiểm tra gửi tin nhắn định kỳ...")
    
    while True:
        try:
            # Lưu lại instance hiện tại đang xử lý
            active_bot = bot_instance
            
            # Chỉ gửi nếu bot đã kết nối thành công
            if active_bot and bot_status == "CONNECTED":
                state = active_bot.state
                if state.get("auto_send_enabled", False):
                    groups = list(state.get("auto_send_groups", []))
                    
                    if groups:
                        # Lấy danh sách ID nhóm đang thực sự tham gia từ Zalo
                        joined_group_ids = []
                        try:
                            group_list = bot_instance.fetchAllGroups()
                            if group_list and hasattr(group_list, 'gridVerMap'):
                                joined_group_ids = list(group_list.gridVerMap.keys())
                        except Exception as e:
                            print(f"⚠️ Không thể nạp danh sách nhóm để đối chiếu: {e}")
                            
                        print(f"📢 Bắt đầu chu kỳ rải tin đến {len(groups)} nhóm...")
                        consecutive_errors = 0
                        
                        # Chọn tin nhắn quảng cáo xoay vòng cho chu kỳ này
                        messages = list(bot_instance.state.get("auto_send_messages", []))
                        msg_idx = bot_instance.state.get("current_message_index", 0)
                        
                        if messages:
                            if msg_idx >= len(messages):
                                msg_idx = 0
                            message_text = messages[msg_idx]
                            # Tăng chỉ số xoay vòng cho đợt tiếp theo
                            bot_instance.state["current_message_index"] = (msg_idx + 1) % len(messages)
                            save_state(bot_instance.state)
                            print(f"🔄 Xoay vòng tin nhắn: Đang gửi tin quảng cáo số {msg_idx + 1}/{len(messages)}...")
                        else:
                            message_text = bot_instance.state.get("auto_send_message", "")
                            
                        for idx, group_id in enumerate(groups):
                            # Kiểm tra xem bot có bị ngắt kết nối hoặc tắt rải tin không
                            if bot_instance != active_bot or not bot_instance.state.get("auto_send_enabled", False):
                                print("🛑 Dừng chu kỳ rải tin do tắt tính năng hoặc bot đã khởi động lại.")
                                break
                                
                            # Nếu danh sách nhóm bị thay đổi trên Web, dừng chu kỳ hiện tại để nạp danh sách mới
                            current_groups = list(bot_instance.state.get("auto_send_groups", []))
                            if current_groups != groups:
                                print("🔄 Danh sách nhóm thay đổi. Khởi động lại chu kỳ gửi để cập nhật...")
                                break
                                
                            # Kiểm tra xem bot có thực sự đang ở trong nhóm này không (nếu lấy được danh sách)
                            if joined_group_ids and group_id not in joined_group_ids:
                                print(f"⚠️ Bỏ qua rải tin ID nhóm {group_id}: Bạn không ở trong nhóm này hoặc ID không tồn tại.")
                                continue
                                
                            # Sử dụng tin nhắn đã chọn cho chu kỳ này
                            if not message_text:
                                time.sleep(5)
                                continue
                                
                            # Lấy tên nhóm từ thông tin lưu trên API Zalo
                            group_name = "Không xác định"
                            try:
                                info = bot_instance.fetchGroupInfo(group_id)
                                if info and hasattr(info, 'gridInfoMap') and group_id in info.gridInfoMap:
                                    group_name = info.gridInfoMap[group_id].get("name") or "Không tên"
                            except:
                                pass
                                
                            print(f"👉 [{idx + 1}/{len(groups)}] Gửi tin đến nhóm: {group_name} (ID: {group_id})")
                            try:
                                bot_instance.send(
                                    Message(text=message_text),
                                    thread_id=group_id,
                                    thread_type=ThreadType.GROUP
                                )
                                print(f"✅ Gửi thành công đến nhóm: {group_name} (ID: {group_id})")
                                consecutive_errors = 0  # Reset bộ đếm lỗi khi gửi thành công
                            except Exception as e:
                                print(f"❌ Lỗi khi gửi đến nhóm {group_name} ({group_id}): {e}")
                                consecutive_errors += 1
                                if consecutive_errors >= 3:
                                    print("🚨 Phát hiện 3 lỗi gửi liên tiếp. Có thể Cookie đã hết hạn hoặc mất kết nối. Dừng chu kỳ rải tin!")
                                    bot_status = "ERROR"
                                    bot_error_message = "Mất kết nối hoặc Cookie hết hạn (3 lỗi liên tiếp)."
                                    break
                            
                            # Chờ giãn cách trước khi gửi nhóm tiếp theo (nếu chưa phải nhóm cuối cùng)
                            if idx < len(groups) - 1:
                                # Xác định khoảng thời gian giãn cách theo múi giờ
                                if is_silent_hours():
                                    current_delay = 10800  # 3 tiếng (3 * 3600)
                                    print("🌙 Đêm (22:00 - 07:00): Chuyển chế độ chờ đêm 3 tiếng trước khi gửi nhóm tiếp theo...")
                                else:
                                    if bot_instance.state.get("random_delay_enabled", True):
                                        current_delay = random.randint(600, 900)  # Ngẫu nhiên 10 - 15 phút
                                        print(f"⏳ Giãn cách ngẫu nhiên: Chờ {current_delay // 60} phút {current_delay % 60} giây trước khi gửi nhóm tiếp theo...")
                                    else:
                                        current_delay = bot_instance.state.get("delay_between_groups", 30)
                                        print(f"⏳ Giãn cách cố định: Chờ {current_delay} giây trước khi gửi nhóm tiếp theo...")
                                
                                start_sleep_time = time.time()
                                elapsed = 0
                                while elapsed < current_delay:
                                    # Thường xuyên kiểm tra xem bot có bị thay đổi hoặc tắt tính năng không
                                    if bot_instance != active_bot or not bot_instance.state.get("auto_send_enabled", False) or bot_status == "ERROR":
                                        break
                                    # Nếu danh sách nhóm thay đổi, thoát chờ để nạp danh sách mới
                                    if list(bot_instance.state.get("auto_send_groups", [])) != groups:
                                        break
                                        
                                    time.sleep(1)
                                    elapsed = time.time() - start_sleep_time
                                    
                                    # Hết giờ đêm (qua 7h sáng) -> Chuyển sang chờ Ngày ngẫu nhiên 10-15p ngay lập tức
                                    if current_delay == 10800 and not is_silent_hours():
                                        current_delay = random.randint(600, 900)
                                        print(f"☀️ Đã qua 7h sáng! Tự động rút ngắn thời gian chờ xuống {current_delay // 60} phút {current_delay % 60} giây...")
                                        
                                    # Bắt đầu giờ đêm (qua 22h tối) -> Kéo dài thời gian chờ lên 3 tiếng
                                    if current_delay != 10800 and is_silent_hours():
                                        current_delay = 10800
                                        print("🌙 Đã qua 22h tối! Tự động kéo dài thời gian chờ đêm lên 3 tiếng...")
                                    
                        # Chờ chu kỳ tiếp theo sau khi rải hết toàn bộ nhóm
                        if bot_instance == active_bot and bot_instance.state.get("auto_send_enabled", False) and bot_status != "ERROR":
                            global_interval = bot_instance.state.get("auto_send_interval", 1800)
                            print(f"🎉 Đã rải hết các nhóm. Chờ {global_interval} giây trước khi bắt đầu chu kỳ tiếp theo...")
                            
                            start_sleep_time = time.time()
                            while time.time() - start_sleep_time < global_interval:
                                if bot_instance != active_bot or not bot_instance.state.get("auto_send_enabled", False) or bot_status == "ERROR":
                                    break
                                if list(bot_instance.state.get("auto_send_groups", [])) != groups:
                                    break
                                global_interval = bot_instance.state.get("auto_send_interval", 1800)
                                time.sleep(1)
                    else:
                        time.sleep(5)
                else:
                    time.sleep(5)
            else:
                time.sleep(5)
        except Exception as e:
            print(f"❌ Lỗi trong luồng chạy nền tự động gửi: {e}")
            time.sleep(10)


def bot_connection_worker():
    """Luồng kết nối và chạy lắng nghe sự kiện của Zalo Bot"""
    global bot_instance, bot_status, bot_error_message, auto_send_started
    
    # Reload lại biến môi trường để lấy Cookie/IMEI mới nhất nếu được chỉnh sửa từ giao diện Web
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    cookie_val = os.getenv("COOKIE", "").strip()
    imei_val = os.getenv("IMEI", "").strip()
    phone_val = os.getenv("PHONE_NUMBER", "").strip()
    pass_val = os.getenv("PASSWORD", "").strip()
    
    if not cookie_val or cookie_val == "YOUR_COOKIE_HERE" or not imei_val or imei_val == "YOUR_IMEI_HERE":
        bot_status = "DISCONNECTED"
        bot_error_message = "Vui lòng nhập COOKIE và IMEI để bắt đầu kết nối Zalo."
        return

    bot_status = "CONNECTING"
    bot_error_message = ""
    print("🚀 Bắt đầu luồng kết nối Zalo Bot cá nhân...")
    
    try:
        cookies_dict = parse_cookie_string(cookie_val)
        
        # Khởi tạo instance Bot
        bot_instance = PersonalZaloBot(
            phone=phone_val if phone_val != "YOUR_PHONE_NUMBER_HERE" else "",
            password=pass_val if pass_val != "YOUR_PASSWORD_HERE" else "",
            imei=imei_val,
            cookies=cookies_dict
        )
        
        bot_status = "CONNECTED"
        # Kiểm tra xem uid là hàm hay là thuộc tính
        uid_str = bot_instance.uid() if callable(bot_instance.uid) else bot_instance.uid
        print(f"🔑 Đăng nhập thành công tài khoản UID: {uid_str}")

        # Tải và lưu danh sách nhóm hiện tại để nhận dạng nhóm mới sau này
        try:
            groups = bot_instance.fetchAllGroups()
            bot_instance.existing_groups = set(groups.gridVerMap.keys()) if (groups and hasattr(groups, 'gridVerMap')) else set()
            print(f"📦 Đã nhận diện {len(bot_instance.existing_groups)} nhóm chat hiện tại.")
        except Exception as e:
            print(f"⚠️ Không thể quét danh sách nhóm ban đầu: {e}")
            bot_instance.existing_groups = set()

        # Đồng bộ nhóm từ file groups.txt
        txt_groups = load_groups_from_txt()
        if txt_groups:
            updated = False
            for g_id in txt_groups:
                if g_id not in bot_instance.state["auto_send_groups"]:
                    bot_instance.state["auto_send_groups"].append(g_id)
                    updated = True
            if updated:
                save_state(bot_instance.state)
            print(f"📁 Đã đồng bộ {len(txt_groups)} ID nhóm từ groups.txt")
        
        # Khởi chạy luồng chạy nền gửi tin định kỳ
        if not auto_send_started:
            worker = threading.Thread(target=auto_send_thread_worker, daemon=True)
            worker.start()
            auto_send_started = True
            
        print("✨ Zalo Bot đã sẵn sàng! Đang lắng nghe tin nhắn mới để tự động phản hồi 24/24...")
        bot_instance.listen()
        
    except Exception as e:
        bot_status = "ERROR"
        bot_error_message = str(e)
        bot_instance = None
        print(f"❌ Lỗi kết nối Zalo: {e}")


def write_env_file(cookie, imei, phone="", password=""):
    """Ghi đè lại file .env với thông tin cấu hình mới"""
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write("# Cấu hình tài khoản Zalo cá nhân\n")
            f.write(f"PHONE_NUMBER={phone}\n")
            f.write(f"PASSWORD={password}\n")
            f.write(f"IMEI={imei}\n")
            f.write(f"COOKIE={cookie}\n\n")
            f.write("# API Key của Gemini AI\n")
            f.write(f"GEMINI_API_KEY={GEMINI_API_KEY or ''}\n")
        return True
    except Exception as e:
        print(f"❌ Lỗi ghi file .env: {e}")
        return False

# =====================================================================
# CÁC ROUTE CỦA FLASK WEB DASHBOARD
# =====================================================================

@app.route("/")
def dashboard():
    """Trang giao diện Web Control Panel"""
    # Đọc cấu hình hiện tại trong file .env
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    env_phone = os.getenv("PHONE_NUMBER", "")
    env_password = os.getenv("PASSWORD", "")
    env_imei = os.getenv("IMEI", "")
    env_cookie = os.getenv("COOKIE", "")
    
    # Lấy danh sách ID nhóm từ file groups.txt để hiển thị
    group_list_txt = ""
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                group_list_txt = f.read()
        except:
            pass
            
    # Load state hiện tại của bot
    state = load_state()
    
    return render_template(
        "index.html",
        status=bot_status,
        error_msg=bot_error_message,
        state=state,
        group_list_txt=group_list_txt,
        env_phone=env_phone,
        env_password=env_password,
        env_imei=env_imei,
        env_cookie=env_cookie
    )

cached_groups = []

@app.route("/api/get_all_joined_groups", methods=["GET"])
def get_all_joined_groups():
    """Lấy danh sách tất cả các nhóm chat mà bot đang tham gia cùng với tên nhóm, hỗ trợ cache"""
    global bot_instance, bot_status, cached_groups
    
    force_rescan = request.args.get("force_rescan", "false").lower() == "true"
    
    if not bot_instance or bot_status != "CONNECTED":
        return jsonify({"success": False, "message": "Bot chưa kết nối Zalo. Hãy khởi động kết nối Bot trước!"})
        
    if cached_groups and not force_rescan:
        return jsonify({"success": True, "groups": cached_groups})
        
    try:
        groups_res = bot_instance.fetchAllGroups()
        if not groups_res or not hasattr(groups_res, 'gridVerMap'):
            cached_groups = []
            return jsonify({"success": True, "groups": []})
            
        group_ids = list(groups_res.gridVerMap.keys())
        result = []
        
        # Quét tên các nhóm
        for g_id in group_ids:
            group_name = "Không xác định"
            try:
                info = bot_instance.fetchGroupInfo(g_id)
                if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                    group_name = info.gridInfoMap[g_id].get("name") or "Không tên"
            except:
                pass
            result.append({"id": g_id, "name": group_name})
            
        cached_groups = result
        return jsonify({"success": True, "groups": result})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi lấy danh sách nhóm Zalo: {e}"})

@app.route("/api/toggle", methods=["POST"])
def toggle_feature():
    """API bật/tắt tự động trả lời hoặc gửi tin nhắn nhóm"""
    data = request.json
    feature = data.get("feature")
    state = load_state()
    
    if feature == "reply":
        state["auto_reply_enabled"] = not state.get("auto_reply_enabled", True)
        save_state(state)
        # Đồng bộ với instance đang chạy nếu có
        if bot_instance:
            bot_instance.state["auto_reply_enabled"] = state["auto_reply_enabled"]
        return jsonify({
            "success": True, 
            "enabled": state["auto_reply_enabled"], 
            "message": f"Đã {'BẬT' if state['auto_reply_enabled'] else 'TẮT'} tự động trả lời!"
        })
        
    elif feature == "autosend":
        state["auto_send_enabled"] = not state.get("auto_send_enabled", False)
        save_state(state)
        # Đồng bộ với instance đang chạy nếu có
        if bot_instance:
            bot_instance.state["auto_send_enabled"] = state["auto_send_enabled"]
        return jsonify({
            "success": True, 
            "enabled": state["auto_send_enabled"], 
            "message": f"Đã {'BẬT' if state['auto_send_enabled'] else 'TẮT'} rải tin nhóm định kỳ!"
        })
        
    elif feature == "random_delay":
        state["random_delay_enabled"] = not state.get("random_delay_enabled", True)
        save_state(state)
        # Đồng bộ với instance đang chạy nếu có
        if bot_instance:
            bot_instance.state["random_delay_enabled"] = state["random_delay_enabled"]
        return jsonify({
            "success": True, 
            "enabled": state["random_delay_enabled"], 
            "message": f"Đã {'BẬT' if state['random_delay_enabled'] else 'TẮT'} giãn cách ngẫu nhiên (10p - 15p)!"
        })
        
    return jsonify({"success": False, "message": "Yêu cầu không hợp lệ."})

@app.route("/api/update_config", methods=["POST"])
def update_config():
    """API cập nhật nội dung tin nhắn và thời gian chu kỳ"""
    global trigger_send_now
    data = request.json
    state = load_state()
    
    state["auto_send_interval"] = int(data.get("interval", 1800))
    state["delay_between_groups"] = int(data.get("delay_between_groups", 30))
    state["auto_send_message"] = data.get("message", "")
    save_state(state)
    
    # Đồng bộ với instance đang chạy
    if bot_instance:
        bot_instance.state["auto_send_interval"] = state["auto_send_interval"]
        bot_instance.state["delay_between_groups"] = state["delay_between_groups"]
        bot_instance.state["auto_send_message"] = state["auto_send_message"]
        
    trigger_send_now = True
    return jsonify({"success": True})

@app.route("/api/update_groups", methods=["POST"])
def update_groups():
    """API cập nhật trực tiếp file groups.txt và đồng bộ danh sách nhóm của bot"""
    global trigger_send_now
    data = request.json
    groups_txt = data.get("groups", "")
    
    # Lưu vào file groups.txt
    try:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            f.write(groups_txt)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
        
    # Phân tích danh sách ID nhóm để cập nhật vào state JSON
    groups = []
    for line in groups_txt.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            groups.append(line)
            
    state = load_state()
    state["auto_send_groups"] = groups
    save_state(state)
    
    # Đồng bộ với instance đang chạy
    if bot_instance:
        bot_instance.state["auto_send_groups"] = groups
        
    trigger_send_now = True
    return jsonify({"success": True})

@app.route("/api/update_env", methods=["POST"])
def update_env():
    """API cập nhật các giá trị trong tệp .env"""
    data = request.json
    cookie = data.get("cookie", "").strip()
    imei = data.get("imei", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    
    success = write_env_file(cookie, imei, phone, password)
    return jsonify({"success": success})

@app.route("/api/control", methods=["POST"])
def control_bot():
    """API khởi chạy hoặc dừng kết nối Zalo Bot"""
    global bot_instance, bot_status, bot_thread
    data = request.json
    action = data.get("action")
    
    if action == "start":
        # Dừng bot cũ nếu đang chạy
        if bot_instance:
            try:
                bot_instance.ws.close()
            except:
                pass
            time.sleep(1)
            
        # Chạy kết nối bot trong một luồng mới
        bot_thread = threading.Thread(target=bot_connection_worker, daemon=True)
        bot_thread.start()
        return jsonify({"success": True, "message": "Đang tiến hành kết nối lại Zalo..."})
        
    elif action == "stop":
        if bot_instance:
            try:
                bot_instance.ws.close()
            except:
                pass
            bot_status = "DISCONNECTED"
            bot_instance = None
            return jsonify({"success": True, "message": "Đã ngắt kết nối Zalo Bot!"})
        else:
            return jsonify({"success": True, "message": "Bot chưa kết nối."})
            
    return jsonify({"success": False, "message": "Hành động không hợp lệ."})


def run_flask_dashboard():
    """Khởi chạy máy chủ Web Flask ở chế độ không debug"""
    # Mở port 5000 cho phép truy cập từ tất cả các địa chỉ IP của VPS
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


def main():
    global bot_thread
    
    print("\n" + "="*50)
    print("🤖 HỆ THỐNG ZALO BOT CÁ NHÂN & WEB DASHBOARD")
    print("="*50)
    print("👉 Mở trình duyệt và truy cập: http://localhost:5000")
    print("👉 Nếu chạy trên VPS, truy cập: http://<IP_VPS>:5000")
    print("="*50 + "\n")
    
    # 1. Khởi chạy giao diện Web Dashboard trên luồng riêng
    flask_thread = threading.Thread(target=run_flask_dashboard, daemon=True)
    flask_thread.start()
    
    # 2. Tự động thử kết nối Zalo Bot trên luồng riêng khi khởi động
    bot_thread = threading.Thread(target=bot_connection_worker, daemon=True)
    bot_thread.start()
    
    # Giữ luồng chính hoạt động
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Đang đóng hệ thống Zalo Bot...")
        if bot_instance:
            try:
                bot_instance.ws.close()
            except:
                pass

if __name__ == "__main__":
    main()
