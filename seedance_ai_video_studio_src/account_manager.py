import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from config import ACCOUNTS_STATE_FILE, MAX_QUOTA_PER_ACCOUNT, COOLDOWN_SECONDS
from utils import safe_json_load, safe_json_save, get_timestamp, log


def parse_via_cookie_string(raw_text: str) -> list[dict]:
    """Parse chuỗi cookie hoặc dòng VIA (UID|Pass|2FA|Cookie... hoặc c_user=...; xs=...)
    thành danh sách cookie dictionaries tương thích với Playwright & Chrome CDP.
    """
    if not raw_text:
        return []

    cookies = []
    # 1. Regex tìm tất cả các key cookie Facebook phổ biến
    matches = re.findall(r'(c_user|xs|fr|datr|sb|wd|dpr|locale|presence)=([^;|\s]+)', raw_text, re.IGNORECASE)
    if matches:
        for name, val in matches:
            n_clean = name.strip()
            v_clean = val.strip()
            is_http_only = n_clean.lower() in ["xs", "fr", "datr", "sb"]
            cookies.append({
                "name": n_clean,
                "value": v_clean,
                "domain": ".facebook.com",
                "path": "/",
                "httpOnly": is_http_only,
                "secure": True,
                "sameSite": "None"
            })
        return cookies

    # 2. Xử lý chuỗi định dạng c_user=123; xs=456 hoặc cắt từ c_user
    text = raw_text.strip()
    if "|" in text:
        for part in text.split("|"):
            if "c_user=" in part or "xs=" in part:
                text = part
                break
    if "c_user=" in text:
        text = text[text.find("c_user="):]
    if "|" in text:
        text = text.split("|")[0].strip()

    pairs = text.split(";")
    for pair in pairs:
        p = pair.strip()
        if not p or "=" not in p:
            continue
        parts = p.split("=", 1)
        name = parts[0].strip()
        val = parts[1].strip() if len(parts) > 1 else ""
        if "|" in name:
            name = name.split("|")[-1].strip()
        if name and val:
            is_http_only = name.lower() in ["xs", "fr", "datr", "sb"]
            cookies.append({
                "name": name,
                "value": val,
                "domain": ".facebook.com",
                "path": "/",
                "httpOnly": is_http_only,
                "secure": True,
                "sameSite": "None"
            })
    return cookies


def parse_bulk_via_text(raw_text: str) -> list[str]:
    """Phân tách chuỗi nhập chứa 1 hoặc nhiều VIA (ngăn cách bởi xuống dòng hoặc khoảng trắng).

    Hỗ trợ:
    - Mỗi VIA 1 dòng riêng biệt
    - Nhiều VIA trên cùng 1 dòng cách nhau bởi khoảng trắng
    - Định dạng UID|Pass|2FA|Cookie... hoặc chuỗi cookie c_user=...; xs=...
    Returns: danh sách chuỗi VIA đã được làm sạch, không trùng lặp.
    """
    if not raw_text or not raw_text.strip():
        return []

    text = raw_text.strip()
    raw_lines = text.splitlines()
    candidates = []

    for line in raw_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Nếu dòng có chứa format VIA dạng UID|...
        if "|" in line:
            # Chỉ tách khi gặp VIA mới ở đầu: khoảng trắng + UID (hoặc email) + '|'
            # Tuyệt đối không tách tại 'c_user=' vì đây là cookie nằm trong trường của VIA
            parts = re.split(r'\s+(?=(?:\d{4,20}|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\|)', line)
        else:
            # Dòng cookie thuần: chỉ tách nếu có khoảng trắng KHÔNG đi liền sau dấu ';' trước 'c_user='
            # (tránh cắt nhầm '; c_user=' vốn là các cookie ngăn cách bởi dấu chấm phẩy)
            parts = re.split(r'(?<!;)\s+(?=\bc_user=)', line)

        for p in parts:
            p_clean = p.strip()
            # Kiểm tra xem có chứa cookie FB hoặc UID hợp lệ không
            if ("c_user" in p_clean or "xs=" in p_clean or "|" in p_clean) and len(p_clean) >= 10:
                candidates.append(p_clean)

    # Loại bỏ trùng lặp mà vẫn giữ đúng thứ tự
    seen = set()
    result = []
    for item in candidates:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


