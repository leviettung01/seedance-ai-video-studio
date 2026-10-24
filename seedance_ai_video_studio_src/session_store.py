# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Session Store
Lưu trữ / phục hồi Dola session cookies & localStorage từ file JSON.
Mỗi account chỉ tốn ~5KB thay vì ~500MB Chrome profile.
"""

import os
import json
import time
from typing import Optional

from config import DATA_DIR
from utils import log, log_info

SESSIONS_FILE = os.path.join(DATA_DIR, "accounts_sessions.json")


def parse_bulk_dola_cookies(raw_text: str, default_name: str = "") -> list[tuple[str, list[dict]]]:
    """Parse text chứa 1 hoặc nhiều tài khoản kèm cookies Dola.
    
    Hỗ trợ các định dạng:
    1. Multi-account dạng:
       username:
       [ { "name": ... }, ... ]
       
       username2:
       [ { ... } ]
       
    2. JSON Object:
       { "acc1": [ ... ], "acc2": [ ... ] }
       
    3. Single JSON Array:
       [ { "name": ... } ]  (dùng default_name nếu có)
       
    4. Single cookie string:
       name=val; name2=val2 (dùng default_name nếu có)
       
    Returns: list[tuple[account_name, cookies_list]]
    """
    text = raw_text.strip()
    if not text:
        return []

    # Bỏ markdown code block fences (```json ... ```) nếu có
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 1. Thử parse toàn bộ như JSON dict hoặc list
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Kiểm tra nếu data bọc trong key "accounts", "sessions", hoặc "profiles"
            items = data
            for wrap_key in ["accounts", "sessions", "profiles", "multi_profiles"]:
                if wrap_key in data and isinstance(data[wrap_key], (dict, list)):
                    items = data[wrap_key]
                    break

            res = []
            if isinstance(items, dict):
                for k, v in items.items():
                    if isinstance(v, list):
                        res.append((k.strip(), v))
                    elif isinstance(v, dict):
                        acc_n = v.get("name") or k.strip()
                        c_list = v.get("cookies", [])
                        if isinstance(c_list, list) and c_list:
                            res.append((acc_n, c_list))
            elif isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "cookies" in item and isinstance(item["cookies"], list):
                        res.append((item.get("name") or default_name or f"acc_{len(res)+1}", item["cookies"]))
            if res:
                return res
        elif isinstance(data, list):
            # Trường hợp list chứa các object account: [{"name": "...", "cookies": [...]}]
            if data and isinstance(data[0], dict) and "cookies" in data[0] and isinstance(data[0]["cookies"], list):
                res = []
                for item in data:
                    res.append((item.get("name") or default_name or f"acc_{len(res)+1}", item["cookies"]))
                if res:
                    return res
            # Single JSON array cookies
            return [(default_name or "dola_account", data)]
    except Exception:
        pass

    # 2. Block parser cho `username:\n[...]` hoặc `username: [...]`
    import re
    results = []
    lines = text.splitlines()
    current_name = ""
    current_json_lines = []
    bracket_depth = 0
    in_json = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_json:
                current_json_lines.append(line)
            continue

        # Header dạng `name:` hoặc `name :`
        header_match = re.match(r'^([a-zA-Z0-9_\-\.@]+)\s*:\s*$', stripped)
        if header_match and not in_json:
            current_name = header_match.group(1).strip()
            current_json_lines = []
            bracket_depth = 0
            continue

        # Header inline dạng `name: [`
        header_inline_match = re.match(r'^([a-zA-Z0-9_\-\.@]+)\s*:\s*(\[.*)$', stripped)
        if header_inline_match and not in_json:
            current_name = header_inline_match.group(1).strip()
            current_json_lines = [header_inline_match.group(2)]
            bracket_depth = header_inline_match.group(2).count('[') - header_inline_match.group(2).count(']')
            in_json = True
            if bracket_depth == 0 and header_inline_match.group(2).endswith(']'):
                try:
                    cookies = json.loads(''.join(current_json_lines))
                    if isinstance(cookies, list):
                        results.append((current_name, cookies))
                except Exception:
                    pass
                current_name = ""
                current_json_lines = []
                in_json = False
            continue

        if stripped.startswith('[') and not in_json:
            in_json = True
            current_json_lines = [line]
            bracket_depth = line.count('[') - line.count(']')
            if bracket_depth == 0 and stripped.endswith(']'):
                try:
                    cookies = json.loads(''.join(current_json_lines))
                    if isinstance(cookies, list):
                        results.append((current_name or default_name or "dola_account", cookies))
                except Exception:
                    pass
                current_name = ""
                current_json_lines = []
                in_json = False
            continue

        if in_json:
            current_json_lines.append(line)
            bracket_depth += line.count('[') - line.count(']')
            if bracket_depth <= 0:
                in_json = False
                json_str = '\n'.join(current_json_lines)
                try:
                    cookies = json.loads(json_str)
                    if isinstance(cookies, list):
                        results.append((current_name or default_name or f"dola_acc_{len(results)+1}", cookies))
                except Exception:
                    pass
                current_name = ""
                current_json_lines = []

    if results:
        return results

    # 3. Fallback: Parse chuỗi name=val; name2=val2
    pairs = text.replace("\n", ";").split(";")
    fallback_cookies = []
    for pair in pairs:
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        parts = pair.split("=", 1)
        n = parts[0].strip()
        v = parts[1].strip() if len(parts) > 1 else ""
        if n and v:
            fallback_cookies.append({
                "name": n,
                "value": v,
                "domain": ".dola.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "Lax",
            })
    if fallback_cookies:
        return [(default_name or "dola_account", fallback_cookies)]

    return []


class SessionStore:
    """Quản lý lưu trữ session Dola (cookies + localStorage) dạng JSON."""

    def __init__(self):
        self._sessions: dict = {}
        self.load()

    # ─── Load / Save ──────────────────────────────────────────────────────

    def load(self):
        """Đọc sessions từ file."""
        if os.path.isfile(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                    self._sessions = json.load(f)
            except Exception:
                pass  # Keep the last good snapshot on a transient read error.
        count = len(self._sessions)
        if count:
            log("SessionStore", f"Loaded {count} saved Dola sessions from disk.")

    def save(self):
        """Publish sessions atomically; preserve the previous file on errors."""
        from utils import safe_json_save
        safe_json_save(SESSIONS_FILE, self._sessions)

    # ─── Core CRUD ────────────────────────────────────────────────────────

    def save_session(self, account_name: str, cookies: list, local_storage: dict):
        """Lưu cookies & localStorage cho 1 account.
        
        cookies: list[dict] — danh sách cookies (Playwright / Chrome extension format)
        local_storage: dict — key-value pairs từ localStorage
        """
        # Lọc và chuẩn hóa cookies Dola
        dola_cookies = []
        for c in cookies:
            domain = c.get("domain", "")
            if not domain:
                domain = ".dola.com"
            if "dola" in domain or "doubao" in domain or "byte" in domain:
                # Serialize cookies — giữ đầy đủ thông tin
                cookie_data = {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": domain,
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", True),
                    "httpOnly": c.get("httpOnly", False),
                }
                
                # Chuẩn hóa sameSite
                if "sameSite" in c and c["sameSite"]:
                    ss = str(c["sameSite"]).lower()
                    if ss in ["strict", "lax", "none"]:
                        cookie_data["sameSite"] = ss.capitalize()
                    elif ss == "no_restriction":
                        cookie_data["sameSite"] = "None"
                    else:
                        cookie_data["sameSite"] = "Lax"
                else:
                    cookie_data["sameSite"] = "Lax"

                # Chuẩn hóa expires
                exp = c.get("expires") or c.get("expirationDate") or 0
                if exp and float(exp) > 0:
                    cookie_data["expires"] = float(exp)

                dola_cookies.append(cookie_data)

        # Lọc localStorage — chỉ giữ keys quan trọng cho Dola
        important_ls_prefixes = [
            "__dola", "__tea_cache", "__lastDola", "__msuuid",
            "flow_", "samantha_", "ARGUS", "xmst", "mode_select",
            "action_bar", "dbx-web", "i18next", "setting_language",
            "HYBRID_SLARDAR", "PUMBAA", "for_ban_appeal",
            "default_reply_mode",
        ]
        filtered_ls = {}
        for k, v in local_storage.items():
            if any(k.startswith(prefix) for prefix in important_ls_prefixes) or k == "":
                filtered_ls[k] = v

        self._sessions[account_name] = {
            "cookies": dola_cookies,
            "local_storage": filtered_ls,
            "saved_at": time.time(),
            "cookies_count": len(dola_cookies),
            "ls_count": len(filtered_ls),
        }
        self.save()

        size_kb = len(json.dumps(self._sessions[account_name])) / 1024
        log("SessionStore",
            f"✅ Saved session for '{account_name}': "
            f"{len(dola_cookies)} cookies + {len(filtered_ls)} localStorage keys "
            f"({size_kb:.1f} KB)")

    def load_session(self, account_name: str) -> Optional[tuple[list, dict]]:
        """Đọc session đã lưu.
        
        Returns: (cookies_list, local_storage_dict) hoặc None nếu chưa lưu.
        """
        session = self._sessions.get(account_name)
        if not session:
            return None
        return session.get("cookies", []), session.get("local_storage", {})

    def has_session(self, account_name: str) -> bool:
        """Kiểm tra account đã có session lưu chưa."""
        return account_name in self._sessions

    def is_session_valid(self, account_name: str) -> bool:
        """Kiểm tra session còn hạn không.
        
        Dola cookies thường hết hạn sau 30-90 ngày.
        Ở đây dùng ngưỡng an toàn 25 ngày.
        """
        session = self._sessions.get(account_name)
        if not session:
            return False

        saved_at = session.get("saved_at", 0)
        age_days = (time.time() - saved_at) / 86400
        if age_days > 25:
            log("SessionStore", f"⚠️ Session '{account_name}' đã cũ ({age_days:.0f} ngày). Cần login lại.")
            return False

        # Kiểm tra cookie expiry
        cookies = session.get("cookies", [])
        now = time.time()
        expired_count = 0
        for c in cookies:
            exp = c.get("expires", 0)
            if exp > 0 and exp < now:
                expired_count += 1

        # Nếu > 50% cookies đã hết hạn → session không hợp lệ
        if cookies and expired_count > len(cookies) * 0.5:
            log("SessionStore", f"⚠️ Session '{account_name}' có {expired_count}/{len(cookies)} cookies đã hết hạn.")
            return False

        return True

    def get_session_info(self, account_name: str) -> dict:
        """Trả về thông tin tóm tắt session."""
        session = self._sessions.get(account_name)
        if not session:
            return {"status": "none", "saved": False}

        saved_at = session.get("saved_at", 0)
        age_days = (time.time() - saved_at) / 86400

        return {
            "status": "valid" if self.is_session_valid(account_name) else "expired",
            "saved": True,
            "cookies_count": session.get("cookies_count", 0),
            "ls_count": session.get("ls_count", 0),
            "saved_at": saved_at,
            "age_days": round(age_days, 1),
        }

    def delete_session(self, account_name: str):
        """Xóa session đã lưu."""
        if account_name in self._sessions:
            del self._sessions[account_name]
            self.save()
            log("SessionStore", f"Đã xóa session cho '{account_name}'")

    def get_all_sessions_summary(self) -> list[dict]:
        """Trả về tóm tắt tất cả sessions."""
        result = []
        for name in self._sessions:
            info = self.get_session_info(name)
            info["account_name"] = name
            result.append(info)
        return result

    # ─── Browser Integration ──────────────────────────────────────────────

    async def extract_from_browser(self, context, page) -> tuple[list, dict]:
        """Trích xuất cookies & localStorage từ browser đang mở.
        
        Args:
            context: Playwright BrowserContext
            page: Playwright Page (đang ở trang dola.com)
        
        Returns: (cookies_list, local_storage_dict)
        """
        cookies = await context.cookies()
        local_storage = await page.evaluate("() => ({ ...localStorage })")
        return cookies, local_storage

    async def inject_to_browser(self, context, page, account_name: str, restore_local_storage: bool = False) -> bool:
        """Nạp session đã lưu vào browser rỗng.
        
        Args:
            context: Playwright BrowserContext
            page: Playwright Page
            account_name: tên account để load session
        
        Returns: True nếu thành công
        """
        session_data = self.load_session(account_name)
        if not session_data:
            log("SessionStore", f"❌ Không có session nào cho '{account_name}'")
            return False

        cookies, local_storage = session_data

        # 1. Inject cookies
        if cookies:
            try:
                pw_cookies = []
                for c in cookies:
                    ck = {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c.get("domain", ".dola.com"),
                        "path": c.get("path", "/"),
                        "secure": c.get("secure", True),
                        "httpOnly": c.get("httpOnly", False),
                    }
                    if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
                        ck["sameSite"] = c["sameSite"]
                    if "expires" in c and c["expires"] and float(c["expires"]) > 0:
                        ck["expires"] = float(c["expires"])
                    pw_cookies.append(ck)

                await context.add_cookies(pw_cookies)
                log("SessionStore", f"✅ Injected {len(pw_cookies)} cookies cho '{account_name}'")
            except Exception as e:
                log("SessionStore", f"⚠️ Lỗi inject cookies: {e}")
                return False

        # 2. Inject localStorage nếu có dữ liệu
        if restore_local_storage and local_storage and len(local_storage) > 0:
            try:
                await page.goto("https://www.dola.com/404", wait_until="domcontentloaded", timeout=10000)
                await page.evaluate("""(storageData) => {
                    for (const [k, v] of Object.entries(storageData)) {
                        try { localStorage.setItem(k, v); } catch(e) {}
                    }
                }""", local_storage)
                log("SessionStore", f"✅ Injected {len(local_storage)} localStorage keys cho '{account_name}'")
            except Exception as e:
                log("SessionStore", f"⚠️ Lỗi inject localStorage: {e}")

        return True
