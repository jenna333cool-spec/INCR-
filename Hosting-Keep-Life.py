import subprocess
import sys
import os

required_modules = {
    'telebot': 'pyTelegramBotAPI',
    'requests': 'requests',
    'Crypto': 'pycryptodome'
}
missing_packages = []

for module, package in required_modules.items():
    try:
        __import__(module)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print(f"📦 جاري تثبيت الحزم المفقودة: {missing_packages}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
        print("✅ تم التثبيت بنجاح، يرجى إعادة تشغيل السكريبت.")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"❌ فشل التثبيت: {e}")
        sys.exit(1)

import telebot
import json
import threading
import time
import random
import string
import re
import requests
import zipfile
import hashlib
import base64
from telebot import types
from datetime import datetime, timedelta
from html import escape
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

def silent_stay_alive():
    links = [
        "https://www.google.com",
        "https://www.bing.com",
        "https://www.wikipedia.org"
    ]
    while True:
        try:
            requests.get(random.choice(links), timeout=15)
            time.sleep(random.randint(120, 240))
        except:
            time.sleep(60)

threading.Thread(target=silent_stay_alive, daemon=True).start()

TOKEN = '8655570041:AAFb4WIwEmzAkadOhRlAf8RyMb9qTdWjUtA'
ADMIN_ID = 8281397757 #id حسابك 
HIDDEN_LONG = "ㅤ" * 50

bot = telebot.TeleBot(TOKEN, threaded=True, parse_mode="HTML")

# Use Railway's persistent volume if available, otherwise use local directory
BASE_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(os.path.abspath(__file__)))
RUNNING_DIR = os.path.join(BASE_DIR, 'active_bots')
LOGS_DIR = os.path.join(BASE_DIR, 'bot_logs')
DB_DIR = os.path.join(BASE_DIR, 'database')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
STORE_DIR = os.path.join(BASE_DIR, 'store_files')
THUMBS_DIR = os.path.join(ASSETS_DIR, 'thumbs')
MARKET_DIR = os.path.join(BASE_DIR, 'market')
ENV_DIR = os.path.join(BASE_DIR, 'bot_environments')
ENCRYPTED_DIR = os.path.join(BASE_DIR, 'encrypted_files')

for d in [RUNNING_DIR, LOGS_DIR, DB_DIR, ASSETS_DIR, STORE_DIR, THUMBS_DIR, MARKET_DIR, ENV_DIR, ENCRYPTED_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

USERS_DB = os.path.join(DB_DIR, 'users.json')
FILES_DB = os.path.join(DB_DIR, 'files.json')
SETTINGS_DB = os.path.join(DB_DIR, 'settings.json')
STORE_DB = os.path.join(DB_DIR, 'store.json')
ADMINS_DB = os.path.join(DB_DIR, 'admins.json')
MARKET_DB = os.path.join(DB_DIR, 'market.json')
SECURITY_DB = os.path.join(DB_DIR, 'security.json')

db_lock = threading.Lock()
cancel_states = {}
last_bot_messages = {}
active_processes = {}
process_hours = {}
user_notifications = {}

def read_json(path):
    with db_lock:
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}

def write_json(path, data):
    with db_lock:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

def init_db():
    default_settings = {
        "channels": [],
        "bot_name": "HOSTING PYTHON",
        "bot_image": None,
        "file_thumb": None,
        "bot_locked": False,
        "auto_approve": True
    }
    current_settings = read_json(SETTINGS_DB)
    for key, value in default_settings.items():
        if key not in current_settings:
            current_settings[key] = value
    write_json(SETTINGS_DB, current_settings)
    
    for path in [USERS_DB, FILES_DB, STORE_DB, MARKET_DB, SECURITY_DB]:
        if not os.path.exists(path):
            write_json(path, {})
    
    if not os.path.exists(ADMINS_DB):
        write_json(ADMINS_DB, {"admins": [ADMIN_ID]})
    else:
        admins_data = read_json(ADMINS_DB)
        if ADMIN_ID not in admins_data.get("admins", []):
            admins_data["admins"] = admins_data.get("admins", []) + [ADMIN_ID]
            write_json(ADMINS_DB, admins_data)
    
    for uid in user_notifications:
        user_notifications[uid] = True
    
    init_security()

def init_security():
    security = read_json(SECURITY_DB)
    if 'master_key' not in security:
        master_key = base64.b64encode(get_random_bytes(32)).decode('utf-8')
        security['master_key'] = master_key
        security['file_keys'] = {}
        write_json(SECURITY_DB, security)

def get_master_key():
    security = read_json(SECURITY_DB)
    master_key = security.get('master_key')
    if not master_key:
        master_key = base64.b64encode(get_random_bytes(32)).decode('utf-8')
        security['master_key'] = master_key
        write_json(SECURITY_DB, security)
    return base64.b64decode(master_key)

def generate_file_key(fid, user_id):
    security = read_json(SECURITY_DB)
    file_keys = security.get('file_keys', {})
    
    if fid not in file_keys:
        combined = f"{fid}:{user_id}:{ADMIN_ID}:{TOKEN}"
        salt = hashlib.sha256(combined.encode()).digest()[:16]
        
        master_key = get_master_key()
        kdf = hashlib.pbkdf2_hmac('sha256', master_key, salt, 100000, dklen=32)
        
        file_keys[fid] = {
            'key': base64.b64encode(kdf).decode('utf-8'),
            'salt': base64.b64encode(salt).decode('utf-8'),
            'user_id': user_id
        }
        security['file_keys'] = file_keys
        write_json(SECURITY_DB, security)
    
    return file_keys[fid]

def get_file_key(fid):
    security = read_json(SECURITY_DB)
    file_keys = security.get('file_keys', {})
    return file_keys.get(fid)

def encrypt_file_content(content, fid, user_id):
    try:
        file_key_info = generate_file_key(fid, user_id)
        key = base64.b64decode(file_key_info['key'])
        salt = base64.b64decode(file_key_info['salt'])
        
        cipher = AES.new(key, AES.MODE_CBC)
        ct_bytes = cipher.encrypt(pad(content.encode('utf-8'), AES.block_size))
        
        encrypted_data = {
            'iv': base64.b64encode(cipher.iv).decode('utf-8'),
            'ciphertext': base64.b64encode(ct_bytes).decode('utf-8'),
            'salt': base64.b64encode(salt).decode('utf-8'),
            'fid': fid,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        }
        
        return json.dumps(encrypted_data)
    except Exception as e:
        print(f"Encryption error: {e}")
        return None

def decrypt_file_content(encrypted_json, fid):
    try:
        data = json.loads(encrypted_json)
        
        file_key_info = get_file_key(fid)
        if not file_key_info:
            return None
        
        key = base64.b64decode(file_key_info['key'])
        iv = base64.b64decode(data['iv'])
        ct = base64.b64decode(data['ciphertext'])
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        
        return pt.decode('utf-8')
    except Exception as e:
        print(f"Decryption error: {e}")
        return None

def save_encrypted_file(fid, content, user_id):
    encrypted_content = encrypt_file_content(content, fid, user_id)
    if encrypted_content:
        encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
        with open(encrypted_path, 'w', encoding='utf-8') as f:
            f.write(encrypted_content)
        return True
    return False

def load_encrypted_file(fid):
    encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
    if os.path.exists(encrypted_path):
        with open(encrypted_path, 'r', encoding='utf-8') as f:
            encrypted_content = f.read()
        return decrypt_file_content(encrypted_content, fid)
    return None

