import os
import sys
import time
import glob as _glob
import shutil
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import threading
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import schedule
import telebot
import re
from telebot import types

# Setup logging with rotation (max 5MB per file, keep 3 backups)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    "monitor.log", maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
root_logger.addHandler(stream_handler)

# --- SINGLE INSTANCE LOCK ---
import msvcrt
lock_file_path = "alert_gov.lock"
# Keep file open for the lifetime of the process
lock_file_fd = open(lock_file_path, "w")
try:
    msvcrt.locking(lock_file_fd.fileno(), msvcrt.LK_NBLCK, 1)
except IOError:
    logging.error("Another instance of monitor.py is already running. Exiting to prevent 409 Conflict...")
    sys.exit(1)
# ----------------------------

# Load environment variables
load_dotenv()

# Configuration
URL = os.getenv("TARGET_URL", "https://giayphep.abei.gov.vn/g1")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MINUTES", 360))
STATE_FILE = "monitor_state.json"
DATA_FILE = "data.json"
WATCH_FILE = "watch_list.json"

# In-memory database
game_database = []

if not BOT_TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN is missing!")
    exit(1)

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)

def load_database():
    """Loads data.json into memory."""
    global game_database
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                game_database = json.load(f)
            logging.info(f"Loaded {len(game_database)} games into memory.")
        except Exception as e:
            logging.error(f"Error loading database: {e}")
            game_database = []
    else:
        logging.warning("data.json not found. Database empty.")
        game_database = []

def load_watchlist():
    """Loads watch_list.json into memory."""
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('keywords', [])
        except Exception as e:
            logging.error(f"Error loading watchlist: {e}")
    return []

def save_watchlist(keywords):
    """Saves watchlist keywords to watch_list.json."""
    with open(WATCH_FILE, 'w', encoding='utf-8') as f:
        json.dump({'keywords': keywords}, f, indent=2, ensure_ascii=False)

def get_content_hash(url):
    """Fetches the URL and returns a hash of its meaningful content."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Improve cleaning: remove scripts, styles, meta, noscript
        for element in soup(['script', 'style', 'meta', 'noscript']):
            element.decompose()
            
        text_content = soup.get_text(separator=' ', strip=True)
        return hashlib.sha256(text_content.encode('utf-8')).hexdigest()
        
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def check_website():
    """Main logic to check for changes."""
    logging.info(f"Checking {URL}...")
    
    current_hash = get_content_hash(URL)
    
    if not current_hash:
        logging.warning("Could not fetch website content.")
        return

    # Load previous state
    previous_hash = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                previous_hash = state.get('hash')
        except Exception as e:
            logging.error(f"Error reading state file: {e}")

    # Compare
    if previous_hash is None:
        logging.info("First run. Saving initial state.")
        send_message(f"🚀 *Website Monitor Started*\nMonitoring: {URL}\n\nI will check every {CHECK_INTERVAL//60} hours.")
        save_state(current_hash)
    elif current_hash != previous_hash:
        logging.info("Change detected!")
        send_message(f"⚠️ *Website Update Detected!*\n\nThe content at {URL} has changed. Running quick check for new games...")
        save_state(current_hash)
        
        # Use quick_check (safe merge) instead of full scrape
        try:
            logging.info("Running quick check after change detection...")
            result = subprocess.run(
                [sys.executable, "scraper_full.py", "--quick"],
                check=True, timeout=120, capture_output=True, text=True
            )
            logging.info(f"Quick check output: {result.stdout.strip()}")
            load_database()
            send_message(f"✅ *Database Updated*\nQuick check complete. Database now has {len(game_database)} games.")
        except Exception as e:
            logging.error(f"Failed to update database after change: {e}")
            send_message(f"❌ Error updating database: {e}")
    else:
        logging.info("No changes detected.")

def save_state(new_hash):
    """Saves the new hash to the state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'hash': new_hash, 'last_checked': time.time()}, f)
    except Exception as e:
        logging.error(f"Error saving state file: {e}")

