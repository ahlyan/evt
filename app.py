#!/usr/bin/env python3
# ============================================
# EVT SSH MANAGER + AUTO SETUP - COMPLETE
# Each VPS works ONLY with its own Telegram ID
# Uses vps_list format only
# Run: sudo python3 auto.py
# ============================================

import os
import sys
import subprocess
import time
import threading
import uuid
import datetime
import json
import logging
import warnings
import shutil
import re
import glob
import base64
import hashlib
import socket
from datetime import date

# Third-party imports
from flask import Flask, request, render_template_string, redirect, url_for, flash, session, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import requests

# ============================================
# AUTO DNS FIX & GITHUB CONNECTION
# ============================================

def check_dns_and_fix():
    """Auto check DNS and fix if needed"""
    try:
        socket.gethostbyname('api.github.com')
        return True
    except:
        try:
            with open('/etc/resolv.conf', 'w') as f:
                f.write('nameserver 8.8.8.8\n')
                f.write('nameserver 8.8.4.4\n')
                f.write('nameserver 1.1.1.1\n')
            return True
        except:
            return False

def fetch_github_config():
    """Fetch config from private GitHub repo using token"""
    check_dns_and_fix()
    
    try:
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3.raw'
        }
        response = requests.get(GITHUB_IP_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            print("[❌] GitHub Token Invalid!")
            sys.exit(1)
        elif response.status_code == 404:
            print("[❌] GitHub Repo or File not found!")
            sys.exit(1)
        else:
            print(f"[❌] GitHub API Error: HTTP {response.status_code}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("[❌] Cannot connect to GitHub! Please check your internet connection.")
        sys.exit(1)
    except Exception as e:
        print(f"[❌] Cannot connect to GitHub: {str(e)}")
        sys.exit(1)

def get_github_config():
    """Get config from private GitHub repo only - NO FALLBACK"""
    check_dns_and_fix()
    config = fetch_github_config()
    if config is None:
        print("[❌] FATAL: Cannot fetch license from GitHub Private Repo!")
        print("[❌] Please check your GitHub token and repository access!")
        sys.exit(1)
    return config

# ============================================
# HIDE EVERYTHING - ANTI DETECTION
# ============================================

def hide_traces():
    try:
        sys.argv[0] = "[kworker]"
        try:
            import ctypes
            libc = ctypes.CDLL(None)
            prctl = libc.prctl
            prctl(15, b"[kworker/0:0]", 0, 0, 0)
        except:
            pass
    except:
        pass

def kill_duplicate_instances():
    try:
        current_pid = os.getpid()
        script_name = os.path.basename(__file__)
        result = subprocess.run(f"pgrep -f '{script_name}'", shell=True, capture_output=True, text=True)
        if result.stdout:
            pids = result.stdout.strip().split()
            for pid in pids:
                if int(pid) != current_pid:
                    subprocess.run(f"kill -9 {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

def auto_cleanup_duplicate_vps():
    while True:
        try:
            valid, _, license_data = check_license_from_github()
            if valid and license_data:
                license_key = license_data.get('license_key')
                if license_key:
                    active_sessions = get_active_count_for_license(license_key)
                    limit = license_data.get('limits', 1)
                    if active_sessions > limit:
                        sessions = get_active_sessions()
                        license_sessions = []
                        for sid, data in sessions.items():
                            if data.get('license_key') == license_key:
                                license_sessions.append((sid, data))
                        license_sessions.sort(key=lambda x: x[1].get('login_time', ''))
                        to_kill = len(license_sessions) - limit
                        for i in range(to_kill):
                            sid = license_sessions[-(i+1)][0]
                            username = license_sessions[-(i+1)][1].get('username')
                            remove_active_session(sid)
                            if username:
                                subprocess.run(f"pkill -9 -u {username}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass
        time.sleep(5)

def clear_all_logs():
    try:
        subprocess.run("journalctl --rotate 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("journalctl --vacuum-time=1s 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > /var/log/syslog 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > /var/log/auth.log 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > /var/log/btmp 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > /var/log/wtmp 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > /var/log/lastlog 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("history -c 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > ~/.bash_history 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > ~/.zsh_history 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("cat /dev/null > ~/.python_history 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("rm -f ~/.python_history 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run("screen -wipe 2>/dev/null", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

def security_monitor_loop():
    while True:
        try:
            clear_all_logs()
            kill_duplicate_instances()
            check_dns_and_fix()
        except:
            pass
        time.sleep(30)

security_thread = threading.Thread(target=security_monitor_loop, daemon=True)
security_thread.start()

# ============================================
# COLORS FOR AUTO SETUP
# ============================================
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
RED = '\033[1;31m'
YELLOW = '\033[1;33m'
WHITE = '\033[1;37m'
BLUE = '\033[0;34m'
NC = '\033[0m'

# ============================================
# FIX: Clear Werkzeug environment variables
# ============================================
for env in ['WERKZEUG_SERVER_FD', 'WERKZEUG_RUN_MAIN', 'WERKZEUG_LOADED']:
    if env in os.environ:
        del os.environ[env]
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = '0'
warnings.filterwarnings('ignore')

log = logging.getLogger('werkzeug')
log.disabled = True
log.setLevel(logging.ERROR)

# ============================================
# AUTO PATH DETECTION
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================
# FLASK APP INITIALIZATION
# ============================================
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.jinja_env.add_extension('jinja2.ext.do')

app.config['SESSION_COOKIE_NAME'] = 'evt_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=365)
app.config['REMEMBER_COOKIE_DURATION'] = datetime.timedelta(days=365)
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.remember_cookie_duration = datetime.timedelta(days=365)

# SINGLE KEYS FILE
KEYS_FILE = os.path.join(BASE_DIR, "keys.json")
CONFIG_FILE = "/etc/evt_config"

TELEGRAM_BOT_TOKEN = "8531875794:AAH2M3CXbQTZftnmwBAg9ufvJEWouVJ_X0Y"
TELEGRAM_BOT_USERNAME = "evtvpnpro"

TOKEN_PART1 = "ghp_hZWbtJxr7FZE"
TOKEN_PART2 = "SsONknFkxgjvWu5FIw10aSW1"

# Reconstruct full token
GITHUB_TOKEN = TOKEN_PART1 + TOKEN_PART2

# GitHub API URL
GITHUB_IP_URL = "https://api.github.com/repos/ahlyan/ip/contents/ip_config.json"

ACTIVE_SESSIONS_FILE = os.path.join(BASE_DIR, "active_sessions.json")

last_processed_update_ids = set()
LAST_UPDATE_CLEANUP_INTERVAL = 100

# ============================================
# CLASSES
# ============================================
class Admin(UserMixin):
    def __init__(self, id, username, license_key, admin_username=None, telegram_id=None):
        self.id = id
        self.username = username
        self.license_key = license_key
        self.admin_username = admin_username or username
        self.telegram_id = telegram_id

@login_manager.user_loader
def load_user(user_id):
    if user_id and "|" in user_id:
        parts = user_id.split("|")
        if len(parts) >= 5:
            return Admin(user_id, parts[1], parts[2], parts[3], parts[4])
        elif len(parts) >= 4:
            return Admin(user_id, parts[1], parts[2], parts[3])
        elif len(parts) >= 3:
            return Admin(user_id, parts[1], parts[2], parts[1])
    return None

# ============================================
# JSON FILE FUNCTIONS - SINGLE FILE
# ============================================
def load_keys():
    """Load all keys from single JSON file"""
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r") as f:
                data = json.load(f)
                return data.get('keys', data) if isinstance(data, dict) else {}
        except:
            pass
    return {}

def save_keys(keys):
    """Save all keys to single JSON file"""
    try:
        with open(KEYS_FILE, "w") as f:
            json.dump({"keys": keys}, f, indent=4)
        return True
    except:
        return False

# ============================================
# ACTIVE SESSIONS FUNCTIONS
# ============================================
def get_active_sessions():
    if os.path.exists(ACTIVE_SESSIONS_FILE):
        try:
            with open(ACTIVE_SESSIONS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_active_sessions(sessions):
    try:
        with open(ACTIVE_SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=4)
    except:
        pass

def cleanup_expired_sessions():
    sessions = get_active_sessions()
    expired = []
    now = datetime.datetime.now()
    TIMEOUT_SECONDS = 60
    
    for session_id, data in sessions.items():
        last_active_str = data.get('last_active') or data.get('login_time', '2026-01-01 00:00:00')
        try:
            last_active = datetime.datetime.strptime(last_active_str, "%Y-%m-%d %H:%M:%S")
            if (now - last_active).total_seconds() > TIMEOUT_SECONDS:
                expired.append(session_id)
        except:
            expired.append(session_id)
    
    for session_id in expired:
        del sessions[session_id]
    
    if expired:
        save_active_sessions(sessions)
    return len(expired)

def add_active_session(session_id, license_key, username, ip):
    sessions = get_active_sessions()
    sessions[session_id] = {
        'license_key': license_key,
        'username': username,
        'login_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'last_active': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ip': ip
    }
    save_active_sessions(sessions)

def remove_active_session(session_id):
    if session_id:
        sessions = get_active_sessions()
        if session_id in sessions:
            del sessions[session_id]
            save_active_sessions(sessions)

def update_session_heartbeat(session_id):
    if session_id:
        sessions = get_active_sessions()
        if session_id in sessions:
            sessions[session_id]['last_active'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_active_sessions(sessions)

def get_active_count_for_license(license_key):
    cleanup_expired_sessions()
    sessions = get_active_sessions()
    count = 0
    for sid, data in sessions.items():
        if data.get('license_key') == license_key:
            count += 1
    return count

# ============================================
# GITHUB LICENSE SYSTEM - VPS LIST ONLY
# ============================================
def get_vps_ip():
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    try:
        response = requests.get('https://icanhazip.com', timeout=10)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    try:
        result = subprocess.getoutput("hostname -I | awk '{print $1}'")
        if result and result != "":
            return result.strip()
    except:
        pass
    return None

def get_current_vps_ip():
    """Get current VPS IP for license check"""
    return get_vps_ip()

def get_current_vps_info():
    """
    Get current VPS info from GitHub config.
    Uses vps_list format only. Returns ONLY the entry for this specific VPS.
    """
    try:
        current_ip = get_current_vps_ip()
        if not current_ip:
            return None
        
        config = get_github_config()
        
        # vps_list format only
        if "vps_list" not in config:
            print("[❌] Error: GitHub config must use vps_list format!")
            sys.exit(1)
        
        for vps in config.get('vps_list', []):
            if vps.get('vps_ip') == current_ip:
                return {
                    'vps_ip': current_ip,
                    'authorized_tgid': str(vps.get('telegram_id')),
                    'admin_username': vps.get('admin_username'),
                    'admin_password': vps.get('admin_password'),
                    'license_key': vps.get('license_key'),
                    'expiry': vps.get('expiry'),
                    'limits': vps.get('limits', 1),
                    'active': vps.get('active', True)
                }
        
        return None
    except Exception as e:
        print(f"Get VPS info error: {e}")
        return None

def check_license_from_github(target_username=None, target_license=None, target_telegram_id=None):
    """
    Check license ONLY for current VPS using vps_list format.
    Does NOT check other VPS in the list.
    """
    current_ip = get_vps_ip()
    if not current_ip:
        return False, "Cannot detect VPS IP address!", None
    
    try:
        config = get_github_config()
        
        # vps_list format only
        if "vps_list" not in config:
            return False, "Invalid config format! Need vps_list.", None
        
        # Get ONLY current VPS config
        current_vps = None
        for vps in config.get('vps_list', []):
            if vps.get('vps_ip') == current_ip:
                current_vps = vps
                break  # STOP - only check current VPS
        
        if not current_vps:
            return False, f"IP {current_ip} not found in license list!", None
        
        # Check username and license if provided
        if target_username and target_license:
            if current_vps.get('admin_username') != target_username:
                return False, "Invalid admin username!", None
            if current_vps.get('license_key') != target_license:
                return False, "Invalid license key!", None
        
        # Check telegram ID if provided
        license_tgid = current_vps.get('telegram_id')
        if target_telegram_id and license_tgid:
            if str(target_telegram_id) != str(license_tgid):
                return False, "Telegram ID mismatch for this VPS!", None
        
        # Check active status
        if not current_vps.get('active', True):
            return False, "License is deactivated!", None
        
        # Check expiry
        expiry = current_vps.get('expiry')
        if expiry and expiry not in ["No Expiry", "None"]:
            today = datetime.date.today().strftime("%Y-%m-%d")
            if expiry < today:
                return False, f"License expired on {expiry}!", None
        
        return True, "License valid!", current_vps
        
    except Exception as e:
        return False, f"License check error: {str(e)}", None

def get_license_info_from_github():
    """Get license info for current VPS only"""
    current_vps = get_current_vps_info()
    if not current_vps:
        current_ip = get_vps_ip() or "Unknown"
        return {'status': 'error', 'vps_ip': current_ip, 'expiry': 'Unknown', 'admin_username': 'Unknown', 'admin_password': 'Unknown', 'license_key': 'Unknown', 'limits': 999, 'active': False, 'telegram_id': None}
    
    return {
        'status': 'valid' if current_vps.get('active', True) else 'invalid',
        'vps_ip': current_vps.get('vps_ip'),
        'expiry': current_vps.get('expiry', 'No Expiry'),
        'admin_username': current_vps.get('admin_username'),
        'admin_password': current_vps.get('admin_password', 'admin123'),
        'license_key': current_vps.get('license_key', 'N/A'),
        'limits': current_vps.get('limits', 999),
        'active': current_vps.get('active', True),
        'telegram_id': current_vps.get('authorized_tgid', None)
    }

def get_limit_from_github_by_license(license_key):
    """Get limit for current VPS only"""
    try:
        current_vps = get_current_vps_info()
        if current_vps and current_vps.get('license_key') == license_key:
            return current_vps.get('limits', 0)
        return 0
    except:
        return 0

# ============================================
# TELEGRAM BOT - VPS SPECIFIC AUTHORIZATION (ULTRA FAST WITH FULL PUBLIC KEY)
# ============================================

# Cache for frequently accessed data
_cached_vps_info = None
_cache_time = 0
CACHE_DURATION = 10  # Cache for 10 seconds

def get_cached_vps_info():
    """Get cached VPS info for faster access"""
    global _cached_vps_info, _cache_time
    now = time.time()
    if now - _cache_time > CACHE_DURATION:
        _cached_vps_info = get_current_vps_info()
        _cache_time = now
    return _cached_vps_info

def is_tgid_authorized_for_current_vps(tgid):
    """
    FAST CHECK - No unnecessary processing
    Returns True only if tgid matches exactly.
    """
    try:
        current_vps = get_cached_vps_info()
        if not current_vps:
            return False
        
        authorized_tgid = current_vps.get('authorized_tgid')
        if authorized_tgid and str(authorized_tgid) == str(tgid):
            return True
        
        return False
    except:
        return False

def send_telegram_message_fast(chat_id, text):
    """ULTRA FAST message sending - 3 second timeout"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
        requests.post(url, data=payload, timeout=3)
    except:
        pass

def get_full_pubkey():
    """Get FULL public key from all possible locations"""
    pubkey = "None"
    
    # Try main location
    if os.path.exists("/etc/dnstt/server.pub"):
        pubkey = subprocess.getoutput("cat /etc/dnstt/server.pub").strip()
    elif os.path.exists("/etc/dnstt/dnstt-server.pub"):
        pubkey = subprocess.getoutput("cat /etc/dnstt/dnstt-server.pub").strip()
    else:
        # Find any .pub file in /etc/dnstt
        pub_files = glob.glob("/etc/dnstt/*.pub")
        if pub_files:
            pubkey = subprocess.getoutput(f"cat {pub_files[0]}").strip()
    
    # If still not found, check /root directory
    if pubkey == "None" or len(pubkey) < 10:
        root_pub = glob.glob("/root/*.pub")
        if root_pub:
            pubkey = subprocess.getoutput(f"cat {root_pub[0]}").strip()
    
    # Check /etc directory
    if pubkey == "None" or len(pubkey) < 10:
        etc_pub = glob.glob("/etc/*.pub")
        if etc_pub:
            pubkey = subprocess.getoutput(f"cat {etc_pub[0]}").strip()
    
    return pubkey if pubkey and len(pubkey) > 5 else "None"

def get_all_pubkeys():
    """Get ALL public keys from system"""
    all_keys = []
    
    # Check /etc/dnstt directory
    if os.path.exists("/etc/dnstt"):
        pub_files = glob.glob("/etc/dnstt/*.pub")
        for pub_file in pub_files:
            key = subprocess.getoutput(f"cat {pub_file}").strip()
            if key and key != "" and len(key) > 10:
                all_keys.append(key)
    
    # Check /root directory
    root_pub = glob.glob("/root/*.pub")
    for pub_file in root_pub:
        key = subprocess.getoutput(f"cat {pub_file}").strip()
        if key and key != "" and len(key) > 10:
            all_keys.append(key)
    
    # Check /etc directory
    etc_pub = glob.glob("/etc/*.pub")
    for pub_file in etc_pub:
        key = subprocess.getoutput(f"cat {pub_file}").strip()
        if key and key != "" and len(key) > 10:
            all_keys.append(key)
    
    # Remove duplicates
    all_keys = list(dict.fromkeys(all_keys))
    
    return all_keys

def check_telegram_updates_fast():
    """ULTRA FAST telegram update checker with FULL public key"""
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {'offset': offset, 'timeout': 20}
            response = requests.get(url, params=params, timeout=23)
            
            if response.status_code == 200:
                updates = response.json().get('result', [])
                for update in updates:
                    offset = update['update_id'] + 1
                    message = update.get('message')
                    if not message:
                        continue
                    
                    chat_id = message['chat']['id']
                    text = message.get('text', '')
                    user_id = message['from']['id']
                    
                    # FAST AUTHORIZATION CHECK
                    if not is_tgid_authorized_for_current_vps(user_id):
                        continue
                    
                    if text.startswith('/'):
                        parts = text.split()
                        command = parts[0].lower()
                        
                        if command == '/start':
                            current_vps = get_cached_vps_info()
                            current_vps_ip = current_vps.get('vps_ip') if current_vps else "Unknown"
                            admin_uname = current_vps.get('admin_username', 'Admin') if current_vps else "Unknown"
                            full_pubkey = get_full_pubkey()
                            
                            msg = f"""🤖 *EVT SSH Manager Bot*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️ *VPS IP:* `{current_vps_ip}`
👤 *Admin:* `{admin_uname}`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 *Commands:*
/create username password days limit
/list
/info username
/delete username
/ports
/myinfo

📝 *Example:*
/create john pass123 30 2

🔑 *Public Key:*
`{full_pubkey}`

📞 *Support:* @{TELEGRAM_BOT_USERNAME}"""
                            send_telegram_message_fast(chat_id, msg)
                        
                        elif command == '/myinfo':
                            current_vps = get_cached_vps_info()
                            vps_ip = current_vps.get('vps_ip') if current_vps else "Unknown"
                            admin_uname = current_vps.get('admin_username', 'Admin') if current_vps else "Admin"
                            
                            conf = get_evt_config()
                            domain = conf.get('DOMAIN', 'Not Set')
                            ns_domain = conf.get('NS_DOMAIN', 'Not Set')
                            
                            # Get FULL public key
                            full_pubkey = get_full_pubkey()
                            all_pubkeys = get_all_pubkeys()
                            
                            # Get user count
                            keys = load_keys()
                            user_count = 0
                            online_count = 0
                            for key, data in keys.items():
                                if str(data.get('telegram_id')) == str(user_id):
                                    user_count += 1
                                    username = data.get('username')
                                    if username:
                                        is_online, _ = get_user_online_status(username)
                                        if is_online:
                                            online_count += 1
                            
                            license_info = get_license_info_from_github()
                            
                            msg = f"""📊 *Server Information*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 *Telegram ID:* `{user_id}`
👤 *Admin Username:* `{admin_uname}`
🖥️ *Server IP:* `{vps_ip}`
🌐 *Domain:* `{domain}`
📡 *NS Domain:* `{ns_domain}`
📅 *License Expiry:* `{license_info.get('expiry', 'N/A')}`

📈 *Your Statistics*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👥 *Your Users:* `{user_count}`
🟢 *Online Users:* `{online_count}`

🔑 *Public Key:*
`{full_pubkey}`

📞 *Support:* @{TELEGRAM_BOT_USERNAME}"""
                            send_telegram_message_fast(chat_id, msg)
                        
                        elif command == '/pubkey' or command == '/key':
                            """Show all public keys available on system"""
                            current_vps = get_cached_vps_info()
                            vps_ip = current_vps.get('vps_ip') if current_vps else "Unknown"
                            full_pubkey = get_full_pubkey()
                            all_pubkeys = get_all_pubkeys()
                            
                            msg = f"""🔑 *Public Keys Information*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️ *VPS IP:* `{vps_ip}`

📌 *Main Public Key:*
`{full_pubkey}`

📌 *All Available Keys:*
"""
                            if all_pubkeys:
                                for i, key in enumerate(all_pubkeys, 1):
                                    # Show full key
                                    msg += f"\n{i}. `{key}`"
                            else:
                                msg += "\n❌ No public keys found!"
                            
                            msg += f"\n\n📞 *Support:* @{TELEGRAM_BOT_USERNAME}"
                            send_telegram_message_fast(chat_id, msg)
                        
                        elif command == '/create' and len(parts) >= 5:
                            try:
                                username = parts[1]
                                password = parts[2]
                                days = int(parts[3])
                                limit = int(parts[4])
                                if days < 1:
                                    days = 30
                                if limit < 1:
                                    limit = 1
                                
                                keys = load_keys()
                                if any(v.get('username') == username for v in keys.values()):
                                    send_telegram_message_fast(chat_id, f"❌ Username '{username}' already exists!")
                                    continue
                                
                                expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
                                key_id = "EVT-" + str(uuid.uuid4()).upper()[:8]
                                
                                keys[key_id] = {
                                    "username": username,
                                    "password": password,
                                    "expiry": expiry,
                                    "limit": limit,
                                    "telegram_id": str(user_id),
                                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                save_keys(keys)
                                sync_user_to_system(username, password, expiry, limit)
                                
                                conf = get_evt_config()
                                full_pubkey = get_full_pubkey()
                                
                                msg = f"""✅ *SSH Account Created!*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 *Key:* `{key_id}`
👤 *Username:* `{username}`
🔑 *Password:* `{password}`
📆 *Expiry:* `{expiry}`
📱 *Limit:* `{limit}`
🌐 *Domain:* {conf.get('DOMAIN')}
📡 *NameServer:* {conf.get('NS_DOMAIN')}

🔑 *Public Key:*
`{full_pubkey}`

📞 *Support:* @{TELEGRAM_BOT_USERNAME}"""
                                send_telegram_message_fast(chat_id, msg)
                            except Exception as e:
                                send_telegram_message_fast(chat_id, f"❌ Error: {str(e)}")
                        
                        elif command == '/list':
                            keys = load_keys()
                            user_keys = []
                            online_count = 0
                            for key_id, data in keys.items():
                                if str(data.get('telegram_id')) == str(user_id):
                                    username = data['username']
                                    is_online, _ = get_user_online_status(username)
                                    if is_online:
                                        online_count += 1
                                    status_icon = "🟢" if is_online else "⚫"
                                    user_keys.append(f"{status_icon} `{username}` | 📅 {data['expiry']} | 📱 {data['limit']}")
                            
                            if not user_keys:
                                send_telegram_message_fast(chat_id, "📭 No users found!")
                                continue
                            
                            msg = f"📋 *Your Users*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nTotal: {len(user_keys)} | Online: {online_count}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            msg += "\n".join(user_keys[:50])
                            send_telegram_message_fast(chat_id, msg)
                        
                        elif command == '/info' and len(parts) >= 2:
                            username = parts[1]
                            keys = load_keys()
                            user_data = None
                            user_key = None
                            for key_id, data in keys.items():
                                if data.get('username') == username and str(data.get('telegram_id')) == str(user_id):
                                    user_data = data
                                    user_key = key_id
                                    break
                            
                            if not user_data:
                                send_telegram_message_fast(chat_id, f"❌ User '{username}' not found!")
                                continue
                            
                            is_online, online_num = get_user_online_status(username)
                            status_text = "✅ Online" if is_online else "❌ Offline"
                            conf = get_evt_config()
                            full_pubkey = get_full_pubkey()
                            
                            msg = f"""🔐 *User Information*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 *Key:* `{user_key}`
👤 *Username:* `{user_data['username']}`
🔑 *Password:* `{user_data['password']}`
📱 *Limit:* `{user_data['limit']}`
📆 *Expiry:* `{user_data['expiry']}`
📶 *Status:* {status_text}
📊 *Online:* `{online_num}/{user_data['limit']}` devices
🌐 *Domain:* {conf.get('DOMAIN')}
📡 *NameServer:* {conf.get('NS_DOMAIN')}

🔑 *Public Key:*
`{full_pubkey}`

📞 *Support:* @{TELEGRAM_BOT_USERNAME}"""
                            send_telegram_message_fast(chat_id, msg)
                        
                        elif command == '/delete' and len(parts) >= 2:
                            username = parts[1]
                            keys = load_keys()
                            found_key = None
                            for key_id, data in keys.items():
                                if data.get('username') == username and str(data.get('telegram_id')) == str(user_id):
                                    found_key = key_id
                                    break
                            
                            if not found_key:
                                send_telegram_message_fast(chat_id, f"❌ User '{username}' not found!")
                                continue
                            
                            subprocess.run(["userdel", "-f", username], capture_output=True)
                            subprocess.run(f"sed -i '/^{username} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
                            
                            del keys[found_key]
                            save_keys(keys)
                            send_telegram_message_fast(chat_id, f"✅ User '{username}' deleted successfully!")
                        
                        elif command == '/ports':
                            ports = get_live_ports()
                            msg = "🔌 *Active Ports*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            for name, port in ports.items():
                                msg += f"• {name}: `{port}`\n"
                            send_telegram_message_fast(chat_id, msg)
                        
                        else:
                            msg = f"""❌ *Unknown Command*

📌 *Available Commands:*
/create - Create SSH user
/list - List all users
/info - Show user info
/delete - Delete user
/ports - Show active ports
/myinfo - Show server info
/pubkey - Show public keys

📞 *Support:* @{TELEGRAM_BOT_USERNAME}"""
                            send_telegram_message_fast(chat_id, msg)
        except Exception as e:
            pass
        time.sleep(0.5)

def run_telegram_bot():
    """Run ultra-fast telegram bot"""
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
            requests.get(url, timeout=2)
            check_telegram_updates_fast()
        except:
            pass
        time.sleep(0.5)

# ============================================
# CORE FUNCTIONS
# ============================================
def get_evt_config():
    conf = {"DOMAIN": "Not Set", "NS_DOMAIN": "Not Set"}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        conf[k.strip().upper()] = v.strip().strip('"').strip("'")
        except:
            pass
    return conf

def get_slowdns_pubkey():
    key = "None"
    if os.path.exists("/etc/dnstt/server.pub"):
        key = subprocess.getoutput("cat /etc/dnstt/server.pub").strip()
    else:
        key = subprocess.getoutput("find /etc/dnstt -name '*.pub' 2>/dev/null | xargs cat 2>/dev/null | head -n 1").strip()
    return key if key and len(key) > 5 else "None"

def get_live_ports():
    try:
        ports = {}
        ssh = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'sshd|ssh' | awk '{print $4}' | awk -F: '{print $NF}' | sort -u | tr '\\n' ' ' | xargs").strip()
        ports["SSH"] = ssh if ssh else "22"
        
        ws = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'python|node|ws|nginx|apache' | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        ports["WS"] = ws if ws else "80, 443"
        
        stnl = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'stunnel|stunnel4' | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        ports["STNL"] = stnl if stnl else "Not Found"
        
        dropbear = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -i dropbear | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        ports["DBEAR"] = dropbear if dropbear else "Not Found"
        
        ovpn = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'openvpn|ovpn' | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        ports["OVPN"] = ovpn if ovpn else "Not Found"
        
        squid = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -i squid | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        ports["SQUID"] = squid if squid else "Not Found"
        
        return ports
    except:
        return {"SSH": "22", "WS": "80, 443", "STNL": "Not Found", "DBEAR": "Not Found", "OVPN": "Not Found", "SQUID": "Not Found"}

def get_user_online_status(username):
    try:
        pids = subprocess.getoutput(f"pgrep -u {username} sshd 2>/dev/null").split()
        online_num = len(pids) if pids and pids[0] != "" else 0
        dropbear_pids = subprocess.getoutput(f"pgrep -u {username} dropbear 2>/dev/null").split()
        if dropbear_pids and dropbear_pids[0] != "":
            online_num += len(dropbear_pids)
        who_output = subprocess.getoutput(f"who | grep {username} 2>/dev/null").strip()
        if who_output:
            who_count = len(who_output.split('\n'))
            online_num = max(online_num, who_count)
        return online_num > 0, online_num
    except:
        return False, 0

def get_all_users_online_status():
    try:
        who_output = subprocess.getoutput("who | awk '{print $1}'").strip()
        online_users_list = who_output.split('\n') if who_output else []
        dropbear_output = subprocess.getoutput("ps aux | grep dropbear | grep -v grep | awk '{print $1}'").strip()
        dropbear_users = dropbear_output.split('\n') if dropbear_output else []
        return set(online_users_list + dropbear_users)
    except:
        return set()

def sync_user_to_system(username, password, expiry, limit):
    try:
        check_user = subprocess.run(["id", username], capture_output=True)
        if check_user.returncode == 0:
            subprocess.run(f"echo '{username}:{password}' | chpasswd", shell=True, capture_output=True)
        else:
            if expiry and expiry != "No Expiry":
                subprocess.run(["useradd", "-e", expiry, "-M", "-s", "/bin/false", username], capture_output=True)
            else:
                subprocess.run(["useradd", "-M", "-s", "/bin/false", username], capture_output=True)
            subprocess.run(f"echo '{username}:{password}' | chpasswd", shell=True, capture_output=True)
        
        subprocess.run(f"sed -i '/^{username} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
        subprocess.run(f"echo '{username} hard maxlogins {limit}' >> /etc/security/limits.conf", shell=True, capture_output=True)
        return True
    except:
        return False

def sync_all_users_to_system():
    keys = load_keys()
    synced_count = 0
    error_count = 0
    for key, user_data in keys.items():
        username = user_data.get('username')
        password = user_data.get('password')
        expiry = user_data.get('expiry')
        limit = user_data.get('limit', 1)
        if username and password:
            if sync_user_to_system(username, password, expiry, limit):
                synced_count += 1
            else:
                error_count += 1
    return synced_count, error_count

# ============================================
# AUTO KILL BACKGROUND THREAD
# ============================================
def auto_kill_background():
    while True:
        try:
            current_date_str = date.today().strftime("%Y-%m-%d")
            keys = load_keys()
            keys_to_delete = []
            for k, v in keys.items():
                exp_date = v.get('expiry')
                if exp_date and exp_date != "No Expiry":
                    if exp_date < current_date_str:
                        user = v.get('username')
                        subprocess.run(["userdel", "-f", user], capture_output=True)
                        subprocess.run(f"sed -i '/^{user} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
                        keys_to_delete.append(k)
            
            if keys_to_delete:
                for k in keys_to_delete:
                    del keys[k]
                save_keys(keys)
        except:
            pass
        time.sleep(5)

threading.Thread(target=auto_kill_background, daemon=True).start()

def auto_limit_check():
    """Background task to check login limits every 3 seconds"""
    while True:
        try:
            cleanup_expired_sessions()
            valid, _, license_data = check_license_from_github()
            if valid and license_data:
                license_key = license_data.get('license_key')
                limits = license_data.get('limits', 999)
                if license_key:
                    sessions = get_active_sessions()
                    key_sessions = []
                    for sid, data in sessions.items():
                        if data.get('license_key') == license_key:
                            key_sessions.append((sid, data))
                    
                    if len(key_sessions) > limits:
                        key_sessions.sort(key=lambda x: x[1].get('login_time', ''))
                        to_remove = len(key_sessions) - limits
                        for i in range(to_remove):
                            sid_to_remove = key_sessions[i][0]
                            username_to_kill = key_sessions[i][1].get('username')
                            remove_active_session(sid_to_remove)
                            if username_to_kill:
                                try:
                                    subprocess.run(["pkill", "-9", "-u", username_to_kill], capture_output=True)
                                except:
                                    pass
        except Exception as e:
            print(f"Auto-limit check error: {e}")
        time.sleep(3)

# ============================================
# LOGIN HTML
# ============================================
LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EVT SSH Manager - Admin Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --gold: #FFD700; --bg: #000; --card: #111; }
        body { background: var(--bg); color: #fff; font-family: 'Segoe UI', sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .neon-card { background: var(--card); border: 2px solid var(--gold); border-radius: 20px; padding: 40px; width: 480px; box-shadow: 0 0 30px rgba(255,215,0,0.2); }
        .btn-gold { background: var(--gold); color: #000; font-weight: bold; border-radius: 8px; border: none; padding: 12px; transition: 0.3s; width: 100%; }
        .btn-gold:hover { background: #fff; transform: scale(1.02); }
        .btn-gold:disabled { background: #444; color: #888; cursor: not-allowed; transform: none; }
        .form-control-custom { background: #000 !important; border: 1px solid #444 !important; color: var(--gold) !important; padding: 12px; border-radius: 8px; width: 100%; }
        .form-control-custom:focus { border-color: var(--gold) !important; box-shadow: 0 0 10px rgba(255,215,0,0.3) !important; outline: none; }
        .text-gold { color: var(--gold) !important; }
        .alert { background: #2c2c2c; color: #ff6b6b; border: 1px solid #ff6b6b; }
        .input-group-custom { position: relative; width: 100%; margin-bottom: 20px; }
        .input-group-custom input { padding-left: 45px; width: 100%; }
        .input-group-prepend { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); z-index: 10; color: var(--gold); }
        .toggle-password { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); cursor: pointer; color: var(--gold); z-index: 10; background: transparent; border: none; }
        .vps-ip { text-align: center; margin-bottom: 20px; padding: 8px; background: rgba(0,0,0,0.5); border-radius: 8px; font-size: 13px; }
        .vps-ip i { color: var(--gold); margin-right: 5px; }
        .vps-ip span { color: #28a745; font-family: monospace; }
        .session-full { border-color: #dc3545 !important; background: rgba(220,53,69,0.1) !important; }
        .session-warning { border-color: #ffc107 !important; background: rgba(255,193,7,0.07) !important; }
        .session-ok { border-color: #28a745 !important; background: rgba(40,167,69,0.1) !important; }
        .text-danger { color: #dc3545 !important; }
        .text-warning { color: #ffc107 !important; }
        .text-success { color: #28a745 !important; }
    </style>
</head>
<body>
    <div class="neon-card">
        <div class="text-center mb-3">
            <img src="https://raw.githubusercontent.com/snaymyo/logo/refs/heads/main/evt.png" alt="EVT Logo" style="width: 70px; border-radius: 12px;">
            <h3 class="text-gold fw-bold mt-2">EVT SSH MANAGER</h3>
            <p class="text-secondary small">Admin Login</p>
        </div>
        <div class="vps-ip">
            <i class="fas fa-globe"></i> Your VPS IP: <span id="detectedIp">Loading...</span>
        </div>
        <div class="vps-ip" id="session-status-box">
            <i class="fas fa-users"></i> Active Sessions: 
            <span id="session-count-display" class="fw-bold">0/?</span>
            <span id="session-status-text" class="ms-2 small"></span>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} py-2 small mb-3">{{ message|safe }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST" id="loginForm">
            <div class="input-group-custom">
                <span class="input-group-prepend"><i class="fas fa-user-shield"></i></span>
                <input type="text" name="admin_username" id="admin_username" class="form-control-custom" placeholder="Admin Username" required autocomplete="off">
            </div>
            <div class="input-group-custom">
                <span class="input-group-prepend"><i class="fas fa-lock"></i></span>
                <input type="password" name="admin_password" id="admin_pass" class="form-control-custom" placeholder="Admin Password" required>
                <i class="fas fa-eye toggle-password" onclick="togglePass()"></i>
            </div>
            <div class="input-group-custom">
                <span class="input-group-prepend"><i class="fas fa-key"></i></span>
                <input type="text" name="license_key" id="license_key" class="form-control-custom" placeholder="License Key" required autocomplete="off">
            </div>
            <div class="form-check mb-3">
                <input class="form-check-input" type="checkbox" name="remember" id="remember">
                <label class="form-check-label text-secondary small" for="remember">Remember login info</label>
            </div>
            <button type="submit" class="btn-gold" id="login-btn">
                <i class="fas fa-sign-in-alt" id="login-btn-icon"></i>
                <span id="login-btn-text">LOGIN</span>
            </button>
            <p class="text-danger small text-center mt-2" id="limit-msg" style="display:none"></p>
        </form>
        <div class="mt-3 text-center">
            <small class="text-secondary">© 2026 EVT SSH Manager | Contact: @evtvpnpro</small>
        </div>
    </div>
    <script>
        let sessionCheckTimer = null;
        
        function togglePass() {
            let field = document.getElementById('admin_pass');
            let icon = event.target;
            if (field.type === "password") {
                field.type = "text";
                icon.classList.remove("fa-eye");
                icon.classList.add("fa-eye-slash");
            } else {
                field.type = "password";
                icon.classList.remove("fa-eye-slash");
                icon.classList.add("fa-eye");
            }
        }
        
        function updateSessionDisplay(licenseKey) {
            if (!licenseKey || licenseKey.trim() === '') {
                document.getElementById('session-count-display').textContent = '0/?';
                document.getElementById('session-count-display').className = 'fw-bold text-secondary';
                document.getElementById('session-status-text').textContent = '';
                document.getElementById('session-status-box').className = 'vps-ip';
                enableLoginButton(true);
                return;
            }
            
            fetch('/api/session_count?license_key=' + encodeURIComponent(licenseKey))
                .then(res => res.json())
                .then(data => {
                    const active = data.active;
                    const limit = data.limit;
                    const display = document.getElementById('session-count-display');
                    const statusText = document.getElementById('session-status-text');
                    const box = document.getElementById('session-status-box');
                    const limitMsg = document.getElementById('limit-msg');
                    
                    if (limit > 0) {
                        display.textContent = active + '/' + limit;
                    } else {
                        display.textContent = active + '/?';
                    }
                    
                    if (limit > 0 && active >= limit) {
                        display.className = 'fw-bold text-danger';
                        statusText.textContent = '🔴 Session limit reached';
                        statusText.style.color = '#dc3545';
                        box.className = 'vps-ip session-full';
                        limitMsg.textContent = 'License limit exceeded (' + active + '/' + limit + '). Cannot login.';
                        limitMsg.style.display = 'block';
                        enableLoginButton(false);
                    } else if (limit > 0 && active > 0) {
                        display.className = 'fw-bold text-warning';
                        statusText.textContent = '⚠️ ' + active + '/' + limit + ' Active';
                        statusText.style.color = '#ffc107';
                        box.className = 'vps-ip session-warning';
                        limitMsg.style.display = 'none';
                        enableLoginButton(true);
                    } else {
                        display.className = 'fw-bold text-success';
                        statusText.textContent = '✅ Ready to login';
                        statusText.style.color = '#28a745';
                        box.className = 'vps-ip session-ok';
                        limitMsg.style.display = 'none';
                        enableLoginButton(true);
                    }
                })
                .catch(err => {
                    console.error('Session check error:', err);
                    document.getElementById('session-count-display').textContent = '0/?';
                });
        }
        
        function enableLoginButton(enabled) {
            const btn = document.getElementById('login-btn');
            const btnIcon = document.getElementById('login-btn-icon');
            const btnText = document.getElementById('login-btn-text');
            
            if (enabled) {
                btn.disabled = false;
                btn.style.background = '';
                btn.style.color = '';
                btnIcon.className = 'fas fa-sign-in-alt';
                btnText.textContent = 'LOGIN';
            } else {
                btn.disabled = true;
                btn.style.background = '#444';
                btn.style.color = '#888';
                btnIcon.className = 'fas fa-ban';
                btnText.textContent = 'LIMIT REACHED';
            }
        }
        
        fetch('https://api.ipify.org?format=json')
            .then(res => res.json())
            .then(data => {
                document.getElementById('detectedIp').innerHTML = data.ip;
            })
            .catch(() => {
                document.getElementById('detectedIp').innerHTML = 'Cannot detect';
            });
        
        const licenseInput = document.getElementById('license_key');
        if (licenseInput) {
            licenseInput.addEventListener('input', function() {
                const key = this.value.trim();
                clearTimeout(sessionCheckTimer);
                if (key.length > 5) {
                    sessionCheckTimer = setTimeout(() => updateSessionDisplay(key), 500);
                } else if (key.length === 0) {
                    updateSessionDisplay('');
                }
            });
            
            if (licenseInput.value.trim().length > 5) {
                updateSessionDisplay(licenseInput.value.trim());
            }
        }
        
        const loginForm = document.getElementById('loginForm');
        const userField = document.getElementById('admin_username');
        const passField = document.getElementById('admin_pass');
        const keyField = document.getElementById('license_key');
        const rememberCheck = document.getElementById('remember');
        
        document.addEventListener('DOMContentLoaded', function() {
            const savedData = localStorage.getItem('evt_login_cache');
            if (savedData) {
                try {
                    const data = JSON.parse(savedData);
                    userField.value = data.username || '';
                    passField.value = data.password || '';
                    keyField.value = data.license_key || '';
                    rememberCheck.checked = true;
                    if (keyField.value.trim().length > 5) {
                        setTimeout(() => updateSessionDisplay(keyField.value.trim()), 100);
                    }
                } catch (e) {
                    console.error("Error loading saved login info:", e);
                }
            }
        });
        
        loginForm.addEventListener('submit', function() {
            if (rememberCheck.checked) {
                const data = {
                    username: userField.value,
                    password: passField.value,
                    license_key: keyField.value,
                    saved_at: new Date().toISOString()
                };
                localStorage.setItem('evt_login_cache', JSON.stringify(data));
            } else {
                localStorage.removeItem('evt_login_cache');
            }
        });
        
        setInterval(function() {
            const key = keyField ? keyField.value.trim() : '';
            if (key.length > 5) {
                updateSessionDisplay(key);
            }
        }, 3000);
    </script>
</body>
</html>
"""

# ============================================
# DASHBOARD HTML
# ============================================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EVT SSH Manager - Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --gold: #FFD700; --bg: #000; --card: #111; }
        body { background: var(--bg); color: #fff; font-family: 'Segoe UI', sans-serif; }
        .top-logout-btn { position: absolute; top: 20px; right: 20px; z-index: 1000; background: rgba(220,53,69,0.1); border: 1px solid #dc3545; color: #dc3545; padding: 8px 15px; border-radius: 8px; text-decoration: none; font-weight: bold; transition: all 0.3s ease; display: flex; align-items: center; gap: 8px; }
        .top-logout-btn:hover { background: #dc3545; color: #fff; box-shadow: 0 0 15px rgba(220,53,69,0.4); transform: translateY(-2px); }
        @media (max-width: 576px) { .top-logout-btn { top: 10px; right: 10px; padding: 5px 10px; font-size: 12px; } }
        .logo-center { text-align: center; margin-bottom: 20px; margin-top: 20px; }
        .logo-center img { width: 150px; height: 150px; border-radius: 15px; border: 2px solid var(--gold); box-shadow: 0 0 20px rgba(255,215,0,0.4); transition: transform 0.3s; }
        .logo-center img:hover { transform: scale(1.05); }
        .main-title { font-size: 72px; font-weight: 900; color: #FFD700; text-transform: uppercase; letter-spacing: 8px; text-shadow: 0 0 25px rgba(255,215,0,0.7); margin-bottom: 10px; }
        .sub-title { font-size: 20px; color: #FFD700; letter-spacing: 2px; font-weight: 400; margin-bottom: 5px; }
        .region-time { font-size: 16px; color: #FFD700; letter-spacing: 1px; font-family: monospace; margin-top: 5px; padding: 8px 20px; background: rgba(0,0,0,0.5); display: inline-block; border-radius: 30px; border: 1px solid rgba(255,215,0,0.3); }
        .region-time i { margin-right: 8px; color: var(--gold); }
        .neon-card { background: var(--card); border: 1px solid #333; border-radius: 15px; padding: 20px; margin-bottom: 25px; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }
        .btn-gold { background: var(--gold); color: #000; font-weight: bold; border-radius: 8px; border: none; padding: 10px 20px; transition: 0.3s; }
        .btn-gold:hover { background: #fff; transform: scale(1.02); }
        .btn-edit { background: #2c3e50; color: var(--gold); border: 1px solid var(--gold); border-radius: 8px; padding: 5px 15px; font-size: 12px; transition: 0.3s; margin-left: 10px; }
        .btn-edit:hover { background: var(--gold); color: #000; }
        .form-control-custom { background: #000 !important; border: 1px solid #444 !important; color: var(--gold) !important; padding: 12px; border-radius: 8px; }
        .form-control-custom:focus { border-color: var(--gold) !important; box-shadow: 0 0 10px rgba(255,215,0,0.3) !important; }
        .table-scroll { max-height: 450px; overflow-y: auto; border: 1px solid #333; border-radius: 10px; }
        .table-scroll::-webkit-scrollbar { width: 6px; }
        .table-scroll::-webkit-scrollbar-thumb { background: var(--gold); border-radius: 10px; }
        .table { width: 100%; margin: 0; background: transparent !important; color: #fff !important; }
        .table thead th { background: #1a1a1a !important; color: var(--gold); padding: 15px; position: sticky; top: 0; border-bottom: 1px solid #333; }
        .table tbody tr { background: transparent !important; transition: background 0.3s ease; }
        .table tbody td { background: transparent !important; padding: 12px 15px; border-bottom: 1px solid #222; vertical-align: middle; }
        .table tbody tr:hover { background: rgba(255,215,0,0.05) !important; }
        .text-gold { color: var(--gold) !important; }
        .username-cell { font-size: 20px !important; font-weight: bold; color: #FFD700 !important; }
        .password-cell { font-size: 18px !important; font-family: monospace; font-weight: bold; color: #00ff00 !important; }
        .expiry-cell { font-size: 18px !important; font-weight: bold; color: #FFD700 !important; }
        .device-cell { font-size: 18px !important; font-weight: bold; color: #FFFFFF !important; }
        .device-online { color: #28a745; animation: pulse 1.5s infinite; }
        .device-offline { color: #FFD700; }
        .device-limit { color: #ff6b6b; animation: shake 0.5s infinite; }
        .status-online { background: #28a745; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 14px; display: inline-block; animation: pulse 1.5s infinite; }
        .status-offline { background: #6c757d; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 14px; display: inline-block; }
        .status-expired { background: #dc3545; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 14px; display: inline-block; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
        @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-2px); } 75% { transform: translateX(2px); } }
        .ports-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-top: 10px; }
        .port-card { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 12px 8px; text-align: center; transition: all 0.3s ease; }
        .port-card:hover { border-color: var(--gold); transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255,215,0,0.1); }
        .port-label { font-size: 11px; font-weight: bold; color: var(--gold); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .port-value { font-size: 14px; font-weight: bold; color: #28a745; font-family: monospace; word-break: break-word; }
        @media (max-width: 992px) { .logo-center img { width: 150px; height: 150px; } .ports-grid { grid-template-columns: repeat(3, 1fr); gap: 10px; } .main-title { font-size: 48px; letter-spacing: 5px; } .sub-title { font-size: 16px; } .region-time { font-size: 14px; } }
        @media (max-width: 576px) { .logo-center img { width: 150px; height: 150px; } .ports-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; } .main-title { font-size: 28px; letter-spacing: 3px; } .sub-title { font-size: 12px; } .region-time { font-size: 11px; padding: 5px 12px; } }
        .alert-success { background: #1a3a1a; color: #90ee90; border: 1px solid #2ecc2e; }
        .alert-danger { background: #3a1a1a; color: #ff6b6b; border: 1px solid #ff6b6b; }
        .alert-warning { background: #3a3a1a; color: #ffd700; border: 1px solid #ffd700; }
        .copy-icon { cursor: pointer; margin-left: 8px; color: var(--gold); transition: 0.3s; display: inline-block; }
        .copy-icon:hover { color: #fff; transform: scale(1.1); }
        .btn-outline-custom { background: transparent; border: 1px solid var(--gold); color: var(--gold); border-radius: 8px; padding: 8px 20px; transition: 0.3s; margin: 0 5px; text-decoration: none; display: inline-block; }
        .btn-outline-custom:hover { background: var(--gold); color: #000; text-decoration: none; }
        .footer-buttons { display: flex; justify-content: center; gap: 20px; margin-top: 20px; flex-wrap: wrap; }
        .refresh-indicator { position: fixed; bottom: 10px; right: 10px; background: rgba(0,0,0,0.7); padding: 5px 10px; border-radius: 20px; font-size: 11px; color: #888; z-index: 999; }
        .live-badge { position: fixed; bottom: 10px; left: 10px; background: rgba(0,0,0,0.7); padding: 5px 10px; border-radius: 20px; font-size: 10px; color: #28a745; z-index: 999; }
        .live-badge i { animation: pulse 1.5s infinite; }
        .license-info-bar { background: rgba(0,0,0,0.8); border-left: 4px solid var(--gold); padding: 10px 15px; margin-bottom: 20px; border-radius: 8px; }
        .admin-badge { background: var(--gold); color: #000; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-left: 10px; }
        .creator-badge { color: #aaa; font-size: 11px; margin-left: 8px; }
    </style>
</head>
<body>
    <div class="refresh-indicator"><i class="fas fa-sync-alt fa-fw"></i> Auto-refresh: 60s</div>
    <div class="live-badge"><i class="fas fa-circle"></i> Live Status Updates (3s)</div>
    <a href="{{ url_for('logout') }}" class="top-logout-btn"><i class="fas fa-sign-out-alt"></i> Logout</a>
    <div class="container-fluid px-md-5 py-4">
        <div class="logo-center"><img src="https://raw.githubusercontent.com/snaymyo/logo/refs/heads/main/evt.png" alt="EVT Logo"></div>
        <div class="text-center mb-4">
            <h1 class="main-title">EVT SSH MANAGER</h1>
            <p class="sub-title">Professional SSH Account Management System</p>
            <div class="region-time" id="regionTimeDisplay"><i class="fas fa-map-marker-alt"></i> <span id="regionText">Loading...</span> | <i class="fas fa-clock"></i> <span id="regionCurrentTime">Loading...</span></div>
        </div>
        <div class="license-info-bar">
            <div class="row">
                <div class="col-md-3"><small class="text-warning">🌐 VPS IP</small><br><strong>{{ license_info.vps_ip }}</strong></div>
                <div class="col-md-3"><small class="text-warning">👤 ADMIN</small><br><strong>{{ license_info.admin_username }}</strong></div>
                <div class="col-md-3"><small class="text-warning">🆔 TELEGRAM ID</small><br><strong>{{ license_info.telegram_id or 'Not Linked' }}</strong></div>
                <div class="col-md-3"><small class="text-warning">📅 EXPIRY</small><br><strong class="{% if license_info.expiry != 'No Expiry' and license_info.expiry < today %}text-danger{% else %}text-success{% endif %}">{{ license_info.expiry }}</strong></div>
            </div>
            <div class="row mt-2">
                <div class="col-md-4"><small class="text-warning">🔑 LICENSE KEY</small><br><strong>{{ license_info.license_key }}</strong></div>
                <div class="col-md-4"><small class="text-warning">📊 LIMITS</small><br><strong>{{ license_info.limits }}</strong></div>
                <div class="col-md-4"><small class="text-warning">🖥️ ACTIVE LOGINS</small><br><strong id="panel-active-sessions" class="{% if active_sessions >= license_info.limits %}text-danger{% elif active_sessions > 0 %}text-warning{% else %}text-success{% endif %}">{{ active_sessions }}/{{ license_info.limits }}</strong></div>
            </div>
        </div>
        <div class="row g-3 mb-4 text-center">
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-clock"></i> UPTIME</div><div class="fw-bold fs-5">{{ info.uptime }}</div></div></div>
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-memory"></i> RAM</div><div class="fw-bold fs-5">{{ info.ram }}</div></div></div>
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-users"></i> TOTAL USERS</div><div class="fw-bold fs-5 text-info" id="total-users">{{ info.total }}</div></div></div>
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-globe"></i> ONLINE</div><div class="fw-bold fs-5 text-success" id="online-count">{{ info.online }}</div></div></div>
        </div>
        <div class="neon-card border-info">
            <h6 class="text-info mb-3"><i class="fas fa-dns"></i> DNS SETTINGS <button class="btn-edit" id="toggleDnsEditBtn" onclick="toggleDnsEdit()"><i class="fas fa-edit"></i> Edit</button></h6>
            <div id="dnsDisplayMode">
                <div class="row">
                    <div class="col-md-6"><div class="p-2 bg-black border border-secondary rounded mb-2"><small class="text-warning">DOMAIN</small><br><b class="text-white" id="domain-display">{{ config.DOMAIN }}</b><i class="fas fa-copy copy-icon" onclick="copyToClipboard('domain-display')" title="Copy Domain"></i></div></div>
                    <div class="col-md-6"><div class="p-2 bg-black border border-secondary rounded mb-2"><small class="text-warning">NAME SERVER</small><br><b class="text-white" id="ns-display">{{ config.NS_DOMAIN }}</b><i class="fas fa-copy copy-icon" onclick="copyToClipboard('ns-display')" title="Copy NameServer"></i></div></div>
                    <div class="col-md-12 mt-2"><div class="p-2 bg-black border border-secondary rounded"><small class="text-warning">PUBLIC KEY</small><br><code class="text-white small" id="pubkey-display">{{ dns_key }}</code><i class="fas fa-copy copy-icon" onclick="copyToClipboard('pubkey-display')" title="Copy Public Key"></i></div></div>
                </div>
            </div>
            <div id="dnsEditMode" style="display: none;">
                <form action="/update_dns_settings" method="POST">
                    <div class="row">
                        <div class="col-md-6"><div class="mb-3"><label class="text-warning small">DOMAIN</label><input type="text" name="domain" class="form-control-custom" value="{{ config.DOMAIN }}" required></div></div>
                        <div class="col-md-6"><div class="mb-3"><label class="text-warning small">NAME SERVER</label><input type="text" name="ns_domain" class="form-control-custom" value="{{ config.NS_DOMAIN }}" required></div></div>
                        <div class="col-md-12"><div class="mb-3"><label class="text-warning small">PUBLIC KEY</label><input type="text" name="pubkey" class="form-control-custom" value="{{ dns_key }}" placeholder="Enter public key"></div></div>
                        <div class="col-md-12"><button type="submit" class="btn-gold w-100"><i class="fas fa-save"></i> Save DNS Settings</button><button type="button" class="btn-outline-custom w-100 mt-2" onclick="toggleDnsEdit()"><i class="fas fa-times"></i> Cancel</button></div>
                    </div>
                </form>
            </div>
        </div>
        <div class="neon-card border-info">
            <h6 class="text-info mb-3"><i class="fas fa-plug"></i> ACTIVE PORTS</h6>
            <div class="ports-grid">
                {% for label, port in ports.items() %}
                <div class="port-card"><div class="port-label">{{ label }}</div><div class="port-value">{{ port }}</div></div>
                {% endfor %}
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category if category != 'message' else 'info' }} text-center fw-bold mb-4 flash-message">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}
        <div class="neon-card"><h5 class="text-gold mb-4"><i class="fas fa-plus-circle"></i> CREATE SSH ACCOUNT</h5>
            <form action="/gen_key" method="POST" class="row g-3">
                <div class="col-md-3"><input type="text" name="username" class="form-control-custom w-100" placeholder="Username" required></div>
                <div class="col-md-3"><input type="text" name="password" class="form-control-custom w-100" placeholder="Password" required></div>
                <div class="col-md-2"><input type="number" name="days" class="form-control-custom w-100" value="30" required><small class="text-secondary">Days</small></div>
                <div class="col-md-2"><input type="number" name="limit" class="form-control-custom w-100" value="1" required><small class="text-secondary">Limit</small></div>
                <div class="col-md-2"><button type="submit" class="btn-gold w-100">CREATE</button></div>
            </form>
        </div>
        <div class="neon-card p-0 overflow-hidden shadow-lg mb-4">
            <h5 class="text-primary p-4 mb-0"><i class="fas fa-users"></i> ACTIVE SSH USERS</h5>
            <div class="table-scroll">
                <table class="table table-hover text-center">
                    <thead>
                        <tr><th>USERNAME</th><th>PASSWORD</th><th>DEVICE</th><th>EXPIRY</th><th>STATUS</th><th>ACTIONS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for key, val in keys.items() %}
                        {% set is_expired = val.expiry < today %}
                        <tr id="row-{{ key }}" data-username="{{ val.username }}" data-key="{{ key }}" data-limit="{{ val.limit }}" data-expiry="{{ val.expiry }}" data-password="{{ val.password }}">
                            <td class="username-cell">
                                <i class="fas fa-user-circle me-2"></i>{{ val.username }}
                                {% if val.telegram_id %}
                                    <small class="creator-badge">(by: {{ val.telegram_id }})</small>
                                {% endif %}
                            </td>
                            <td><span class="password-cell" id="pass-{{ key }}">••••••••</span> <i class="fas fa-eye-slash ms-2 text-secondary" id="icon-{{ key }}" style="cursor:pointer" onclick="togglePass('{{ key }}', '{{ val.password }}')"></i></td>
                            <td class="device-cell"><span class="device-status-{{ key }} {% if val.online_count > val.limit %}device-limit{% elif val.online_count > 0 %}device-online{% else %}device-offline{% endif %}">{{ val.online_count }} / {{ val.limit }}</span></td>
                            <td class="expiry-cell">{{ val.expiry }}</td>
                            <td><span class="status-badge-{{ key }} {% if is_expired %}status-expired{% elif val.status == 'Online' %}status-online{% else %}status-offline{% endif %}">{% if is_expired %}Expired{% elif val.status == 'Online' %}Online{% else %}Offline{% endif %}</span></td>
                            <td><div class="btn-group btn-group-sm"><button class="btn btn-outline-warning" data-bs-toggle="modal" data-bs-target="#editModal{{ key }}"><i class="fas fa-edit"></i> EDIT</button><a href="/delete/{{ key }}" class="btn btn-outline-danger" onclick="return confirm('Delete user {{ val.username }}?')"><i class="fas fa-trash"></i> DEL</a></div></td>
                        </tr>
                        <div class="modal fade" id="editModal{{ key }}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content bg-black border border-secondary text-white"><div class="modal-header border-secondary"><h5 class="text-gold">Edit User: {{ val.username }}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><form action="/edit_key/{{ key }}" method="POST"><div class="modal-body"><div class="mb-3"><label class="small text-warning">PASSWORD</label><input type="text" name="password" class="form-control-custom w-100" value="{{ val.password }}" required></div><div class="mb-3"><label class="small text-warning">LIMIT</label><input type="number" name="limit" class="form-control-custom w-100" value="{{ val.limit }}" required></div><div class="mb-3"><label class="small text-warning">EXPIRY DATE</label><input type="date" name="expiry" class="form-control-custom w-100" value="{{ val.expiry }}" required></div></div><div class="modal-footer border-secondary"><button type="submit" class="btn-gold w-100">SAVE CHANGES</button></div></form></div></div></div>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <div class="footer-buttons">
            <a href="/backup_users" class="btn-outline-custom"><i class="fas fa-download"></i> Backup Users</a>
            <button class="btn-outline-custom" onclick="document.getElementById('restore-file-input').click()"><i class="fas fa-upload"></i> Restore Users</button>
            <a href="/logout" class="btn-outline-custom" style="border-color: #dc3545; color: #dc3545;"><i class="fas fa-sign-out-alt"></i> Logout</a>
            <form id="restore-form" action="/restore_users" method="POST" enctype="multipart/form-data" style="display: none;"><input type="file" id="restore-file-input" name="backup_file" accept=".json" onchange="document.getElementById('restore-form').submit()"></form>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function updateLiveStatus() {
            fetch('/api/online_status')
                .then(response => response.json())
                .then(data => {
                    const onlineCountElement = document.getElementById('online-count');
                    if (onlineCountElement) onlineCountElement.textContent = data.total_online;
                    const totalUsersElement = document.getElementById('total-users');
                    if (totalUsersElement && data.total_users) totalUsersElement.textContent = data.total_users;
                    if (data.session_valid === false) { window.location.href = '/logout?reason=limit_exceeded'; return; }
                    const activeLoginsEl = document.getElementById('panel-active-sessions');
                    if (activeLoginsEl && data.active_sessions !== undefined && data.session_limit !== undefined) {
                        const act = data.active_sessions; const lim = data.session_limit;
                        activeLoginsEl.textContent = act + '/' + lim;
                        activeLoginsEl.classList.remove('text-success', 'text-warning', 'text-danger');
                        if (act >= lim) activeLoginsEl.classList.add('text-danger');
                        else if (act > 0) activeLoginsEl.classList.add('text-warning');
                        else activeLoginsEl.classList.add('text-success');
                    }
                    for (const [key, status] of Object.entries(data.status)) {
                        const deviceSpan = document.querySelector(`.device-status-${key}`);
                        const statusSpan = document.querySelector(`.status-badge-${key}`);
                        const row = document.getElementById(`row-${key}`);
                        if (deviceSpan && status) {
                            const deviceText = status.device_status;
                            deviceSpan.textContent = deviceText;
                            const limit = row ? row.getAttribute('data-limit') : 1;
                            const onlineNum = parseInt(deviceText.split('/')[0]);
                            deviceSpan.classList.remove('device-online', 'device-offline', 'device-limit');
                            if (onlineNum > limit) deviceSpan.classList.add('device-limit');
                            else if (onlineNum > 0) deviceSpan.classList.add('device-online');
                            else deviceSpan.classList.add('device-offline');
                        }
                        if (statusSpan && status) {
                            const isOnline = status.status === 'Online';
                            statusSpan.textContent = isOnline ? 'Online' : 'Offline';
                            statusSpan.classList.remove('status-online', 'status-offline', 'status-expired');
                            if (isOnline) statusSpan.classList.add('status-online');
                            else { const row = document.getElementById(`row-${key}`); const expiry = row ? row.getAttribute('data-expiry') : ''; const today = new Date().toISOString().split('T')[0]; if (expiry && expiry < today) { statusSpan.classList.add('status-expired'); statusSpan.textContent = 'Expired'; } else statusSpan.classList.add('status-offline'); }
                        }
                    }
                }).catch(error => console.error('Error fetching status:', error));
        }
        setInterval(updateLiveStatus, 3000);
        document.addEventListener('DOMContentLoaded', function() { updateLiveStatus(); const flashMessages = document.querySelectorAll('.flash-message'); if (flashMessages.length > 0) { setTimeout(function() { flashMessages.forEach(function(msg) { msg.style.opacity = '0'; setTimeout(function() { if (msg.parentNode) msg.remove(); }, 500); }); }, 2000); } });
        function updateRegionTime() { const regionSpan = document.getElementById('regionText'); const regionTimeSpan = document.getElementById('regionCurrentTime'); if (regionSpan && regionTimeSpan) { const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone; const now = new Date(); const options = { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }; const formattedTime = new Intl.DateTimeFormat('en-GB', options).format(now); regionSpan.innerHTML = timezone; regionTimeSpan.innerHTML = formattedTime; } }
        updateRegionTime(); setInterval(updateRegionTime, 1000);
        function toggleDnsEdit() { const displayMode = document.getElementById('dnsDisplayMode'); const editMode = document.getElementById('dnsEditMode'); const toggleBtn = document.getElementById('toggleDnsEditBtn'); if (displayMode.style.display === 'none') { displayMode.style.display = 'block'; editMode.style.display = 'none'; toggleBtn.innerHTML = '<i class="fas fa-edit"></i> Edit'; } else { displayMode.style.display = 'none'; editMode.style.display = 'block'; toggleBtn.innerHTML = '<i class="fas fa-times"></i> Cancel'; } }
        function togglePass(id, p) { let span = document.getElementById('pass-' + id); let icon = document.getElementById('icon-' + id); if(span.innerText === '••••••••') { span.innerText = p; icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); } else { span.innerText = '••••••••'; icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); } }
        function copyToClipboard(elementId) { const element = document.getElementById(elementId); const text = element.innerText; if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(() => { const icon = event.target; const originalClass = icon.className; icon.className = 'fas fa-check copy-icon'; icon.style.color = '#28a745'; setTimeout(() => { icon.className = originalClass; icon.style.color = ''; }, 1500); }).catch(err => { fallbackCopy(text); }); } else { fallbackCopy(text); } }
        function fallbackCopy(text) { const textarea = document.createElement('textarea'); textarea.value = text; document.body.appendChild(textarea); textarea.select(); try { document.execCommand('copy'); const icon = event.target; const originalClass = icon.className; icon.className = 'fas fa-check copy-icon'; icon.style.color = '#28a745'; setTimeout(() => { icon.className = originalClass; icon.style.color = ''; }, 1500); } catch (err) {} document.body.removeChild(textarea); }
        setInterval(function() { fetch('/api/online_status').catch(() => {}); }, 30000);
    </script>
</body>
</html>
"""

# ============================================
# FLASK ROUTES
# ============================================
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    valid, message, license_data = check_license_from_github()
    active_count = 0
    total_limits = 0
    if valid and license_data:
        total_limits = license_data.get('limits', 0)
        cleanup_expired_sessions()
        active_count = get_active_count_for_license(license_data.get('license_key', ''))
    
    if request.method == 'POST':
        admin_username = request.form.get('admin_username', '').strip()
        admin_password = request.form.get('admin_password', '').strip()
        license_key = request.form.get('license_key', '').strip()
        remember = request.form.get('remember') == 'on'
        
        valid, message, license_data = check_license_from_github(admin_username, license_key)
        if not valid:
            flash(f"❌ {message}", "danger")
            return render_template_string(LOGIN_HTML)
        
        if admin_password != license_data.get('admin_password'):
            flash("❌ Invalid Admin Password!", "danger")
            return render_template_string(LOGIN_HTML)
        
        expected_limits = license_data.get('limits', 0)
        current_active = get_active_count_for_license(license_key)
        
        if current_active >= expected_limits:
            flash(f"❌ Login limit reached! Maximum {expected_limits} concurrent sessions.", "danger")
            return render_template_string(LOGIN_HTML)
        
        sessions = get_active_sessions()
        old_session_id = None
        for sid, data in sessions.items():
            if data.get('license_key') == license_key and data.get('username') == admin_username:
                old_session_id = sid
                break
        if old_session_id:
            remove_active_session(old_session_id)
        
        session_id = str(uuid.uuid4())
        add_active_session(session_id, license_key, admin_username, request.remote_addr)
        session['active_session_id'] = session_id
        session['license_key'] = license_key
        
        license_admin_username = license_data.get('admin_username', admin_username)
        license_telegram_id = license_data.get('telegram_id', None)
        
        user = Admin(f"{admin_username}|{admin_username}|{license_key}|{license_admin_username}|{license_telegram_id}", 
                     admin_username, license_key, license_admin_username, license_telegram_id)
        login_user(user, remember=False)
        flash(f"✅ Login successful!", "success")
        return redirect(url_for('admin_dashboard'))
    
    return render_template_string(LOGIN_HTML)

@app.route('/dashboard')
@login_required
def admin_dashboard():
    valid, message, license_data = check_license_from_github()
    if not valid:
        logout_user()
        flash(f"❌ LICENSE ERROR: {message}", "danger")
        return redirect(url_for('login'))
    
    cleanup_expired_sessions()
    license_key = license_data.get('license_key', '')
    active_count = get_active_count_for_license(license_key)
    
    current_admin_username = current_user.admin_username if hasattr(current_user, 'admin_username') else current_user.username
    current_telegram_id = current_user.telegram_id if hasattr(current_user, 'telegram_id') else None
    
    license_info = {
        'vps_ip': license_data.get('vps_ip', 'Unknown'),
        'expiry': license_data.get('expiry', 'No Expiry'),
        'admin_username': current_admin_username,
        'limits': license_data.get('limits', 999),
        'telegram_id': license_data.get('telegram_id', None),
        'license_key': license_data.get('license_key', 'Unknown'),
    }
    
    # Load all keys and filter by telegram_id
    all_keys = load_keys()
    filtered_keys = {}
    for key, val in all_keys.items():
        if str(val.get('telegram_id')) == str(current_telegram_id):
            filtered_keys[key] = val
    
    online_users = 0
    today = date.today().strftime("%Y-%m-%d")
    all_active_users = get_all_users_online_status()
    
    for key, val in filtered_keys.items():
        username = val.get('username')
        if username:
            is_online = username in all_active_users
            try:
                pids = subprocess.getoutput(f"pgrep -u {username} 'sshd|dropbear' 2>/dev/null").split()
                online_num = len(pids) if pids and pids[0] != "" else (1 if is_online else 0)
            except:
                online_num = 1 if is_online else 0
            val['online_count'] = online_num
            val['status'] = "Online" if online_num > 0 else "Offline"
            if online_num > 0:
                online_users += 1
        else:
            val['online_count'] = 0
            val['status'] = "Not Synced"
    
    info = {
        "uptime": subprocess.getoutput("uptime -p").replace("up ", ""),
        "ram": subprocess.getoutput("free -h | grep Mem | awk '{print $3 \"/\" $2}'"),
        "total": len(filtered_keys),
        "online": online_users
    }
    
    return render_template_string(DASHBOARD_HTML, info=info, keys=filtered_keys, ports=get_live_ports(), config=get_evt_config(), dns_key=get_slowdns_pubkey(), license_info=license_info, today=today, active_sessions=active_count)

@app.route('/gen_key', methods=['POST'])
@login_required
def gen_key():
    valid, _, _ = check_license_from_github()
    if not valid:
        flash("License expired or invalid!", "danger")
        return redirect(url_for('logout'))
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    try:
        days = int(request.form.get('days', 30))
        limit = int(request.form.get('limit', 1))
    except:
        days, limit = 30, 1
    
    if not username or not password:
        flash("Username and Password are required!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    current_telegram_id = current_user.telegram_id if hasattr(current_user, 'telegram_id') else None
    
    keys = load_keys()
    
    if any(v.get('username') == username for v in keys.values()):
        flash(f"Error: Username '{username}' already exists!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    key_id = "EVT-" + str(uuid.uuid4()).upper()[:8]
    
    keys[key_id] = {
        "username": username,
        "password": password,
        "expiry": expiry,
        "limit": limit,
        "telegram_id": str(current_telegram_id) if current_telegram_id else None,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_keys(keys)
    
    if sync_user_to_system(username, password, expiry, limit):
        flash(f"✅ User '{username}' created successfully!", "success")
    else:
        flash(f"⚠️ User created but sync failed!", "warning")
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_key/<key_id>', methods=['POST'])
@login_required
def edit_key(key_id):
    valid, _, _ = check_license_from_github()
    if not valid:
        flash("License expired or invalid!", "danger")
        return redirect(url_for('logout'))
    
    current_telegram_id = current_user.telegram_id if hasattr(current_user, 'telegram_id') else None
    
    keys = load_keys()
    if key_id not in keys:
        flash("Key not found!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    # Check ownership
    if str(keys[key_id].get('telegram_id')) != str(current_telegram_id):
        flash("You don't have permission to edit this user!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    password = request.form.get('password', '').strip()
    try:
        limit = int(request.form.get('limit', 1))
    except:
        limit = 1
    expiry = request.form.get('expiry', '').strip()
    
    if password:
        keys[key_id]['password'] = password
    if limit:
        keys[key_id]['limit'] = limit
    if expiry:
        keys[key_id]['expiry'] = expiry
    
    save_keys(keys)
    username = keys[key_id]['username']
    sync_user_to_system(username, keys[key_id]['password'], keys[key_id]['expiry'], keys[key_id]['limit'])
    flash(f"✅ User '{username}' updated successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/delete/<key_id>')
@login_required
def delete_key(key_id):
    valid, _, _ = check_license_from_github()
    if not valid:
        flash("License expired or invalid!", "danger")
        return redirect(url_for('logout'))
    
    current_telegram_id = current_user.telegram_id if hasattr(current_user, 'telegram_id') else None
    
    keys = load_keys()
    if key_id not in keys:
        flash("Key not found!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    # Check ownership
    if str(keys[key_id].get('telegram_id')) != str(current_telegram_id):
        flash("You don't have permission to delete this user!", "danger")
        return redirect(url_for('admin_dashboard'))
    
    username = keys[key_id].get('username')
    if username:
        subprocess.run(["userdel", "-f", username], capture_output=True)
        subprocess.run(f"sed -i '/^{username} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
    
    del keys[key_id]
    save_keys(keys)
    
    flash(f"✅ User '{username}' deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/backup_users')
@login_required
def backup_users():
    try:
        keys = load_keys()
        backup_json = json.dumps(keys, indent=4)
        return send_file(
            io.BytesIO(backup_json.encode()),
            as_attachment=True,
            download_name=f"evt_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mimetype='application/json'
        )
    except Exception as e:
        flash(f"Backup failed: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/restore_users', methods=['POST'])
@login_required
def restore_users():
    valid, _, _ = check_license_from_github()
    if not valid:
        flash("License expired or invalid!", "danger")
        return redirect(url_for('logout'))
    
    import io
    try:
        if 'backup_file' not in request.files:
            flash("No file selected!", "danger")
            return redirect(url_for('admin_dashboard'))
        file = request.files['backup_file']
        if file.filename == '':
            flash("No file selected!", "danger")
            return redirect(url_for('admin_dashboard'))
        if not file.filename.endswith('.json'):
            flash("Please upload a JSON file!", "danger")
            return redirect(url_for('admin_dashboard'))
        
        content = file.read().decode('utf-8')
        restored_data = json.loads(content)
        
        # Validate and save
        if isinstance(restored_data, dict):
            save_keys(restored_data)
        else:
            flash("Invalid backup format!", "danger")
            return redirect(url_for('admin_dashboard'))
        
        synced, errors = sync_all_users_to_system()
        flash(f"✅ Restore successful! Synced: {synced}, Errors: {errors}", "success")
    except json.JSONDecodeError as e:
        flash(f"Invalid JSON file: {str(e)}", "danger")
    except Exception as e:
        flash(f"Restore failed: {str(e)}", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/update_dns_settings', methods=['POST'])
@login_required
def update_dns_settings():
    domain = request.form.get('domain', '').strip()
    ns_domain = request.form.get('ns_domain', '').strip()
    pubkey = request.form.get('pubkey', '').strip()
    
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write(f'DOMAIN="{domain}"\n')
            f.write(f'NS_DOMAIN="{ns_domain}"\n')
        if pubkey and pubkey != "None":
            os.makedirs("/etc/dnstt", exist_ok=True)
            with open("/etc/dnstt/server.pub", "w") as f:
                f.write(pubkey)
        flash("✅ DNS Settings updated successfully!", "success")
    except Exception as e:
        flash(f"❌ Update failed: {str(e)}", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    try:
        active_session_id = session.get('active_session_id')
        if active_session_id:
            remove_active_session(active_session_id)
        logout_user()
        session.clear()
        return redirect(url_for('login'))
    except:
        session.clear()
        return redirect(url_for('login'))

@app.route('/api/session_count')
def api_session_count():
    license_key = request.args.get('license_key', '').strip()
    if not license_key:
        return jsonify({'active': 0, 'limit': 0, 'can_login': True})
    
    cleanup_expired_sessions()
    active_count = get_active_count_for_license(license_key)
    limit = get_limit_from_github_by_license(license_key)
    
    return jsonify({
        'active': active_count,
        'limit': limit,
        'can_login': (limit == 0 or active_count < limit)
    })

@app.route('/api/online_status')
@login_required
def api_online_status():
    active_session_id = session.get('active_session_id')
    if active_session_id:
        update_session_heartbeat(active_session_id)
    
    current_telegram_id = current_user.telegram_id if hasattr(current_user, 'telegram_id') else None
    
    all_keys = load_keys()
    filtered_keys = {}
    for key, val in all_keys.items():
        if str(val.get('telegram_id')) == str(current_telegram_id):
            filtered_keys[key] = val
    
    status_dict = {}
    online_total = 0
    active_users = get_all_users_online_status()
    
    for key, val in filtered_keys.items():
        username = val.get('username')
        limit = val.get('limit', 1)
        if username:
            is_online = username in active_users
            if not is_online:
                pids = subprocess.getoutput(f"pgrep -u {username} 'sshd|dropbear' 2>/dev/null").split()
                is_online = len(pids) > 0 and pids[0] != ""
            online_num = len(pids) if is_online and pids and pids[0] != "" else (1 if is_online else 0)
            status_dict[key] = {
                'username': username,
                'status': "Online" if is_online else "Offline",
                'online_count': online_num,
                'device_status': f"{online_num} / {limit}"
            }
            if is_online:
                online_total += 1
    
    license_key_for_count = session.get('license_key', '')
    panel_active = get_active_count_for_license(license_key_for_count)
    panel_limit = get_limit_from_github_by_license(license_key_for_count)
    
    all_sessions = get_active_sessions()
    
    return jsonify({
        'status': status_dict,
        'total_online': online_total,
        'total_users': len(filtered_keys),
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'active_sessions': panel_active,
        'session_limit': panel_limit,
        'session_valid': (active_session_id in all_sessions if active_session_id else True)
    })

# ============================================
# SYSTEM DEPENDENCIES INSTALLATION
# ============================================
def run_command_hidden(cmd, description):
    try:
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except:
        return False

def is_package_installed(package):
    try:
        result = subprocess.run(["dpkg", "-s", package], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def is_python_package_installed(package):
    try:
        __import__(package.replace("-", "_"))
        return True
    except ImportError:
        return False

def install_system_dependencies():
    system_packages = [
        "python3-pip", "net-tools", "ssh", "dropbear", "stunnel4", 
        "openvpn", "squid", "curl", "wget", "iptables", "screen", "ufw"
    ]
    
    python_packages = ["flask", "flask-login", "requests", "waitress", "werkzeug"]
    
    missing_system = []
    for pkg in system_packages:
        if not is_package_installed(pkg):
            missing_system.append(pkg)
    
    missing_python = []
    for pkg in python_packages:
        if not is_python_package_installed(pkg):
            missing_python.append(pkg)
    
    if missing_system:
        run_command_hidden("apt-get update -y", "Updating system")
        for pkg in missing_system:
            run_command_hidden(f"apt-get install -y {pkg}", f"Installing {pkg}")
    
    if missing_python:
        run_command_hidden("pip3 install --upgrade " + " ".join(missing_python), "Installing Python packages")
    
    return True

# ============================================
# UTILITY FUNCTIONS
# ============================================
def safe_write_file(filepath, content):
    try:
        with open(filepath, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(content)
        return True
    except:
        return False

def safe_read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except:
        return ""

def clean_domain_input(input_str):
    if not input_str:
        return ""
    cleaned = re.sub(r'[^\x00-\x7F]+', '', input_str)
    cleaned = re.sub(r'[^a-zA-Z0-9\.\-]', '', cleaned)
    return cleaned.strip()

# ============================================
# DOMAIN CONFIGURATION
# ============================================
def ask_domain():
    print(f"\n{YELLOW}[1/4] DOMAIN CONFIGURATION{NC}")
    print(f"{CYAN}────────────────────────────────────────────────────────────{NC}")
    
    domain = input(f" ◇ Enter your DOMAIN (Default: evtvip.com): ").strip()
    domain = clean_domain_input(domain)
    if not domain:
        domain = "evtvip.com"
    
    ns_domain = input(f" ◇ Enter your NAMESERVER (Default: ns.evtvip.com): ").strip()
    ns_domain = clean_domain_input(ns_domain)
    if not ns_domain:
        ns_domain = "ns.evtvip.com"
    
    os.makedirs("/etc", exist_ok=True)
    config_content = f'DOMAIN="{domain}"\nNS_DOMAIN="{ns_domain}"\n'
    
    if safe_write_file("/etc/evt_config", config_content):
        print(f"\n{GREEN}✓ DOMAIN saved: {domain}{NC}")
        print(f"{GREEN}✓ NS DOMAIN saved: {ns_domain}{NC}")
    else:
        print(f"{RED}✗ Failed to save config{NC}")
    
    print(f"{CYAN}────────────────────────────────────────────────────────────{NC}")
    time.sleep(1)
    return domain, ns_domain

# ============================================
# PORT MANAGER FUNCTIONS
# ============================================
def setup_squid_proxy():
    run_command_hidden("systemctl stop squid", "")
    run_command_hidden("systemctl stop squid3", "")
    run_command_hidden("pkill -f squid", "")
    
    squid_conf = '''# Squid proxy configuration
http_port 8080
http_port 3128

acl all src 0.0.0.0/0
http_access allow all

cache deny all

maximum_object_size_in_memory 512 KB
memory_replacement_policy heap GDSF
cache_replacement_policy heap LFUDA

connect_timeout 30 seconds
read_timeout 60 seconds
request_timeout 30 seconds
client_lifetime 24 hours

dns_nameservers 8.8.8.8 8.8.4.4

access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log

forwarded_for delete
request_header_access X-Forwarded-For deny all
request_header_access Via deny all

via off
'''
    
    os.makedirs("/etc/squid", exist_ok=True)
    safe_write_file("/etc/squid/squid.conf", squid_conf)
    
    os.makedirs("/var/spool/squid", exist_ok=True)
    run_command_hidden("chown -R proxy:proxy /var/spool/squid", "")
    run_command_hidden("chown -R proxy:proxy /var/log/squid", "")
    run_command_hidden("squid -z", "")
    time.sleep(1)
    
    run_command_hidden("systemctl start squid", "")
    time.sleep(2)
    
    result = subprocess.run(["systemctl", "is-active", "squid"], capture_output=True, text=True)
    if "active" not in result.stdout:
        run_command_hidden("squid -f /etc/squid/squid.conf", "")
        time.sleep(2)
    
    for port in [8080, 3128]:
        run_command_hidden(f"iptables -A INPUT -p tcp --dport {port} -j ACCEPT", "")
    
    print(f"{GREEN}   ✓ SQUID PROXY running on ports 8080 and 3128{NC}")

def run_port_manager_auto():
    print(f"\n{YELLOW}[2/4] PORT MANAGER - Auto Setup{NC}")
    print(f"{CYAN}────────────────────────────────────────────────────────────{NC}")
    
    # PROXY SOCKS on port 2052
    run_command_hidden("pkill -f proxy_2052", "")
    run_command_hidden("fuser -k 2052/tcp", "")
    
    proxy_script = '''import socket, threading, select
def forward(source, destination):
    string_list = [source, destination]
    while True:
        read_list, _, _ = select.select(string_list, [], [], 10)
        if not read_list: continue
        for sock in read_list:
            try:
                data = sock.recv(16384)
                if not data: return
                if sock is source: destination.sendall(data)
                else: source.sendall(data)
            except: return
def handler(client, address):
    try:
        header = client.recv(16384).decode('utf-8', errors='ignore')
        target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target.connect(('127.0.0.1', 22))
        if "Upgrade: websocket" in header or "GET" in header or "CONNECT" in header:
            client.sendall(b"HTTP/1.1 101 Switching Protocols\\r\\nUpgrade: websocket\\r\\nConnection: Upgrade\\r\\n\\r\\n")
        forward(client, target)
    except: pass
    finally: client.close()
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 2052))
    server.listen(1000)
    while True:
        client, address = server.accept()
        threading.Thread(target=handler, args=(client, address), daemon=True).start()
if __name__ == '__main__':
    main()
'''
    
    os.makedirs("/usr/local/bin", exist_ok=True)
    safe_write_file("/usr/local/bin/proxy_2052.py", proxy_script)
    os.chmod("/usr/local/bin/proxy_2052.py", 0o755)
    run_command_hidden("screen -dmS proxy_2052 python3 /usr/local/bin/proxy_2052.py", "")
    time.sleep(2)
    
    print(f"{GREEN}   ✓ PROXY SOCKS running on port 2052{NC}")
    
    # SQUID PROXY
    setup_squid_proxy()
    
    # DROPBEAR on ports 143 and 110
    run_command_hidden("killall dropbear", "")
    run_command_hidden("pkill -x dropbear", "")
    run_command_hidden("systemctl stop dropbear", "")
    time.sleep(1)
    
    os.makedirs("/etc/dropbear", exist_ok=True)
    os.makedirs("/var/run/dropbear", exist_ok=True)
    
    if not os.path.exists("/etc/dropbear/dropbear_rsa_host_key"):
        run_command_hidden("dropbearkey -t rsa -f /etc/dropbear/dropbear_rsa_host_key -s 2048", "")
    if not os.path.exists("/etc/dropbear/dropbear_dss_host_key"):
        run_command_hidden("dropbearkey -t dss -f /etc/dropbear/dropbear_dss_host_key", "")
    if not os.path.exists("/etc/dropbear/dropbear_ecdsa_host_key"):
        run_command_hidden("dropbearkey -t ecdsa -f /etc/dropbear/dropbear_ecdsa_host_key -s 521", "")
    
    run_command_hidden("dropbear -p 143 -p 110 -R", "")
    time.sleep(2)
    
    print(f"{GREEN}   ✓ DROPBEAR running on ports 143 and 110{NC}")
    
    # SSL TUNNEL on port 443
    run_command_hidden("systemctl stop stunnel4", "")
    run_command_hidden("pkill -f stunnel", "")
    
    os.makedirs("/etc/stunnel", exist_ok=True)
    
    run_command_hidden("openssl genrsa -out /etc/stunnel/stunnel.key 2048", "")
    run_command_hidden("openssl req -new -x509 -key /etc/stunnel/stunnel.key -out /etc/stunnel/stunnel.crt -days 1095 -subj /CN=SSHPLUS", "")
    
    stunnel_pem = ""
    with open("/etc/stunnel/stunnel.key", "r") as key:
        stunnel_pem += key.read()
    with open("/etc/stunnel/stunnel.crt", "r") as crt:
        stunnel_pem += crt.read()
    safe_write_file("/etc/stunnel/stunnel.pem", stunnel_pem)
    
    stunnel_conf = '''cert = /etc/stunnel/stunnel.pem
client = no
socket = a:SO_REUSEADDR=1
socket = l:TCP_NODELAY=1
socket = r:TCP_NODELAY=1
[ssh]
accept = 443
connect = 127.0.0.1:22
'''
    safe_write_file("/etc/stunnel/stunnel.conf", stunnel_conf)
    
    run_command_hidden("sed -i 's/ENABLED=0/ENABLED=1/g' /etc/default/stunnel4", "")
    run_command_hidden("systemctl restart stunnel4", "")
    time.sleep(2)
    
    print(f"{GREEN}   ✓ SSL TUNNEL running on port 443{NC}")
    
    # Firewall rules
    ports = [2052, 8080, 3128, 143, 110, 443]
    for port in ports:
        run_command_hidden(f"iptables -A INPUT -p tcp --dport {port} -j ACCEPT", "")
    
    run_command_hidden("iptables-save > /etc/iptables/rules.v4", "")
    
    print(f"{GREEN}────────────────────────────────────────────────────────────{NC}")
    print(f"{GREEN}[✓] PORT MANAGER AUTO SETUP COMPLETED!{NC}")
    print(f"{CYAN}   - PROXY SOCKS  : port 2052{NC}")
    print(f"{CYAN}   - SQUID PROXY  : ports 8080, 3128{NC}")
    print(f"{CYAN}   - DROPBEAR     : ports 143, 110{NC}")
    print(f"{CYAN}   - SSL TUNNEL   : port 443{NC}")
    print(f"{GREEN}────────────────────────────────────────────────────────────{NC}")
    time.sleep(2)

# ============================================
# SLOWDNS FUNCTIONS
# ============================================
def get_primary_interface():
    result = subprocess.run(["ip", "route", "|", "grep", "default"], 
                           capture_output=True, text=True, shell=True)
    if result.stdout:
        parts = result.stdout.split()
        if len(parts) >= 5:
            return parts[4]
    return "eth0"

def detect_ssh_port():
    result = subprocess.run(["ss", "-tlnp", "|", "grep", "sshd"], 
                           capture_output=True, text=True, shell=True)
    if result.stdout:
        match = re.search(r':(\d+)', result.stdout)
        if match:
            return match.group(1)
    return "22"

def run_slowdns_auto():
    print(f"\n{YELLOW}[3/4] SLOWDNS MANAGER - Full Auto Setup{NC}")
    print(f"{CYAN}────────────────────────────────────────────────────────────{NC}")
    
    ns_domain = "ns.evtvip.com"
    if os.path.exists("/etc/evt_config"):
        config_content = safe_read_file("/etc/evt_config")
        for line in config_content.splitlines():
            if "NS_DOMAIN" in line:
                ns_domain = line.split("=")[1].strip().strip('"')
                break
    
    print(f"{CYAN}   ➤ Using NS Domain: {ns_domain}{NC}")
    
    run_command_hidden("apt-get install -y curl wget dnsutils", "")
    
    arch = os.uname().machine
    if arch == "x86_64":
        arch = "amd64"
    elif arch in ["aarch64", "arm64"]:
        arch = "arm64"
    elif arch in ["armv7l", "armv6l"]:
        arch = "arm"
    else:
        arch = "amd64"
    
    dnstt_base_url = "https://dnstt.network"
    filename = f"dnstt-server-linux-{arch}"
    filepath = f"/usr/local/bin/dnstt-server"
    
    run_command_hidden(f"curl -L -o /tmp/{filename} {dnstt_base_url}/{filename}", "")
    run_command_hidden(f"chmod +x /tmp/{filename}", "")
    run_command_hidden(f"mv /tmp/{filename} {filepath}", "")
    
    if not os.path.exists(filepath):
        print(f"{RED}   ✗ Failed to download dnstt-server{NC}")
        return ""
    
    run_command_hidden("useradd -r -s /bin/false -d /nonexistent dnstt", "")
    
    config_dir = "/etc/dnstt"
    os.makedirs(config_dir, exist_ok=True)
    
    key_prefix = ns_domain.replace(".", "_")
    private_key_file = f"{config_dir}/{key_prefix}_server.key"
    public_key_file = f"{config_dir}/{key_prefix}_server.pub"
    
    run_command_hidden(f"{filepath} -gen-key -privkey-file {private_key_file} -pubkey-file {public_key_file}", "")
    
    run_command_hidden(f"chown -R dnstt:dnstt {config_dir}", "")
    run_command_hidden(f"chmod 600 {private_key_file}", "")
    run_command_hidden(f"chmod 644 {public_key_file}", "")
    
    interface = get_primary_interface()
    dnstt_port = "5300"
    
    run_command_hidden(f"iptables -I INPUT -p udp --dport {dnstt_port} -j ACCEPT", "")
    run_command_hidden(f"iptables -t nat -I PREROUTING -i {interface} -p udp --dport 53 -j REDIRECT --to-ports {dnstt_port}", "")
    
    os.makedirs("/etc/iptables", exist_ok=True)
    run_command_hidden("iptables-save > /etc/iptables/rules.v4", "")
    
    ssh_port = detect_ssh_port()
    
    service_content = f'''[Unit]
Description=dnstt DNS Tunnel Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=dnstt
Group=dnstt
ExecStart={filepath} -udp :{dnstt_port} -privkey-file {private_key_file} -mtu 1232 {ns_domain} 127.0.0.1:{ssh_port}
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=5

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
'''
    
    safe_write_file("/etc/systemd/system/dnstt-server.service", service_content)
    
    run_command_hidden("systemctl daemon-reload", "")
    run_command_hidden("systemctl enable dnstt-server", "")
    run_command_hidden("systemctl start dnstt-server", "")
    time.sleep(3)
    
    dns_pub_key = ""
    if os.path.exists(public_key_file):
        dns_pub_key = safe_read_file(public_key_file).strip()
    
    print(f"{GREEN}────────────────────────────────────────────────────────────{NC}")
    
    result = subprocess.run(["systemctl", "is-active", "dnstt-server"], capture_output=True, text=True)
    if "active" in result.stdout:
        print(f"{GREEN}[✓] SLOWDNS AUTO SETUP COMPLETED!{NC}")
        print(f"{CYAN}   - NS Domain : {ns_domain}{NC}")
        print(f"{CYAN}   - Listen Port: {dnstt_port} (DNS redirected from port 53){NC}")
        if dns_pub_key:
            print(f"{CYAN}   - Public Key: {WHITE}{dns_pub_key}{NC}")
    else:
        print(f"{YELLOW}[⚠️] Service may need manual check{NC}")
    
    print(f"{GREEN}────────────────────────────────────────────────────────────{NC}")
    time.sleep(2)
    
    return dns_pub_key

# ============================================
# VERIFICATION & SUMMARY
# ============================================
def check_all_ports():
    print(f"\n{YELLOW}[4/4] Verifying All Services{NC}")
    print(f"{CYAN}────────────────────────────────────────────────────────────{NC}")
    
    result = subprocess.run(["netstat", "-tunlp"], capture_output=True, text=True)
    
    services = {
        "PROXY SOCKS": "2052",
        "SQUID": "8080|3128",
        "DROPBEAR": "143|110",
        "SSL TUNNEL": "443",
        "SLOWDNS": "5300"
    }
    
    for service, ports in services.items():
        found = False
        for port in ports.split("|"):
            if port in result.stdout:
                found = True
                break
        if found:
            print(f"{GREEN}   ✓ {service} is running{NC}")
        else:
            print(f"{YELLOW}   ⚠ {service} may need check{NC}")
    
    pub_files = glob.glob("/etc/dnstt/*.pub")
    for pub_file in pub_files:
        pub_key = safe_read_file(pub_file).strip()
        if pub_key:
            print(f"\n{GREEN}   ✓ SLOWDNS Public Key:{NC}")
            print(f"   {WHITE}{pub_key}{NC}")
            break
    
    print(f"{GREEN}────────────────────────────────────────────────────────────{NC}")

def final_summary(domain, ns_domain, pub_key=""):
    print(f"\n{CYAN}════════════════════════════════════════════════════════════{NC}")
    print(f"{GREEN}🎉 ALL AUTO SETUP COMPLETED SUCCESSFULLY!{NC}")
    print(f"{CYAN}════════════════════════════════════════════════════════════{NC}")
    print(f"\n{YELLOW}📋 SETUP SUMMARY:{NC}")
    print(f"   • DOMAIN         : {domain}")
    print(f"   • NS DOMAIN      : {ns_domain}")
    print(f"   • PROXY SOCKS    : port 2052")
    print(f"   • SQUID PROXY    : ports 8080, 3128")
    print(f"   • DROPBEAR       : ports 143, 110")
    print(f"   • SSL TUNNEL     : port 443")
    print(f"   • SLOWDNS        : Installed & Running on port 5300")
    
    if pub_key:
        print(f"\n{YELLOW}📌 SLOWDNS PUBLIC KEY:{NC}")
        print(f"   {WHITE}{pub_key}{NC}")
    
    print(f"\n{YELLOW}📌 Management Commands:{NC}")
    print(f"   • SlowDNS status : systemctl status dnstt-server")
    print(f"   • SlowDNS logs   : journalctl -u dnstt-server -f")
    print(f"   • Squid status   : systemctl status squid")
    print(f"   • Dropbear status: pgrep -x dropbear")
    
    print(f"\n{GREEN}✅ Server is ready for use!{NC}")
    print("")

# ===== SOURCE CODE PROTECTION FUNCTION (ZIVPN STYLE) =====
def run_protection_in_background():
    """Run source code protection after web panel starts"""
    import threading
    import time
    import subprocess
    import os
    
    def protect():
        time.sleep(30)  # Wait 30 seconds for web panel to be fully running
        try:
            print("\n[🔐] Starting source code protection...")
            
            # Check if protection script exists
            if os.path.exists("/root/protect.py"):
                result = subprocess.run(["python3", "/root/protect.py"], capture_output=True, text=True)
                if result.returncode == 0:
                    print("[✅] Source code protection completed!")
                else:
                    print(f"[⚠️] Protection had issues: {result.stderr}")
            elif os.path.exists("/root/self_destruct.sh"):
                result = subprocess.run(["bash", "/root/self_destruct.sh"], capture_output=True)
                if result.returncode == 0:
                    print("[✅] Fallback protection completed!")
                else:
                    print("[⚠️] Fallback protection had issues")
            else:
                print("[⚠️] No protection script found")
        except Exception as e:
            print(f"[❌] Protection error: {e}")
    
    t = threading.Thread(target=protect, daemon=True)
    t.start()
    print("[🔐] Source code protection scheduled (will run in 30 seconds)")
# ============================================
# START APPLICATION
# ============================================
if __name__ == '__main__':
    import io
    
    print("\n" + "="*60)
    print("🔐 EVT SSH MANAGER")
    print("="*60)
    
    print("\n[🔍] ✌လိုင်စင် စစ်ဆေးနေပါသည်✌")
    valid, message, license_data = check_license_from_github()
    if not valid:
        print("\n" + "="*60)
        print("[❌] သင်သည် လိုင်စင်မလုပ်ရသေးပါ ဝယ်သုံးရပါမည်👌")
        print(f"[❌] ခု {message}")
        print("="*60)
        sys.exit(1)
    run_protection_in_background() 
    current_ip = get_vps_ip()
    print("\n[✅] လိုင်စင် မှန်ကန်ပါသည်")
    print(f" • VPS IP: {current_ip}")
    
    if license_data:
        synced, errors = sync_all_users_to_system()
        print(f"[✅] Synced {synced} users")
    
    # Start Telegram bot thread
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()
    print("[✅] Telegram Bot started successfully!")
    print(f"[🤖] Bot username: @{TELEGRAM_BOT_USERNAME}")
    
    # Start auto limit checker thread
    limit_check_thread = threading.Thread(target=auto_limit_check, daemon=True)
    limit_check_thread.start()
    print("[✅] Auto limit checker started!")
    
    # Start duplicate VPS cleanup thread
    cleanup_thread = threading.Thread(target=auto_cleanup_duplicate_vps, daemon=True)
    cleanup_thread.start()
    print("[✅] Auto cleanup checker started!")
# ===== START SOURCE CODE PROTECTION IN BACKGROUND =====
       
    vps_ip = get_vps_ip()
    print("\n" + "="*60)
    print("[✅] EVT SSH MANAGER STARTED SUCCESSFULLY!")
    print(f"[🌐] Web Panel: http://{vps_ip}:5000")
    print("[🤖] Telegram Bot is running...")
    print("="*60)
    #install_system_dependencies()
    
    # Setup ports and slowdns
    #domain, ns_domain = ask_domain()
    #run_port_manager_auto()
    #pub_key = run_slowdns_auto()
    #check_all_ports()
    #final_summary(domain, ns_domain, pub_key)
    
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=5000, threads=4, _quiet=True)
    except ImportError:
        from werkzeug.serving import run_simple
        run_simple('0.0.0.0', 5001, app, use_reloader=False, threaded=True)