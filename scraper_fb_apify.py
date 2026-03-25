import os
import json
import logging
from datetime import datetime, date
import requests
from dotenv import load_dotenv
from apify_client import ApifyClient

# 1. Khởi tạo & Cấu hình
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Sử dụng Token mặc định của user nếu .env không có
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
# Cho phép thay đổi Actor ID qua biến môi trường để linh động giữa Pages và Groups
ACTOR_ID = os.getenv("APIFY_FB_ACTOR", "apify/facebook-pages-scraper")

WATCH_FILE = "fb_watch_list.json"
SPIKE_THRESHOLD_PERCENT = 0.05 # Tăng trưởng 5%
SPIKE_THRESHOLD_COUNT = 500    # Tăng tối thiểu 500 thành viên
SPIKE_MIN_LIKES = 1000         # Chỉ cảnh báo khi likes >= 1000

# Biến Telegram
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(text):
    if not BOT_TOKEN or not TARGET_CHAT_ID:
        logging.warning("Chưa cấu hình TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. Bỏ qua gửi tin nhắn.")
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logging.info("Đã gửi cảnh báo Telegram thành công.")
        else:
            logging.error(f"Lỗi gửi tin Telegram: {resp.text}")
    except Exception as e:
        logging.error(f"Exception gửi tin Telegram: {e}")

def load_watch_list():
    if not os.path.exists(WATCH_FILE):
        return []
    try:
        with open(WATCH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Lỗi đọc {WATCH_FILE}: {e}")
        return []

def save_watch_list(data):
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_spike(entry, new_count):
    """Check for spike and return alert snippet if triggered, or None."""
    history = entry.setdefault("history", {})
    today_str = date.today().isoformat()
    
    dates = sorted(history.keys())
    alert_snippet = None
    
    # Bỏ qua nếu chưa có dữ liệu ngày hôm trước
    if not dates:
        history[today_str] = new_count
        return None
        
    # Tính từ ngày ghi nhận gần nhất
    last_date = dates[-1]
    last_count = history[last_date]
    
    if last_count > 0:
        diff = new_count - last_count
        percent = diff / last_count
        
        # Chỉ cảnh báo nếu: hôm nay chưa lưu, likes >= ngưỡng tối thiểu, và tăng trưởng đạt ngưỡng
        if today_str not in dates and new_count >= SPIKE_MIN_LIKES and (diff >= SPIKE_THRESHOLD_COUNT or percent >= SPIKE_THRESHOLD_PERCENT):
            alert_snippet = (
                f"🎮 Game: <b>{entry.get('game_name', 'Không rõ')}</b>\n"
                f"📈 {entry.get('type', 'Fanpage')} tăng đột biến!\n"
                f"🔥 Mức tăng: <b>+{diff}</b> (<b>+{(percent*100):.1f}%</b>) so với {last_date}\n"
                f"👥 Hiện tại: <b>{new_count:,}</b> likes\n"
                f"🔗 {entry.get('url')}"
            )
            logging.info(f"Phát hiện tăng đột biến cho {entry.get('game_name')}")

    # Cập nhật số liệu hôm nay
    history[today_str] = new_count
    return alert_snippet

def run_scraper():
    watch_list = load_watch_list()
    if not watch_list:
        logging.info("Danh sách theo dõi rỗng.")
        return

    urls = [{"url": item["url"]} for item in watch_list if item.get("url")]
    
    client = ApifyClient(APIFY_TOKEN)
    run_input = {"startUrls": urls}
    
    logging.info(f"Bắt đầu gọi Apify Actor [{ACTOR_ID}] cho {len(urls)} links...")
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        logging.info(f"Apify call completed. Status: {run.get('status')}")
        
        # Duyệt qua các kết quả Apify trả về
        alerts = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            # URL tùy vào cấu trúc trả về của mỗi Apify Actor
            res_url = item.get("pageUrl") or item.get("url") or item.get("facebookUrl")
            
            # Lấy chỉ số lượt Likes hoặc Members (cả Page hoặc Group)
            likes = item.get("likes") or item.get("members") or item.get("followers") or item.get("memberCount") or 0
            
            if not res_url or int(likes) == 0:
                continue
                
            # Đối chiếu với danh sách theo dõi
            for entry in watch_list:
                # Do URL khi nhập và xử lý có thể rút gọn/chứa param nên ta check chuỗi con
                if entry["url"].strip("/") in res_url:
                    snippet = check_spike(entry, int(likes))
                    if snippet:
                        alerts.append(snippet)
                    break

        save_watch_list(watch_list)
        
        # Gộp tất cả cảnh báo thành 1 tin nhắn duy nhất
        if alerts:
            combined = (
                f"🚨 <b>TRINH SÁT BÁO ĐỘNG</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            combined += "\n━━━━━━━━━━━━━━━━━━━━\n\n".join(alerts)
            combined += (
                f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 Dấu hiệu game chuẩn bị Alpha Test hoặc đang chạy Ads mạnh!"
            )
            send_telegram_alert(combined)
            logging.info(f"Đã gửi {len(alerts)} cảnh báo gộp trong 1 tin nhắn.")
        logging.info(f"Hoàn tất quét Facebook qua Apify lúc {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        logging.error(f"Lỗi khi bắt cầu Apify: {e}")

if __name__ == '__main__':
    run_scraper()