def send_message(text, retries=3):
    """Sends a message to the configured Chat ID with retry logic."""
    if not CHAT_ID:
        logging.warning("CHAT_ID not set, skipping notification.")
        return False
    for attempt in range(1, retries + 1):
        try:
            bot.send_message(CHAT_ID, text, parse_mode="Markdown")
            return True
        except Exception as e:
            logging.error(f"Telegram send attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(5 * attempt)  # 5s, 10s backoff
    logging.critical(f"FAILED to send Telegram message after {retries} attempts!")
    return False

# --- Bot Commands ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        "🤖 *Website Monitor Bot*\n\n"
        "I am monitoring `giayphep.abei.gov.vn` for you.\n\n"
        "Commands:\n"
        "• /check - Force a check right now\n"
        "• /status - Confirm I am running\n"
        "• /search <keyword> - Tìm game theo tên, công ty, domain...\n"
        "• /searchdate <keyword> <từ> <đến> - Tìm theo khoảng thời gian\n"
        "• /license <số> - Tìm theo số giấy phép\n"
        "• /latest - Game mới nhất\n"
        "• /top5 - 5 game mới nhất\n"
        "• /week - Báo cáo tuần\n"
        "• /month - Báo cáo tháng\n"
        "• /scrape - Quick check game mới\n"
        "• /fullscrape - Crawl toàn bộ (merge, ~20p)\n"
        "• /backup - Xem/Restore backup\n"
        "• /stats - Thống kê database\n\n"
        "💡 *Mẹo:* `/searchdate Tam Quốc 01/01/2026 15/02/2026`"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['check'])
def manual_check(message):
    bot.reply_to(message, "🔍 Checking website now...")
    check_website()
    bot.send_message(message.chat.id, "✅ Check complete.")

@bot.message_handler(commands=['status'])
def status_check(message):
    last_checked = "Never"
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                ts = state.get('last_checked', 0)
                last_checked = time.ctime(ts)
        except Exception:
            pass
            
    bot.reply_to(message, f"🟢 **Running**\n\nTarget: {URL}\nInterval: {CHECK_INTERVAL}m\nLast Checked: {last_checked}", parse_mode="Markdown")

# Cache for game detail buttons
_detail_cache = {}

_search_sessions = {}

def _send_search_results(chat_id, results, title, page=0):
    """Sends search results with pagination and simple 4-field display."""
    # Dedup results by ID or name+license combo
    seen = set()
    unique_results = []
    for g in results:
        key = g.get('id', '') or (g.get('name', '') + g.get('license', ''))
        if key and key not in seen:
            seen.add(key)
            unique_results.append(g)
    
    _search_sessions[chat_id] = {
        'results': unique_results,
        'title': title
    }
    _render_search_page(chat_id, 0)

