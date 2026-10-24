# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Configuration
Hằng số, đường dẫn, và cấu hình mặc định cho toàn bộ hệ thống.
"""

import os
import sys

# ─── Đường dẫn gốc ───────────────────────────────────────────────────────────
APP_NAME = "Seedance AI Video Studio"
APP_VERSION = "5.0.0"

# Thư mục gốc của ứng dụng (nơi chứa main.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Thư mục dữ liệu người dùng (lưu state, profiles, etc.)
USER_HOME = os.path.expanduser("~")
DATA_DIR = os.path.join(USER_HOME, ".seedance_ai_video_studio")
os.makedirs(DATA_DIR, exist_ok=True)

# ─── Server ───────────────────────────────────────────────────────────────────
API_HOST = "127.0.0.1"
API_PORT = 8899

# ─── Chrome / Browser ────────────────────────────────────────────────────────
# Đường dẫn Chrome executable — tự detect
CHROME_PATHS = [
    os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
    os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
    os.path.join(USER_HOME, "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe"),
]
CHROME_PATH = ""
for p in CHROME_PATHS:
    if os.path.isfile(p):
        CHROME_PATH = p
        break

# Chrome debug port bắt đầu (mỗi account dùng port riêng: 9230, 9231, ...)
CHROME_DEBUG_PORT_START = 9230

# Thư mục chứa Chrome user data (mỗi account 1 profile)
CHROME_USER_DATA_BASE = os.path.join(DATA_DIR, "chrome_user_data_dola")
os.makedirs(CHROME_USER_DATA_BASE, exist_ok=True)

# ─── Extension ────────────────────────────────────────────────────────────────
# Đường dẫn mặc định tới thư mục extension mới (Dola_Bypass_30s_Viet_Hoa)
EXTENSION_DIR = os.path.join(os.path.dirname(BASE_DIR), "Dola_Bypass_30s_Viet_Hoa")
if not os.path.isdir(EXTENSION_DIR):
    # Fallback: tìm trong thư mục user
    _alt = os.path.join(USER_HOME, "Dola_Bypass_30s_Viet_Hoa")
    if os.path.isdir(_alt):
        EXTENSION_DIR = _alt

# ─── Dola / Doubao ────────────────────────────────────────────────────────────
DOLA_URL = "https://www.dola.com/chat/"
DOLA_CHAT_URL_PREFIX = "https://www.dola.com/chat/"

# ─── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(BASE_DIR), "output_videos", "pet_room_30s")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DOWNLOAD_DIR = os.path.join(os.path.splitdrive(USER_HOME)[0] + os.sep, "downloads")
if os.path.isdir("E:\\downloads"):
    DOWNLOAD_DIR = "E:\\downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ─── Account ──────────────────────────────────────────────────────────────────
ACCOUNTS_STATE_FILE = os.path.join(DATA_DIR, "accounts_state.json")
MAX_QUOTA_PER_ACCOUNT = 4          # Số video tối đa mỗi chu kỳ cooldown
COOLDOWN_SECONDS = 24 * 60 * 60   # 24 giờ cooldown sau khi hết quota

# ─── Proxy ────────────────────────────────────────────────────────────────────
PROXY_POOL_FILE = os.path.join(DATA_DIR, "proxy_pool.json")
PROXY_5STARS_API = "https://proxy.5sao.ink/api/getIP.php"
PROXY_RESOLVE_WAIT = 6  # Giây chờ sau khi xoay proxy

# ─── License ──────────────────────────────────────────────────────────────────
LICENSE_STATE_FILE = os.path.join(DATA_DIR, "license_state.json")

# ─── Video Generation ────────────────────────────────────────────────────────
VIDEO_WAIT_TIMEOUT = 900           # 15 phút timeout chờ video
VIDEO_POLL_INTERVAL = 15           # Polling mỗi 15 giây
EXTENSION_REACTIVATE_INTERVAL = 15 # Re-activate extension bypass mỗi 15s
SEEN_URLS_FILE = os.path.join(DATA_DIR, "seen_video_urls.json")

# ─── Video Creation Modes ────────────────────────────────────────────────────
# Tỉ lệ khung hình đầy đủ (Dola UI supports all 6)
ASPECT_RATIOS = ["1:1", "3:4", "4:3", "9:16", "16:9", "21:9"]
ASPECT_RATIO_LABELS = {
    "1:1": "1:1 (Vuông)",
    "3:4": "3:4 (Dọc nhẹ)",
    "4:3": "4:3 (Ngang nhẹ)",
    "9:16": "9:16 (Dọc)",
    "16:9": "16:9 (Ngang)",
    "21:9": "21:9 (Siêu rộng)",
}

# Model Seedance
SEEDANCE_MODELS = ["Seedance 2.5", "Seedance 2.0"]
SEEDANCE_MODEL_MAP = {
    "Dreamina Seedance 2.5": "2.5",
    "Seedance 2.5": "2.5",
    "Seedance 2.0 Nhanh": "2.0",
    "Seedance 2.0": "2.0",
    "Seedance 1.0": "1.0",
}

# Fast Mode durations (pill buttons)
FAST_DURATIONS = ["5s", "10s", "15s", "20s", "25s", "30s", "60s"]
FAST_DURATION_MAP = {
    "5s": 5,
    "10s": 10,
    "15s": 15,
    "20s": 20,
    "25s": 25,
    "30s": 30,
    "60s": 60,
    "30s (Bypass Pro)": 30,
    "31s (Bypass Max)": 30,
}

# Pro Mode settings
PRO_DURATION = "30s"  # Pro mặc định 30s bypass
PRO_MAX_VIDEOS = 200  # Tối đa video/lệnh Pro
PRO_POLL_INTERVAL = 15  # Polling mỗi 15 giây khi theo dõi
PRO_TIMEOUT = 14400  # 4 giờ timeout cho Pro mode

PRO_PROMPT_TEMPLATE = """{prompt_list}"""

# ─── FFmpeg / Upscale ─────────────────────────────────────────────────────────
FFMPEG_PATH = "ffmpeg"   # Mặc định dùng ffmpeg trong PATH
FFPROBE_PATH = "ffprobe"
UPSCALE_ENCODER_PRIORITY = ["h264_nvenc", "libx264"]  # GPU trước, CPU fallback

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE = os.path.join(DATA_DIR, "api_server_startup.log")

# ─── Chrome Launch Flags (Anti-detect & Automation) ───────────────────────────
CHROME_FLAGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-fre",
    "--suppress-first-run-default-browser-prompt",
    "--disable-signin-fre",
    "--disable-search-engine-choice-screen",
    "--profile-picker-on-startup=false",
    "--enable-unsafe-extension-debugging",
    "--allow-insecure-localhost",
    "--disable-sync",
    "--disable-default-apps",
    "--disable-popup-blocking",
    "--disable-features=Translate,BackForwardCache,SigninIntercept,"
        "ChromeSigninIntercept,ProfilePicker,ChromeProfileCreation,"
        "SyncPromo,DiceAccountReconcilorSkipMigrationOnSignin,"
        "SigninInterceptBubble,ChromeSigninInterceptPeek,"
        "DiceWebSigninInterception,DiceWebSigninInterceptionEnabled,"
        "ProfileCreationInterception,FirstRunExperience,SearchEngineChoice",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--ignore-gpu-blocklist",
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--disable-session-crashed-bubble",
    "--noerrdialogs",
    "--disable-signin-promo",
    "--silent-debugger-extension-api",
    "--disable-backgrounding-occluded-windows",
]
