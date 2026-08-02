import os
import time
import random
import threading
from datetime import datetime, timezone, timedelta
import google.generativeai as genai

import shared
from state_manager import load_state, save_state, save_groups_to_txt
from zlapi import ZaloAPI
from zlapi.models import Message, ThreadType

# Khởi động Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
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
    """Gửi thông báo tin nhắn mới qua Telegram"""
    import requests
    token = shared.TELEGRAM_BOT_TOKEN
    state = load_state()
    chat_id = state.get("telegram_admin_chat_id")
    if not chat_id:
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        
    if token and chat_id and token != "YOUR_TELEGRAM_BOT_TOKEN_HERE" and str(chat_id) != "YOUR_TELEGRAM_CHAT_ID_HERE":
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
        
        if author_id == my_uid:
            if message and isinstance(message, str) and message.strip().startswith("."):
                pass
            else:
                timestamps = self.state.get("last_reply_timestamps", {})
                timestamps[thread_id] = time.time()
                self.state["last_reply_timestamps"] = timestamps
                save_state(self.state)
                return

        if thread_type == ThreadType.GROUP:
            if hasattr(self, 'existing_groups') and thread_id not in self.existing_groups:
                self.existing_groups.add(thread_id)
                
                # 1. Lấy thông tin tên nhóm
                group_name = "Không xác định"
                try:
                    info = self.fetchGroupInfo(thread_id)
                    if info and hasattr(info, 'gridInfoMap') and thread_id in info.gridInfoMap:
                        group_name = info.gridInfoMap[thread_id].get("name") or "Không tên"
                except:
                    pass
                
                # 2. Cập nhật groups.txt
                try:
                    state = load_state()
                    blacklist = state.get("blacklisted_groups", [])
                    groups_res = self.fetchAllGroups()
                    if groups_res and hasattr(groups_res, 'gridVerMap'):
                        all_ids = list(groups_res.gridVerMap.keys())
                        active_groups = [gid for gid in all_ids if gid not in blacklist]
                        save_groups_to_txt(active_groups)
                except:
                    pass
                    
                print(f"🆕 [TỰ ĐỘNG] Phát hiện nhóm mới gia nhập: {group_name} (ID: {thread_id}).")
                
                # 3. Gửi tin nhắn xác nhận cho Admin Telegram
                try:
                    state = load_state()
                    chat_id = state.get("telegram_admin_chat_id")
                    if chat_id and shared.tb:
                        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                        markup = InlineKeyboardMarkup(row_width=2)
                        btn_rai = InlineKeyboardButton("📢 Rải", callback_data=f"newg_rai_{thread_id}")
                        btn_khong = InlineKeyboardButton("❌ Không Rải", callback_data=f"newg_skip_{thread_id}")
                        markup.row(btn_rai, btn_khong)
                        
                        # Escape tên nhóm tránh lỗi parse Markdown
                        from telegram_controller import escape_markdown
                        escaped_name = escape_markdown(group_name)
                        
                        msg_text = (
                            f"🔔 **PHÁT HIỆN NHÓM MỚI GIA NHẬP!**\n\n"
                            f"📌 Tên nhóm: **{escaped_name}**\n"
                            f"🆔 ID nhóm: `{thread_id}`\n\n"
                            f"Bạn có muốn rải tin nhắn vào nhóm mới này không?"
                        )
                        shared.tb.send_message(chat_id, msg_text, parse_mode="Markdown", reply_markup=markup)
                except Exception as ex:
                    print(f"⚠️ Lỗi gửi thông báo Telegram nhóm mới: {ex}")

        if message and isinstance(message, str) and message.strip().startswith("."):
            if author_id == my_uid:
                self.handle_command(message.strip(), thread_id, thread_type)
            return

        if message and isinstance(message, str) and message.strip().startswith("..."):
            return

        if self.state.get("auto_reply_enabled", True) and thread_type == ThreadType.USER:
            # Chờ 3 giây trước khi rep 1-1
            time.sleep(3)
            
            # Cú pháp kiểm tra tin nhắn gần nhất
            timestamps = self.state.get("last_reply_timestamps", {})
            last_reply = timestamps.get(thread_id, 0)
            if time.time() - last_reply < 60:
                return

            reply_text = ""
            if use_gemini and ai_model:
                try:
                    prompt = (
                        f"Bạn là trợ lý Zalo trả lời tin nhắn bán hàng/giao dịch tự động. "
                        f"Nhận tin nhắn: '{message}'. Hãy trả lời một cách lịch sự, tự nhiên, ngắn gọn bằng tiếng Việt."
                    )
                    response = ai_model.generate_content(prompt)
                    reply_text = response.text.strip()
                except Exception as e:
                    print(f"❌ Lỗi gọi Gemini AI: {e}")
                    
            if not reply_text:
                reply_text = "Dạ, em chào anh/chị ạ! Hiện tại em đang bận một chút. Anh/chị cần hỗ trợ gì cứ nhắn tin, em sẽ trả lời ngay khi online nhé! Xin cảm ơn."

            try:
                self.replyMessage(Message(text=reply_text), message_object, thread_id, thread_type)
                print(f"📤 Đã gửi phản hồi tự động đến {thread_id}")
                timestamps[thread_id] = time.time()
                self.state["last_reply_timestamps"] = timestamps
                save_state(self.state)
            except Exception as e:
                print(f"❌ Lỗi gửi tin nhắn phản hồi: {e}")

        # Gửi thông báo đến Telegram
        if thread_type == ThreadType.USER:
            sender_name = "Người dùng ẩn danh"
            try:
                info = self.fetchUserInfo(author_id)
                profiles = getattr(info, "changed_profiles", {}) or {}
                user_info = profiles.get(str(author_id)) or profiles.get(int(author_id))
                if user_info:
                    sender_name = user_info.get("displayName") or user_info.get("zaloName") or sender_name
            except Exception as e:
                print(f"⚠️ Lỗi fetchUserInfo: {e}")
            notify_text = f"📩 [ZALO] Tin nhắn mới từ {sender_name} (ID: {author_id}):\n{message}"
            send_telegram_notification(notify_text)

    def handle_command(self, text, thread_id, thread_type):
        cmd_parts = text[1:].split(" ", 1)
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
        print(f"🛠️ Thực thi lệnh: {cmd} {args}")
        
        if cmd == "help":
            help_msg = (
                "🤖 HƯỚNG DẪN CÁC LỆNH ĐIỀU KHIỂN ZALO:\n\n"
                ".help - Xem danh sách lệnh\n"
                ".gdtg <sđt> - Gửi danh thiếp nhanh cho số điện thoại này vào nhóm"
            )
            self.send(Message(text=help_msg), thread_id, thread_type)
            
        elif cmd == "gdtg":
            if not args:
                self.send(Message(text="⚠️ Cú pháp: .gdtg <số điện thoại>"), thread_id, thread_type)
                return
                
            phone = args.strip()
            self.send(Message(text=f"🔍 Đang tìm danh thiếp cho SĐT {phone}..."), thread_id, thread_type)
            
            uid, qr = search_user_by_phone(self, phone)
            if uid and qr:
                try:
                    self.sendBusinessCard(uid, qr, thread_id, thread_type, phone=phone)
                    self.send(Message(text=f"✅ Đã gửi danh thiếp cho SĐT {phone}!"), thread_id, thread_type)
                except Exception as e:
                    self.send(Message(text=f"❌ Lỗi khi gửi danh thiếp: {e}"), thread_id, thread_type)
            else:
                self.send(Message(text=f"⚠️ Không tìm thấy người dùng Zalo nào có SĐT: {phone}"), thread_id, thread_type)

