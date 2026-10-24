# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Bulk Importer
Tự động hóa nhập hàng loạt 100-200 tài khoản Facebook VIA và login Dola.

Quy trình (hoàn toàn tự động, không cần thao tác tay):
┌────────────────────────────────────────────────────────────────┐
│ 1. Đọc file .txt chứa 100-200 dòng VIA cookies                │
│ 2. Cho mỗi dòng (chạy N luồng song song):                     │
│    a) Mở Chrome tạm (Port 9250 + worker_id)                   │
│    b) Inject Facebook cookies qua Playwright                    │
│    c) Mở facebook.com → Xác minh FB đã login                   │
│    d) Mở dola.com → Click "Login with Facebook"                 │
│    e) Xử lý OAuth popup (auto-approve vì FB đã có cookies)     │
│    f) Chờ Dola login thành công (chờ sessionid cookie)          │
│    g) Trích xuất Dola session → Lưu vào SessionStore (5KB)     │
│    h) Đóng Chrome + Xóa temp dir                               │
│ 3. Báo cáo: N thành công / M thất bại                         │
└────────────────────────────────────────────────────────────────┘
"""

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from config import DOLA_URL, EXTENSION_DIR
from utils import log, log_info
from account_manager import AccountManager, parse_via_cookie_string, Account
from browser_manager import BrowserManager
from session_store import SessionStore


@dataclass
class ImportResult:
    """Kết quả import 1 tài khoản."""
    account_name: str
    fb_uid: str = ""
    fb_name: str = ""
    success: bool = False
    dola_cookies_count: int = 0
    error: str = ""
    elapsed: float = 0.0


class BulkImporter:
    """Nhập hàng loạt VIA cookies và tự động login Dola.
    
    Usage:
        importer = BulkImporter(max_concurrent=5)
        results = await importer.import_from_file("via_cookies.txt")
        # hoặc
        results = await importer.import_from_lines(["uid|pass|2fa|cookies", ...])
    """

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = min(max_concurrent, 20)
        self.bm = BrowserManager()
        self.ss = SessionStore()
        self.am = AccountManager()
        self._on_progress: Optional[Callable] = None
        self._results: list[ImportResult] = []

    def set_progress_callback(self, callback: Callable):
        """Callback(account_name: str, message: str, current: int, total: int)"""
        self._on_progress = callback

    def _notify(self, acc_name: str, msg: str, current: int = 0, total: int = 0):
        log("BulkImport", f"[{acc_name}] {msg}")
        if self._on_progress:
            try:
                self._on_progress(acc_name, msg, current, total)
            except Exception:
                pass

    # ─── Parse Input ──────────────────────────────────────────────────────

    @staticmethod
    def parse_via_line(line: str) -> dict:
        """Parse 1 dòng VIA thành dict.
        
        Hỗ trợ format:
        - uid|password|2fa|cookie_string
        - uid|password|cookie_string
        - cookie_string (chỉ có cookies)
        - JSON format (hiếm)
        
        Returns: {"uid": "...", "password": "...", "2fa": "...", "cookies": "..."}
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return {}

        parts = line.split("|")
        result = {"uid": "", "password": "", "2fa": "", "cookies": ""}

        if len(parts) >= 4:
            # uid|pass|2fa|cookies...
            result["uid"] = parts[0].strip()
            result["password"] = parts[1].strip()
            result["2fa"] = parts[2].strip()
            # Cookie phần có thể chứa "|" bên trong
            result["cookies"] = "|".join(parts[3:]).strip()
        elif len(parts) == 3:
            # uid|pass|cookies
            result["uid"] = parts[0].strip()
            result["password"] = parts[1].strip()
            result["cookies"] = parts[2].strip()
        elif len(parts) == 2:
            # uid|cookies
            result["uid"] = parts[0].strip()
            result["cookies"] = parts[1].strip()
        else:
            # Chỉ có cookie string
            result["cookies"] = line

        # Extract uid from cookie nếu chưa có
        if not result["uid"] and result["cookies"]:
            m = re.search(r'c_user=(\d+)', result["cookies"])
            if m:
                result["uid"] = m.group(1)

        return result

    @staticmethod
    def parse_file(filepath: str) -> list[dict]:
        """Đọc file VIA cookies, trả về danh sách dicts."""
        results = []
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parsed = BulkImporter.parse_via_line(line)
                if parsed and parsed.get("cookies"):
                    parsed["line_number"] = i
                    results.append(parsed)
        return results

    # ─── Single Account Import ────────────────────────────────────────────

    async def _import_single(
        self,
        worker_id: int,
        via_data: dict,
        account_index: int,
        total: int,
    ) -> ImportResult:
        """Import 1 tài khoản: Inject FB cookies → Login Dola → Save session."""
        uid = via_data.get("uid", "")
        cookies_raw = via_data.get("cookies", "")
        account_name = f"via_{uid}" if uid else f"via_auto_{account_index:03d}"

        result = ImportResult(account_name=account_name, fb_uid=uid)
        t0 = time.time()

        self._notify(account_name, f"Bat dau import ({account_index}/{total})...",
                     account_index, total)

        try:
            # 1. Parse FB cookies
            fb_cookies = parse_via_cookie_string(cookies_raw)
            if not fb_cookies:
                raise Exception("Khong parse duoc cookie FB hop le tu VIA string")

            c_user = next((c["value"] for c in fb_cookies if c["name"] == "c_user"), "")
            if c_user:
                result.fb_uid = c_user
                account_name = f"via_{c_user}"
                result.account_name = account_name

            self._notify(account_name,
                f"Parse OK: {len(fb_cookies)} FB cookies, c_user={c_user}",
                account_index, total)

            # 2. Mở Chrome tạm
            self._notify(account_name, "Mo Chrome tam...", account_index, total)
            port = await self.bm.launch_temp_chrome(worker_id)

            # 3. Kết nối Playwright
            browser = await self.bm.connect_worker(worker_id)
            if not browser:
                raise Exception("Khong ket noi duoc Playwright")

            ctx = await self.bm.get_worker_context(worker_id)
            page = await self.bm.get_worker_page(worker_id)

            # 4. Inject FB cookies
            self._notify(account_name,
                f"Inject {len(fb_cookies)} FB cookies...", account_index, total)
            pw_cookies = []
            for c in fb_cookies:
                pw_cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".facebook.com"),
                    "path": c.get("path", "/"),
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", True),
                    "sameSite": "None" if c.get("secure") else "Lax",
                })
            await ctx.add_cookies(pw_cookies)

            # 5. Verify FB login
            self._notify(account_name, "Kiem tra FB login...", account_index, total)
            await page.goto("https://www.facebook.com/me", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            fb_url = page.url
            if "login" in fb_url.lower() or "checkpoint" in fb_url.lower():
                raise Exception(f"FB cookie da het han hoac bi checkpoint (redirect: {fb_url})")

            # Lấy tên FB user
            try:
                fb_name = await page.evaluate("""
                    () => {
                        const h1 = document.querySelector('h1');
                        if (h1) return h1.innerText;
                        const title = document.title;
                        if (title && !title.includes('Facebook')) return title;
                        return '';
                    }
                """)
                result.fb_name = fb_name.strip() if fb_name else ""
            except Exception:
                pass

            self._notify(account_name,
                f"FB OK! User: {result.fb_name or c_user}", account_index, total)

            # 6. Navigate to Dola → Login with Facebook
            self._notify(account_name, "Mo Dola, login bang Facebook...", account_index, total)
            await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            # Kiểm tra nếu đã login rồi (có thể xảy ra nếu Dola đọc FB cookies trực tiếp)
            body_text = await page.inner_text("body")
            already_logged_in = any(kw in body_text for kw in [
                "Tạo video", "Create Video", "Nhập mô tả", "Enter your prompt",
            ])

            if not already_logged_in:
                # Click nút Login / Sign in
                login_clicked = await self._click_dola_login(page)
                if not login_clicked:
                    raise Exception("Khong tim thay nut Login tren Dola")

                # Xử lý OAuth Facebook popup hoặc redirect
                await self._handle_facebook_oauth(page, ctx)

                # Chờ Dola login thành công
                self._notify(account_name, "Cho Dola xac nhan login...", account_index, total)
                success = await self._wait_dola_login_success(page, timeout=30)
                if not success:
                    raise Exception("Dola khong xac nhan login sau 30s")

            self._notify(account_name, "Dola login THANH CONG!", account_index, total)

            # 7. Kích hoạt Extension bypass
            await page.evaluate("""
                () => {
                    localStorage.setItem('__dolaDurBypass', '1');
                    localStorage.setItem('__dolaTargetDur', '31');
                    localStorage.setItem('__dolaDur31', '1');
                    localStorage.setItem('__dolaDur15', '1');
                }
            """)

            # 8. Trích xuất + Lưu Dola Session
            self._notify(account_name, "Trich xuat Dola session...", account_index, total)
            cookies, ls = await self.ss.extract_from_browser(ctx, page)
            self.ss.save_session(account_name, cookies, ls)
            result.dola_cookies_count = len([c for c in cookies if ".dola.com" in c.get("domain", "")])

            # 9. Tạo/update Account trong AccountManager
            existing = self.am.get_account(account_name)
            if not existing:
                acc = Account(
                    name=account_name,
                    login_type="facebook",
                    fb_uid=c_user,
                    fb_cookies=cookies_raw[:500],  # Lưu tóm tắt, không lưu đầy đủ
                    dola_session_saved=True,
                )
                self.am.accounts.append(acc)
            else:
                existing.dola_session_saved = True
                existing.fb_uid = c_user
                existing.status = "active"
            self.am.save()

            result.success = True
            result.elapsed = time.time() - t0
            self._notify(account_name,
                f"THANH CONG! ({result.dola_cookies_count} Dola cookies, {result.elapsed:.1f}s)",
                account_index, total)

        except Exception as e:
            result.error = str(e)
            result.elapsed = time.time() - t0
            self._notify(account_name, f"THAT BAI: {e}", account_index, total)

        finally:
            # Cleanup Chrome tạm
            await self.bm.cleanup_worker(worker_id)

        return result

    # ─── Dola Login Helpers ───────────────────────────────────────────────

    async def _click_dola_login(self, page) -> bool:
        """Tìm và click nút Login trên Dola."""
        # Đóng modals trước
        try:
            await page.evaluate("""
                () => {
                    document.querySelectorAll('.semi-modal-wrap, .semi-portal, .semi-modal-mask')
                        .forEach(el => el.remove());
                }
            """)
        except Exception:
            pass

        # Tìm nút Login
        login_selectors = [
            'button:has-text("Log in")',
            'button:has-text("Đăng nhập")',
            'button:has-text("Sign in")',
            'div[role="button"]:has-text("Log in")',
            'a:has-text("Log in")',
            '[data-testid="login-button"]',
        ]
        for sel in login_selectors:
            try:
                btn = await page.wait_for_selector(sel, timeout=3000)
                if btn:
                    await btn.click()
                    log("BulkImport", f"Clicked login button: {sel}")
                    await asyncio.sleep(2)
                    return True
            except Exception:
                continue

        return False

    async def _handle_facebook_oauth(self, page, ctx) -> bool:
        """Xử lý OAuth Facebook (popup hoặc redirect).
        
        Khi user đã có FB cookies, OAuth flow sẽ:
        1. Hiện popup FB "Continue as [User]"
        2. Tự động approve (hoặc cần click "Continue")
        3. Redirect về Dola
        """
        try:
            # Chờ popup Facebook
            popup = None
            try:
                popup = await page.wait_for_event("popup", timeout=5000)
            except Exception:
                pass

            if popup:
                log("BulkImport", f"OAuth popup opened: {popup.url}")
                await popup.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)

                # Tìm nút "Continue" hoặc "Tiếp tục" trong popup
                continue_selectors = [
                    'button[name="__CONFIRM__"]',
                    'button:has-text("Continue")',
                    'button:has-text("Tiếp tục")',
                    'input[value="Continue"]',
                    '#platformDialogForm button',
                    '[data-testid="auth_dialog_continue_button"]',
                ]
                for sel in continue_selectors:
                    try:
                        btn = await popup.wait_for_selector(sel, timeout=3000)
                        if btn:
                            await btn.click()
                            log("BulkImport", f"Clicked Continue in OAuth popup: {sel}")
                            break
                    except Exception:
                        continue

                # Chờ popup đóng
                try:
                    await popup.wait_for_event("close", timeout=15000)
                except Exception:
                    pass
                return True

            else:
                # Không có popup → có thể Dola dùng redirect
                # Kiểm tra xem trang hiện tại có phải facebook.com/dialog/oauth không
                current_url = page.url
                if "facebook.com" in current_url:
                    log("BulkImport", "OAuth redirect detected, looking for Continue button...")
                    continue_selectors = [
                        'button[name="__CONFIRM__"]',
                        'button:has-text("Continue")',
                        'button:has-text("Tiếp tục")',
                    ]
                    for sel in continue_selectors:
                        try:
                            btn = await page.wait_for_selector(sel, timeout=3000)
                            if btn:
                                await btn.click()
                                log("BulkImport", f"Clicked Continue on redirect: {sel}")
                                await asyncio.sleep(3)
                                break
                        except Exception:
                            continue
                return True

        except Exception as e:
            log("BulkImport", f"OAuth handling error (may still work): {e}")
            return True

    async def _wait_dola_login_success(self, page, timeout: int = 30) -> bool:
        """Chờ Dola xác nhận login thành công."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                # Kiểm tra URL (redirect về /chat/ khi login thành công)
                if "/chat" in page.url and "login" not in page.url.lower():
                    # Kiểm tra có khung chat không
                    body = await page.inner_text("body")
                    if any(kw in body for kw in [
                        "Tạo video", "Create Video", "Nhập mô tả",
                        "Enter your prompt", "Send a message",
                    ]):
                        return True
            except Exception:
                pass
            await asyncio.sleep(2)
        return False

    # ─── Batch Import ─────────────────────────────────────────────────────

    async def import_from_lines(self, via_lines: list[str]) -> list[ImportResult]:
        """Import từ danh sách dòng VIA cookies."""
        parsed = []
        for line in via_lines:
            p = self.parse_via_line(line)
            if p and p.get("cookies"):
                parsed.append(p)

        if not parsed:
            log("BulkImport", "Khong tim thay VIA cookie hop le trong input.")
            return []

        return await self._run_batch(parsed)

    async def import_from_file(self, filepath: str) -> list[ImportResult]:
        """Import từ file .txt"""
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File khong ton tai: {filepath}")

        parsed = self.parse_file(filepath)
        if not parsed:
            log("BulkImport", f"Khong tim thay VIA cookie hop le trong file: {filepath}")
            return []

        log("BulkImport", f"Parsed {len(parsed)} VIA cookies tu file: {filepath}")
        return await self._run_batch(parsed)

    async def _run_batch(self, parsed_list: list[dict]) -> list[ImportResult]:
        """Chạy batch import N luồng song song."""
        total = len(parsed_list)
        self._results = []
        sem = asyncio.Semaphore(self.max_concurrent)

        async def limited_import(idx, via_data):
            async with sem:
                worker_id = idx % self.max_concurrent
                result = await self._import_single(worker_id, via_data, idx + 1, total)
                self._results.append(result)

        tasks = [limited_import(i, d) for i, d in enumerate(parsed_list)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Summary
        success = sum(1 for r in self._results if r.success)
        failed = sum(1 for r in self._results if not r.success)
        log("BulkImport",
            f"HOAN THANH: {success}/{total} thanh cong, {failed} that bai")

        return self._results

    def get_summary(self) -> dict:
        """Trả về tóm tắt kết quả import."""
        return {
            "total": len(self._results),
            "success": sum(1 for r in self._results if r.success),
            "failed": sum(1 for r in self._results if not r.success),
            "results": [
                {
                    "account": r.account_name,
                    "fb_uid": r.fb_uid,
                    "fb_name": r.fb_name,
                    "success": r.success,
                    "cookies": r.dola_cookies_count,
                    "error": r.error,
                    "time": f"{r.elapsed:.1f}s",
                }
                for r in self._results
            ],
        }
