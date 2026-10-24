# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Utilities
Tiện ích chung: logging, file IO, hash, helpers.
"""

import json
import logging
import os
import sys
import time
import uuid
import hashlib
import platform
import subprocess
from datetime import datetime

from config import LOG_FILE, DATA_DIR


# ─── Logging ──────────────────────────────────────────────────────────────────

def setup_logging():
    """Cấu hình logging ra file + console."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logger = logging.getLogger("seedance")
    logger.setLevel(logging.DEBUG)

    # File handler — append mode
    fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def log(tag: str, message: str):
    """Log message với tag prefix, khớp format gốc: [Tag] message"""
    logger = logging.getLogger("seedance")
    logger.info(f"[{tag}] {message}")


def log_info(message: str):
    """Log message dạng [*] message — khớp format gốc."""
    logger = logging.getLogger("seedance")
    logger.info(f"[*] {message}")


def log_bootstrap():
    """Ghi header bootstrap khi server khởi động."""
    logger = logging.getLogger("seedance")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("")
    logger.info(f"=== API SERVER BOOTSTRAP AT {now} ===")


# ─── File IO ──────────────────────────────────────────────────────────────────

def safe_json_load(path: str, default=None):
    """Đọc file JSON an toàn, trả về default nếu lỗi."""
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        log("Utils", f"Lỗi đọc JSON {path}: {e}")
    return default if default is not None else {}


def safe_json_save(path: str, data):
    """Atomically replace JSON so readers never see a truncated file."""
    temporary = str(path) + '.' + uuid.uuid4().hex + '.tmp'
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temporary, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(10):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.01)
    except (IOError, OSError) as error:
        log('Utils', f'Lỗi ghi JSON {path}: {error}')
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


# ─── ID Generation ───────────────────────────────────────────────────────────

def generate_job_id() -> str:
    """Tạo job ID duy nhất: job_xxxxxxxx"""
    return f"job_{uuid.uuid4().hex[:8]}"


def generate_upload_id() -> str:
    """Tạo upload ID duy nhất: upload_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"""
    return f"upload_{uuid.uuid4().hex}"


def generate_bypass_id() -> str:
    """Tạo bypass image ID."""
    return f"bypass_{uuid.uuid4().hex}"


# ─── Device / Hardware ID ────────────────────────────────────────────────────

def get_device_id() -> str:
    """Tạo device ID duy nhất dựa trên hardware info."""
    try:
        info_parts = [
            platform.node(),
            platform.machine(),
            platform.processor(),
        ]
        # Thêm serial number nếu có (Windows)
        try:
            result = subprocess.run(
                ["wmic", "bios", "get", "serialnumber"],
                capture_output=True, text=True, timeout=5
            )
            serial = result.stdout.strip().split("\n")[-1].strip()
            if serial and serial != "SerialNumber":
                info_parts.append(serial)
        except Exception:
            pass

        raw = "|".join(info_parts)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.md5(platform.node().encode("utf-8")).hexdigest()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_timestamp() -> float:
    """Trả về Unix timestamp hiện tại."""
    return time.time()


def sanitize_filename(name: str) -> str:
    """Làm sạch tên file — loại bỏ ký tự không hợp lệ."""
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    return name.strip().rstrip(".")


def format_bytes(size: int) -> str:
    """Format bytes thành chuỗi dễ đọc: 1,234,567 bytes"""
    return f"{size:,}"


def truncate_text(text: str, max_len: int = 80) -> str:
    """Cắt ngắn text dài, thêm '...' ở cuối."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def is_valid_url(url: str) -> bool:
    """Kiểm tra URL có hợp lệ không (bắt đầu bằng http/https)."""
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def clean_temp_sessions():
    """Dọn sạch temp sessions từ phiên trước."""
    log("Startup", "Đã dọn sạch tất cả temp sessions từ phiên trước.")