def _render_search_page(chat_id, page, message_id=None):
    session = _search_sessions.get(chat_id)
    if not session:
        bot.send_message(chat_id, "⚠️ Phiên tìm kiếm đã hết hạn. Vui lòng thử lại.")
        return
        
    results = session['results']
    title = session['title']
    
    per_page = 10
    total_pages = max(1, (len(results) - 1) // per_page + 1)
    
    if page < 0: page = 0
    if page >= total_pages: page = total_pages - 1
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_results = results[start_idx:end_idx]
    
    response = f"{title}\n_(Trang {page+1}/{total_pages} - Tổng {len(results)} kết quả)_\n\n"
    
    for g in page_results:
        g_name = g.get('name', '?').replace('*', '')  # Escape markdown
        g_company = g.get('company', '?')
        g_license = g.get('license', '?')
        g_date = g.get('date', '?')
        
        response += (
            f"🎮 *{g_name}*\n"
            f"🏢 {g_company}\n"
            f"📜 {g_license}\n"
            f"📅 {g_date}\n"
            f"──────────────\n"
        )
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    if page > 0:
        buttons.append(types.InlineKeyboardButton("⬅️ Trước", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        buttons.append(types.InlineKeyboardButton("Sau ➡️", callback_data=f"page_{page+1}"))
        
    if buttons:
        markup.add(*buttons)
        
    if message_id:
        try:
            bot.edit_message_text(response, chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            logging.error(f"Error editing pagination message: {e}")
    else:
        bot.send_message(chat_id, response, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def page_callback(call):
    page = int(call.data.split("_")[1])
    chat_id = call.message.chat.id
    _render_search_page(chat_id, page, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['search'])
def search_handle(message):
    query = message.text.replace("/search", "").strip().lower()
    if not query:
        bot.reply_to(message, "Nhập từ khóa. Ví dụ: `/search GAMOTA`", parse_mode="Markdown")
        return
    if not game_database:
        bot.reply_to(message, "⚠️ Database trống.")
        return

    results = [g for g in game_database
        if (query in g.get('name', '').lower() or 
            query in g.get('company', '').lower() or 
            query in g.get('license', '').lower() or
            query in g.get('domain', '').lower() or
            query in g.get('date', '').lower())]
    
    if not results:
        bot.reply_to(message, f"❌ Không tìm thấy kết quả cho '{query}'.")
        return
    
    _send_search_results(message.chat.id, results, f"✅ Tìm thấy *{len(results)}* kết quả cho *{query}*:")

@bot.message_handler(commands=['searchdate'])
def searchdate_handle(message):
    query = message.text.replace("/searchdate", "").strip()
    if not query:
        bot.reply_to(message, "Nhập cú pháp: `từ khóa 01/01/2026 15/02/2026`\nVí dụ: `/searchdate Tam Quốc 01/01/2026 15/02/2026`", parse_mode="Markdown")
        return
    if not game_database:
        bot.reply_to(message, "⚠️ Database trống.")
        return

    # Extract dates
    dates = re.findall(r'\b\d{1,2}/\d{1,2}/\d{4}\b', query)
    if len(dates) < 2:
        bot.reply_to(message, "⚠️ Cần nhập đủ 2 ngày (từ ngày và đến ngày). Ví dụ: `/searchdate Tam Quốc từ 01/01/2026 đến 15/02/2026`", parse_mode="Markdown")
        return

    try:
        start_date = datetime.strptime(dates[0], "%d/%m/%Y")
        end_date = datetime.strptime(dates[1], "%d/%m/%Y")
        if start_date > end_date:
            start_date, end_date = end_date, start_date
    except ValueError:
        bot.reply_to(message, "⚠️ Định dạng ngày không hợp lệ. Hãy dùng DD/MM/YYYY.")
        return

    # Extract keyword
    clean_query = query
    for d in dates[:2]:
        clean_query = clean_query.replace(d, "")
    clean_query = re.sub(r'(?i)\btừ\b|\bđến\b|-', '', clean_query)
    keyword = ' '.join(clean_query.split()).lower()

    results = []
    for g in game_database:
        # Check date
        g_date_str = g.get('date')
        if not g_date_str:
            continue
        try:
            g_date = datetime.strptime(g_date_str, "%d/%m/%Y")
            if not (start_date <= g_date <= end_date):
                continue
        except ValueError:
            continue

        # Check keyword if provided
        if keyword:
            if not (keyword in g.get('name', '').lower() or 
                    keyword in g.get('company', '').lower() or 
                    keyword in g.get('license', '').lower() or
                    keyword in g.get('domain', '').lower()):
                continue
                
        results.append(g)

    # Sort results by date descending
    results.sort(key=lambda x: datetime.strptime(x.get('date'), "%d/%m/%Y"), reverse=True)

    if not results:
        kw_str = f" cho '{keyword}'" if keyword else ""
        date_str = f" từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}"
        bot.reply_to(message, f"❌ Không tìm thấy kết quả{kw_str}{date_str}.")
        return
    
    kw_str = f" *{keyword}*" if keyword else " tất cả"
    date_str = f" từ {start_date.strftime('%d/%m/%Y')} đến {end_date.strftime('%d/%m/%Y')}"
    title = f"✅ Tìm thấy *{len(results)}* kết quả cho{kw_str}{date_str}:"
    _send_search_results(message.chat.id, results, title)

@bot.message_handler(commands=['license'])
def license_handle(message):
    query = message.text.replace("/license", "").strip()
    if not query:
        bot.reply_to(message, "Nhập số giấy phép. Ví dụ: `/license 92`", parse_mode="Markdown")
        return
    if not game_database:
        bot.reply_to(message, "⚠️ Database trống.")
        return
    
    results = [g for g in game_database if query.lower() in g.get('license', '').lower()]
    
    if not results:
        bot.reply_to(message, f"❌ Không tìm thấy giấy phép chứa '{query}'.")
        return
    
    _send_search_results(message.chat.id, results, f"📜 Tìm thấy *{len(results)}* kết quả cho giấy phép `{query}`:")
@bot.message_handler(commands=['watch'])
def watch_handle(message):
    keyword = message.text.replace("/watch", "").strip().lower()
    if not keyword:
        bot.reply_to(message, "Nhập tên công ty. Ví dụ: `/watch VTC`", parse_mode="Markdown")
        return
    keywords = load_watchlist()
    if keyword in keywords:
        bot.reply_to(message, f"⚠️ Bạn đã theo dõi `{keyword}` rồi.", parse_mode="Markdown")
        return
    keywords.append(keyword)
    save_watchlist(keywords)
    bot.reply_to(message, f"✅ Đã theo dõi: `{keyword}`\n\nBot sẽ báo ngay khi công ty này có game mới!", parse_mode="Markdown")

@bot.message_handler(commands=['unwatch'])
def unwatch_handle(message):
    keyword = message.text.replace("/unwatch", "").strip().lower()
    if not keyword:
        bot.reply_to(message, "Nhập từ khóa. Ví dụ: `/unwatch VTC`", parse_mode="Markdown")
        return
    keywords = load_watchlist()
    if keyword not in keywords:
        bot.reply_to(message, f"❌ Không tìm thấy `{keyword}` trong danh sách theo dõi.", parse_mode="Markdown")
        return
    keywords.remove(keyword)
    save_watchlist(keywords)
    bot.reply_to(message, f"🗑️ Đã xóa: `{keyword}`", parse_mode="Markdown")

@bot.message_handler(commands=['watchlist'])
def watchlist_handle(message):
    keywords = load_watchlist()
    if not keywords:
        bot.reply_to(message, "📋 Danh sách theo dõi đang trống.\n\nThêm bằng: `/watch <tên công ty>`", parse_mode="Markdown")
        return
    text = "🔔 *DANH SÁCH THEO DÕI:*\n\n"
    for i, kw in enumerate(keywords, 1):
        text += f"{i}. `{kw}`\n"
    text += f"\n_Tổng: {len(keywords)} công ty_\n"
    text += "\nDiếu chỉnh bằng: `/watch` hoặc `/unwatch`"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['trend'])
def trend_handle(message):
    parts = message.text.strip().split()
    months = 6
    if len(parts) > 1:
        try:
            months = max(1, min(24, int(parts[1])))
        except ValueError:
            pass

    if not game_database:
        bot.reply_to(message, "⚠️ Database trống.")
        return

    # Count games per month
    monthly = defaultdict(int)
    for g in game_database:
        date_str = g.get('date')
        if date_str:
            try:
                d = datetime.strptime(date_str, "%d/%m/%Y")
                key = d.strftime("%m/%Y")
                monthly[key] += 1
            except (ValueError, TypeError):
                continue

    # Get last N months sorted
    now = datetime.now()
    labels = []
    for i in range(months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        labels.append(f"{m:02d}/{y}")

    max_val = max((monthly.get(lb, 0) for lb in labels), default=1)
    if max_val == 0:
        max_val = 1

    bar_width = 10
    lines = []
    total = 0
    for lb in labels:
        count = monthly.get(lb, 0)
        total += count
        bar_len = int((count / max_val) * bar_width)
        bar = "█" * max(bar_len, 0 if count == 0 else 1)
        lines.append(f"`{lb}` {bar:<{bar_width}} {count}")

    chart = "━" * 22 + "\n"
    chart += f"📈 *XU HƯỚNG CẤP PHÉP GAME*\n"
    chart += "━" * 22 + "\n"
    chart += "\n".join(lines)
    chart += "\n" + "━" * 22
    chart += f"\nℹ️ Tổng: *{total}* game | {months} tháng"
    bot.reply_to(message, chart, parse_mode="Markdown")

# ============================================================
# AI ARTICLE READER (NODE.JS PIPELINE) - Processed via ai_reader_feature.py
# ============================================================
# from ai_reader_feature import register_ai_handlers
# register_ai_handlers(bot)

@bot.message_handler(commands=['stats'])
def stats_handle(message):
    update_time = "Unknown"
    if os.path.exists(DATA_FILE):
        ts = os.path.getmtime(DATA_FILE)
        update_time = time.ctime(ts)
        
    stats_msg = (
        f"📊 *Database Statistics*\n\n"
        f"Games Indexed: {len(game_database)}\n"
        f"Last Update: {update_time}\n"
    )
    bot.reply_to(message, stats_msg, parse_mode="Markdown")

def get_sorted_games():
    """Returns games sorted by date (newest first)."""
    dated_games = []
    for game in game_database:
        date_str = game.get('date')
        if date_str:
            try:
                game_date = datetime.strptime(date_str, "%d/%m/%Y")
                dated_games.append((game_date, game))
            except (ValueError, TypeError):
                continue
    dated_games.sort(key=lambda x: x[0], reverse=True)
    return [g for _, g in dated_games]

def format_game_card(game, index=None):
    """Formats a single game into a readable message block."""
    prefix = f"{index}. " if index else ""
    company_short = game.get('company', '').replace("CÔNG TY CỔ PHẦN ", "").replace("CÔNG TY TNHH ", "").replace(" -", "").strip()
    company_short = (company_short[:25] + '..') if len(company_short) > 27 else company_short
    return (
        f"🎮 *{prefix}{game.get('name', 'Unknown')}*\n"
        f"🏢 {company_short}\n"
        f"📜 {game.get('license', '')}\n"
        f"📅 Ngày cấp: {game.get('date', 'N/A')}\n"
        f"🌐 {game.get('domain', '')}\n"
    )

@bot.message_handler(commands=['latest'])
def latest_handle(message):
    if not game_database:
        bot.reply_to(message, "⚠️ Database trống.")
        return
    sorted_games = get_sorted_games()
    if not sorted_games:
        bot.reply_to(message, "⚠️ Không tìm thấy game nào có ngày cấp phép.")
        return
    game = sorted_games[0]
    response = "🆕 *GAME MỚI NHẤT ĐƯỢC CẤP PHÉP:*\n\n" + format_game_card(game)
    bot.reply_to(message, response, parse_mode="Markdown")

@bot.message_handler(commands=['top5'])
def top5_handle(message):
    if not game_database:
        bot.reply_to(message, "⚠️ Database trống.")
        return
    sorted_games = get_sorted_games()
    if not sorted_games:
        bot.reply_to(message, "⚠️ Không tìm thấy game nào có ngày cấp phép.")
        return
    top = sorted_games[:5]
    response = "🏆 *TOP 5 GAME MỚI NHẤT:*\n\n"
    for i, game in enumerate(top, 1):
        response += format_game_card(game, index=i)
    bot.reply_to(message, response, parse_mode="Markdown")

def generate_report(days=7):
    """Generates a summary report (header) and detail list separately.
    
    Returns (summary_str, detail_messages_list, game_count).
    days=7  -> from most recent Monday (start of week)
    days=30 -> from 1st of current month
    """
    if not game_database:
        load_database()
    
    now = datetime.now()
    if days <= 7:
        # From most recent Monday (weekday 0 = Monday)
        days_since_monday = now.weekday()  # 0=Mon, 6=Sun
        cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        period_name = "TUẦN"
    else:
        # From 1st of current month
        cutoff_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_name = "THÁNG"
    
    new_games = []
    
    for game in game_database:
        date_str = game.get('date')
        if date_str:
            try:
                game_date = datetime.strptime(date_str, "%d/%m/%Y")
                if game_date >= cutoff_date:
                    new_games.append(game)
            except (ValueError, TypeError):
                continue
                
    if not new_games:
        return None, None, 0
    
    unique_dates = set(g.get('date', '') for g in new_games if g.get('date'))
    active_days = len(unique_dates)
    avg_per_day = round(len(new_games) / active_days, 1) if active_days > 0 else 0
    
    # Group by company
    companies = {}
    for g in new_games:
        name = g['company'].strip()
        name = name.replace("CÔNG TY CỔ PHẦN ", "").replace("CÔNG TY TNHH ", "")
        name = name.replace("CÔNG TY CP ", "").replace(" -", "")
        companies[name] = companies.get(name, 0) + 1
    top_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)[:5]
    max_count = top_companies[0][1] if top_companies else 1
    
    # --- Summary message ---
    summary = f"━━━━━━━━━━━━━━━━━━━━\n"
    summary += f"📊 *BÁO CÁO {period_name} {now.strftime('%m/%Y')}*\n"
    summary += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    summary += f"📅 Kỳ: {cutoff_date.strftime('%d/%m')} → {now.strftime('%d/%m/%Y')}\n"
    summary += f"🎮 Tổng game mới: *{len(new_games)}*\n"
    summary += f"📆 Số ngày có game mới: {active_days}\n"
    summary += f"📈 Trung bình: {avg_per_day} game/ngày\n\n"
    
    summary += "🏢 *NHÀ PHÁT HÀNH:*\n"
    for comp, count in top_companies:
        bar_len = int((count / max_count) * 8)
        bar = "█" * max(bar_len, 1)
        comp_short = (comp[:20] + "..") if len(comp) > 22 else comp
        summary += f"  {comp_short}  {bar} {count}\n"
    
    # --- Detail messages (full game list) ---
    games_by_date = {}
    for g in new_games:
        d = g.get('date', 'N/A')
        if d not in games_by_date:
            games_by_date[d] = []
        games_by_date[d].append(g)
    
    sorted_dates = sorted(games_by_date.keys(), 
        key=lambda x: datetime.strptime(x, "%d/%m/%Y") if x != 'N/A' else datetime.min, 
        reverse=True)
    
    detail_messages = []
    game_list = "📋 *DANH SÁCH ĐẦY ĐỦ:*\n"
    for date_key in sorted_dates:
        games = games_by_date[date_key]
        game_list += f"\n🔸 *{date_key}* ({len(games)} game)\n"
        for g in games:
            g_name = (g['name'][:28] + '..') if len(g['name']) > 30 else g['name']
            company_short = g.get('company', '').replace("CÔNG TY CỔ PHẦN ", "").replace("CÔNG TY TNHH ", "").replace(" -", "").strip()
            company_short = (company_short[:15] + '..') if len(company_short) > 17 else company_short
            game_list += f"  • {g_name} — {company_short}\n"
        
        if len(game_list) > 3500:
            detail_messages.append(game_list)
            game_list = ""
    
    if game_list:
        detail_messages.append(game_list)
    
    return summary, detail_messages, len(new_games)

# Cache for storing detail messages pending user confirmation
_report_cache = {}

@bot.message_handler(commands=['week'])
def week_handle(message):
    summary, details, count = generate_report(days=7)
    if summary:
        cache_key = f"week_{message.chat.id}"
        _report_cache[cache_key] = details
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Xem đầy đủ", callback_data=cache_key))
        bot.send_message(message.chat.id, summary, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.reply_to(message, "📊 Không có game mới nào trong 7 ngày qua.")

@bot.message_handler(commands=['month'])
def month_handle(message):
    summary, details, count = generate_report(days=30)
    if summary:
        cache_key = f"month_{message.chat.id}"
        _report_cache[cache_key] = details
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Xem đầy đủ", callback_data=cache_key))
        bot.send_message(message.chat.id, summary, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.reply_to(message, "📊 Không có game mới nào trong 30 ngày qua.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("week_", "month_")))
def report_detail_callback(call):
    cache_key = call.data
    details = _report_cache.pop(cache_key, None)
    if details:
        bot.answer_callback_query(call.id, "Đang gửi danh sách...")
        for msg in details:
            bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "Báo cáo đã hết hạn. Gõ lại /week hoặc /month.")

def send_weekly_report():
    """Automated task for Monday mornings — sends summary only."""
    summary, details, count = generate_report(days=7)
    if summary:
        send_message(summary)
    else:
        logging.info("No new games for automated weekly report.")

def send_monthly_report():
    """Automated task for 1st of each month — sends summary only."""
    summary, details, count = generate_report(days=30)
    if summary:
        send_message(summary)
    else:
        logging.info("No new games for automated monthly report.")

def daily_scrape():
    """Checks for new games with retry logic. Never miss a notification.
    
    - Runs quick_check via subprocess
    - Retries up to 3 times on failure (5 min apart)
    - Sends Telegram notification for new games
    """
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        logging.info(f"Quick check attempt {attempt}/{max_retries}...")
        try:
            old_count = len(game_database)
            result = subprocess.run(
                [sys.executable, "scraper_full.py", "--quick"],
                check=True, timeout=120, capture_output=True, text=True
            )
            logging.info(f"Quick check output: {result.stdout.strip()}")
            load_database()
            new_count = len(game_database)
            diff = new_count - old_count
            if diff > 0:
                new_games = game_database[:diff]
                new_games_info = ""
                for g in new_games:
                    company_short = g.get('company', '').replace("CÔNG TY CỔ PHẦN ", "").replace("CÔNG TY TNHH ", "").replace(" -", "").strip()
                    company_short = (company_short[:25] + '..') if len(company_short) > 27 else company_short
                    new_games_info += f"  • *{g.get('name', '?')}* ({g.get('date', 'N/A')})\n"
                    new_games_info += f"    🏢 {company_short}\n"
                send_message(
                    f"🔔 *GAME MỚI ĐƯỢC CẤP PHÉP!*\n\n"
                    f"✅ Phát hiện *{diff} game mới!*\n\n"
                    f"{new_games_info}\n"
                    f"📊 Tổng: {new_count} game trong database."
                )
                logging.info(f"✅ ALERT SENT: {diff} new games. Total: {new_count}")
                # --- Watchlist check ---
                keywords = load_watchlist()
                if keywords:
                    for g in new_games:
                        company = g.get('company', '').lower()
                        for kw in keywords:
                            if kw in company:
                                send_message(
                                    f"\U0001f514\U0001f514 *WATCH ALERT!*\n\n"
                                    f"🏢 Công ty bạn đang theo dõi (`{kw}`) vừa có game mới!\n\n"
                                    f"🎮 *{g.get('name', '?')}*\n"
                                    f"📜 {g.get('license', '')}\n"
                                    f"📅 {g.get('date', 'N/A')}\n"
                                    f"🌐 {g.get('domain', '')}\n"
                                    f"🔗 https://giayphep.abei.gov.vn/g1/{g.get('id', '')}"
                                )
                                logging.info(f"Watch alert sent for keyword '{kw}': {g.get('name')}.")
                                break  # One alert per game
            else:
                logging.info(f"\u2705 Quick check OK: No new games. Total: {new_count}")
            return  # Success, exit retry loop
            
        except subprocess.TimeoutExpired:
            logging.error(f"Quick check attempt {attempt}: Timed out after 2 minutes.")
        except Exception as e:
            logging.error(f"Quick check attempt {attempt} failed: {e}")
        
        if attempt < max_retries:
            wait_min = 5 * attempt
            logging.info(f"Retrying in {wait_min} minutes...")
            time.sleep(wait_min * 60)
    
    # All retries failed
    logging.critical("All quick check attempts failed!")
    send_message("\u26a0\ufe0f *C\u1ea2NH B\u00c1O:* Ki\u1ec3m tra game m\u1edbi th\u1ea5t b\u1ea1i sau 3 l\u1ea7n th\u1eed. Vui l\u00f2ng ki\u1ec3m tra th\u1ee7 c\u00f4ng b\u1eb1ng /scrape")

@bot.message_handler(commands=['scrape'])
def scrape_handle(message):
    bot.reply_to(message, "🔄 Đang chạy quick check... (có thể mất vài phút)")
    daily_scrape()
    bot.send_message(message.chat.id, f"✅ Hoàn tất! Database hiện có {len(game_database)} game.")

# --- Backup & Full Scrape Commands ---


@bot.message_handler(commands=['backup'])
def backup_handle(message):
    backup_dir = os.path.join(os.path.dirname(__file__) or '.', 'backups')
    if not os.path.exists(backup_dir):
        bot.reply_to(message, "📂 Chưa có bản backup nào.")
        return
    
    backups = sorted(_glob.glob(os.path.join(backup_dir, "data_backup_*.json")), reverse=True)
    if not backups:
        bot.reply_to(message, "📂 Chưa có bản backup nào.")
        return
    
    text = "💾 *DANH SÁCH BACKUP:*\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, bp in enumerate(backups):
        fname = os.path.basename(bp)
        fsize = os.path.getsize(bp)
        # Parse date from filename
        try:
            ts = fname.replace('data_backup_', '').replace('.json', '')
            dt_obj = datetime.strptime(ts, '%Y%m%d_%H%M%S')
            date_str = dt_obj.strftime('%d/%m/%Y %H:%M:%S')
        except (ValueError, KeyError):
            date_str = fname
        
        # Count games in backup
        try:
            with open(bp, 'r', encoding='utf-8') as f:
                count = len(json.load(f))
        except Exception:
            count = '?'
        
        text += f"{i+1}. `{date_str}` — {count} games ({fsize//1024}KB)\n"
        cache_key = f"restore_{i}"
        _detail_cache[cache_key] = bp
        markup.add(types.InlineKeyboardButton(
            f"🔄 Restore: {date_str}", callback_data=cache_key
        ))
    
    text += f"\n📊 Database hiện tại: *{len(game_database)}* games"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("restore_"))
def restore_callback(call):
    bp = _detail_cache.get(call.data)
    if not bp or not os.path.exists(bp):
        bot.answer_callback_query(call.id, "Backup không tồn tại.")
        return
    
    bot.answer_callback_query(call.id, "Đang restore...")
    try:
        # Backup current before restore
        if os.path.exists(DATA_FILE):
            backup_dir = os.path.join(os.path.dirname(__file__) or '.', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            shutil.copy2(DATA_FILE, os.path.join(backup_dir, f"data_backup_{ts}_pre_restore.json"))
        
        shutil.copy2(bp, DATA_FILE)
        load_database()
        bot.send_message(call.message.chat.id, f"✅ Restore thành công! Database hiện có *{len(game_database)}* games.", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Lỗi restore: {e}")

@bot.message_handler(commands=['fullscrape'])
def fullscrape_handle(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Chạy Full Scrape", callback_data="confirm_fullscrape"),
        types.InlineKeyboardButton("❌ Hủy", callback_data="cancel_fullscrape")
    )
    bot.send_message(
        message.chat.id,
        "⚠️ *Full Scrape* sẽ crawl lại toàn bộ website (~20 phút).\n"
        "Dữ liệu sẽ được *backup* trước và *merge* (không mất game cũ).\n\n"
        "Bạn muốn tiếp tục?",
        parse_mode="Markdown", reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ("confirm_fullscrape", "cancel_fullscrape"))
def fullscrape_callback(call):
    if call.data == "cancel_fullscrape":
        bot.answer_callback_query(call.id, "Đã hủy.")
        bot.edit_message_text("❌ Full scrape đã bị hủy.", call.message.chat.id, call.message.message_id)
        return
    
    bot.answer_callback_query(call.id, "Đang chạy...")
    bot.edit_message_text("🔄 Đang chạy full scrape... (khoảng 20 phút)", call.message.chat.id, call.message.message_id)
    
    def run_fullscrape():
        try:
            old_count = len(game_database)
            result = subprocess.run(
                [sys.executable, "scraper_full.py"],
                check=True, timeout=1800, capture_output=True, text=True
            )
            load_database()
            new_count = len(game_database)
            diff = new_count - old_count
            bot.send_message(
                call.message.chat.id,
                f"✅ *Full Scrape Hoàn Tất!*\n\n"
                f"Trước: {old_count} games\n"
                f"Sau: *{new_count}* games\n"
                f"Thêm mới: {diff} games",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Full scrape lỗi: {e}")
    
    threading.Thread(target=run_fullscrape, daemon=True).start()

# --- Threading ---

def scheduler_thread():
    """Runs the schedule loop in a separate thread."""
    # Check for new games twice daily: morning + evening
    schedule.every().day.at("08:00").do(daily_scrape)
    schedule.every().day.at("18:00").do(daily_scrape)
    # Reload database from disk every hour
    schedule.every(1).hours.do(load_database)
    # Weekly report every Monday at 08:30 AM
    schedule.every().monday.at("08:30").do(send_weekly_report)
    # Monthly report on 1st of each month at 09:00 AM
    schedule.every().day.at("09:00").do(
        lambda: send_monthly_report() if datetime.now().day == 1 else None
    )
    
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    logging.info("Starting Monitor Bot...")
    
    # Set bot command menu (visible in Telegram UI)
    bot.set_my_commands([
        types.BotCommand("help", "📖 Hướng dẫn sử dụng"),
        types.BotCommand("search", "🔍 Tìm game theo từ khóa"),
        types.BotCommand("searchdate", "📅 Tìm game theo thời gian"),
        types.BotCommand("license", "📜 Tìm theo số giấy phép"),
        types.BotCommand("latest", "🆕 Game mới nhất"),
        types.BotCommand("top5", "🏆 Top 5 game mới"),
        types.BotCommand("week", "📊 Báo cáo tuần"),
        types.BotCommand("month", "📊 Báo cáo tháng"),
        types.BotCommand("trend", "📈 Xu hướng cấp phép theo tháng"),
        types.BotCommand("watch", "🔔 Theo dõi công ty"),
        types.BotCommand("unwatch", "🗑 Bỏ theo dõi công ty"),
        types.BotCommand("watchlist", "📋 Danh sách đang theo dõi"),
        types.BotCommand("backup", "💾 Xem/Restore backup"),
        types.BotCommand("fullscrape", "🔃 Scrape toàn bộ (merge)"),
        types.BotCommand("stats", "📈 Thống kê database"),
        types.BotCommand("scrape", "🔄 Quick check game mới"),
        types.BotCommand("status", "✅ Kiểm tra bot"),
    ])
    logging.info("Bot command menu registered.")
    
    # Load Database first
    load_database()
    
    # Start Scheduler
    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()
    
    # Run quick check immediately on startup to catch anything missed
    logging.info("Startup: Running quick check for missed games...")
    startup_thread = threading.Thread(target=daily_scrape, daemon=True)
    startup_thread.start()
    
    # Start Bot Polling (Blocking)
    try:
        logging.info("Bot polling started...")
        bot.infinity_polling()
    except Exception as e:
        logging.error(f"Bot polling crashed: {e}")

if __name__ == "__main__":
    main()
