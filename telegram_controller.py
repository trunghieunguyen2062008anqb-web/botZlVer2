import os
import time
import threading

import shared
from state_manager import load_state, save_state, save_groups_to_txt
from zalo_client import bot_connection_worker

# Escape ký tự Markdown đặc biệt
def escape_markdown(text):
    if not text:
        return ""
    for char in ['*', '_', '`', '[']:
        text = text.replace(char, f'\\{char}')
    return text

# Các phím điều khiển
def get_main_menu_keyboard(state):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=2)
    
    btn_start = InlineKeyboardButton("🔄 Khởi Động Bot", callback_data="bot_restart")
    btn_stop = InlineKeyboardButton("🛑 Dừng Bot", callback_data="bot_stop")
    markup.row(btn_start, btn_stop)
    
    reply_status = "🟢 Rep 1-1: BẬT" if state.get("auto_reply_enabled") else "🔴 Rep 1-1: TẮT"
    btn_reply = InlineKeyboardButton(reply_status, callback_data="toggle_reply")
    
    send_status = "🟢 Rải Tin: BẬT" if state.get("auto_send_enabled") else "🔴 Rải Tin: TẮT"
    btn_send = InlineKeyboardButton(send_status, callback_data="toggle_send")
    markup.row(btn_reply, btn_send)
    
    delay_status = "🟢 Giãn Cách: BẬT" if state.get("random_delay_enabled") else "🔴 Giãn Cách: TẮT"
    btn_delay = InlineKeyboardButton(delay_status, callback_data="toggle_delay")
    markup.row(btn_delay)
    
    btn_edit = InlineKeyboardButton("📝 Thay Đổi Nội Dung", callback_data="menu_edit_msg")
    btn_groups = InlineKeyboardButton("👥 Quét & Chọn Nhóm", callback_data="menu_scan_groups")
    markup.row(btn_edit, btn_groups)
    
    btn_new_groups = InlineKeyboardButton("🔍 Quét Nhóm (Join Sau)", callback_data="menu_scan_new_groups")
    btn_clear_groups = InlineKeyboardButton("🗑️ Xóa Tất Cả Nhóm", callback_data="menu_clear_groups")
    markup.row(btn_new_groups, btn_clear_groups)
    
    btn_time = InlineKeyboardButton("⏱️ Cấu Hinh Thời Gian", callback_data="menu_edit_time")
    btn_status = InlineKeyboardButton("🔍 Xem Trạng Thái Chi Tiết", callback_data="bot_status")
    markup.row(btn_time, btn_status)
    
    return markup

def get_groups_page_keyboard(chat_id, page_idx):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup()
    
    cache = shared.groups_page_cache.get(chat_id, {})
    groups = cache.get("groups", [])
    if not groups:
        markup.add(InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="back_to_menu"))
        return markup
        
    total_pages = (len(groups) + 9) // 10
    start = page_idx * 10
    end = min(start + 10, len(groups))
    
    state = load_state()
    blacklist = state.get("blacklisted_groups", [])
    
    # Tạo các nút tương tác cho 10 nhóm trên trang hiện tại
    buttons = []
    for i in range(start, end):
        g_id = groups[i]["id"]
        g_name = groups[i]["name"]
        
        # Số thứ tự trong trang: 1 đến 10
        local_idx = i - start + 1
        
        from shared import is_permanently_blocked
        if is_permanently_blocked(g_name):
            btn_text = f"{local_idx}. 🔒"
        else:
            is_blacklisted = g_id in blacklist
            emoji = "🔴" if is_blacklisted else "🟢"
            btn_text = f"{local_idx}. {emoji}"
            
        buttons.append(InlineKeyboardButton(btn_text, callback_data=f"tgl_grp_{page_idx}_{i}"))
        
    # Sắp xếp nút thành hàng tối đa 5 nút
    row_width = 5
    for idx in range(0, len(buttons), row_width):
        markup.row(*buttons[idx : idx + row_width])
        
    # Hàng điều hướng trang
    nav_buttons = []
    if page_idx > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"page_grp_{page_idx-1}"))
    nav_buttons.append(InlineKeyboardButton(f"Trang {page_idx + 1}/{total_pages}", callback_data="page_grp_info"))
    if page_idx < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Sau ➡️", callback_data=f"page_grp_{page_idx+1}"))
        
    markup.row(*nav_buttons)
    markup.add(InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="back_to_menu"))
    return markup

def get_groups_page_text(chat_id, page_idx):
    cache = shared.groups_page_cache.get(chat_id, {})
    groups = cache.get("groups", [])
    if not groups:
        return "⚠️ Không tìm thấy thông tin nhóm."
        
    total_pages = (len(groups) + 9) // 10
    start = page_idx * 10
    end = min(start + 10, len(groups))
    
    state = load_state()
    blacklist = state.get("blacklisted_groups", [])
    
    text_lines = [
        f"👥 **BỘ LỌC NHÓM CHAT ZALO (Trang {page_idx + 1}/{total_pages})**\n",
        "👉 Bấm số tương ứng phía dưới để Bật/Tắt trạng thái rải tin nhắn cho nhóm đó:\n"
    ]
    
    for idx, i in enumerate(range(start, end), 1):
        g = groups[i]
        g_id = g["id"]
        g_name = g["name"]
        
        from shared import is_permanently_blocked
        if is_permanently_blocked(g_name):
            status_str = "🔴 CẤM RẢI VĨNH VIỄN"
        else:
            is_blacklisted = g_id in blacklist
            status_str = "🔴 KHÔNG RẢI" if is_blacklisted else "🟢 ĐANG RẢI TIN"
            
        escaped_name = escape_markdown(g_name)
        text_lines.append(f"**{idx}.** {escaped_name} — {status_str}")
        
    return "\n".join(text_lines)

def get_time_settings_keyboard(state):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(row_width=3)
    
    # Hàng 1: Chu kỳ rải tin nhắn
    btn_int_dec = InlineKeyboardButton("➖ 5 phút", callback_data="settime_int_-5")
    btn_int_val = InlineKeyboardButton(f"⏱️ Rải: {state.get('auto_send_interval', 900) // 60}p", callback_data="settime_int_info")
    btn_int_inc = InlineKeyboardButton("➕ 5 phút", callback_data="settime_int_+5")
    markup.row(btn_int_dec, btn_int_val, btn_int_inc)
    
    # Hàng 2: Giãn cách giữa các nhóm
    btn_del_dec = InlineKeyboardButton("➖ 5 giây", callback_data="settime_del_-5")
    btn_del_val = InlineKeyboardButton(f"⏱️ Giãn cách: {state.get('delay_between_groups', 30)}s", callback_data="settime_del_info")
    btn_del_inc = InlineKeyboardButton("➕ 5 giây", callback_data="settime_del_+5")
    markup.row(btn_del_dec, btn_del_val, btn_del_inc)
    
    # Hàng 3: Quay lại
    markup.add(InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="back_to_menu"))
    return markup

