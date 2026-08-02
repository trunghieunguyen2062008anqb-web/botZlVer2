import builtins
import sys

# Luôn tự động đẩy dữ liệu ra terminal không bị nghẽn (unbuffered print)
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    builtins.print(*args, **kwargs)

import os
import telebot
from dotenv import load_dotenv

# Load môi trường
load_dotenv(override=True)

# Khởi tạo Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
tb = None
if TELEGRAM_BOT_TOKEN:
    # Tắt log spam của telebot
    import logging
    telebot.logger.setLevel(logging.CRITICAL)
    tb = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Trạng thái kết nối Zalo
bot_instance = None
bot_status = "DISCONNECTED"  # CONNECTED, CONNECTING, DISCONNECTED, ERROR
bot_error_message = ""
bot_thread = None

# Trạng thái rải tin nhắn
trigger_send_now = False
auto_send_started = False

# Session người dùng Telegram
user_sessions = {}
groups_page_cache = {}

def is_permanently_blocked(group_name):
    """Kiểm tra xem tên nhóm có nằm trong danh sách cấm rải vĩnh viễn hay không"""
    if not group_name:
        return False
    name_lower = group_name.lower()
    
    # Từ khóa cấm vĩnh viễn (nhóm học tập, hỗ trợ btool, nhóm nhạy cảm, quảng cáo không phù hợp)
    permanent_keywords = [
        "hỗ trợ btool",
        "ho tro btool",
        "12a7",
        "12a7-thptqn",
        "a1_cs1",
        "a1 cs1",
        "xsmm.net",
        "xsmm",
        "mmovn"
    ]
    
    for kw in permanent_keywords:
        if kw in name_lower:
            return True
            
    # So khớp chính xác các nhóm
    exact_names = [
        "nhóm hỗ trợ btool",
        "nhóm bcs lớp 12a7(2023-2026)",
        "lớp 12a7-thptqn(2023-2026)",
        "sh lại a1_cs1 (trụ sở ở quảng ninh)",
        "xsmm.net",
        "[1] mmovn community - thảo luận, chợ giời tk số"
    ]
    for ex in exact_names:
        if name_lower == ex.lower():
            return True
            
    return False