def search_user_by_phone(bot, phone_number):
    """Tìm kiếm UID và QR Code của một SĐT trên Zalo"""
    try:
        res = bot.searchPhone(phone_number)
        if res and hasattr(res, 'uid') and res.uid:
            return str(res.uid), getattr(res, 'qrCodeUrl', '')
    except Exception as e:
        print(f"⚠️ Lỗi khi tìm kiếm số điện thoại {phone_number}: {e}")
    return None, None

def auto_send_messages_worker():
    """Luồng gửi tin nhắn rải định kỳ chạy ngầm"""
    print("🚀 Bắt đầu luồng kiểm tra gửi tin nhắn định kỳ...")
    
    msg_idx = 0
    consecutive_errors = 0
    
    while True:
        try:
            state = load_state()
            is_enabled = state.get("auto_send_enabled", False)
            messages = state.get("auto_send_messages", [])
            global_interval = state.get("auto_send_interval", 900)
            
            if not is_enabled or not messages or shared.bot_instance is None or shared.bot_status != "CONNECTED":
                time.sleep(5)
                continue
                
            # Lấy toàn bộ danh sách nhóm chat đang tham gia trực tiếp từ Zalo
            try:
                groups_res = shared.bot_instance.fetchAllGroups()
                if groups_res and hasattr(groups_res, 'gridVerMap'):
                    all_joined_groups = list(groups_res.gridVerMap.keys())
                else:
                    all_joined_groups = []
            except Exception as e:
                print(f"⚠️ Không thể lấy danh sách nhóm từ Zalo: {e}")
                time.sleep(10)
                continue
                
            # Lọc bỏ nhóm trong danh sách đen (Không rải)
            blacklist = state.get("blacklisted_groups", [])
            groups = [g_id for g_id in all_joined_groups if g_id not in blacklist]
            
            # Ghi danh sách nhóm thực tế rải ra groups.txt để admin xem
            save_groups_to_txt(groups)
            
            if not groups:
                print("ℹ️ Không có nhóm nào để rải (Tất cả đều nằm trong danh sách đen bị chặn).")
                time.sleep(10)
                continue
                
            print(f"📢 Bắt đầu chu kỳ rải tin đến {len(groups)} nhóm...")
            
            # Đảm bảo chỉ gửi 1 tin nhắn xoay vòng cho mỗi đợt
            active_message = messages[msg_idx]
            print(f"🔄 Xoay vòng tin nhắn: Đang gửi tin quảng cáo số {msg_idx + 1}/{len(messages)}...")
            
            for idx, group_id in enumerate(groups):
                # 1. Kiểm tra dừng đột ngột
                state = load_state()
                if not state.get("auto_send_enabled", False) or shared.bot_instance is None or shared.bot_status != "CONNECTED":
                    print("🛑 Dừng chu kỳ rải tin do tắt tính năng hoặc bot đã dừng.")
                    break
                    
                # 2. Kiểm tra danh sách chặn thay đổi
                current_blacklist = state.get("blacklisted_groups", [])
                if blacklist != current_blacklist:
                    print("🔄 Danh sách đen (chặn nhóm) thay đổi. Khởi động lại chu kỳ gửi để cập nhật...")
                    break
                    
                group_name = "Nhóm Zalo"
                try:
                    group_info = shared.bot_instance.fetchGroupInfo(group_id)
                    if group_info and hasattr(group_info, 'gridInfoMap') and group_id in group_info.gridInfoMap:
                        group_name = group_info.gridInfoMap[group_id].get("name") or "Không tên"
                except Exception as e:
                    print(f"⚠️ Bỏ qua rải tin ID nhóm {group_id}: {e}")
                    continue
                # 3. Kiểm tra cấm rải vĩnh viễn (Nhóm học tập, hỗ trợ btool...)
                from shared import is_permanently_blocked
                if is_permanently_blocked(group_name):
                    print(f"🚫 [BẢO VỆ] Phát hiện nhóm '{group_name}' nằm trong danh sách CẤM RẢI VĨNH VIỄN. Bỏ qua.")
                    continue    
                print(f"👉 [{idx + 1}/{len(groups)}] Gửi tin đến nhóm: {group_name} (ID: {group_id})")
                
                try:
                    # Gửi tin nhắn chính
                    shared.bot_instance.send(Message(text=active_message), group_id, ThreadType.GROUP)
                    print(f"✅ Gửi thành công đến nhóm: {group_name} (ID: {group_id})")
                    consecutive_errors = 0
                    
                    # Nếu tin nhắn có từ 'gdtg' + SĐT, tự động quét và gửi kèm danh thiếp
                    import re
                    phone_match = re.search(r'gdtg.*?(0\d{9})', active_message.lower())
                    if phone_match:
                        target_phone = phone_match.group(1)
                        print(f"🎴 Phát hiện tin nhắn GDTG chứa SĐT {target_phone}. Đang lấy danh thiếp...")
                        
                        time.sleep(1.5)
                        uid, qr = search_user_by_phone(shared.bot_instance, target_phone)
                        if uid and qr:
                            try:
                                shared.bot_instance.sendBusinessCard(uid, qr, group_id, ThreadType.GROUP, phone=target_phone)
                                print(f"✅ Đã gửi kèm danh thiếp cho SĐT {target_phone} vào nhóm {group_name}!")
                            except Exception as card_err:
                                print(f"⚠️ Lỗi gửi danh thiếp: {card_err}")
                        else:
                            print(f"⚠️ Không tìm thấy UID của {target_phone}. Bỏ qua gửi danh thiếp.")
                except Exception as e:
                    print(f"❌ Lỗi khi gửi đến nhóm {group_name} ({group_id}): {e}. Bỏ qua nhóm này.")
                        
                # Giãn cách giữa các nhóm
                delay_between = state.get("delay_between_groups", 30)
                time.sleep(delay_between)
                
            # Đổi sang tin nhắn tiếp theo cho đợt rải sau
            msg_idx = (msg_idx + 1) % len(messages)
            
            print(f"🎉 Đã rải hết các nhóm. Chờ {global_interval} giây trước khi bắt đầu chu kỳ tiếp theo...")
            
            # Giữ thời gian chờ cho đến chu kỳ tiếp theo
            start_wait = time.time()
            shared.trigger_send_now = False
            
            while time.time() - start_wait < global_interval:
                if shared.trigger_send_now:
                    print("⚡ Phát hiện tín hiệu kích hoạt gửi ngay lập tức! Bỏ qua thời gian chờ.")
                    break
                state = load_state()
                if not state.get("auto_send_enabled", False):
                    break
                time.sleep(1)
                
        except Exception as e:
            print(f"❌ Lỗi trong luồng chạy nền tự động gửi: {e}")
            time.sleep(10)

