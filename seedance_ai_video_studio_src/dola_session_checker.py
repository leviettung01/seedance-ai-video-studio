# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Dola Session Checker
Rà quét hàng loạt tài khoản Dola: cookie còn sống hay đã die.

Cơ chế: gọi API passport của Dola bằng cookie đã lưu (HTTP thuần, không mở Chrome):
    GET https://www.dola.com/passport/account/info/v2/
    - Sống : {"message":"success","data":{"user_id":..., "screen_name":...}}
    - Die  : {"message":"error","data":{"error_code":13,"description":"session expired, please sign in again"}}
→ Nhanh (~0.5s/acc), chạy song song nhiều luồng, không tốn RAM.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from utils import log

DOLA_ACCOUNT_INFO_URL = "https://www.dola.com/passport/account/info/v2/"
DOLA_AUTH_COOKIE_NAMES = ("sessionid", "sessionid_ss", "sid_tt")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

STATUS_LIVE = "live"              # Cookie còn sống
STATUS_DEAD = "dead"              # Cookie đã die (session expired)
STATUS_NO_SESSION = "no_session"  # Không có session / không có cookie sessionid
STATUS_ERROR = "error"            # Lỗi mạng / không xác định → KHÔNG xoá

# error_code của passport = session hết hạn / không hợp lệ
_DEAD_ERROR_CODES = {1, 13}


@dataclass
class SessionCheckResult:
    name: str
    status: str
    user_id: str = ""
    screen_name: str = ""
    detail: str = ""

    @property
    def is_dead(self) -> bool:
        return self.status in (STATUS_DEAD, STATUS_NO_SESSION)


def check_dola_cookies(cookies: list, timeout: float = 15, retries: int = 2) -> SessionCheckResult:
    """Kiểm tra 1 bộ cookie Dola. (name trong kết quả để trống)"""
    jar = requests.cookies.RequestsCookieJar()
    has_auth = False
    for c in cookies or []:
        try:
            name, value = c.get("name"), c.get("value")
            domain = c.get("domain") or ".dola.com"
            if not name or value is None or "dola" not in domain.lower():
                continue
            jar.set(name, value, domain=domain, path=c.get("path") or "/")
            if name in DOLA_AUTH_COOKIE_NAMES and value:
                has_auth = True
        except Exception:
            continue

    if not has_auth:
        return SessionCheckResult("", STATUS_NO_SESSION, detail="Không có cookie sessionid")

    last_err = ""
    for attempt in range(retries + 1):
        try:
            r = requests.get(
                DOLA_ACCOUNT_INFO_URL, cookies=jar, timeout=timeout,
                headers={"User-Agent": _UA, "Referer": "https://www.dola.com/chat/",
                         "Accept": "application/json, text/plain, */*"},
            )
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {r.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            data = r.json()
            msg = data.get("message")
            d = data.get("data") or {}
            if msg == "success" and d.get("user_id"):
                if d.get("is_visitor_account"):
                    return SessionCheckResult("", STATUS_DEAD, detail="Tài khoản khách (visitor)")
                return SessionCheckResult(
                    "", STATUS_LIVE,
                    user_id=str(d.get("user_id_str") or d.get("user_id") or ""),
                    screen_name=str(d.get("screen_name") or d.get("name") or ""),
                )
            code = d.get("error_code")
            desc = str(d.get("description") or "")
            low = desc.lower()
            if code in _DEAD_ERROR_CODES or "expired" in low or "sign in" in low or "log in" in low or "过期" in desc:
                return SessionCheckResult("", STATUS_DEAD, detail=f"{desc} (code={code})")
            last_err = f"{desc} (code={code})"
            break
        except Exception as e:
            last_err = str(e)
            time.sleep(1.0 * (attempt + 1))
    return SessionCheckResult("", STATUS_ERROR, detail=last_err[:200])


def scan_accounts(
    names: list,
    session_store,
    max_workers: int = 8,
    on_progress: Optional[Callable] = None,
    should_stop: Optional[Callable] = None,
) -> list:
    """Quét song song danh sách tài khoản.

    on_progress(result: SessionCheckResult, done: int, total: int)
    should_stop() -> bool : trả True để dừng sớm
    """
    total = len(names)
    results: list = []
    if not total:
        return results

    def _one(name: str) -> SessionCheckResult:
        if should_stop and should_stop():
            return SessionCheckResult(name, STATUS_ERROR, detail="Đã dừng")
        data = session_store.load_session(name)
        if not data:
            return SessionCheckResult(name, STATUS_NO_SESSION, detail="Chưa lưu session")
        cookies, _ls = data
        res = check_dola_cookies(cookies)
        res.name = name
        return res

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 16))) as ex:
        futures = {ex.submit(_one, n): n for n in names}
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                res = fut.result()
            except Exception as e:
                res = SessionCheckResult(futures[fut], STATUS_ERROR, detail=str(e))
            results.append(res)
            log("SessionCheck", f"[{done}/{total}] {res.name}: {res.status} {res.screen_name or res.detail}")
            if on_progress:
                try:
                    on_progress(res, done, total)
                except Exception:
                    pass

    order = {n: i for i, n in enumerate(names)}
    results.sort(key=lambda r: order.get(r.name, 0))
    return results


def delete_accounts(names: list, account_manager, session_store) -> list:
    """Xoá tài khoản khỏi AccountManager + SessionStore. Returns danh sách đã xoá."""
    deleted = []
    account_manager.load()
    session_store.load()
    for name in names:
        removed = False
        acc = account_manager.get_account(name)
        if acc:
            account_manager.accounts.remove(acc)
            removed = True
        if session_store.has_session(name):
            del session_store._sessions[name]
            removed = True
        if removed:
            deleted.append(name)
    if deleted:
        account_manager.save()
        session_store.save()
        log("SessionCheck", f"Đã xoá {len(deleted)} tài khoản die: {', '.join(deleted)}")
    return deleted
