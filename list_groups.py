import sys
import io
from config import PHONE_NUMBER, PASSWORD, IMEI, COOKIE
from zlapi import ZaloAPI

# Cấu hình encoding UTF-8 để hiển thị tiếng Việt trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

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

    print("🚀 Đang kết nối Zalo để lấy danh sách nhóm...")
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
        print("🔑 Kết nối thành công!")
        print("📁 Đang tải danh sách nhóm chat của bạn...")
        
        groups = bot.fetchAllGroups()
        
        if not groups or not hasattr(groups, 'gridVerMap'):
            print("ℹ️ Không tìm thấy nhóm chat nào hoặc danh sách trống.")
            return
            
        group_ids = list(groups.gridVerMap.keys())
        print("\n================= DANH SÁCH NHÓM CHAT =================")
        print(f"Tìm thấy {len(group_ids)} nhóm chat. Hãy copy ID dán vào file groups.txt:\n")
        
        for g_id in group_ids:
            try:
                info = bot.fetchGroupInfo(g_id)
                if info and hasattr(info, 'gridInfoMap') and g_id in info.gridInfoMap:
                    group_details = info.gridInfoMap[g_id]
                    group_name = group_details.get("name") or "Không tên"
                    print(f"👥 Tên nhóm: {group_name}")
                    print(f"👉 ID nhóm : {g_id}")
                    print("-" * 50)
                else:
                    print(f"👥 Tên nhóm: [Không tìm thấy tên]")
                    print(f"👉 ID nhóm : {g_id}")
                    print("-" * 50)
            except Exception as e:
                print(f"👥 Tên nhóm: [Lỗi tải tên: {e}]")
                print(f"👉 ID nhóm : {g_id}")
                print("-" * 50)
            
    except Exception as e:
        print(f"❌ Lỗi kết nối lấy danh sách nhóm: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