def parse_cookie_string(cookie_str):
    """Phân tích chuỗi Cookie Zalo thành một dict"""
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
        print(f"❌ Lỗi phân tích Cookie: {e}")
    return cookies

def bot_connection_worker():
    """Luồng thiết lập và quản lý kết nối Zalo Bot chạy ngầm"""
    from config import PHONE_NUMBER, PASSWORD, IMEI, COOKIE
    
    print("🚀 Bắt đầu luồng kết nối Zalo Bot cá nhân...")
    
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Đặt giá trị mặc định cho SDT và Password nếu người dùng chọn bỏ qua và dùng cookie
        phone_val = os.getenv("PHONE_NUMBER", PHONE_NUMBER)
        phone_val = phone_val if phone_val and phone_val != "YOUR_PHONE_NUMBER_HERE" else ""
        
        pass_val = os.getenv("PASSWORD", PASSWORD)
        pass_val = pass_val if pass_val and pass_val != "YOUR_PASSWORD_HERE" else ""
        
        env_imei = os.getenv("IMEI", IMEI)
        env_cookie = os.getenv("COOKIE", COOKIE)
        
        shared.bot_status = "CONNECTING"
        shared.bot_error_message = ""
        
        # Phân tích Cookie
        cookies_dict = parse_cookie_string(env_cookie)
        
        # Khởi tạo instance kết nối ZaloAPI
        bot = PersonalZaloBot(
            phone=phone_val,
            password=pass_val,
            imei=env_imei,
            cookies=cookies_dict
        )
        
        shared.bot_instance = bot
        uid_str = str(bot.uid() if callable(bot.uid) else bot.uid)
        print(f"🔑 Đăng nhập thành công tài khoản UID: {uid_str}")
        
        shared.bot_status = "CONNECTED"
        shared.bot_error_message = ""
        
        # Tải trước danh sách các nhóm hiện có để tránh báo sai "nhóm mới gia nhập" khi tin nhắn đến
        try:
            groups_res = bot.fetchAllGroups()
            if groups_res and hasattr(groups_res, 'gridVerMap'):
                bot.existing_groups = set(groups_res.gridVerMap.keys())
                print(f"👥 Đã tải trước {len(bot.existing_groups)} nhóm Zalo hiện có vào bộ nhớ.")
        except Exception as ge:
            print(f"⚠️ Lỗi tải trước danh sách nhóm: {ge}")
        
        # Khởi chạy luồng gửi tin tự động định kỳ một lần duy nhất
        if not shared.auto_send_started:
            send_thread = threading.Thread(target=auto_send_messages_worker, daemon=True)
            send_thread.start()
            shared.auto_send_started = True
            
        bot.listen()
        
    except Exception as e:
        shared.bot_status = "ERROR"
        shared.bot_error_message = str(e)
        shared.bot_instance = None
        print(f"❌ Lỗi kết nối Zalo: {e}")