@dataclass
class Account:
    """Mô hình dữ liệu 1 tài khoản — hỗ trợ đầy đủ Facebook VIA & Cookie."""
    name: str
    quota_max: int = MAX_QUOTA_PER_ACCOUNT
    quota_used: int = 0
    quota_reserved: int = 0
    first_use_time: float = 0.0
    status: str = "active"           # "active" | "cooldown" | "error"
    login_status: str = "unknown"    # "logged_in" | "unknown" | "failed"
    gmail_email: str = ""
    gmail_password: str = ""
    proxy: str = ""                  # Proxy cũ (compat)
    proxy_key: str = ""              # API key proxy riêng cho account (5Stars / TM Proxy)
    proxy_direct: str = ""           # Proxy cố định dạng http://user:pass@ip:port
    videos_15s_used: int = 0
    login_type: str = "facebook"     # "facebook" | "google"
    fb_uid: str = ""
    fb_password: str = ""
    fb_2fa: str = ""
    fb_cookies: str = ""
    fb_token: str = ""
    dola_session_saved: bool = False  # Đã lưu session Dola chưa
    session_expires_at: float = 0.0   # Thời điểm session hết hạn (epoch)
    # ─── v5.0 fields ─────────────────────────────────────────────
    dola_uid: str = ""              # UID trên Dola (từ cookie/profile)
    session_count: int = 0          # Số session cookies hiện có
    cookie_count: int = 0           # Số FB cookies đã lưu
    session_health: float = 0.0     # Độ bền phiên (0.0 - 100.0%)
    expires_date: str = ""          # Ngày hết hạn session (human-readable)
    last_check_time: float = 0.0    # Timestamp kiểm tra gần nhất
    created_date: str = ""          # Ngày tạo account

    def remaining_quota(self) -> int:
        return max(0, self.quota_max - self.quota_used - self.quota_reserved)

    def is_available(self) -> bool:
        """Account có sẵn sàng để nhận job không?"""
        if self.status == "error":
            return False
        if self.status == "cooldown":
            # Kiểm tra đã hết cooldown chưa
            if self.first_use_time > 0 and (time.time() - self.first_use_time) >= COOLDOWN_SECONDS:
                return True  # Sẽ được reset bởi check_and_reset_cooldowns()
            return False
        return self.remaining_quota() > 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class AccountManager:
    """Quản lý toàn bộ danh sách accounts."""

    def __init__(self):
        self.accounts: list[Account] = []
        self.updated_at: float = 0.0
        self.load()

    # ─── Load / Save ──────────────────────────────────────────────────────

    def load(self):
        """Đọc danh sách accounts từ file."""
        data = safe_json_load(ACCOUNTS_STATE_FILE, {})
        if not isinstance(data, dict) or 'accounts' not in data:
            return
        self.accounts = [Account.from_dict(a) for a in data['accounts']]
        self.updated_at = data.get("updated_at", 0.0)
        if self.accounts:
            log("AccountManager", f"Loaded {len(self.accounts)} accounts from: {ACCOUNTS_STATE_FILE}")

    def save(self):
        """Ghi danh sách accounts ra file."""
        self.updated_at = get_timestamp()
        data = {
            "accounts": [a.to_dict() for a in self.accounts],
            "updated_at": self.updated_at,
        }
        safe_json_save(ACCOUNTS_STATE_FILE, data)

    # ─── CRUD ─────────────────────────────────────────────────────────────

    def get_all(self) -> list[dict]:
        """Trả về tất cả accounts dạng dict."""
        self.check_and_reset_cooldowns()
        return [a.to_dict() for a in self.accounts]

    def get_account(self, name: str) -> Optional[Account]:
        """Tìm account theo tên."""
        for a in self.accounts:
            if a.name == name:
                return a
        return None

    def add_account(self, name: str, login_type: str = "google", **kwargs) -> Account:
        """Thêm account mới."""
        # Kiểm tra trùng tên
        if self.get_account(name):
            raise ValueError(f"Account '{name}' đã tồn tại")

        acc = Account(name=name, login_type=login_type, **kwargs)
        self.accounts.append(acc)
        self.save()
        log("AccountManager", f"Đã thêm account: {name}")
        return acc

    def delete_account(self, name: str) -> bool:
        """Xóa account."""
        acc = self.get_account(name)
        if acc:
            self.accounts.remove(acc)
            self.save()
            log("AccountManager", f"Đã xóa account: {name}")
            return True
        return False

    def update_account(self, name: str, **kwargs):
        """Cập nhật thông tin account."""
        acc = self.get_account(name)
        if not acc:
            return
        for key, value in kwargs.items():
            if hasattr(acc, key):
                setattr(acc, key, value)
        self.save()

    # ─── Quota Management ────────────────────────────────────────────────

    def get_available_account(self, require_session: bool = True) -> Optional[Account]:
        """Chọn account còn quota, ưu tiên active + có session Dola."""
        self.check_and_reset_cooldowns()

        # Ưu tiên active accounts có quota VÀ có session Dola
        for acc in self.accounts:
            if acc.status == "active" and acc.remaining_quota() > 0:
                if require_session and not acc.dola_session_saved:
                    continue
                return acc

        # Fallback: tìm account vừa được reset (có hoặc không session)
        for acc in self.accounts:
            if acc.is_available():
                if require_session and not acc.dola_session_saved:
                    continue
                return acc

        # Cuối cùng: bỏ qua yêu cầu session
        if require_session:
            return self.get_available_account(require_session=False)

        return None

    def get_proxy_for_account(self, account_name: str) -> str:
        """Lấy proxy gắn chặt với account (ưu tiên: proxy_direct > proxy_key > proxy cũ)."""
        acc = self.get_account(account_name)
        if not acc:
            return ""
        if acc.proxy_direct:
            return acc.proxy_direct
        if acc.proxy_key:
            return acc.proxy_key
        return acc.proxy

    def deduct_quota(self, name: str, points: int = 1):
        """Trừ quota cho account sau khi tạo video thành công."""
        acc = self.get_account(name)
        if not acc:
            return

        # Ghi nhận first_use_time nếu chưa có
        if acc.first_use_time == 0:
            acc.first_use_time = get_timestamp()

        acc.quota_used += points
        remaining = acc.remaining_quota()

        # Chuyển sang cooldown nếu hết quota
        if remaining <= 0:
            acc.status = "cooldown"

        self.save()
        log("AccountManager",
            f"✅ Đã trừ {points} điểm cho '{name}'. "
            f"Đã dùng: {acc.quota_used}/{acc.quota_max} "
            f"(còn {remaining}pt, status={acc.status})")

    def reserve_quota(self, name: str):
        """Đặt trước 1 quota khi bắt đầu tạo video."""
        acc = self.get_account(name)
        if acc:
            acc.quota_reserved += 1
            self.save()

    def release_reservation(self, name: str):
        """Giải phóng reservation (khi job kết thúc hoặc bị hủy)."""
        acc = self.get_account(name)
        if acc and acc.quota_reserved > 0:
            acc.quota_reserved -= 1
            self.save()

    def check_and_reset_cooldowns(self):
        """Tự động reset quota cho accounts đã hết cooldown (24h)."""
        now = get_timestamp()
        changed = False
        for acc in self.accounts:
            if acc.status == "cooldown" and acc.first_use_time > 0:
                elapsed = now - acc.first_use_time
                if elapsed >= COOLDOWN_SECONDS:
                    acc.quota_used = 0
                    acc.quota_reserved = 0
                    acc.first_use_time = 0.0
                    acc.status = "active"
                    acc.videos_15s_used = 0
                    changed = True
                    log("AccountManager", f"🔄 Reset cooldown cho '{acc.name}' — sẵn sàng lại!")
        if changed:
            self.save()

    def update_login_status(self, name: str, status: str):
        """Cập nhật trạng thái đăng nhập."""
        acc = self.get_account(name)
        if acc:
            acc.login_status = status
            self.save()

    # ─── v5.0: VIA Import ─────────────────────────────────────────────────

    def add_account_from_via(self, raw_cookie: str, display_name: str = "") -> Account:
        """Tạo account mới từ VIA cookie string.

        Auto parse c_user thành UID, đặt tên tự động nếu không cung cấp.
        Returns: Account vừa tạo
        """
        # Parse UID từ c_user
        uid = ""
        m = re.search(r'c_user=(\d+)', raw_cookie)
        if m:
            uid = m.group(1)

        # Tên tự động: dùng display_name hoặc "FB_{uid}" hoặc "nick_{count+1}"
        if not display_name:
            if uid:
                display_name = f"FB_{uid}"
            else:
                display_name = f"Nick {len(self.accounts) + 1}"

        # Kiểm tra trùng — thêm suffix nếu cần
        base_name = display_name
        counter = 1
        while self.get_account(display_name):
            counter += 1
            display_name = f"{base_name}_{counter}"

        # Parse cookies
        parsed = parse_via_cookie_string(raw_cookie)
        cookie_count = len(parsed)

        acc = Account(
            name=display_name,
            login_type="facebook",
            fb_uid=uid,
            fb_cookies=raw_cookie[:1000],  # Lưu gọn
            cookie_count=cookie_count,
            created_date=time.strftime("%Y-%m-%d %H:%M"),
        )
        self.accounts.append(acc)
        self.save()
        log("AccountManager", f"Đã tạo account từ VIA: {display_name} (UID={uid}, {cookie_count} cookies)")
        return acc

    def update_session_stats(self, name: str, session_count: int = 0,
                             cookie_count: int = 0, health: float = 0.0,
                             expires_date: str = "", dola_uid: str = ""):
        """Cập nhật thống kê session cho account (gọi từ SessionStore)."""
        acc = self.get_account(name)
        if not acc:
            return
        acc.session_count = session_count
        acc.cookie_count = cookie_count
        acc.session_health = health
        acc.expires_date = expires_date
        acc.last_check_time = time.time()
        if dola_uid:
            acc.dola_uid = dola_uid
        self.save()