def save_running_file(fid, content):
    running_path = os.path.join(RUNNING_DIR, f"{fid}.py")
    with open(running_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return running_path

def verify_file_access(fid, user_id):
    files = read_json(FILES_DB)
    if fid not in files:
        return False
    
    file_info = files[fid]
    file_user_id = file_info.get('user_id')
    
    if user_id == ADMIN_ID or is_admin(user_id):
        return True
    
    if file_user_id == user_id:
        return True
    
    if file_info.get('type') == 'store':
        store = read_json(STORE_DB)
        if fid in store:
            return True
    
    return False

def get_settings():
    return read_json(SETTINGS_DB)

def save_settings(settings):
    write_json(SETTINGS_DB, settings)

def is_bot_locked():
    return get_settings().get('bot_locked', False)

def toggle_bot_lock():
    settings = get_settings()
    settings['bot_locked'] = not settings.get('bot_locked', False)
    save_settings(settings)
    return settings['bot_locked']

def toggle_auto_approve():
    settings = get_settings()
    settings['auto_approve'] = not settings.get('auto_approve', True)
    save_settings(settings)
    return settings['auto_approve']

def is_admin(user_id):
    if user_id == ADMIN_ID:
        return True
    admins_data = read_json(ADMINS_DB)
    return user_id in admins_data.get("admins", [])

def is_main_admin(user_id):
    return user_id == ADMIN_ID

def get_admins():
    admins_data = read_json(ADMINS_DB)
    return admins_data.get("admins", [ADMIN_ID])

def add_admin(user_id):
    admins_data = read_json(ADMINS_DB)
    if user_id not in admins_data.get("admins", []):
        admins_data["admins"] = admins_data.get("admins", []) + [user_id]
        write_json(ADMINS_DB, admins_data)
        return True
    return False

def remove_admin(user_id):
    if user_id == ADMIN_ID:
        return False
    admins_data = read_json(ADMINS_DB)
    if user_id in admins_data.get("admins", []):
        admins_data["admins"].remove(user_id)
        write_json(ADMINS_DB, admins_data)
        return True
    return False

def deco(title, content):
    settings = get_settings()
    name = settings.get('bot_name', 'HOSTING PYTHON')
    return f"┌─⊷『 {title} 』\n│\n├ {content}\n│\n└─⊷ <b>{name}</b>\n<code>الذئب الأبيض @j49_c</code>\n{HIDDEN_LONG}"

def delete_last_message(chat_id):
    if chat_id in last_bot_messages:
        try:
            bot.delete_message(chat_id, last_bot_messages[chat_id])
        except:
            pass

def save_message(chat_id, msg_id):
    last_bot_messages[chat_id] = msg_id

def send_msg(chat_id, text, markup=None):
    delete_last_message(chat_id)
    settings = get_settings()
    try:
        if settings.get('bot_image'):
            msg = bot.send_photo(chat_id, settings['bot_image'], caption=text, parse_mode="HTML", reply_markup=markup)
        else:
            msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_message(chat_id, msg.message_id)
        return msg
    except:
        msg = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        save_message(chat_id, msg.message_id)
        return msg

def edit_msg(call, text, markup):
    try:
        if call.message.content_type == 'photo':
            bot.edit_message_caption(text[:4096], call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        else:
            bot.edit_message_text(text[:4096], call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        save_message(call.message.chat.id, call.message.message_id)
    except:
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        settings = get_settings()
        try:
            if settings.get('bot_image'):
                msg = bot.send_photo(call.message.chat.id, settings['bot_image'], caption=text[:4096], parse_mode="HTML", reply_markup=markup)
            else:
                msg = bot.send_message(call.message.chat.id, text[:4096], parse_mode="HTML", reply_markup=markup)
            save_message(call.message.chat.id, msg.message_id)
        except:
            msg = bot.send_message(call.message.chat.id, text[:4096], parse_mode="HTML", reply_markup=markup)
            save_message(call.message.chat.id, msg.message_id)

def del_msg(chat_id, *msg_ids):
    for msg_id in msg_ids:
        if msg_id:
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass

def is_user_pro(uid):
    if uid == ADMIN_ID or is_admin(uid):
        return True
    users = read_json(USERS_DB)
    u = users.get(str(uid), {})
    expiry = u.get('expiry')
    if not expiry or expiry == 'null':
        return False
    if expiry == 'LIFETIME' or expiry == 0:
        return True
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        if datetime.now() < exp_date:
            return True
        else:
            u['expiry'] = None
            users[str(uid)] = u
            write_json(USERS_DB, users)
            return False
    except:
        return False

def check_sub(user_id):
    if user_id == ADMIN_ID or is_admin(user_id):
        return True
    settings = get_settings()
    channels = settings.get('channels', [])
    if not channels:
        return True
    try:
        for ch in channels:
            member = bot.get_chat_member(ch["username"], user_id)
            if member.status in ['left', 'kicked']:
                return False
        return True
    except:
        return True

def get_preview(path, lines=40):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.readlines()
                preview = "".join(content[:lines])
                safe = escape(preview)
                if len(safe) > 3000:
                    safe = safe[:3000] + "\n..."
                return f"<pre><code class='language-python'>{safe}</code></pre>"
        return "❌ تعذر قراءة الملف"
    except:
        return "❌ خطأ في القراءة"

def get_logs(fid, lines=40):
    log_path = os.path.join(LOGS_DIR, f"{fid}.log")
    try:
        if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                last = all_lines[-lines:] if len(all_lines) > lines else all_lines
                output = "".join(last)
                safe = escape(output)
                if len(safe) > 3000:
                    safe = safe[:3000] + "\n..."
                return f"<pre><code>{safe}</code></pre>"
        return "📝 لا توجد مخرجات"
    except:
        return "❌ خطأ في القراءة"

def update_token(path, new_token):
    keywords = ["TOKEN", "bot_token", "api_key", "tok", "TKN", "BOT_TKN", "API_TOKEN"]
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = r"(['\"])\d{8,12}:[a-zA-Z0-9_-]{35,}(['\"])"
        new_content = re.sub(pattern, f"\\1{new_token}\\2", content)
        for kw in keywords:
            kw_pattern = rf"{kw}\s*=\s*(['\"])[^'\"]+(['\"])"
            new_content = re.sub(kw_pattern, f"{kw} = \\1{new_token}\\2", new_content)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    except:
        return False

def check_token(token):
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        res = requests.get(url, timeout=15).json()
        if res.get("ok"):
            return True, res["result"]
        return False, res.get("description")
    except Exception as e:
        return False, str(e)

def gen_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def set_cancel(uid, state=True):
    cancel_states[uid] = state

def is_cancelled(uid):
    return cancel_states.get(uid, False)

def clear_cancel(uid):
    if uid in cancel_states:
        del cancel_states[uid]

def get_thumb():
    settings = get_settings()
    thumb = settings.get('file_thumb')
    if thumb and os.path.exists(thumb):
        return thumb
    return None

def locked_msg(chat_id):
    text = "🔒 <b>البوت مغلق حالياً</b>\n\nتم إيقاف الخدمة مؤقتاً\n\nيمكنك التواصل عبر الزر أدناه."
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👨‍💻 تواصل مع المطور", url=f"tg://user?id={ADMIN_ID}"))
    send_msg(chat_id, deco("🔒 البوت مغلق", text), markup)

def start_script(fid):
    files = read_json(FILES_DB)
    if fid not in files:
        return False
    
    file_info = files[fid]
    user_id = file_info.get('user_id')
    
    if not verify_file_access(fid, user_id):
        return False
    
    encrypted_content = load_encrypted_file(fid)
    if not encrypted_content:
        return False
    
    env_dir = os.path.join(ENV_DIR, fid)
    if not os.path.exists(env_dir):
        os.makedirs(env_dir)
    
    env_file_path = os.path.join(env_dir, f"{fid}.py")
    
    if fid in active_processes and active_processes[fid].poll() is None:
        return True
    
    try:
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(encrypted_content)
    except:
        return False
    
    log_path = os.path.join(LOGS_DIR, f"{fid}.log")
    try:
        log_file = open(log_path, "a", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-u", env_file_path],
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE,
            cwd=env_dir,
            start_new_session=True,
            env={**os.environ, "PYTHONPATH": env_dir}
        )
        active_processes[fid] = proc
        return True
    except:
        return False

def stop_script(fid):
    if fid in active_processes:
        proc = active_processes[fid]
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except:
            try:
                proc.terminate()
            except:
                pass
        del active_processes[fid]
        if fid in process_hours:
            del process_hours[fid]
        return True
    return False

def stop_all_scripts():
    for fid in list(active_processes.keys()):
        stop_script(fid)
    return True

def write_proc(fid, cmd):
    if fid in active_processes and active_processes[fid].poll() is None:
        try:
            proc = active_processes[fid]
            if proc.stdin:
                proc.stdin.write(cmd.encode('utf-8') + b'\n')
                proc.stdin.flush()
                return True
        except:
            pass
    return False

def create_zip(files_list, zip_name):
    zip_path = os.path.join(BASE_DIR, zip_name)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in files_list:
            if os.path.exists(file_path):
                zipf.write(file_path, os.path.basename(file_path))
    return zip_path

def auto_fix_errors(code):
    fixes = [
        (r'print\s+(\S+)', r'print(\1)'),
        (r'raw_input', 'input'),
        (r'xrange', 'range'),
        (r'\.iteritems\(\)', '.items()'),
        (r'\.itervalues\(\)', '.values()'),
        (r'\.iterkeys\(\)', '.keys()'),
    ]
    for pattern, replacement in fixes:
        code = re.sub(pattern, replacement, code)
    return code

def main_kb(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📤 رفع ملف جديد", callback_data="nav_upload"))
    kb.row(
        types.InlineKeyboardButton("📁 ملفاتي", callback_data="nav_files"),
        types.InlineKeyboardButton("🛒 المتجر", callback_data="nav_store")
    )
    kb.row(
        types.InlineKeyboardButton("💼 محفظتي", callback_data="nav_wallet"),
        types.InlineKeyboardButton("📊 حسابي", callback_data="nav_stats")
    )
    kb.row(
        types.InlineKeyboardButton("🛠 تثبيت مكتبة", callback_data="nav_lib"),
        types.InlineKeyboardButton("📖 التعليمات", callback_data="nav_help")
    )
    if is_user_pro(uid):
        kb.row(
            types.InlineKeyboardButton("🔧 لوحة Pro", callback_data="nav_pro")
        )
    kb.add(types.InlineKeyboardButton("👨‍💻 تواصل مع المطور", url=f"tg://user?id={ADMIN_ID}"))
    if is_admin(uid):
        kb.add(types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="nav_admin"))
    return kb

def pro_panel_kb(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📥 تحميل جميع الملفات", callback_data="pro_download_all"))
    kb.add(types.InlineKeyboardButton("🔍 فحص تلقائي", callback_data="pro_auto_fix"))
    kb.add(types.InlineKeyboardButton("▶️ تشغيل تجريبي", callback_data="pro_test_run"))
    kb.add(types.InlineKeyboardButton("🛒 بيع في المتجر", callback_data="pro_sell"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
    return kb

def cancel_kb(data="cancel"):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data=data))
    return kb

def back_kb(data="nav_main"):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=data))
    return kb

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    try:
        uid = msg.from_user.id
        if is_bot_locked() and not is_admin(uid):
            try:
                bot.delete_message(msg.chat.id, msg.message_id)
            except:
                pass
            locked_msg(msg.chat.id)
            return
        users = read_json(USERS_DB)
        clear_cancel(uid)
        if str(uid) not in users:
            if len(msg.text.split()) > 1:
                ref = msg.text.split()[1]
                if ref.isdigit() and int(ref) != uid:
                    udb = read_json(USERS_DB)
                    if str(ref) in udb:
                        udb[str(ref)]['points'] = udb[str(ref)].get('points', 0) + 10
                        write_json(USERS_DB, udb)
                        try:
                            bot.send_message(int(ref), deco("🎁 مكافأة", "حصلت على 10 نقاط لإحالة شخص!"))
                        except:
                            pass
            users[str(uid)] = {
                'username': msg.from_user.username,
                'first_name': msg.from_user.first_name,
                'last_name': msg.from_user.last_name,
                'points': 10,
                'join_date': str(datetime.now().date()),
                'is_banned': 0,
                'expiry': None,
                'last_daily': None,
                'notifications': True
            }
            write_json(USERS_DB, users)
            user_notifications[uid] = True
            try:
                name = escape(f"{msg.from_user.first_name} {msg.from_user.last_name or ''}")
                uname = f"@{msg.from_user.username}" if msg.from_user.username else "لا يوجد"
                cap = f"🆕 <b>مستخدم جديد</b>\n\n👤 {name}\n🆔 <code>{uid}</code>\n🔗 {uname}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                for adm in get_admins():
                    try:
                        photos = bot.get_user_profile_photos(uid)
                        if photos.total_count > 0:
                            bot.send_photo(adm, photos.photos[0][-1].file_id, caption=cap, parse_mode="HTML")
                        else:
                            bot.send_message(adm, cap, parse_mode="HTML")
                    except:
                        pass
            except:
                pass
        users = read_json(USERS_DB)
        if users.get(str(uid), {}).get('is_banned', 0) == 1:
            return bot.send_message(msg.chat.id, deco("🚫 محظور", "تم حظرك من البوت."))
        if not check_sub(uid):
            return sub_msg(msg.chat.id)
        try:
            bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass
        settings = get_settings()
        u = users.get(str(uid), {})
        vip = is_user_pro(uid)
        text = f"👋 أهلاً <b>{escape(msg.from_user.first_name)}</b>!\n\n💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n💰 نقاطك: <code>{u.get('points', 0)}</code>\n📅 عضو منذ: {u.get('join_date', 'اليوم')}"
        send_msg(msg.chat.id, deco("🏠 القائمة الرئيسية", text), main_kb(uid))
    except Exception as e:
        print(f"Start Error: {e}")

def sub_msg(chat_id):
    settings = get_settings()
    channels = settings.get('channels', [])
    if not channels:
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        kb.add(types.InlineKeyboardButton(f"📢 {ch['name']}", url=f"https://t.me/{ch['username'].replace('@', '')}"))
    kb.add(types.InlineKeyboardButton("✅ تحقق", callback_data="check_sub"))
    text = "🔔 <b>اشتراك إجباري</b>\n\nيجب الاشتراك في القنوات التالية:"
    send_msg(chat_id, deco("🔔 اشتراك مطلوب", text), kb)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        uid = call.from_user.id
        cid = call.message.chat.id
        data = call.data
        users = read_json(USERS_DB)
        if is_bot_locked() and not is_admin(uid):
            bot.answer_callback_query(call.id, "🔒 البوت مغلق!", show_alert=True)
            locked_msg(cid)
            return
        if str(uid) in users and users[str(uid)].get('is_banned', 0) == 1:
            return bot.answer_callback_query(call.id, "🚫 أنت محظور!", show_alert=True)
        if data == "cancel":
            set_cancel(uid, True)
            bot.answer_callback_query(call.id, "✅ تم الإلغاء")
            u = users.get(str(uid), {})
            vip = is_user_pro(uid)
            text = f"💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n💰 نقاطك: <code>{u.get('points', 0)}</code>"
            edit_msg(call, deco("🏠 القائمة الرئيسية", text), main_kb(uid))
            return
        if data == "cancel_admin":
            set_cancel(uid, True)
            bot.answer_callback_query(call.id, "✅ تم الإلغاء")
            admin_panel(call)
            return
        if data == "check_sub":
            if check_sub(uid):
                bot.answer_callback_query(call.id, "✅ تم التحقق!")
                u = users.get(str(uid), {})
                vip = is_user_pro(uid)
                text = f"💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n💰 نقاطك: <code>{u.get('points', 0)}</code>"
                edit_msg(call, deco("🏠 القائمة الرئيسية", text), main_kb(uid))
            else:
                bot.answer_callback_query(call.id, "❌ لم تشترك!", show_alert=True)
            return
        if not check_sub(uid) and not is_admin(uid):
            bot.answer_callback_query(call.id, "❌ اشترك أولاً!", show_alert=True)
            return
        clear_cancel(uid)
        if data == "nav_main":
            u = users.get(str(uid), {})
            vip = is_user_pro(uid)
            text = f"💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n💰 نقاطك: <code>{u.get('points', 0)}</code>"
            edit_msg(call, deco("🏠 القائمة الرئيسية", text), main_kb(uid))
        elif data == "nav_pro":
            if not is_user_pro(uid):
                bot.answer_callback_query(call.id, "❌ لمشتركي VIP فقط!", show_alert=True)
                return
            text = "🔧 <b>لوحة VIP المميزة</b>\n\nاستمتع بمزايا حصرية لمشتركي VIP"
            edit_msg(call, deco("🔧 لوحة Pro", text), pro_panel_kb(uid))
        elif data == "pro_download_all":
            if not is_user_pro(uid):
                bot.answer_callback_query(call.id, "❌ لمشتركي VIP فقط!", show_alert=True)
                return
            files = read_json(FILES_DB)
            u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
            if not u_files:
                bot.answer_callback_query(call.id, "📂 لا ملفات!", show_alert=True)
                return
            decrypted_files = []
            for fid in u_files.keys():
                if verify_file_access(fid, uid):
                    content = load_encrypted_file(fid)
                    if content:
                        temp_path = os.path.join(BASE_DIR, f"temp_{fid}_{gen_id(4)}.py")
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        decrypted_files.append(temp_path)
            if decrypted_files:
                zip_name = f"files_{uid}_{gen_id(4)}.zip"
                zip_path = create_zip(decrypted_files, zip_name)
                try:
                    with open(zip_path, 'rb') as f:
                        bot.send_document(cid, f, caption="📦 جميع ملفاتك في أرشيف واحد")
                    for temp_file in decrypted_files:
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    os.remove(zip_path)
                except:
                    bot.answer_callback_query(call.id, "❌ فشل في التحميل!", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ لا ملفات للتحميل!", show_alert=True)
        elif data == "pro_auto_fix":
            if not is_user_pro(uid):
                bot.answer_callback_query(call.id, "❌ لمشتركي VIP فقط!", show_alert=True)
                return
            m = bot.send_message(cid, deco("🔍 فحص تلقائي", "أرسل ملف .py لفحصه وتصحيح الأخطاء:"), reply_markup=cancel_kb())
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, auto_fix_step, m.message_id)
        elif data == "pro_test_run":
            if not is_user_pro(uid):
                bot.answer_callback_query(call.id, "❌ لمشتركي VIP فقط!", show_alert=True)
                return
            files = read_json(FILES_DB)
            u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
            if not u_files:
                bot.answer_callback_query(call.id, "📂 لا ملفات!", show_alert=True)
                return
            kb = types.InlineKeyboardMarkup(row_width=1)
            for fid, f in u_files.items():
                kb.add(types.InlineKeyboardButton(f"📄 {f.get('file_name', '?')[:25]}", callback_data=f"testrun_{fid}"))
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_pro"))
            edit_msg(call, deco("▶️ تشغيل تجريبي", "اختر ملف للتشغيل التجريبي:"), kb)
        elif data.startswith("testrun_"):
            fid = data.split("_")[1]
            if not verify_file_access(fid, uid):
                bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الوصول!", show_alert=True)
                return
            content = load_encrypted_file(fid)
            if not content:
                bot.answer_callback_query(call.id, "❌ الملف غير موجود!", show_alert=True)
                return
            try:
                exec(compile(content, f"test_{fid}", 'exec'), {})
                bot.answer_callback_query(call.id, "✅ تم التشغيل التجريبي بنجاح!")
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ خطأ: {str(e)[:100]}", show_alert=True)
        elif data == "pro_sell":
            if not is_user_pro(uid):
                bot.answer_callback_query(call.id, "❌ لمشتركي VIP فقط!", show_alert=True)
                return
            m = bot.send_message(cid, deco("🛒 بيع في المتجر", "أرسل ملف .py للبيع:"), reply_markup=cancel_kb())
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, sell_file_step, m.message_id)
        elif data == "nav_wallet":
            u = users.get(str(uid), {})
            vip = is_user_pro(uid)
            exp = "لا يوجد"
            if vip:
                e = u.get('expiry')
                if e == 'LIFETIME' or e == 0:
                    exp = "دائم ♾"
                elif e:
                    exp = e
            today = str(datetime.now().date())
            can = u.get('last_daily') != today
            text = f"💰 رصيدك: <code>{u.get('points', 0)}</code>\n💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n⏰ صلاحية VIP: {exp}\n\n💡 كل نقطة = ساعة"
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton(f"🎁 الهدية {'✅' if can else '❌'}", callback_data="daily"),
                types.InlineKeyboardButton("🔗 رابط الإحالة", callback_data="ref")
            )
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
            edit_msg(call, deco("💼 محفظتي", text), kb)
        elif data == "daily":
            u = users.get(str(uid))
            today = str(datetime.now().date())
            if u.get('last_daily') == today:
                return bot.answer_callback_query(call.id, "❌ حصلت عليها اليوم!", show_alert=True)
            gift = random.randint(5, 15)
            u['points'] = u.get('points', 0) + gift
            u['last_daily'] = today
            users[str(uid)] = u
            write_json(USERS_DB, users)
            bot.answer_callback_query(call.id, f"🎁 حصلت على {gift} نقاط!", show_alert=True)
            vip = is_user_pro(uid)
            text = f"💰 رصيدك: <code>{u.get('points', 0)}</code>\n💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n\n✅ تم إضافة {gift} نقاط!"
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🎁 الهدية ❌", callback_data="daily"),
                types.InlineKeyboardButton("🔗 رابط الإحالة", callback_data="ref")
            )
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
            edit_msg(call, deco("💼 محفظتي", text), kb)
        elif data == "ref":
            info = bot.get_me()
            link = f"https://t.me/{info.username}?start={uid}"
            text = f"🔗 رابطك:\n<code>{link}</code>\n\n💰 كل شخص = 10 نقاط!"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_wallet"))
            edit_msg(call, deco("🔗 رابط الإحالة", text), kb)
        elif data == "nav_help":
            text = "📖 <b>دليل الاستخدام</b>\n\n🚀 الاستضافة:\n• ارفع ملف .py\n• اختر المدة\n• ينتظر الموافقة\n\n💰 النقاط:\n• كل نقطة = ساعة\n• هدية يومية 5-15\n• إحالة = 10\n\n💎 VIP:\n• استضافة غير محدودة\n• بدون خصم نقاط"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("👨‍💻 المطور", url=f"tg://user?id={ADMIN_ID}"))
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
            edit_msg(call, deco("📖 التعليمات", text), kb)
        elif data == "nav_upload":
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🆓 مجانية", callback_data="up_free"),
                types.InlineKeyboardButton("💎 VIP", callback_data="up_pro")
            )
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
            text = "📤 اختر نوع الاستضافة:\n\n🆓 مجانية: بالنقاط\n💎 VIP: غير محدودة"
            edit_msg(call, deco("📤 رفع ملف", text), kb)
        elif data.startswith("up_"):
            h_type = data.split("_")[1]
            if h_type == "pro" and not is_user_pro(uid):
                return bot.answer_callback_query(call.id, "❌ لمشتركي VIP فقط!", show_alert=True)
            if h_type == "free":
                u = users.get(str(uid), {})
                if u.get('points', 0) < 1:
                    return bot.answer_callback_query(call.id, "❌ لا نقاط كافية!", show_alert=True)
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("📤 إرسال الملف", "📥 أرسل ملف .py:"), reply_markup=cancel_kb())
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, upload_step, h_type, m.message_id)
        elif data == "nav_files":
            files = read_json(FILES_DB)
            u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
            if not u_files:
                return bot.answer_callback_query(call.id, "📂 لا ملفات!", show_alert=True)
            kb = types.InlineKeyboardMarkup(row_width=1)
            for fid, f in u_files.items():
                running = fid in active_processes and active_processes[fid].poll() is None
                icon = "🟢" if running else "🔴"
                ft = "💎" if f.get('type') == 'pro' else "🆓"
                kb.add(types.InlineKeyboardButton(f"{icon} {ft} {f.get('file_name', '?')[:25]}", callback_data=f"manage_{fid}"))
            if is_user_pro(uid):
                kb.add(types.InlineKeyboardButton("📦 تحميل الكل (ZIP)", callback_data="pro_download_all"))
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
            running_count = sum(1 for fid in u_files if fid in active_processes and active_processes[fid].poll() is None)
            text = f"📊 الملفات: {len(u_files)}\n🟢 تعمل: {running_count}\n🔴 متوقفة: {len(u_files) - running_count}"
            edit_msg(call, deco("📁 ملفاتي", text), kb)
        elif data.startswith("manage_"):
            file_panel(call, data.split("_")[1])
        elif data.startswith("toggle_"):
            toggle_file(call, data.split("_")[1])
        elif data.startswith("delc_"):
            fid = data.split("_")[1]
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✅ نعم", callback_data=f"del_{fid}"),
                types.InlineKeyboardButton("❌ لا", callback_data=f"manage_{fid}")
            )
            edit_msg(call, deco("🗑️ تأكيد", "هل تريد حذف الملف؟"), kb)
        elif data.startswith("del_"):
            delete_file(call, data.split("_")[1])
        elif data.startswith("dl_"):
            download_file(call, data.split("_")[1])
        elif data.startswith("term_"):
            terminal(call, data.split("_")[1])
        elif data.startswith("rterm_"):
            terminal(call, data.split("_")[1])
        elif data.startswith("inp_"):
            fid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("⌨️ إدخال", "اكتب الأمر:"), reply_markup=cancel_kb())
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, input_step, fid, m.message_id)
        elif data.startswith("chtoken_"):
            fid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("🔑 تغيير التوكن", "أرسل التوكن:"), reply_markup=cancel_kb())
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, token_step, fid, m.message_id)
        elif data.startswith("tokinfo_"):
            token_info(call, data.split("_")[1])
        elif data == "nav_store":
            store_view(call)
        elif data.startswith("buy_"):
            buy_confirm(call, data.split("_")[1])
        elif data.startswith("ebuy_"):
            buy_exec(call, data.split("_")[1])
        elif data == "nav_lib":
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("🛠 تثبيت مكتبة", "أرسل اسم المكتبة:"), reply_markup=cancel_kb())
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, lib_step, m.message_id)
        elif data == "nav_stats":
            files = read_json(FILES_DB)
            u = users.get(str(uid), {})
            u_files = [f for f in files.values() if f.get('user_id') == uid and f.get('status') == 'active']
            running = sum(1 for fid, f in files.items() if f.get('user_id') == uid and fid in active_processes and active_processes[fid].poll() is None)
            vip = is_user_pro(uid)
            exp = "لا يوجد"
            if vip:
                e = u.get('expiry')
                if e == 'LIFETIME' or e == 0:
                    exp = "دائم ♾"
                elif e:
                    try:
                        ed = datetime.strptime(e, "%Y-%m-%d %H:%M:%S")
                        rem = ed - datetime.now()
                        exp = f"{rem.days} يوم"
                    except:
                        exp = e
            text = f"🆔 الآيدي: <code>{uid}</code>\n🔗 المعرف: @{u.get('username', 'لا يوجد')}\n📅 الانضمام: {u.get('join_date', '?')}\n\n💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n⏰ صلاحية VIP: {exp}\n💰 النقاط: <code>{u.get('points', 0)}</code>\n\n📁 الملفات: {len(u_files)}\n🟢 تعمل: {running}"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💼 محفظتي", callback_data="nav_wallet"))
            kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
            edit_msg(call, deco("📊 حسابي", text), kb)
        elif data == "nav_admin" and is_admin(uid):
            admin_panel(call)
        elif data == "lock_bot" and is_admin(uid):
            new = toggle_bot_lock()
            st = "مغلق 🔒" if new else "مفتوح 🔓"
            bot.answer_callback_query(call.id, f"✅ البوت {st}")
            admin_panel(call)
        elif data == "adm_users" and is_admin(uid):
            users_panel(call)
        elif data.startswith("userpage_"):
            page = int(data.split("_")[1])
            users_panel(call, page)
        elif data.startswith("uctrl_") and is_admin(uid):
            user_panel(call, data.split("_")[1])
        elif data.startswith("ban_") and is_admin(uid):
            ban_toggle(call, data.split("_")[1])
        elif data.startswith("pro_") and is_admin(uid):
            tuid = data.split("_")[1]
            if is_user_pro(int(tuid)):
                pro_remove(call, tuid)
            else:
                try:
                    bot.delete_message(cid, call.message.message_id)
                except:
                    pass
                m = bot.send_message(cid, deco("💎 منح VIP", "أرسل عدد الأيام (0 = دائم):"), reply_markup=cancel_kb("cancel_admin"))
                save_message(cid, m.message_id)
                bot.register_next_step_handler(m, pro_grant_step, tuid, m.message_id)
        elif data.startswith("charge_") and is_admin(uid):
            tuid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("💰 شحن", f"أرسل عدد النقاط لـ <code>{tuid}</code>:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, charge_step, tuid, m.message_id)
        elif data.startswith("msguser_") and is_admin(uid):
            tuid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("💬 رسالة", f"اكتب رسالتك لـ <code>{tuid}</code>:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, msg_user_step, tuid, m.message_id)
        elif data == "adm_admins" and is_admin(uid):
            admins_panel(call)
        elif data == "add_admin" and is_main_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("➕ إضافة أدمن", "أرسل آيدي المستخدم:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, add_admin_step, m.message_id)
        elif data == "add_admin" and not is_main_admin(uid):
            bot.answer_callback_query(call.id, "❌ فقط المالك الرئيسي!", show_alert=True)
        elif data.startswith("rmadmin_") and is_admin(uid):
            aid = int(data.split("_")[1])
            if aid == ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ لا يمكن إزالة المالك!", show_alert=True)
            elif not is_main_admin(uid) and aid != uid:
                bot.answer_callback_query(call.id, "❌ فقط المالك يمكنه!", show_alert=True)
            elif remove_admin(aid):
                bot.answer_callback_query(call.id, "✅ تم إزالة الأدمن")
                admins_panel(call)
            else:
                bot.answer_callback_query(call.id, "❌ فشل!", show_alert=True)
        elif data == "adm_store" and is_admin(uid):
            store_panel(call)
        elif data == "add_store" and is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("📥 إضافة ملف", "أرسل الملف:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, store_add_step, m.message_id)
        elif data.startswith("estore_"):
            store_edit(call, data.split("_")[1])
        elif data.startswith("sprice_"):
            sid = data.split("_")[1]
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("💰 السعر", "أرسل السعر:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, store_price_step, sid, m.message_id)
        elif data.startswith("delstore_"):
            store_del(call, data.split("_")[1])
        elif data == "adm_pending" and is_admin(uid):
            pending_list(call)
        elif data.startswith("vpend_") and is_admin(uid):
            pending_view(call, data.split("_")[1])
        elif data.startswith("approve_") and is_admin(uid):
            approve_file(call, data.split("_")[1])
        elif data.startswith("reject_") and is_admin(uid):
            reject_file(call, data.split("_")[1])
        elif data == "adm_broadcast" and is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("📢 إذاعة", "أرسل رسالتك:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, broadcast_step, m.message_id)
        elif data == "adm_settings" and is_admin(uid):
            settings_panel(call)
        elif data == "adm_channels" and is_admin(uid):
            channels_panel(call)
        elif data == "add_channel" and is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("📢 إضافة قناة", "أرسل معرف القناة (@...):"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, add_channel_step, m.message_id)
        elif data.startswith("delch_") and is_admin(uid):
            del_channel(call, int(data.split("_")[1]))
        elif data == "set_img" and is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("🖼 صورة البوت", "أرسل الصورة:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, img_step, m.message_id)
        elif data == "rm_img" and is_admin(uid):
            settings = get_settings()
            settings['bot_image'] = None
            save_settings(settings)
            bot.answer_callback_query(call.id, "✅ تم إزالة الصورة")
            settings_panel(call)
        elif data == "set_thumb" and is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("🎨 أيقونة الملفات", "أرسل الصورة:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, thumb_step, m.message_id)
        elif data == "rm_thumb" and is_admin(uid):
            settings = get_settings()
            if settings.get('file_thumb') and os.path.exists(settings.get('file_thumb', '')):
                try:
                    os.remove(settings['file_thumb'])
                except:
                    pass
            settings['file_thumb'] = None
            save_settings(settings)
            bot.answer_callback_query(call.id, "✅ تم إزالة الأيقونة")
            settings_panel(call)
        elif data == "set_name" and is_admin(uid):
            try:
                bot.delete_message(cid, call.message.message_id)
            except:
                pass
            m = bot.send_message(cid, deco("✏️ اسم البوت", "أرسل الاسم:"), reply_markup=cancel_kb("cancel_admin"))
            save_message(cid, m.message_id)
            bot.register_next_step_handler(m, name_step, m.message_id)
        elif data == "stop_all" and is_admin(uid):
            stop_all_scripts()
            bot.answer_callback_query(call.id, "✅ تم إيقاف جميع البوتات")
            admin_panel(call)
        elif data == "toggle_auto" and is_admin(uid):
            new = toggle_auto_approve()
            st = "مفعّل ✅" if new else "معطّل ❌"
            bot.answer_callback_query(call.id, f"✅ الموافقة التلقائية {st}")
            settings_panel(call)
        elif data == "adm_files" and is_admin(uid):
            all_files_panel(call)
        elif data.startswith("afpage_"):
            page = int(data.split("_")[1])
            all_files_panel(call, page)
        elif data.startswith("afile_"):
            fid = data.split("_")[1]
            file_panel_admin(call, fid)
        elif data == "download_all_files" and is_admin(uid):
            all_files = read_json(FILES_DB)
            decrypted_files = []
            for fid in all_files.keys():
                if verify_file_access(fid, ADMIN_ID):
                    content = load_encrypted_file(fid)
                    if content:
                        temp_path = os.path.join(BASE_DIR, f"temp_{fid}_{gen_id(4)}.py")
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        decrypted_files.append(temp_path)
            if decrypted_files:
                zip_name = f"all_files_{gen_id(4)}.zip"
                zip_path = create_zip(decrypted_files, zip_name)
                try:
                    with open(zip_path, 'rb') as f:
                        bot.send_document(cid, f, caption="📦 جميع ملفات البوت")
                    for temp_file in decrypted_files:
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    os.remove(zip_path)
                except:
                    bot.answer_callback_query(call.id, "❌ فشل في التحميل!", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ لا ملفات للتحميل!", show_alert=True)
    except Exception as e:
        print(f"Callback Error: {e}")

def auto_fix_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document or not msg.document.file_name.endswith('.py'):
        send_msg(msg.chat.id, deco("❌ خطأ", "يجب ملف .py"), back_kb("nav_pro"))
        return
    try:
        finfo = bot.get_file(msg.document.file_id)
        file_content = bot.download_file(finfo.file_path).decode('utf-8')
        fixed_content = auto_fix_errors(file_content)
        fixed_name = f"fixed_{msg.document.file_name}"
        temp_path = os.path.join(BASE_DIR, fixed_name)
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        with open(temp_path, 'rb') as f:
            bot.send_document(msg.chat.id, f, caption="🔧 الملف بعد التصحيح التلقائي")
        os.remove(temp_path)
    except Exception as e:
        send_msg(msg.chat.id, deco("❌ خطأ", f"فشل التصحيح: {str(e)[:200]}"), back_kb("nav_pro"))

def sell_file_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document or not msg.document.file_name.endswith('.py'):
        send_msg(msg.chat.id, deco("❌ خطأ", "يجب ملف .py"), back_kb("nav_pro"))
        return
    m = bot.send_message(msg.chat.id, deco("💰 السعر", f"الملف: <b>{escape(msg.document.file_name)}</b>\n\nأرسل السعر بالنقاط:"), reply_markup=cancel_kb())
    save_message(msg.chat.id, m.message_id)
    bot.register_next_step_handler(m, sell_price_step, msg.document, m.message_id)

def sell_price_step(msg, doc, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        send_msg(msg.chat.id, deco("❌ خطأ", "سعر غير صحيح!"), back_kb("nav_pro"))
        return
    price = int(msg.text.strip())
    market = read_json(MARKET_DB)
    sid = gen_id()
    market[sid] = {
        'name': doc.file_name,
        'price': price,
        'seller_id': uid,
        'seller_name': f"{msg.from_user.first_name} {msg.from_user.last_name or ''}",
        'rating': 0,
        'votes': 0,
        'downloads': 0,
        'category': 'عام',
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    write_json(MARKET_DB, market)
    finfo = bot.get_file(doc.file_id)
    with open(os.path.join(MARKET_DIR, f"{sid}.py"), 'wb') as f:
        f.write(bot.download_file(finfo.file_path))
    send_msg(msg.chat.id, deco("✅ تم", f"تم إضافة ملف للبيع!\n📄 {doc.file_name}\n💰 {price} نقطة"), back_kb("nav_pro"))

def store_view(call):
    store = read_json(STORE_DB)
    if not store:
        return bot.answer_callback_query(call.id, "🛒 المتجر فارغ!", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=2)
    for sid, item in store.items():
        kb.add(types.InlineKeyboardButton(f"📦 {item['name'][:15]} • {item['price']}pt", callback_data=f"buy_{sid}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
    users = read_json(USERS_DB)
    text = f"🛒 متجر الملفات\n\n💰 نقاطك: <code>{users.get(str(call.from_user.id), {}).get('points', 0)}</code>"
    edit_msg(call, deco("🛒 المتجر", text), kb)

def buy_confirm(call, sid):
    store = read_json(STORE_DB)
    item = store.get(sid)
    if not item:
        return
    users = read_json(USERS_DB)
    pts = users.get(str(call.from_user.id), {}).get('points', 0)
    text = f"📦 الملف: {item['name']}\n💰 السعر: {item['price']}\n💵 رصيدك: <code>{pts}</code>\n\n{'✅ نقاط كافية!' if pts >= item['price'] else '❌ نقاط غير كافية!'}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    if pts >= item['price']:
        kb.add(
            types.InlineKeyboardButton("✅ شراء", callback_data=f"ebuy_{sid}"),
            types.InlineKeyboardButton("❌ إلغاء", callback_data="nav_store")
        )
    else:
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_store"))
    edit_msg(call, deco("🛒 تأكيد", text), kb)

def buy_exec(call, sid):
    uid = call.from_user.id
    users = read_json(USERS_DB)
    store = read_json(STORE_DB)
    item = store.get(sid)
    if not item:
        return bot.answer_callback_query(call.id, "❌ غير موجود!", show_alert=True)
    if users.get(str(uid), {}).get('points', 0) < item['price']:
        return bot.answer_callback_query(call.id, "❌ نقاط غير كافية!", show_alert=True)
    users[str(uid)]['points'] -= item['price']
    write_json(USERS_DB, users)
    path = os.path.join(STORE_DIR, f"{sid}.py")
    try:
        thumb = get_thumb()
        with open(path, 'rb') as f:
            if thumb:
                with open(thumb, 'rb') as t:
                    bot.send_document(uid, f, thumb=t, caption=f"✅ تم شراء: {item['name']}", parse_mode="HTML")
            else:
                bot.send_document(uid, f, caption=f"✅ تم شراء: {item['name']}", parse_mode="HTML")
        bot.answer_callback_query(call.id, "✅ تم الشراء!")
        store_view(call)
    except:
        users[str(uid)]['points'] += item['price']
        write_json(USERS_DB, users)
        bot.answer_callback_query(call.id, "❌ خطأ!", show_alert=True)

def admin_panel(call):
    users = read_json(USERS_DB)
    files = read_json(FILES_DB)
    pending = [f for f in files.values() if f.get('status') == 'pending']
    active = sum(1 for fid in active_processes if active_processes[fid].poll() is None)
    settings = get_settings()
    locked = settings.get('bot_locked', False)
    auto_approve = settings.get('auto_approve', True)
    text = f"👥 المستخدمين: {len(users)}\n📁 الملفات: {len(files)}\n⏳ المعلقة: {len(pending)}\n🟢 النشطة: {active}\n👮 الأدمن: {len(get_admins())}\n\n🔐 حالة البوت: {'مغلق 🔒' if locked else 'مفتوح 🔓'}\n✅ الموافقة التلقائية: {'مفعّلة' if auto_approve else 'معطّلة'}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🔓 فتح" if locked else "🔒 قفل", callback_data="lock_bot"))
    kb.add(types.InlineKeyboardButton("✅ موافقة تلقائية" if auto_approve else "❌ موافقة تلقائية", callback_data="toggle_auto"))
    kb.row(
        types.InlineKeyboardButton("👤 المستخدمين", callback_data="adm_users"),
        types.InlineKeyboardButton("👮 الأدمن", callback_data="adm_admins")
    )
    kb.row(
        types.InlineKeyboardButton("🛒 المتجر", callback_data="adm_store"),
        types.InlineKeyboardButton(f"⏳ المعلقة ({len(pending)})", callback_data="adm_pending")
    )
    kb.row(
        types.InlineKeyboardButton("📢 إذاعة", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("📢 القنوات", callback_data="adm_channels")
    )
    kb.row(
        types.InlineKeyboardButton("📁 الملفات", callback_data="adm_files"),
        types.InlineKeyboardButton("⏸️ إيقاف الكل", callback_data="stop_all")
    )
    kb.add(types.InlineKeyboardButton("🖼 الإعدادات", callback_data="adm_settings"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
    edit_msg(call, deco("⚙️ لوحة الإدارة", text), kb)

def users_panel(call, page=0):
    users = read_json(USERS_DB)
    user_ids = list(users.keys())
    items_per_page = 10
    total_pages = (len(user_ids) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_users = user_ids[start_idx:end_idx]
    kb = types.InlineKeyboardMarkup(row_width=2)
    for uid in page_users:
        u = users[uid]
        name = u.get('first_name', 'غير معروف')
        kb.add(types.InlineKeyboardButton(f"👤 {name[:10]}", callback_data=f"uctrl_{uid}"))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️ السابق", callback_data=f"userpage_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("التالي ▶️", callback_data=f"userpage_{page+1}"))
    if nav_buttons:
        kb.row(*nav_buttons)
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_admin"))
    text = f"📊 الصفحة {page+1} من {total_pages}\n👥 إجمالي المستخدمين: {len(users)}"
    edit_msg(call, deco("👤 المستخدمين", text), kb)

def all_files_panel(call, page=0):
    files = read_json(FILES_DB)
    file_ids = list(files.keys())
    items_per_page = 10
    total_pages = (len(file_ids) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_files = file_ids[start_idx:end_idx]
    kb = types.InlineKeyboardMarkup(row_width=2)
    for fid in page_files:
        f = files[fid]
        kb.add(types.InlineKeyboardButton(f"📄 {f.get('file_name', '?')[:15]}", callback_data=f"afile_{fid}"))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️ السابق", callback_data=f"afpage_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("التالي ▶️", callback_data=f"afpage_{page+1}"))
    if nav_buttons:
        kb.row(*nav_buttons)
    kb.add(types.InlineKeyboardButton("📥 تحميل الكل", callback_data="download_all_files"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_admin"))
    text = f"📁 الصفحة {page+1} من {total_pages}\n📊 إجمالي الملفات: {len(files)}"
    edit_msg(call, deco("📁 جميع الملفات", text), kb)

def file_panel_admin(call, fid):
    files = read_json(FILES_DB)
    if fid not in files:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    f = files[fid]
    content = load_encrypted_file(fid)
    preview = "❌ غير مصرح بالوصول"
    if content:
        safe = escape(content[:1000])
        if len(safe) > 3000:
            safe = safe[:3000] + "\n..."
        preview = f"<pre><code class='language-python'>{safe}</code></pre>"
    running = fid in active_processes and active_processes[fid].poll() is None
    text = f"📄 الملف: {f.get('file_name')}\n👤 المستخدم: <code>{f.get('user_id')}</code>\n💎 النوع: {'VIP 👑' if f.get('type') == 'pro' else 'مجاني 🆓'}\n🟢 الحالة: {'يعمل ✅' if running else 'متوقف ❌'}\n📅 {f.get('created_at')}\n\n🔍 الكود (أول 1000 حرف):\n{preview}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="afpage_0"))
    edit_msg(call, deco("📁 ملف", text), kb)

def admins_panel(call):
    uid = call.from_user.id
    admins = get_admins()
    text = f"👮 الأدمن ({len(admins)}):\n\n"
    kb = types.InlineKeyboardMarkup(row_width=1)
    if is_main_admin(uid):
        kb.add(types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="add_admin"))
    for aid in admins:
        try:
            user = bot.get_chat(aid)
            name = user.first_name
            owner = "👑" if aid == ADMIN_ID else "👮"
            text += f"{owner} {escape(name)} - <code>{aid}</code>\n"
            if aid != ADMIN_ID and is_main_admin(uid):
                kb.add(types.InlineKeyboardButton(f"🗑️ إزالة {name[:10]}", callback_data=f"rmadmin_{aid}"))
        except:
            text += f"👮 <code>{aid}</code>\n"
            if aid != ADMIN_ID and is_main_admin(uid):
                kb.add(types.InlineKeyboardButton(f"🗑️ إزالة {aid}", callback_data=f"rmadmin_{aid}"))
    if not is_main_admin(uid):
        text += "\n\n⚠️ فقط المالك يمكنه إضافة/إزالة أدمن"
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_admin"))
    edit_msg(call, deco("👮 الأدمن", text), kb)

def add_admin_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not is_main_admin(uid):
        send_msg(msg.chat.id, deco("❌ خطأ", "فقط المالك!"), back_kb("adm_admins"))
        return
    if not msg.text or not msg.text.strip().isdigit():
        send_msg(msg.chat.id, deco("❌ خطأ", "آيدي غير صحيح!"), back_kb("adm_admins"))
        return
    new_id = int(msg.text.strip())
    if add_admin(new_id):
        try:
            bot.send_message(new_id, deco("🎉 تهانينا", "تم تعيينك أدمن!"))
        except:
            pass
        text = f"✅ تم إضافة: <code>{new_id}</code>"
    else:
        text = "❌ موجود مسبقاً!"
    send_msg(msg.chat.id, deco("👮 إضافة أدمن", text), back_kb("adm_admins"))

def user_panel(call, tuid):
    users = read_json(USERS_DB)
    u = users.get(str(tuid))
    if not u:
        return
    banned = u.get('is_banned', 0) == 1
    vip = is_user_pro(int(tuid))
    exp = "لا يوجد"
    if vip:
        e = u.get('expiry')
        if e == 'LIFETIME' or e == 0:
            exp = "دائم ♾"
        elif e:
            exp = e
    files = read_json(FILES_DB)
    u_files = [f for f in files.values() if f.get('user_id') == int(tuid)]
    text = f"🆔 الآيدي: <code>{tuid}</code>\n🔗 المعرف: @{u.get('username', 'لا يوجد')}\n📅 الانضمام: {u.get('join_date', '?')}\n\n💰 النقاط: <code>{u.get('points', 0)}</code>\n💎 الرتبة: {'VIP 👑' if vip else 'مجاني 🆓'}\n⏰ صلاحية VIP: {exp}\n\n📁 الملفات: {len(u_files)}\n🚫 الحالة: {'محظور ❌' if banned else 'نشط ✅'}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔓 فك الحظر" if banned else "🚫 حظر", callback_data=f"ban_{tuid}"),
        types.InlineKeyboardButton("🆓 سحب VIP" if vip else "💎 منح VIP", callback_data=f"pro_{tuid}")
    )
    kb.add(
        types.InlineKeyboardButton("💰 شحن", callback_data=f"charge_{tuid}"),
        types.InlineKeyboardButton("💬 رسالة", callback_data=f"msguser_{tuid}")
    )
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_users"))
    edit_msg(call, deco("👤 إدارة المستخدم", text), kb)

def charge_step(msg, tuid, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().lstrip('-').isdigit():
        send_msg(msg.chat.id, deco("❌ خطأ", "رقم غير صحيح!"), back_kb(f"uctrl_{tuid}"))
        return
    amount = int(msg.text.strip())
    users = read_json(USERS_DB)
    if str(tuid) in users:
        users[str(tuid)]['points'] = users[str(tuid)].get('points', 0) + amount
        write_json(USERS_DB, users)
        try:
            bot.send_message(int(tuid), deco("💰 شحن", f"تم شحن <b>{amount}</b> نقطة!"))
        except:
            pass
        send_msg(msg.chat.id, deco("✅ تم", f"تم شحن {amount} نقطة"), back_kb(f"uctrl_{tuid}"))

def msg_user_step(msg, tuid, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    try:
        bot.copy_message(int(tuid), msg.chat.id, msg.message_id)
        send_msg(msg.chat.id, deco("✅ تم", "تم الإرسال!"), back_kb(f"uctrl_{tuid}"))
    except:
        send_msg(msg.chat.id, deco("❌ فشل", "تعذر الإرسال!"), back_kb(f"uctrl_{tuid}"))

def pro_grant_step(msg, tuid, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        send_msg(msg.chat.id, deco("❌ خطأ", "رقم غير صحيح!"), back_kb(f"uctrl_{tuid}"))
        return
    days = int(msg.text.strip())
    users = read_json(USERS_DB)
    if str(tuid) in users:
        if days == 0:
            users[str(tuid)]['expiry'] = 'LIFETIME'
            exp_text = "دائم ♾"
        else:
            exp_date = datetime.now() + timedelta(days=days)
            users[str(tuid)]['expiry'] = exp_date.strftime("%Y-%m-%d %H:%M:%S")
            exp_text = f"{days} يوم"
        write_json(USERS_DB, users)
        try:
            bot.send_message(int(tuid), deco("💎 VIP", f"تم ترقيتك!\n⏰ المدة: {exp_text}"))
        except:
            pass
        send_msg(msg.chat.id, deco("✅ تم", f"تم منح VIP لمدة {exp_text}"), back_kb(f"uctrl_{tuid}"))

def ban_toggle(call, tuid):
    users = read_json(USERS_DB)
    if str(tuid) in users:
        curr = users[str(tuid)].get('is_banned', 0)
        users[str(tuid)]['is_banned'] = 0 if curr == 1 else 1
        write_json(USERS_DB, users)
        try:
            if users[str(tuid)]['is_banned'] == 1:
                bot.send_message(int(tuid), deco("🚫 محظور", "تم حظرك!"))
            else:
                bot.send_message(int(tuid), deco("✅ فك الحظر", "تم فك حظرك!"))
        except:
            pass
        bot.answer_callback_query(call.id, "✅ تم")
        user_panel(call, tuid)

def pro_remove(call, tuid):
    users = read_json(USERS_DB)
    if str(tuid) in users:
        users[str(tuid)]['expiry'] = None
        write_json(USERS_DB, users)
        try:
            bot.send_message(int(tuid), deco("⚠️ VIP", "تم إلغاء VIP!"))
        except:
            pass
        bot.answer_callback_query(call.id, "✅ تم سحب VIP")
        user_panel(call, tuid)

def store_panel(call):
    store = read_json(STORE_DB)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("➕ إضافة ملف", callback_data="add_store"))
    for sid, item in store.items():
        kb.add(types.InlineKeyboardButton(f"📦 {item['name'][:20]} • {item['price']}pt", callback_data=f"estore_{sid}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_admin"))
    text = f"📊 الملفات: {len(store)}"
    edit_msg(call, deco("🛒 إدارة المتجر", text), kb)

def store_add_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document:
        send_msg(msg.chat.id, deco("❌ خطأ", "أرسل ملفاً!"), back_kb("adm_store"))
        return
    m = bot.send_message(msg.chat.id, deco("💰 السعر", f"الملف: <b>{escape(msg.document.file_name)}</b>\n\nأرسل السعر:"), reply_markup=cancel_kb("cancel_admin"))
    save_message(msg.chat.id, m.message_id)
    bot.register_next_step_handler(m, store_price_add_step, msg.document, m.message_id)

def store_price_add_step(msg, doc, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        send_msg(msg.chat.id, deco("❌ خطأ", "سعر غير صحيح!"), back_kb("adm_store"))
        return
    sid = gen_id()
    store = read_json(STORE_DB)
    store[sid] = {'name': doc.file_name, 'price': int(msg.text.strip())}
    write_json(STORE_DB, store)
    finfo = bot.get_file(doc.file_id)
    with open(os.path.join(STORE_DIR, f"{sid}.py"), 'wb') as f:
        f.write(bot.download_file(finfo.file_path))
    send_msg(msg.chat.id, deco("✅ تم", f"تم إضافة: {doc.file_name}\nالسعر: {msg.text}"), back_kb("adm_store"))

def store_edit(call, sid):
    store = read_json(STORE_DB)
    item = store.get(sid)
    if not item:
        return
    text = f"📄 الملف: {item['name']}\n💰 السعر: {item['price']}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💰 تغيير السعر", callback_data=f"sprice_{sid}"),
        types.InlineKeyboardButton("🗑️ حذف", callback_data=f"delstore_{sid}")
    )
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_store"))
    edit_msg(call, deco("📦 تعديل", text), kb)

def store_price_step(msg, sid, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        send_msg(msg.chat.id, deco("❌ خطأ", "سعر غير صحيح!"), back_kb("adm_store"))
        return
    store = read_json(STORE_DB)
    if sid in store:
        store[sid]['price'] = int(msg.text.strip())
        write_json(STORE_DB, store)
        send_msg(msg.chat.id, deco("✅ تم", f"السعر: {msg.text}"), back_kb("adm_store"))

def store_del(call, sid):
    store = read_json(STORE_DB)
    if sid in store:
        name = store[sid]['name']
        try:
            os.remove(os.path.join(STORE_DIR, f"{sid}.py"))
        except:
            pass
        del store[sid]
        write_json(STORE_DB, store)
        bot.answer_callback_query(call.id, f"🗑️ تم حذف: {name}")
        store_panel(call)

def upload_step(msg, h_type, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.document or not msg.document.file_name.endswith('.py'):
        send_msg(msg.chat.id, deco("❌ خطأ", "يجب ملف .py"), back_kb("nav_upload"))
        return
    if h_type == "free":
        users = read_json(USERS_DB)
        pts = users.get(str(uid), {}).get('points', 0)
        m = bot.send_message(
            msg.chat.id,
            deco("⏰ المدة", f"الملف: <b>{escape(msg.document.file_name)}</b>\n\n💰 نقاطك: <code>{pts}</code>\n\nأرسل عدد الساعات (الحد: {pts}):"),
            reply_markup=cancel_kb()
        )
        save_message(msg.chat.id, m.message_id)
        bot.register_next_step_handler(m, hours_step, msg.document, m.message_id)
    else:
        complete_upload(msg.document, uid, h_type, 0)

def hours_step(msg, doc, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text or not msg.text.strip().isdigit():
        send_msg(msg.chat.id, deco("❌ خطأ", "أرسل رقماً!"), back_kb("nav_upload"))
        return
    hours = int(msg.text.strip())
    users = read_json(USERS_DB)
    pts = users.get(str(uid), {}).get('points', 0)
    if hours < 1:
        send_msg(msg.chat.id, deco("❌ خطأ", "ساعة واحدة على الأقل!"), back_kb("nav_upload"))
        return
    if hours > pts:
        send_msg(msg.chat.id, deco("❌ نقاط غير كافية", f"تحتاج: {hours}\nلديك: {pts}"), back_kb("nav_wallet"))
        return
    complete_upload(doc, uid, "free", hours)

def complete_upload(doc, user_id, h_type, hours):
    fid = gen_id()
    finfo = bot.get_file(doc.file_id)
    file_content = bot.download_file(finfo.file_path).decode('utf-8')
    
    if not save_encrypted_file(fid, file_content, user_id):
        send_msg(user_id, deco("❌ خطأ", "فشل في حفظ الملف!"), back_kb())
        return
    
    files = read_json(FILES_DB)
    files[fid] = {
        'user_id': user_id,
        'file_name': doc.file_name,
        'type': h_type,
        'status': 'pending',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'hours': hours
    }
    write_json(FILES_DB, files)
    
    settings = get_settings()
    if settings.get('auto_approve', True):
        files[fid]['status'] = 'active'
        if h_type == 'free' and hours > 0:
            users = read_json(USERS_DB)
            if str(user_id) in users:
                users[str(user_id)]['points'] -= hours
                write_json(USERS_DB, users)
                process_hours[fid] = hours
        write_json(FILES_DB, files)
        start_script(fid)
        text = f"✅ تم قبول ملفك تلقائياً!\n\n📄 {escape(doc.file_name)}\n{'⏰ ' + str(hours) + ' ساعة' if h_type == 'free' else '♾ غير محدود'}\n🟢 يعمل الآن!"
        send_msg(user_id, deco("✅ تم القبول", text), back_kb())
    else:
        text = f"📄 الملف: {escape(doc.file_name)}\n💎 النوع: {'VIP 👑' if h_type == 'pro' else 'مجاني 🆓'}\n{'⏰ المدة: ' + str(hours) + ' ساعة' if h_type == 'free' else ''}\n\n🔍 قيد المراجعة..."
        send_msg(user_id, deco("⏳ قيد المراجعة", text), back_kb())
    
    try:
        user = bot.get_chat(user_id)
        admin_text = f"⚠️ <b>طلب رفع</b>\n\n👤 {escape(user.first_name)}\n🆔 <code>{user_id}</code>\n📄 {escape(doc.file_name)}\n💎 {'VIP' if h_type == 'pro' else 'مجاني'}\n{'⏰ ' + str(hours) + ' ساعة' if h_type == 'free' else ''}"
        for adm in get_admins():
            try:
                bot.send_message(adm, admin_text, parse_mode="HTML")
            except:
                pass
    except:
        pass

def pending_list(call):
    files = read_json(FILES_DB)
    pending = {fid: f for fid, f in files.items() if f.get('status') == 'pending'}
    if not pending:
        return bot.answer_callback_query(call.id, "✅ لا معلقات!", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for fid, f in pending.items():
        ft = "💎" if f.get('type') == 'pro' else "🆓"
        kb.add(types.InlineKeyboardButton(f"{ft} {f.get('file_name', '?')[:25]}", callback_data=f"vpend_{fid}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_admin"))
    text = f"📊 المعلقة: {len(pending)}"
    edit_msg(call, deco("⏳ الملفات المعلقة", text), kb)

def pending_view(call, fid):
    files = read_json(FILES_DB)
    f = files.get(fid)
    if not f:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    content = load_encrypted_file(fid)
    if not content:
        preview = "❌ تعذر قراءة الملف"
    else:
        safe = escape(content[:1000])
        if len(safe) > 3000:
            safe = safe[:3000] + "\n..."
        preview = f"<pre><code class='language-python'>{safe}</code></pre>"
    try:
        uinfo = bot.get_chat(f['user_id'])
        utext = f"{escape(uinfo.first_name)} (@{uinfo.username if uinfo.username else 'لا يوجد'})"
    except:
        utext = f"ID: {f['user_id']}"
    text = f"📦 الملف: {f.get('file_name')}\n👤 المالك: {utext}\n🆔 <code>{f.get('user_id')}</code>\n💎 النوع: {'VIP 👑' if f.get('type') == 'pro' else 'مجاني 🆓'}\n{'⏰ المدة: ' + str(f.get('hours', 0)) + ' ساعة' if f.get('type') == 'free' else ''}\n📅 {f.get('created_at')}\n\n🔍 الكود (أول 1000 حرف):\n{preview}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_{fid}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_{fid}")
    )
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_pending"))
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    m = bot.send_message(call.message.chat.id, deco("📄 مراجعة", text[:4000]), parse_mode="HTML", reply_markup=kb)
    save_message(call.message.chat.id, m.message_id)

def approve_file(call, fid):
    files = read_json(FILES_DB)
    if fid not in files:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    files[fid]['status'] = 'active'
    h_type = files[fid].get('type')
    hours = files[fid].get('hours', 0)
    user_id = files[fid]['user_id']
    if h_type == 'free' and hours > 0:
        users = read_json(USERS_DB)
        if str(user_id) in users:
            users[str(user_id)]['points'] -= hours
            write_json(USERS_DB, users)
            process_hours[fid] = hours
    write_json(FILES_DB, files)
    start_script(fid)
    try:
        text = f"✅ تم قبول ملفك!\n\n📄 {files[fid]['file_name']}\n{'⏰ ' + str(hours) + ' ساعة' if h_type == 'free' else '♾ غير محدود'}\n🟢 يعمل الآن!"
        bot.send_message(user_id, deco("✅ تم القبول", text))
    except:
        pass
    bot.answer_callback_query(call.id, "✅ تم القبول!")
    pending_list(call)

def reject_file(call, fid):
    files = read_json(FILES_DB)
    if fid not in files:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    user_id = files[fid]['user_id']
    fname = files[fid]['file_name']
    try:
        encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
        if os.path.exists(encrypted_path):
            os.remove(encrypted_path)
    except:
        pass
    
    security = read_json(SECURITY_DB)
    file_keys = security.get('file_keys', {})
    if fid in file_keys:
        del file_keys[fid]
        security['file_keys'] = file_keys
        write_json(SECURITY_DB, security)
    
    del files[fid]
    write_json(FILES_DB, files)
    try:
        bot.send_message(user_id, deco("❌ تم الرفض", f"تم رفض: {fname}"))
    except:
        pass
    bot.answer_callback_query(call.id, "❌ تم الرفض")
    pending_list(call)

def file_panel(call, fid):
    uid = call.from_user.id
    if not verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الوصول!", show_alert=True)
        return
    
    files = read_json(FILES_DB)
    if fid not in files:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    
    f = files[fid]
    content = load_encrypted_file(fid)
    if not content:
        preview = "❌ تعذر قراءة الملف"
    else:
        safe = escape(content[:1000])
        if len(safe) > 3000:
            safe = safe[:3000] + "\n..."
        preview = f"<pre><code class='language-python'>{safe}</code></pre>"
    
    running = fid in active_processes and active_processes[fid].poll() is None
    hrs = "غير محدود"
    if f.get('type') == 'free' and fid in process_hours:
        hrs = f"{process_hours[fid]} ساعة"
    text = f"📄 الملف: {f.get('file_name')}\n💎 النوع: {'VIP 👑' if f.get('type') == 'pro' else 'مجاني 🆓'}\n🟢 الحالة: {'يعمل ✅' if running else 'متوقف ❌'}\n⏰ المتبقي: {hrs}\n📅 {f.get('created_at')}\n\n🔍 الكود (أول 1000 حرف):\n{preview}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⏸ إيقاف" if running else "▶️ تشغيل", callback_data=f"toggle_{fid}"),
        types.InlineKeyboardButton("📟 التيرمنال", callback_data=f"term_{fid}")
    )
    kb.add(
        types.InlineKeyboardButton("🔑 تغيير التوكن", callback_data=f"chtoken_{fid}"),
        types.InlineKeyboardButton("ℹ️ معلومات التوكن", callback_data=f"tokinfo_{fid}")
    )
    kb.add(
        types.InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{fid}"),
        types.InlineKeyboardButton("🗑️ حذف", callback_data=f"delc_{fid}")
    )
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_files"))
    edit_msg(call, deco("📁 إدارة الملف", text), kb)

def toggle_file(call, fid):
    uid = call.from_user.id
    if not verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الوصول!", show_alert=True)
        return
    
    files = read_json(FILES_DB)
    if fid not in files:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    
    running = fid in active_processes and active_processes[fid].poll() is None
    if running:
        stop_script(fid)
        bot.answer_callback_query(call.id, "✅ تم الإيقاف")
    else:
        if start_script(fid):
            bot.answer_callback_query(call.id, "🚀 تم التشغيل")
        else:
            bot.answer_callback_query(call.id, "❌ فشل!")
    file_panel(call, fid)

def delete_file(call, fid):
    uid = call.from_user.id
    if not verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الوصول!", show_alert=True)
        return
    
    stop_script(fid)
    files = read_json(FILES_DB)
    if fid in files:
        fname = files[fid].get('file_name', '?')
        try:
            encrypted_path = os.path.join(ENCRYPTED_DIR, f"{fid}.enc")
            if os.path.exists(encrypted_path):
                os.remove(encrypted_path)
        except:
            pass
        
        try:
            os.remove(os.path.join(LOGS_DIR, f"{fid}.log"))
        except:
            pass
        
        try:
            env_dir = os.path.join(ENV_DIR, fid)
            import shutil
            shutil.rmtree(env_dir, ignore_errors=True)
        except:
            pass
        
        security = read_json(SECURITY_DB)
        file_keys = security.get('file_keys', {})
        if fid in file_keys:
            del file_keys[fid]
            security['file_keys'] = file_keys
            write_json(SECURITY_DB, security)
        
        del files[fid]
        write_json(FILES_DB, files)
        bot.answer_callback_query(call.id, f"🗑️ تم حذف: {fname}")
    
    u_files = {fid: f for fid, f in files.items() if f.get('user_id') == uid and f.get('status') == 'active'}
    if not u_files:
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("📤 رفع ملف", callback_data="nav_upload"),
            types.InlineKeyboardButton("🏠 الرئيسية", callback_data="nav_main")
        )
        edit_msg(call, deco("📁 ملفاتي", "لا ملفات."), kb)
    else:
        kb = types.InlineKeyboardMarkup(row_width=1)
        for fid, f in u_files.items():
            running = fid in active_processes and active_processes[fid].poll() is None
            icon = "🟢" if running else "🔴"
            ft = "💎" if f.get('type') == 'pro' else "🆓"
            kb.add(types.InlineKeyboardButton(f"{icon} {ft} {f.get('file_name', '?')[:25]}", callback_data=f"manage_{fid}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_main"))
        edit_msg(call, deco("📁 ملفاتي", f"📊 الملفات: {len(u_files)}"), kb)

def download_file(call, fid):
    uid = call.from_user.id
    if not verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الوصول!", show_alert=True)
        return
    
    files = read_json(FILES_DB)
    if fid not in files:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    
    content = load_encrypted_file(fid)
    if not content:
        bot.answer_callback_query(call.id, "❌ تعذر تحميل الملف!", show_alert=True)
        return
    
    try:
        temp_path = os.path.join(BASE_DIR, f"temp_{fid}_{gen_id(4)}.py")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        thumb = get_thumb()
        with open(temp_path, 'rb') as f:
            if thumb:
                with open(thumb, 'rb') as t:
                    bot.send_document(call.message.chat.id, f, thumb=t, caption=f"📄 {files[fid]['file_name']}", parse_mode="HTML")
            else:
                bot.send_document(call.message.chat.id, f, caption=f"📄 {files[fid]['file_name']}", parse_mode="HTML")
        os.remove(temp_path)
        bot.answer_callback_query(call.id, "✅ تم!")
    except:
        bot.answer_callback_query(call.id, "❌ فشل!", show_alert=True)

def terminal(call, fid):
    uid = call.from_user.id
    if not verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الوصول!", show_alert=True)
        return
    
    files = read_json(FILES_DB)
    if fid not in files:
        return bot.answer_callback_query(call.id, "❌ غير موجود!")
    
    running = fid in active_processes and active_processes[fid].poll() is None
    output = get_logs(fid, 40)
    text = f"📄 {files[fid]['file_name']}\n🟢 {'يعمل' if running else 'متوقف'}\n\n📺 التيرمنال:\n{output}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 تحديث", callback_data=f"rterm_{fid}"),
        types.InlineKeyboardButton("⌨️ إدخال", callback_data=f"inp_{fid}")
    )
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"manage_{fid}"))
    edit_msg(call, deco("📟 التيرمنال", text), kb)

def input_step(msg, fid, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    if write_proc(fid, msg.text):
        text = f"✅ تم إرسال: <code>{escape(msg.text)}</code>"
    else:
        text = "❌ الملف لا يعمل!"
    send_msg(msg.chat.id, deco("⌨️ إدخال", text), back_kb(f"term_{fid}"))

def token_step(msg, fid, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    token = msg.text.strip()
    
    content = load_encrypted_file(fid)
    if not content:
        send_msg(msg.chat.id, deco("❌ خطأ", "تعذر تحميل الملف!"), back_kb(f"manage_{fid}"))
        return
    
    updated_content = update_token_in_memory(content, token)
    if updated_content:
        files = read_json(FILES_DB)
        if fid in files:
            user_id = files[fid].get('user_id')
            if save_encrypted_file(fid, updated_content, user_id):
                text = "✅ تم تغيير التوكن!\n\n⚠️ أعد تشغيل الملف."
            else:
                text = "❌ فشل في حفظ التغييرات!"
        else:
            text = "❌ الملف غير موجود!"
    else:
        text = "❌ فشل في تحديث التوكن!"
    
    send_msg(msg.chat.id, deco("🔑 التوكن", text), back_kb(f"manage_{fid}"))

def update_token_in_memory(content, new_token):
    try:
        keywords = ["TOKEN", "bot_token", "api_key", "tok", "TKN", "BOT_TKN", "API_TOKEN"]
        pattern = r"(['\"])\d{8,12}:[a-zA-Z0-9_-]{35,}(['\"])"
        new_content = re.sub(pattern, f"\\1{new_token}\\2", content)
        for kw in keywords:
            kw_pattern = rf"{kw}\s*=\s*(['\"])[^'\"]+(['\"])"
            new_content = re.sub(kw_pattern, f"{kw} = \\1{new_token}\\2", new_content)
        return new_content
    except:
        return None

def token_info(call, fid):
    uid = call.from_user.id
    if not verify_file_access(fid, uid):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية الوصول!", show_alert=True)
        return
    
    content = load_encrypted_file(fid)
    if not content:
        bot.answer_callback_query(call.id, "❌ تعذر تحميل الملف!", show_alert=True)
        return
    
    try:
        tokens = re.findall(r"(\d{8,12}:[a-zA-Z0-9_-]{35,})", content)
        if not tokens:
            return bot.answer_callback_query(call.id, "🔍 لا توكن!", show_alert=True)
        token = tokens[0]
        valid, info = check_token(token)
        if valid:
            text = f"✅ التوكن صالح\n\n🤖 الاسم: {escape(info.get('first_name'))}\n👤 المعرف: @{info.get('username')}\n🆔 <code>{info.get('id')}</code>"
        else:
            text = f"❌ التوكن غير صالح\n\n{escape(str(info))}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"manage_{fid}"))
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        m = bot.send_message(call.message.chat.id, deco("ℹ️ معلومات التوكن", text), parse_mode="HTML", reply_markup=kb)
        save_message(call.message.chat.id, m.message_id)
    except:
        bot.answer_callback_query(call.id, "❌ خطأ!", show_alert=True)

def lib_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    lib = msg.text.strip()
    m = bot.send_message(msg.chat.id, deco("⏳ جاري التثبيت", f"المكتبة: <b>{escape(lib)}</b>"))
    save_message(msg.chat.id, m.message_id)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib], timeout=120)
        text = f"✅ تم تثبيت: <b>{escape(lib)}</b>"
    except subprocess.TimeoutExpired:
        text = f"⏰ انتهت المهلة: <b>{escape(lib)}</b>"
    except:
        text = f"❌ فشل: <b>{escape(lib)}</b>"
    bot.edit_message_text(deco("🛠 تثبيت مكتبة", text), msg.chat.id, m.message_id, parse_mode="HTML", reply_markup=back_kb())

def broadcast_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    users = read_json(USERS_DB)
    uids = list(users.keys())
    success, failed = 0, 0
    wait = bot.send_message(msg.chat.id, deco("📢 إذاعة", f"⏳ جاري الإرسال لـ {len(uids)} مستخدم..."))
    save_message(msg.chat.id, wait.message_id)
    for user_id in uids:
        try:
            if msg.content_type == 'text':
                bot.send_message(user_id, msg.text, parse_mode="HTML")
            elif msg.content_type == 'photo':
                bot.send_photo(user_id, msg.photo[-1].file_id, caption=msg.caption, parse_mode="HTML")
            elif msg.content_type == 'document':
                bot.send_document(user_id, msg.document.file_id, caption=msg.caption, parse_mode="HTML")
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    text = f"✅ اكتملت الإذاعة\n\n📫 نجح: {success}\n❌ فشل: {failed}\n📊 الإجمالي: {len(uids)}"
    bot.edit_message_text(deco("📢 إذاعة", text), msg.chat.id, wait.message_id, parse_mode="HTML", reply_markup=back_kb("nav_admin"))

def channels_panel(call):
    settings = get_settings()
    channels = settings.get('channels', [])
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel"))
    for i, ch in enumerate(channels):
        kb.add(types.InlineKeyboardButton(f"🗑️ {ch['name']}", callback_data=f"delch_{i}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_admin"))
    text = f"📊 القنوات: {len(channels)}"
    if channels:
        text += "\n\n"
        for ch in channels:
            text += f"📢 {ch['name']} ({ch['username']})\n"
    edit_msg(call, deco("📢 قنوات الاشتراك", text), kb)

def add_channel_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    username = msg.text.strip()
    if not username.startswith('@'):
        send_msg(msg.chat.id, deco("❌ خطأ", "يجب أن يبدأ بـ @"), back_kb("adm_channels"))
        return
    try:
        chat = bot.get_chat(username)
        settings = get_settings()
        settings['channels'] = settings.get('channels', []) + [{"username": username, "name": chat.title}]
        save_settings(settings)
        send_msg(msg.chat.id, deco("✅ تم", f"تم إضافة: {chat.title}"), back_kb("adm_channels"))
    except:
        send_msg(msg.chat.id, deco("❌ خطأ", "لم أجد القناة!"), back_kb("adm_channels"))

def del_channel(call, index):
    settings = get_settings()
    try:
        channels = settings.get('channels', [])
        if 0 <= index < len(channels):
            name = channels[index]['name']
            del channels[index]
            settings['channels'] = channels
            save_settings(settings)
            bot.answer_callback_query(call.id, f"✅ تم حذف: {name}")
        channels_panel(call)
    except:
        bot.answer_callback_query(call.id, "❌ خطأ!")

def settings_panel(call):
    settings = get_settings()
    has_img = "✅" if settings.get('bot_image') else "❌"
    has_thumb = "✅" if settings.get('file_thumb') and os.path.exists(settings.get('file_thumb', '')) else "❌"
    auto_approve = "✅" if settings.get('auto_approve', True) else "❌"
    text = f"✏️ اسم البوت: {settings.get('bot_name', 'غير محدد')}\n🖼 صورة البوت: {has_img}\n🎨 أيقونة الملفات: {has_thumb}\n✅ موافقة تلقائية: {auto_approve}"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("✏️ تغيير الاسم", callback_data="set_name"))
    if settings.get('bot_image'):
        kb.add(
            types.InlineKeyboardButton("🖼 تغيير الصورة", callback_data="set_img"),
            types.InlineKeyboardButton("🗑️ إزالة الصورة", callback_data="rm_img")
        )
    else:
        kb.add(types.InlineKeyboardButton("🖼 إضافة صورة", callback_data="set_img"))
    if settings.get('file_thumb') and os.path.exists(settings.get('file_thumb', '')):
        kb.add(
            types.InlineKeyboardButton("🎨 تغيير الأيقونة", callback_data="set_thumb"),
            types.InlineKeyboardButton("🗑️ إزالة الأيقونة", callback_data="rm_thumb")
        )
    else:
        kb.add(types.InlineKeyboardButton("🎨 إضافة أيقونة", callback_data="set_thumb"))
    kb.add(types.InlineKeyboardButton("✅ موافقة تلقائية", callback_data="toggle_auto"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_admin"))
    edit_msg(call, deco("🖼 الإعدادات", text), kb)

def name_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.text:
        return
    settings = get_settings()
    settings['bot_name'] = msg.text.strip()
    save_settings(settings)
    send_msg(msg.chat.id, deco("✅ تم", f"الاسم: {msg.text.strip()}"), back_kb("adm_settings"))

def img_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.photo:
        send_msg(msg.chat.id, deco("❌ خطأ", "أرسل صورة!"), back_kb("adm_settings"))
        return
    try:
        fid = msg.photo[-1].file_id
        settings = get_settings()
        settings['bot_image'] = fid
        save_settings(settings)
        send_msg(msg.chat.id, deco("✅ تم", "تم تحديث الصورة!"), back_kb("adm_settings"))
    except:
        send_msg(msg.chat.id, deco("❌ خطأ", "فشل!"), back_kb("adm_settings"))

def thumb_step(msg, prompt_id):
    uid = msg.from_user.id
    if is_cancelled(uid):
        clear_cancel(uid)
        return
    del_msg(msg.chat.id, prompt_id, msg.message_id)
    if not msg.photo:
        send_msg(msg.chat.id, deco("❌ خطأ", "أرسل صورة!"), back_kb("adm_settings"))
        return
    try:
        finfo = bot.get_file(msg.photo[-1].file_id)
        path = os.path.join(THUMBS_DIR, "thumb.jpg")
        with open(path, "wb") as f:
            f.write(bot.download_file(finfo.file_path))
        settings = get_settings()
        settings['file_thumb'] = path
        save_settings(settings)
        send_msg(msg.chat.id, deco("✅ تم", "تم تحديث الأيقونة!"), back_kb("adm_settings"))
    except:
        send_msg(msg.chat.id, deco("❌ خطأ", "فشل!"), back_kb("adm_settings"))

def monitor():
    while True:
        try:
            files = read_json(FILES_DB)
            for fid in list(active_processes.keys()):
                proc = active_processes.get(fid)
                if not proc or proc.poll() is not None:
                    if fid in active_processes:
                        del active_processes[fid]
                    continue
                if fid not in files:
                    continue
                uid = str(files[fid]['user_id'])
                if not check_sub(int(uid)):
                    stop_script(fid)
                    try:
                        bot.send_message(int(uid), deco("⚠️ توقف", f"تم إيقاف {files[fid]['file_name']} لعدم الاشتراك!"))
                    except:
                        pass
                    continue
                if not is_user_pro(int(uid)) and fid in process_hours:
                    process_hours[fid] -= 1
                    if process_hours[fid] <= 0:
                        stop_script(fid)
                        try:
                            bot.send_message(int(uid), deco("⏰ انتهت المدة", f"انتهت مدة {files[fid]['file_name']}"))
                        except:
                            pass
        except Exception as e:
            print(f"Monitor Error: {e}")
        time.sleep(3600)

threading.Thread(target=monitor, daemon=True).start()

init_db()

print("=" * 40)
print("HOSTING PYTHON | الذئب الأبيض @j49_c")
print("=" * 40)

while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