def check_is_admin(chat_id):
    """Kiểm tra quyền truy cập Admin độc quyền của Telegram chat_id"""
    state = load_state()
    admin_id = state.get("telegram_admin_chat_id")
    
    # Nếu chưa đăng ký admin nào, cho phép người đầu tiên sử dụng bot đăng ký làm admin
    if not admin_id:
        state["telegram_admin_chat_id"] = chat_id
        save_state(state)
        os.environ["TELEGRAM_CHAT_ID"] = str(chat_id)
        print(f"🔑 [HỆ THỐNG] Đã nhận diện và đăng ký Chat ID {chat_id} làm Admin độc quyền của Bot Zalo.")
        return True
        
    # Cho phép nếu trùng với ID admin đã đăng ký
    if str(admin_id) == str(chat_id):
        return True
        
    # Từ chối nếu là người lạ
    print(f"🔒 [BẢO MẬT] Từ chối truy cập từ Chat ID lạ: {chat_id}")
    try:
        shared.tb.send_message(chat_id, "🔒 Bảng điều khiển Zalo Bot này là cá nhân và đã bị khóa bảo mật.")
    except:
        pass
    return False

def init_telegram_handlers():
    tb = shared.tb
    if not tb:
        return
        
    # Thiết lập menu nút bấm 3 gạch (Bot Commands)
    from telebot.types import BotCommand
    commands = [
        BotCommand("start", "Khởi động & Mở Bảng điều khiển chính"),
        BotCommand("status", "Xem trạng thái hoạt động Zalo Bot"),
        BotCommand("restart", "Kết nối lại / Khởi động lại Zalo Bot"),
        BotCommand("stop", "Ngắt kết nối / Dừng Zalo Bot")
    ]
    try:
        tb.set_my_commands(commands)
        print("✅ Đã thiết lập menu nút bấm 3 gạch (Bot Commands) trên Telegram.")
    except Exception as e:
        print(f"⚠️ Không thể thiết lập Bot Commands: {e}")
        
    @tb.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
            
        print(f"💬 [TELEGRAM] Nhận lệnh /start hoặc /help từ Admin (Chat ID: {chat_id})")
        state = load_state()
        help_text = (
            "🤖 **HCS ZALO BOT - BẢNG ĐIỀU KHIỂN TELEGRAM** 🤖\n\n"
            "Chào mừng bạn! ID Chat của bạn đã được đăng ký làm Admin nhận thông báo.\n"
            "Hãy sử dụng các nút tương tác dưới đây để điều khiển Bot Zalo từ xa:"
        )
        tb.reply_to(message, help_text, reply_markup=get_main_menu_keyboard(state), parse_mode="Markdown")

    @tb.callback_query_handler(func=lambda call: True)
    def handle_callback_query(call):
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        if not check_is_admin(chat_id):
            return
            
        data = call.data
        
        # Ánh xạ tên hiển thị mô tả thao tác bấm nút ra terminal
        action_name = data
        if data == "bot_restart": action_name = "Khởi động Bot Zalo"
        elif data == "bot_stop": action_name = "Dừng Bot Zalo"
        elif data == "toggle_reply": action_name = "Bật/Tắt Tự động trả lời 1-1"
        elif data == "toggle_send": action_name = "Bật/Tắt Tự động rải tin nhóm"
        elif data == "toggle_delay": action_name = "Bật/Tắt Giãn cách ngẫu nhiên"
        elif data == "bot_status": action_name = "Xem Trạng thái Chi tiết"
        elif data == "menu_edit_msg": action_name = "Quản lý nội dung tin nhắn"
        elif data == "msg_add_new": action_name = "Thêm tin nhắn quảng cáo mới"
        elif data == "msg_clear_all": action_name = "Yêu cầu Xóa hết tin nhắn"
        elif data == "msg_clear_confirm": action_name = "Xác nhận Xóa sạch tin nhắn"
        elif data == "menu_scan_groups": action_name = "Quét danh sách nhóm Zalo"
        elif data == "menu_scan_new_groups": action_name = "Quét nhóm mới gia nhập (Join sau)"
        elif data == "menu_clear_groups": action_name = "Yêu cầu Xóa hết nhóm rải tin"
        elif data == "clear_groups_confirm": action_name = "Xác nhận Xóa sạch nhóm rải tin"
        elif data == "menu_edit_time": action_name = "Mở Cấu hình Thời gian chạy"
        elif data == "settime_int_info": action_name = "Xem thông tin chu kỳ rải"
        elif data == "settime_del_info": action_name = "Xem thông tin giãn cách nhóm"
        elif data.startswith("settime_int_"):
            change = data.replace("settime_int_", "")
            action_name = f"Điều chỉnh Chu kỳ đợt rải: {change} phút"
        elif data.startswith("settime_del_"):
            change = data.replace("settime_del_", "")
            action_name = f"Điều chỉnh Giãn cách nhóm: {change} giây"
        elif data == "back_to_menu": action_name = "Quay lại Menu chính"
        elif data.startswith("edit_msg_"): action_name = f"Chọn chỉnh sửa Tin số {int(data.split('_')[2]) + 1}"
        elif data.startswith("del_msg_"): action_name = f"Xóa Tin số {int(data.split('_')[2]) + 1}"
        elif data.startswith("page_grp_"):
            val = data.replace("page_grp_", "")
            action_name = f"Xem bộ lọc nhóm - Trang {int(val)+1}" if val != "info" else "Xem thông tin số lượng nhóm"
        elif data.startswith("tgl_grp_"):
            parts = data.split("_")
            action_name = f"Bật/Tắt rải nhóm (Index: {parts[3]}) tại Trang {int(parts[2])+1}"
        elif data.startswith("newg_rai_"): action_name = f"Bật rải tin cho nhóm mới phát hiện: {data.replace('newg_rai_', '')}"
        elif data.startswith("newg_skip_"): action_name = f"Bỏ qua rải tin cho nhóm mới phát hiện: {data.replace('newg_skip_', '')}"
        
        print(f"🔘 [TELEGRAM] Admin bấm nút: {action_name}")
        
        # 1. Điều khiển kết nối Bot Zalo
        if data == "bot_restart":
            tb.answer_callback_query(call.id, "🔄 Đang khởi động lại Bot Zalo...")
            tb.edit_message_text("🔄 Đang kết nối lại Zalo Bot, vui lòng đợi...", chat_id, message_id)
            
            if shared.bot_instance:
                try:
                    shared.bot_instance.ws.close()
                except:
                    pass
                shared.bot_instance = None
                
            shared.bot_status = "CONNECTING"
            shared.bot_error_message = ""
            shared.bot_thread = threading.Thread(target=bot_connection_worker, daemon=True)
            shared.bot_thread.start()
            
            time.sleep(1.5)
            state = load_state()
            tb.edit_message_text(
                f"🟢 Tiến trình kết nối đã khởi động.\nTrạng thái Zalo hiện tại: `{shared.bot_status}`\n\nBấm nút kiểm tra trạng thái sau vài giây để cập nhật kết quả!", 
                chat_id, 
                message_id, 
                reply_markup=get_main_menu_keyboard(state)
            )
            
        elif data == "bot_stop":
            tb.answer_callback_query(call.id, "🛑 Đang dừng Bot Zalo...")
            if shared.bot_instance:
                try:
                    shared.bot_instance.ws.close()
                except:
                    pass
                shared.bot_instance = None
                shared.bot_status = "DISCONNECTED"
                state = load_state()
                tb.edit_message_text("🛑 Đã ngắt kết nối và dừng Zalo Bot thành công!", chat_id, message_id, reply_markup=get_main_menu_keyboard(state))
            else:
                state = load_state()
                tb.edit_message_text("ℹ️ Zalo Bot hiện đang không kết nối.", chat_id, message_id, reply_markup=get_main_menu_keyboard(state))
                
        # 2. Bật tắt các tính năng chính của Bot
        elif data == "toggle_reply":
            state = load_state()
            state["auto_reply_enabled"] = not state.get("auto_reply_enabled", True)
            save_state(state)
            if shared.bot_instance:
                shared.bot_instance.state["auto_reply_enabled"] = state["auto_reply_enabled"]
            tb.answer_callback_query(call.id, f"Rep 1-1: {'BẬT' if state['auto_reply_enabled'] else 'TẮT'}")
            tb.edit_message_reply_markup(chat_id, message_id, reply_markup=get_main_menu_keyboard(state))
            
        elif data == "toggle_send":
            state = load_state()
            state["auto_send_enabled"] = not state.get("auto_send_enabled", False)
            save_state(state)
            if shared.bot_instance:
                shared.bot_instance.state["auto_send_enabled"] = state["auto_send_enabled"]
            tb.answer_callback_query(call.id, f"Rải tin nhóm: {'BẬT' if state['auto_send_enabled'] else 'TẮT'}")
            tb.edit_message_reply_markup(chat_id, message_id, reply_markup=get_main_menu_keyboard(state))
            
        elif data == "toggle_delay":
            state = load_state()
            state["random_delay_enabled"] = not state.get("random_delay_enabled", False)
            save_state(state)
            if shared.bot_instance:
                shared.bot_instance.state["random_delay_enabled"] = state["random_delay_enabled"]
            tb.answer_callback_query(call.id, f"Giãn cách: {'BẬT' if state['random_delay_enabled'] else 'TẮT'}")
            tb.edit_message_reply_markup(chat_id, message_id, reply_markup=get_main_menu_keyboard(state))
            
        # 3. Xem Trạng Thái Chi Tiết
        elif data == "bot_status":
            tb.answer_callback_query(call.id, "🔍 Đang lấy thông tin...")
            state = load_state()
            
            # Tính số lượng nhóm rải tin thực tế (tổng nhóm trừ đi nhóm bị chặn)
            active_count = 0
            if shared.bot_instance and shared.bot_status == "CONNECTED":
                try:
                    groups_res = shared.bot_instance.fetchAllGroups()
                    if groups_res and hasattr(groups_res, 'gridVerMap'):
                        all_ids = list(groups_res.gridVerMap.keys())
                        blacklist = state.get("blacklisted_groups", [])
                        active_count = len([gid for gid in all_ids if gid not in blacklist])
                except:
                    pass
            if active_count == 0 and os.path.exists("groups.txt"):
                try:
                    with open("groups.txt", "r", encoding="utf-8") as gf:
                        active_count = len([line.strip() for line in gf if line.strip() and not line.strip().startswith("#")])
                except:
                    pass
                    
            status_text = (
                f"🤖 **TRẠNG THÁI HOẠT ĐỘNG ZALO BOT:**\n\n"
                f"🔴 Kết nối Zalo: `{shared.bot_status}`\n"
                f"📢 Tự động rải tin: `{'BẬT' if state.get('auto_send_enabled') else 'TẮT'}`\n"
                f"💬 Tự động trả lời 1-1: `{'BẬT' if state.get('auto_reply_enabled') else 'TẮT'}`\n"
                f"⏱️ Chu kỳ đợt rải: `{state.get('auto_send_interval', 900) // 60} phút`\n"
                f"⏱️ Giãn cách các nhóm: `{state.get('delay_between_groups', 30)} giây`\n"
                f"🎲 Giãn cách ngẫu nhiên: `{'BẬT' if state.get('random_delay_enabled') else 'TẮT'}`\n"
                f"👥 Nhóm rải tin: `{active_count} nhóm`"
            )
            if shared.bot_error_message:
                status_text += f"\n\n⚠️ **Chi tiết lỗi:** `{shared.bot_error_message}`"
            tb.send_message(chat_id, status_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard(state))
            
        # 4. Thay đổi Nội dung rải tin
        elif data == "menu_edit_msg":
            tb.answer_callback_query(call.id)
            state = load_state()
            msgs = state.get("auto_send_messages", [])
            
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            
            # Xây dựng văn bản hiển thị các tin hiện có
            text_lines = ["📝 **DANH SÁCH TIN NHẮN QUẢNG CÁO HIỆN TẠI:**\n"]
            if not msgs:
                text_lines.append("ℹ️ *Trống (Chưa có tin nhắn nào)*")
            else:
                for idx, m in enumerate(msgs, 1):
                    # Trích xuất 40 ký tự đầu tiên để hiển thị rút gọn
                    summary = (m[:40] + '...') if len(m) > 40 else m
                    summary = summary.replace('\n', ' ')
                    text_lines.append(f"**{idx}.** {summary}")
                    
                    # Tạo hàng nút: [Sửa Tin X] và [Xóa]
                    btn_edit = InlineKeyboardButton(f"📝 Sửa Tin {idx}", callback_data=f"edit_msg_{idx-1}")
                    btn_del = InlineKeyboardButton("❌ Xóa", callback_data=f"del_msg_{idx-1}")
                    markup.row(btn_edit, btn_del)
                    
            text_lines.append("\nHãy chọn sửa một tin nhắn hoặc thêm tin mới:")
            
            btn_add = InlineKeyboardButton("➕ Thêm Tin Mới", callback_data="msg_add_new")
            btn_clear = InlineKeyboardButton("🗑️ Xóa Hết Tin", callback_data="msg_clear_all")
            markup.row(btn_add, btn_clear)
            
            markup.add(InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="back_to_menu"))
            
            tb.edit_message_text("\n".join(text_lines), chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
        elif data.startswith("edit_msg_"):
            idx = int(data.split("_")[2])
            tb.answer_callback_query(call.id)
            shared.user_sessions[chat_id] = {"action": "waiting_for_msg", "index": idx}
            
            state = load_state()
            msgs = state.get("auto_send_messages", [])
            current_val = msgs[idx] if idx < len(msgs) else ""
            
            text = (
                f"📝 Bạn đang chỉnh sửa **Tin {idx + 1}**.\n\n"
                f"📖 **Nội dung hiện tại:**\n`{current_val}`\n\n"
                f"👉 **Vui lòng nhập nội dung mới** và gửi trực tiếp vào đây (không cần gõ lệnh):"
            )
            
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Hủy chỉnh sửa", callback_data="menu_edit_msg"))
            tb.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
        elif data.startswith("del_msg_"):
            idx = int(data.split("_")[2])
            state = load_state()
            msgs = state.get("auto_send_messages", [])
            if 0 <= idx < len(msgs):
                removed_msg = msgs.pop(idx)
                # Cập nhật tin nhắn chính nếu xóa tin nhắn đầu tiên
                if idx == 0:
                    state["auto_send_message"] = msgs[0] if msgs else ""
                state["auto_send_messages"] = msgs
                save_state(state)
                if shared.bot_instance:
                    shared.bot_instance.state["auto_send_messages"] = msgs
                    shared.bot_instance.state["auto_send_message"] = state.get("auto_send_message", "")
                tb.answer_callback_query(call.id, f"🗑️ Đã xóa Tin {idx + 1}")
            
            # Tự động quay lại giao diện quản lý tin nhắn
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            text_lines = ["📝 **DANH SÁCH TIN NHẮN QUẢNG CÁO HIỆN TẠI:**\n"]
            if not msgs:
                text_lines.append("ℹ️ *Trống (Chưa có tin nhắn nào)*")
            else:
                for i, m in enumerate(msgs, 1):
                    summary = (m[:40] + '...') if len(m) > 40 else m
                    summary = summary.replace('\n', ' ')
                    text_lines.append(f"**{i}.** {summary}")
                    btn_edit = InlineKeyboardButton(f"📝 Sửa Tin {i}", callback_data=f"edit_msg_{i-1}")
                    btn_del = InlineKeyboardButton("❌ Xóa", callback_data=f"del_msg_{i-1}")
                    markup.row(btn_edit, btn_del)
                    
            text_lines.append("\nHãy chọn sửa một tin nhắn hoặc thêm tin mới:")
            btn_add = InlineKeyboardButton("➕ Thêm Tin Mới", callback_data="msg_add_new")
            btn_clear = InlineKeyboardButton("🗑️ Xóa Hết Tin", callback_data="msg_clear_all")
            markup.row(btn_add, btn_clear)
            markup.add(InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="back_to_menu"))
            tb.edit_message_text("\n".join(text_lines), chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
        elif data == "msg_clear_all":
            tb.answer_callback_query(call.id)
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(row_width=2)
            btn_yes = InlineKeyboardButton("🗑️ Có, Xóa Hết!", callback_data="msg_clear_confirm")
            btn_no = InlineKeyboardButton("❌ Hủy", callback_data="menu_edit_msg")
            markup.row(btn_yes, btn_no)
            
            warning_text = (
                "⚠️ **CẢNH BÁO XÓA TOÀN BỘ TIN NHẮN RẢI**\n\n"
                "Bạn có chắc chắn muốn xóa sạch toàn bộ danh sách tin nhắn rải không?\n"
                "Hành động này sẽ làm trống danh sách rải tin nhắn trên hệ thống."
            )
            tb.edit_message_text(warning_text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
        elif data == "msg_clear_confirm":
            state = load_state()
            state["auto_send_messages"] = []
            state["auto_send_message"] = ""
            save_state(state)
            
            if shared.bot_instance:
                shared.bot_instance.state["auto_send_messages"] = []
                shared.bot_instance.state["auto_send_message"] = ""
                
            tb.answer_callback_query(call.id, "🗑️ Đã xóa toàn bộ tin nhắn!", show_alert=True)
            
            # Quay lại menu_edit_msg trống
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            text_lines = [
                "📝 **DANH SÁCH TIN NHẮN QUẢNG CÁO HIỆN TẠI:**\n",
                "ℹ️ *Trống (Chưa có tin nhắn nào)*",
                "\nHãy chọn sửa một tin nhắn hoặc thêm tin mới:"
            ]
            btn_add = InlineKeyboardButton("➕ Thêm Tin Mới", callback_data="msg_add_new")
            btn_clear = InlineKeyboardButton("🗑️ Xóa Hết Tin", callback_data="msg_clear_all")
            markup.row(btn_add, btn_clear)
            markup.add(InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="back_to_menu"))
            tb.edit_message_text("\n".join(text_lines), chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
        elif data == "msg_add_new":
            tb.answer_callback_query(call.id)
            shared.user_sessions[chat_id] = {"action": "waiting_for_new_msg"}
            
            text = (
                "➕ **THÊM TIN NHẮN QUẢNG CÁO MỚI**\n\n"
                "👉 Vui lòng nhập nội dung tin nhắn mới và gửi trực tiếp vào đây (không cần gõ lệnh):"
            )
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Hủy", callback_data="menu_edit_msg"))
            tb.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
        elif data == "cancel_edit":
            tb.answer_callback_query(call.id, "❌ Hủy chỉnh sửa.")
            if chat_id in shared.user_sessions:
                del shared.user_sessions[chat_id]
            state = load_state()
            tb.edit_message_text("🤖 **HCS ZALO BOT - BẢNG ĐIỀU KHIỂN TELEGRAM**", chat_id, message_id, reply_markup=get_main_menu_keyboard(state))
            
        # 5. Quét và Duyệt Nhóm Phân Trang (10 nhóm/trang)
        elif data == "menu_scan_groups":
            if shared.bot_status != "CONNECTED" or not shared.bot_instance:
                tb.answer_callback_query(call.id, "⚠️ Zalo Bot chưa kết nối Zalo! Vui lòng khởi chạy trước.", show_alert=True)
                return
                
            tb.answer_callback_query(call.id, "⏳ Đang quét nhóm chat...")
            tb.edit_message_text("⏳ Đang tải toàn bộ nhóm chat từ Zalo của bạn (khoảng 3-5 giây)...", chat_id, message_id)
            
            try:
                groups_res = shared.bot_instance.fetchAllGroups()
                if not groups_res or not hasattr(groups_res, 'gridVerMap'):
                    tb.edit_message_text("⚠️ Không tìm thấy nhóm chat nào trên tài khoản Zalo của bạn.", chat_id, message_id, reply_markup=get_main_menu_keyboard(load_state()))
                    return
                    
                group_ids = list(groups_res.gridVerMap.keys())
                result = []
                for g_id in group_ids:
                    group_name = "Không xác định"
                    try:
                        info = shared.bot_instance.fetchGroupInfo(g_id)
                        if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                            group_name = info.gridInfoMap[g_id].get("name") or "Không tên"
                    except:
                        pass
                    result.append({"id": g_id, "name": group_name})
                    
                result.sort(key=lambda x: x["name"])
                
                shared.groups_page_cache[chat_id] = {"groups": result, "page": 0}
                
                state = load_state()
                state["known_joined_groups"] = group_ids
                save_state(state)
                
                tb.edit_message_text(
                    get_groups_page_text(chat_id, 0), 
                    chat_id, 
                    message_id, 
                    reply_markup=get_groups_page_keyboard(chat_id, 0),
                    parse_mode="Markdown"
                )
            except Exception as e:
                tb.edit_message_text(f"❌ Lỗi khi quét nhóm Zalo: {e}", chat_id, message_id, reply_markup=get_main_menu_keyboard(load_state()))
                
        elif data.startswith("page_grp_"):
            try:
                val = data.replace("page_grp_", "")
                if val == "info":
                    cache = shared.groups_page_cache.get(chat_id, {})
                    groups = cache.get("groups", [])
                    tb.answer_callback_query(call.id, f"Tổng số: {len(groups)} nhóm.")
                else:
                    page_idx = int(val)
                    tb.answer_callback_query(call.id)
                    tb.edit_message_text(
                        get_groups_page_text(chat_id, page_idx),
                        chat_id,
                        message_id,
                        reply_markup=get_groups_page_keyboard(chat_id, page_idx),
                        parse_mode="Markdown"
                    )
            except Exception as e:
                import traceback
                print(f"❌ Lỗi khi chuyển trang nhóm: {e}")
                traceback.print_exc()
                
        elif data.startswith("tgl_grp_"):
            try:
                parts = data.split("_")
                page_idx = int(parts[2])
                global_idx = int(parts[3])
                
                cache = shared.groups_page_cache.get(chat_id, {})
                groups = cache.get("groups", [])
                if groups and 0 <= global_idx < len(groups):
                    g_id = groups[global_idx]["id"]
                    g_name = groups[global_idx]["name"]
                    from shared import is_permanently_blocked
                    if is_permanently_blocked(g_name):
                        tb.answer_callback_query(call.id, "🔒 Nhóm này bị cấm rải vĩnh viễn và không thể bật!", show_alert=True)
                        return
                        
                    state = load_state()
                    blacklist = state.get("blacklisted_groups", [])
                    if not isinstance(blacklist, list):
                        blacklist = []
                    
                    # Chuyển đổi trạng thái (Toggle)
                    if g_id in blacklist:
                        blacklist.remove(g_id)
                        tb.answer_callback_query(call.id, f"📢 Bật rải: {g_name}")
                    else:
                        blacklist.append(g_id)
                        tb.answer_callback_query(call.id, f"❌ Tắt rải: {g_name}")
                        
                    state["blacklisted_groups"] = blacklist
                    save_state(state)
                    
                    # Cập nhật danh sách groups.txt dựa trên danh sách đen mới
                    if shared.bot_instance:
                        try:
                            groups_res = shared.bot_instance.fetchAllGroups()
                            if groups_res and hasattr(groups_res, 'gridVerMap'):
                                all_ids = list(groups_res.gridVerMap.keys())
                                active_groups = [gid for gid in all_ids if gid not in blacklist]
                                save_groups_to_txt(active_groups)
                        except:
                            pass
                            
                    # Cập nhật giao diện của trang hiện tại
                    tb.edit_message_text(
                        get_groups_page_text(chat_id, page_idx),
                        chat_id,
                        message_id,
                        reply_markup=get_groups_page_keyboard(chat_id, page_idx),
                        parse_mode="Markdown"
                    )
                else:
                    tb.answer_callback_query(call.id, "⚠️ Có lỗi xảy ra, vui lòng thử lại.", show_alert=True)
            except Exception as e:
                import traceback
                print(f"❌ Lỗi khi chuyển đổi trạng thái nhóm: {e}")
                traceback.print_exc()
                
        # 6. Quét Thủ Công Nhóm Mới (Join Sau)
        elif data == "menu_scan_new_groups":
            if shared.bot_status != "CONNECTED" or not shared.bot_instance:
                tb.answer_callback_query(call.id, "⚠️ Zalo Bot chưa kết nối Zalo! Vui lòng khởi chạy trước.", show_alert=True)
                return
                
            tb.answer_callback_query(call.id, "⏳ Đang so sánh nhóm mới...")
            tb.edit_message_text("⏳ Đang quét danh sách nhóm mới so với lần quét trước...", chat_id, message_id)
            
            try:
                groups_res = shared.bot_instance.fetchAllGroups()
                if not groups_res or not hasattr(groups_res, 'gridVerMap'):
                    tb.edit_message_text("⚠️ Không lấy được danh sách nhóm Zalo.", chat_id, message_id, reply_markup=get_main_menu_keyboard(load_state()))
                    return
                    
                current_group_ids = list(groups_res.gridVerMap.keys())
                state = load_state()
                known_groups = state.get("known_joined_groups")
                
                if known_groups is None:
                    state["known_joined_groups"] = current_group_ids
                    save_state(state)
                    tb.edit_message_text(
                        "ℹ️ Đã ghi nhận danh sách nhóm hiện tại làm mốc so sánh.\n\nTừ nay nếu bạn tham gia thêm nhóm mới, hãy bấm nút này để quét nhé!", 
                        chat_id, 
                        message_id, 
                        reply_markup=get_main_menu_keyboard(state)
                    )
                    return
                    
                new_group_ids = [g_id for g_id in current_group_ids if g_id not in known_groups]
                
                if not new_group_ids:
                    tb.edit_message_text(
                        "ℹ️ Không phát hiện thêm nhóm mới nào tham gia kể từ lần quét trước.",
                        chat_id,
                        message_id,
                        reply_markup=get_main_menu_keyboard(state)
                    )
                    return
                    
                tb.edit_message_text(f"🔔 Phát hiện {len(new_group_ids)} nhóm mới! Đang gửi danh sách chọn...", chat_id, message_id)
                
                for g_id in new_group_ids:
                    group_name = "Không xác định"
                    try:
                        info = shared.bot_instance.fetchGroupInfo(g_id)
                        if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                            group_name = info.gridInfoMap[g_id].get("name") or "Không tên"
                    except:
                        pass
                        
                    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                    markup = InlineKeyboardMarkup(row_width=2)
                    btn_rai = InlineKeyboardButton("📢 Rải", callback_data=f"newg_rai_{g_id}")
                    btn_khong = InlineKeyboardButton("❌ Không Rải", callback_data=f"newg_skip_{g_id}")
                    markup.row(btn_rai, btn_khong)
                    
                    escaped_name = escape_markdown(group_name)
                    msg_text = (
                        f"🔔 **PHÁT HIỆN NHÓM MỚI ĐÃ THAM GIA!**\n\n"
                        f"📌 Tên nhóm: **{escaped_name}**\n"
                        f"🆔 ID nhóm: `{g_id}`\n\n"
                        f"Bạn có muốn rải tin nhắn vào nhóm mới này không?"
                    )
                    tb.send_message(chat_id, msg_text, parse_mode="Markdown", reply_markup=markup)
                    time.sleep(0.5)
                    
                state["known_joined_groups"] = current_group_ids
                save_state(state)
                tb.send_message(chat_id, "✅ Đã gửi toàn bộ danh sách nhóm mới được tìm thấy!", reply_markup=get_main_menu_keyboard(state))
            except Exception as e:
                tb.edit_message_text(f"❌ Lỗi quét nhóm mới: {e}", chat_id, message_id, reply_markup=get_main_menu_keyboard(load_state()))
                
        elif data.startswith("newg_rai_"):
            g_id = data.replace("newg_rai_", "")
            state = load_state()
            blacklist = state.get("blacklisted_groups", [])
            if g_id in blacklist:
                blacklist.remove(g_id)
                state["blacklisted_groups"] = blacklist
                save_state(state)
                
                # Cập nhật groups.txt
                if shared.bot_instance:
                    try:
                        groups_res = shared.bot_instance.fetchAllGroups()
                        if groups_res and hasattr(groups_res, 'gridVerMap'):
                            all_ids = list(groups_res.gridVerMap.keys())
                            active_groups = [gid for gid in all_ids if gid not in blacklist]
                            save_groups_to_txt(active_groups)
                    except:
                        pass
                    
            group_name = "Nhóm mới"
            if shared.bot_instance:
                try:
                    info = shared.bot_instance.fetchGroupInfo(g_id)
                    if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                        group_name = info.gridInfoMap[g_id].get("name") or "Không tên"
                except:
                    pass
                    
            escaped_name = escape_markdown(group_name)
            tb.answer_callback_query(call.id, "📢 Đã bật rải tin cho nhóm này")
            tb.edit_message_text(f"✅ Đã bật rải tin đối với nhóm **{escaped_name}** (`{g_id}`) thành công!", chat_id, message_id, parse_mode="Markdown")
            
        elif data.startswith("newg_skip_"):
            g_id = data.replace("newg_skip_", "")
            state = load_state()
            blacklist = state.get("blacklisted_groups", [])
            if g_id not in blacklist:
                blacklist.append(g_id)
                state["blacklisted_groups"] = blacklist
                save_state(state)
                
                # Cập nhật groups.txt
                if shared.bot_instance:
                    try:
                        groups_res = shared.bot_instance.fetchAllGroups()
                        if groups_res and hasattr(groups_res, 'gridVerMap'):
                            all_ids = list(groups_res.gridVerMap.keys())
                            active_groups = [gid for gid in all_ids if gid not in blacklist]
                            save_groups_to_txt(active_groups)
                    except:
                        pass
                        
            group_name = "Nhóm mới"
            if shared.bot_instance:
                try:
                    info = shared.bot_instance.fetchGroupInfo(g_id)
                    if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                        group_name = info.gridInfoMap[g_id].get("name") or "Không tên"
                except:
                    pass
                    
            escaped_name = escape_markdown(group_name)
            tb.answer_callback_query(call.id, "❌ Đã chặn rải tin nhóm này")
            tb.edit_message_text(f"❌ Đã chặn rải tin đối với nhóm **{escaped_name}** (`{g_id}`).", chat_id, message_id, parse_mode="Markdown")
            
        elif data == "menu_clear_groups":
            tb.answer_callback_query(call.id)
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(row_width=2)
            btn_yes = InlineKeyboardButton("🗑️ Có, Xóa Hết!", callback_data="clear_groups_confirm")
            btn_no = InlineKeyboardButton("❌ Hủy", callback_data="back_to_menu")
            markup.row(btn_yes, btn_no)
            
            warning_text = (
                "⚠️ **CẢNH BÁO ĐẶT LẠI TRẠNG THÁI RẢI TIN**\n\n"
                "Bạn có chắc chắn muốn đặt lại trạng thái rải tin cho toàn bộ các nhóm không?\n"
                "Hành động này sẽ bỏ chặn tất cả các nhóm (toàn bộ nhóm sẽ được rải mặc định)."
            )
            tb.edit_message_text(warning_text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
        elif data == "clear_groups_confirm":
            state = load_state()
            state["blacklisted_groups"] = []
            save_state(state)
            
            # Lưu groups.txt chứa toàn bộ nhóm
            if shared.bot_instance:
                try:
                    groups_res = shared.bot_instance.fetchAllGroups()
                    if groups_res and hasattr(groups_res, 'gridVerMap'):
                        all_ids = list(groups_res.gridVerMap.keys())
                        save_groups_to_txt(all_ids)
                except:
                    pass
                
            tb.answer_callback_query(call.id, "🗑️ Đã đặt lại trạng thái rải cho toàn bộ nhóm!", show_alert=True)
            tb.edit_message_text("🤖 **HCS ZALO BOT - BẢNG ĐIỀU KHIỂN TELEGRAM**", chat_id, message_id, reply_markup=get_main_menu_keyboard(state))
            
        elif data == "menu_edit_time":
            tb.answer_callback_query(call.id)
            state = load_state()
            
            text = (
                "⏱️ **CẤU HÌNH THỜI GIAN CHẠY BOT**\n\n"
                "👉 Dùng các nút cộng trừ phía dưới để tăng/giảm thời gian cấu hình:\n"
                "• **Chu kỳ đợt rải:** Thời gian nghỉ giữa các đợt rải tin nhắn.\n"
                "• **Giãn cách nhóm:** Thời gian chờ giữa các nhóm trong cùng một đợt rải."
            )
            tb.edit_message_text(text, chat_id, message_id, reply_markup=get_time_settings_keyboard(state), parse_mode="Markdown")
            
        elif data.startswith("settime_int_"):
            val_str = data.replace("settime_int_", "")
            if val_str == "info":
                tb.answer_callback_query(call.id, "Bấm -5p hoặc +5p để điều chỉnh.")
            else:
                change = int(val_str)
                state = load_state()
                current_val = state.get("auto_send_interval", 900)
                new_val = current_val + (change * 60)
                
                # Tối thiểu 1 phút
                if new_val < 60:
                    new_val = 60
                    tb.answer_callback_query(call.id, "⚠️ Chu kỳ tối thiểu là 1 phút!", show_alert=True)
                else:
                    tb.answer_callback_query(call.id, f"✅ Đã điều chỉnh chu kỳ thành {new_val // 60} phút.")
                    
                state["auto_send_interval"] = new_val
                save_state(state)
                if shared.bot_instance:
                    shared.bot_instance.state["auto_send_interval"] = new_val
                    
                # Cập nhật giao diện
                tb.edit_message_reply_markup(chat_id, message_id, reply_markup=get_time_settings_keyboard(state))
                
        elif data.startswith("settime_del_"):
            val_str = data.replace("settime_del_", "")
            if val_str == "info":
                tb.answer_callback_query(call.id, "Bấm -5s hoặc +5s để điều chỉnh.")
            else:
                change = int(val_str)
                state = load_state()
                current_val = state.get("delay_between_groups", 30)
                new_val = current_val + change
                
                # Tối thiểu 5 giây để tránh anti-spam block
                if new_val < 5:
                    new_val = 5
                    tb.answer_callback_query(call.id, "⚠️ Giãn cách tối thiểu là 5 giây!", show_alert=True)
                else:
                    tb.answer_callback_query(call.id, f"✅ Đã điều chỉnh giãn cách thành {new_val} giây.")
                    
                state["delay_between_groups"] = new_val
                save_state(state)
                if shared.bot_instance:
                    shared.bot_instance.state["delay_between_groups"] = new_val
                    
                tb.edit_message_reply_markup(chat_id, message_id, reply_markup=get_time_settings_keyboard(state))
                
        elif data == "back_to_menu":
            tb.answer_callback_query(call.id)
            state = load_state()
            tb.edit_message_text("🤖 **HCS ZALO BOT - BẢNG ĐIỀU KHIỂN TELEGRAM**", chat_id, message_id, reply_markup=get_main_menu_keyboard(state))

    @tb.message_handler(commands=['setinterval'])
    def set_interval(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi lệnh: {message.text}")
        try:
            parts = message.text.split(' ', 1)
            if len(parts) < 2:
                tb.reply_to(message, "⚠️ Cú pháp: /setinterval <số phút>\nVí dụ: `/setinterval 15` để đặt 15 phút.")
                return
            minutes = int(parts[1])
            if minutes < 1:
                tb.reply_to(message, "⚠️ Khoảng thời gian tối thiểu là 1 phút.")
                return
            seconds = minutes * 60
            state = load_state()
            state["auto_send_interval"] = seconds
            save_state(state)
            
            if shared.bot_instance:
                shared.bot_instance.state["auto_send_interval"] = seconds
            import zalo_client
            zalo_client.trigger_send_now = True
            
            tb.reply_to(message, f"✅ Đã đặt chu kỳ rải tin nhắn thành {minutes} phút ({seconds} giây)!")
        except Exception as e:
            tb.reply_to(message, f"❌ Lỗi: {e}")

    @tb.message_handler(commands=['setdelay'])
    def set_delay(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi lệnh: {message.text}")
        try:
            parts = message.text.split(' ', 1)
            if len(parts) < 2:
                tb.reply_to(message, "⚠️ Cú pháp: /setdelay <số giây>\nVí dụ: `/setdelay 30`.")
                return
            seconds = int(parts[1])
            if seconds < 5:
                tb.reply_to(message, "⚠️ Giãn cách tối thiểu là 5 giây để tránh khóa acc.")
                return
            state = load_state()
            state["delay_between_groups"] = seconds
            save_state(state)
            
            if shared.bot_instance:
                shared.bot_instance.state["delay_between_groups"] = seconds
                
            tb.reply_to(message, f"✅ Đã đặt giãn cách giữa các nhóm thành {seconds} giây!")
        except Exception as e:
            tb.reply_to(message, f"❌ Lỗi: {e}")

    @tb.message_handler(commands=['messages'])
    def show_messages(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi lệnh: /messages")
        state = load_state()
        msgs = state.get("auto_send_messages", [])
        if not msgs:
            tb.reply_to(message, "ℹ️ Danh sách tin nhắn rải trống.")
            return
        
        tb.send_message(message.chat.id, "📋 **DANH SÁCH TIN NHẮN XOAY VÒNG HIỆN CÓ:**")
        for idx, m in enumerate(msgs, 1):
            text = f"**[Tin {idx}]:**\n{m}"
            tb.send_message(message.chat.id, text)
            time.sleep(0.5)

    @tb.message_handler(commands=['setmsg'])
    def set_message(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi lệnh: {message.text}")
        try:
            parts = message.text.split(' ', 2)
            if len(parts) < 3:
                tb.reply_to(message, "⚠️ Cú pháp: /setmsg <số_thứ_tự> <nội dung tin nhắn>\nVí dụ:\n`/setmsg 1 Cần 10 con zalo...`")
                return
            idx = int(parts[1]) - 1
            content = parts[2].strip()
            
            state = load_state()
            msgs = state.get("auto_send_messages", [])
            if not isinstance(msgs, list):
                msgs = []
                
            # Đảm bảo danh sách đủ dài
            while len(msgs) <= idx:
                msgs.append("")
                
            msgs[idx] = content
            state["auto_send_messages"] = msgs
            if idx == 0:
                state["auto_send_message"] = content
            save_state(state)
            
            if shared.bot_instance:
                shared.bot_instance.state["auto_send_messages"] = msgs
                if idx == 0:
                    shared.bot_instance.state["auto_send_message"] = content
                    
            tb.reply_to(message, f"✅ Đã cập nhật thành công Tin {idx + 1}!")
        except Exception as e:
            tb.reply_to(message, f"❌ Lỗi: {e}")

    @tb.message_handler(commands=['groups'])
    def show_groups(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi lệnh: /groups")
        state = load_state()
        blacklist = state.get("blacklisted_groups", [])
        
        if not shared.bot_instance or shared.bot_status != "CONNECTED":
            tb.reply_to(message, "⚠️ Zalo Bot chưa kết nối. Vui lòng kết nối để tải danh sách nhóm thực tế.")
            return
            
        try:
            groups_res = shared.bot_instance.fetchAllGroups()
            if groups_res and hasattr(groups_res, 'gridVerMap'):
                all_ids = list(groups_res.gridVerMap.keys())
            else:
                all_ids = []
        except Exception as e:
            tb.reply_to(message, f"❌ Lỗi tải nhóm: {e}")
            return
            
        active_groups = [g_id for g_id in all_ids if g_id not in blacklist]
        if not active_groups:
            tb.reply_to(message, "ℹ️ Danh sách nhóm rải tin hiện đang trống (Tất cả đều bị chặn).")
            return
            
        text = f"📋 **DANH SÁCH NHÓM RẢI TIN ({len(active_groups)} nhóm):**\n\n"
        for idx, g in enumerate(active_groups, 1):
            group_name = "Không tên"
            try:
                info = shared.bot_instance.fetchGroupInfo(g)
                if info and hasattr(info, 'gridInfoMap') and g in info.gridInfoMap:
                    group_name = info.gridInfoMap[g].get("name") or "Không tên"
            except:
                pass
            escaped_name = escape_markdown(group_name)
            text += f"{idx}. **{escaped_name}** (`{g}`)\n"
        tb.send_message(message.chat.id, text, parse_mode="Markdown")

    @tb.message_handler(commands=['addgroup'])
    def add_group(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi lệnh: {message.text}")
        try:
            parts = message.text.split(' ', 1)
            if len(parts) < 2:
                tb.reply_to(message, "⚠️ Cú pháp: /addgroup <ID_nhóm>")
                return
            g_id = parts[1].strip()
            state = load_state()
            
            # Kiểm tra xem nhóm có bị cấm vĩnh viễn không trước khi cho phép rải
            if shared.bot_instance:
                try:
                    info = shared.bot_instance.fetchGroupInfo(g_id)
                    if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                        g_name = info.gridInfoMap[g_id].get("name") or ""
                        from shared import is_permanently_blocked
                        if is_permanently_blocked(g_name):
                            tb.reply_to(message, f"🔒 Nhóm '{g_name}' (`{g_id}`) bị cấm rải vĩnh viễn và không thể thêm vào danh sách rải.")
                            return
                except:
                    pass
                    
            blacklist = state.get("blacklisted_groups", [])
            if g_id in blacklist:
                blacklist.remove(g_id)
                state["blacklisted_groups"] = blacklist
                save_state(state)
                tb.reply_to(message, f"✅ Đã bật rải tin (bỏ chặn) cho nhóm `{g_id}`.")
            else:
                tb.reply_to(message, f"ℹ️ Nhóm `{g_id}` hiện đã có trạng thái rải tin.")
        except Exception as e:
            tb.reply_to(message, f"❌ Lỗi: {e}")

    @tb.message_handler(commands=['delgroup'])
    def del_group(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi lệnh: {message.text}")
        try:
            parts = message.text.split(' ', 1)
            if len(parts) < 2:
                tb.reply_to(message, "⚠️ Cú pháp: /delgroup <ID_nhóm>")
                return
            g_id = parts[1].strip()
            state = load_state()
            blacklist = state.get("blacklisted_groups", [])
            if g_id not in blacklist:
                blacklist.append(g_id)
                state["blacklisted_groups"] = blacklist
                save_state(state)
                tb.reply_to(message, f"✅ Đã chặn rải tin (thêm vào danh sách chặn) cho nhóm `{g_id}`.")
            else:
                tb.reply_to(message, f"ℹ️ Nhóm `{g_id}` đã có trong danh sách chặn.")
        except Exception as e:
            tb.reply_to(message, f"❌ Lỗi: {e}")

    @tb.message_handler(func=lambda message: message.chat.id in shared.user_sessions)
    def handle_session_input(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        session = shared.user_sessions[chat_id]
        
        if session["action"] == "waiting_for_msg":
            idx = session["index"]
            content = message.text.strip()
            print(f"💬 [TELEGRAM] Admin gửi nội dung sửa Tin {idx + 1}: {content[:40]}...")
            
            state = load_state()
            msgs = state.get("auto_send_messages", [])
            if not isinstance(msgs, list):
                msgs = []
                
            if idx < len(msgs):
                msgs[idx] = content
            else:
                msgs.append(content)
                
            state["auto_send_messages"] = msgs
            if idx == 0:
                state["auto_send_message"] = content
            save_state(state)
            
            if shared.bot_instance:
                shared.bot_instance.state["auto_send_messages"] = msgs
                if idx == 0:
                    shared.bot_instance.state["auto_send_message"] = content
                    
            del shared.user_sessions[chat_id]
            tb.reply_to(message, f"✅ Đã cập nhật thành công Tin {idx + 1}!", reply_markup=get_main_menu_keyboard(state))
            
        elif session["action"] == "waiting_for_new_msg":
            content = message.text.strip()
            print(f"💬 [TELEGRAM] Admin gửi nội dung thêm Tin mới: {content[:40]}...")
            
            state = load_state()
            msgs = state.get("auto_send_messages", [])
            if not isinstance(msgs, list):
                msgs = []
                
            msgs.append(content)
            state["auto_send_messages"] = msgs
            if len(msgs) == 1:
                state["auto_send_message"] = content
            save_state(state)
            
            if shared.bot_instance:
                shared.bot_instance.state["auto_send_messages"] = msgs
                if len(msgs) == 1:
                    shared.bot_instance.state["auto_send_message"] = content
                    
            del shared.user_sessions[chat_id]
            tb.reply_to(message, f"✅ Đã thêm mới thành công Tin {len(msgs)}!", reply_markup=get_main_menu_keyboard(state))

    @tb.message_handler(func=lambda message: True)
    def handle_any_text_message(message):
        chat_id = message.chat.id
        if not check_is_admin(chat_id):
            return
        print(f"💬 [TELEGRAM] Admin gửi tin nhắn thường: {message.text}")
        state = load_state()
        tb.send_message(
            chat_id,
            "🤖 **HCS ZALO BOT - BẢNG ĐIỀU KHIỂN CHÍNH**\n\nHãy sử dụng các nút bấm bên dưới để thao tác nhanh:",
            reply_markup=get_main_menu_keyboard(state),
            parse_mode="Markdown"
        )

def new_groups_checker_worker():
    """Luồng kiểm tra nhóm mới tự động định kỳ mỗi 30 phút"""
    print("🚀 Bắt đầu luồng kiểm tra tự động nhóm mới mỗi 30 phút...")
    while True:
        time.sleep(1800)
        
        tb = shared.tb
        if not tb or shared.bot_status != "CONNECTED" or not shared.bot_instance:
            continue
            
        try:
            state = load_state()
            chat_id = state.get("telegram_admin_chat_id")
            if not chat_id:
                continue
                
            groups_res = shared.bot_instance.fetchAllGroups()
            if not groups_res or not hasattr(groups_res, 'gridVerMap'):
                continue
                
            current_group_ids = list(groups_res.gridVerMap.keys())
            known_groups = state.get("known_joined_groups")
            
            if known_groups is None:
                state["known_joined_groups"] = current_group_ids
                save_state(state)
                continue
                
            new_group_ids = [g_id for g_id in current_group_ids if g_id not in known_groups]
            
            if new_group_ids:
                print(f"🔔 [TỰ ĐỘNG PHÁT HIỆN] Tìm thấy {len(new_group_ids)} nhóm mới tham gia!")
                for g_id in new_group_ids:
                    group_name = "Không xác định"
                    try:
                        info = shared.bot_instance.fetchGroupInfo(g_id)
                        if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                            group_name = info.gridInfoMap[g_id].get("name") or "Không tên"
                    except:
                        pass
                        
                    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                    markup = InlineKeyboardMarkup(row_width=2)
                    btn_rai = InlineKeyboardButton("📢 Rải", callback_data=f"newg_rai_{g_id}")
                    btn_khong = InlineKeyboardButton("❌ Không Rải", callback_data=f"newg_skip_{g_id}")
                    markup.row(btn_rai, btn_khong)
                    
                    msg_text = (
                        f"🔔 **[TỰ ĐỘNG PHÁT HIỆN] CẬP NHẬT NHÓM MỚI!**\n\n"
                        f"📌 Tên nhóm: **{group_name}**\n"
                        f"🆔 ID nhóm: `{g_id}`\n\n"
                        f"Bạn có muốn rải tin nhắn vào nhóm mới gia nhập này không?"
                    )
                    tb.send_message(chat_id, msg_text, parse_mode="Markdown", reply_markup=markup)
                    time.sleep(1)
                    
                state["known_joined_groups"] = current_group_ids
                save_state(state)
        except Exception as e:
            print(f"⚠️ Lỗi trong chu kỳ quét nhóm mới tự động: {e}")

def run_telegram_control_bot():
    """Khởi chạy máy chủ điều khiển Telegram Bot"""
    tb = shared.tb
    if not tb:
        print("⚠️ Không có TELEGRAM_BOT_TOKEN trong .env. Telegram control bot KHÔNG hoạt động.")
        return
        
    print("🚀 Bắt đầu khởi chạy Telegram Bot điều khiển...")
    
    # Kích hoạt handlers
    init_telegram_handlers()
    
    while True:
        try:
            tb.polling(none_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"⚠️ [TELEGRAM] Kết nối gián đoạn. Tự động kết nối lại sau 5 giây...")
            time.sleep(5)
