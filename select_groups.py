import sys
import io
import os
import json
from config import PHONE_NUMBER, PASSWORD, IMEI, COOKIE
from zlapi import ZaloAPI

# Cấu hình encoding UTF-8 để hiển thị tiếng Việt trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

STATE_FILE = "bot_state.json"
GROUPS_FILE = "groups.txt"

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
        print(f"❌ Lỗi phân tích Cookie: {e}")
    return cookies

def main():
    if not COOKIE or COOKIE == "YOUR_COOKIE_HERE":
        print("[LỖI] Bạn chưa điền COOKIE trong tệp .env!")
        sys.exit(1)
    if not IMEI or IMEI == "YOUR_IMEI_HERE":
        print("[LỖI] Bạn chưa điền IMEI trong tệp .env!")
        sys.exit(1)

    print("==================================================")
    print("🎯 BỘ LỌC DUYỆT NHÓM RẢI TIN NHẮN TỰ ĐỘNG ZALO")
    print("==================================================")
    print("🚀 Đang kết nối Zalo để lấy danh sách nhóm của bạn...")
    
    cookies_dict = parse_cookie_string(COOKIE)
    
    try:
        phone_val = PHONE_NUMBER if PHONE_NUMBER and PHONE_NUMBER != "YOUR_PHONE_NUMBER_HERE" else ""
        pass_val = PASSWORD if PASSWORD and PASSWORD != "YOUR_PASSWORD_HERE" else ""
        
        bot = ZaloAPI(
            phone=phone_val,
            password=pass_val,
            imei=IMEI,
            cookies=cookies_dict
        )
        print("🔑 Kết nối Zalo thành công!")
        print("📁 Đang tải toàn bộ nhóm chat...")
        
        groups_res = bot.fetchAllGroups()
        
        if not groups_res or not hasattr(groups_res, 'gridVerMap'):
            print("ℹ️ Không tìm thấy nhóm chat nào.")
            return
            
        group_ids = list(groups_res.gridVerMap.keys())
        total_groups = len(group_ids)
        print(f"📦 Tìm thấy tổng cộng {total_groups} nhóm chat.\n")
        print("👉 Hướng dẫn duyệt:")
        print(" - Nhấn [ENTER] (để trống) để CHỌN nhóm này để rải tin.")
        print(" - Gõ phím bất kỳ (ví dụ 'k') rồi [ENTER] để BỎ QUA không chọn.")
        print("--------------------------------------------------\n")
        
        selected_groups = []
        group_names_map = {}
        
        for idx, g_id in enumerate(group_ids, 1):
            group_name = "Không xác định"
            try:
                info = bot.fetchGroupInfo(g_id)
                if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                    group_name = info.gridInfoMap[g_id].get("name") or "Không tên"
            except Exception:
                pass
                
            group_names_map[g_id] = group_name
            print(f"[{idx}/{total_groups}] 👥 Tên nhóm: {group_name}")
            print(f"          🆔 ID nhóm: {g_id}")
            
            user_input = input("👉 Duyệt nhóm này? (ENTER: chọn / Nhấn chữ + ENTER: bỏ qua): ").strip()
            
            if user_input == "":
                selected_groups.append(g_id)
                print("🟢 ĐÃ CHỌN nhóm này.")
            else:
                print("🔴 ĐÃ BỎ QUA nhóm này.")
            print("-" * 50)
            
        print("\n================== HOÀN THÀNH ==================")
        print(f"Tổng số nhóm bạn đã duyệt để rải tin: {len(selected_groups)} / {total_groups} nhóm.")
        print("\n📋 DANH SÁCH CÁC NHÓM BẠN ĐÃ CHỌN RẢI TIN:")
        if selected_groups:
            for i, g_id in enumerate(selected_groups, 1):
                name = group_names_map.get(g_id, "Không rõ tên")
                print(f"  {i}. 👥 {name} (ID: {g_id})")
        else:
            print("  (Chưa chọn nhóm nào)")
        print("=" * 48)
        
        # 1. Lưu vào file groups.txt
        try:
            with open(GROUPS_FILE, "w", encoding="utf-8") as f:
                f.write("# Danh sách nhóm đã duyệt chọn lọc để rải tin nhắn tự động\n")
                for g_id in selected_groups:
                    f.write(f"{g_id}\n")
            print(f"💾 Đã lưu danh sách vào file {GROUPS_FILE}")
        except Exception as e:
            print(f"❌ Lỗi ghi file groups.txt: {e}")
            
        # 2. Đồng bộ vào file bot_state.json
        try:
            state = {}
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
            
            state["auto_send_groups"] = selected_groups
            
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
            print(f"💾 Đã đồng bộ danh sách vào file {STATE_FILE}")
        except Exception as e:
            print(f"❌ Lỗi đồng bộ vào file bot_state.json: {e}")
            
        print("\n✨ Cấu hình đã sẵn sàng! Bây giờ bạn chỉ cần khởi động lại bot.py để rải các nhóm đã chọn.")
        
    except Exception as e:
        print(f"❌ Lỗi kết nối lấy danh sách nhóm: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
