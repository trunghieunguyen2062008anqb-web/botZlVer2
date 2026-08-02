import sys
import threading
import time

# Cấu hình encoding UTF-8 cho console tránh lỗi hiển thị tiếng Việt trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import shared
from zalo_client import bot_connection_worker
from telegram_controller import run_telegram_control_bot, new_groups_checker_worker

def main():
    # Đồng bộ cấu hình mặc định lúc khởi chạy: Tắt rải tin nhắn, Bật tự động trả lời 1-1
    from state_manager import load_state, save_state
    state = load_state()
    state["auto_send_enabled"] = False
    state["auto_reply_enabled"] = True
    save_state(state)

    print("\n" + "="*50)
    print("🤖 HỆ THỐNG ZALO BOT CÁ NHÂN - TELEGRAM CONTROL PANEL")
    print("="*50)
    print("👉 Hãy mở Telegram chat với Bot để cấu hình trực tiếp từ xa!")
    print("="*50 + "\n")
    
    # 1. Khởi chạy giao diện điều khiển Telegram Bot trên luồng riêng
    tele_thread = threading.Thread(target=run_telegram_control_bot, daemon=True)
    tele_thread.start()
    
    # 2. Tự động thử kết nối Zalo Bot trên luồng riêng khi khởi động
    print("⏳ Đang khởi chạy luồng kết nối tự động với Zalo...")
    shared.bot_thread = threading.Thread(target=bot_connection_worker, daemon=True)
    shared.bot_thread.start()
    
    # 3. Khởi chạy luồng tự động quét nhóm mới tham gia sau mỗi 30 phút (Tắt vì thừa, có thể quét thủ công từ Telegram)
    # checker_thread = threading.Thread(target=new_groups_checker_worker, daemon=True)
    # checker_thread.start()
    
    # Giữ luồng chính hoạt động
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Đang đóng hệ thống Zalo Bot...")
        if shared.bot_instance:
            try:
                shared.bot_instance.ws.close()
            except:
                pass

if __name__ == "__main__":
    main()
