# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio v5.1 — FB Login Automation
Module tự động hóa đăng nhập Facebook VIA → Dola.

Quy trình (nhanh, dứt khoát để nick FB không bị die/checkpoint):
1. Bóc tách VIA (UID|Pass|2FA|Cookie|Token|Email...) → cookie, mật khẩu, 2FA, token
2. Inject FB cookies vào domain .facebook.com
3. Mở facebook.com → xác minh THẬT SỰ còn live (cookie c_user/xs còn, không có form login,
   không checkpoint). Nếu cookie die mà VIA có mật khẩu → tự đăng nhập bằng pass + 2FA (TOTP).
4. Chuyển ngay qua dola.com/chat/
5. Kiểm tra Dola:
   a. Nếu đã đăng nhập → xong
   b. Nếu chưa:
      - Bấm nút "Đăng nhập" ở header (click thật bằng chuột CDP)
      - Bấm icon Facebook trong modal, bắt popup OAuth (context.expect_page)
      - CHỜ popup điều hướng tới facebook.com (popup mới mở có URL rỗng / about:blank)
      - Bấm "Tiếp tục dưới tên..." / __CONFIRM__ (đa ngôn ngữ), tự điền pass/2FA nếu FB hỏi lại
      - Chờ cookie sessionid của Dola xuất hiện
6. Xác thực token Dola qua API passport /passport/account/info/v2/ (lấy user_id, tên)
"""

import asyncio
import base64
import hashlib
import hmac
import re
import struct
import time
from typing import Optional, Callable

from playwright.async_api import Page, BrowserContext

from config import DOLA_URL
from account_manager import parse_via_cookie_string
from utils import log


# Cookie xác thực của Dola (ByteDance Passport) — chỉ có khi đã đăng nhập thật
DOLA_AUTH_COOKIE_NAMES = ("sessionid", "sessionid_ss", "sid_tt")
# API passport trả về thông tin user nếu session còn sống
DOLA_ACCOUNT_INFO_URL = "https://www.dola.com/passport/account/info/v2/"


# ─── VIA parsing & TOTP ───────────────────────────────────────────────────────

def parse_via_fields(raw: str) -> dict:
    """Bóc tách 1 dòng VIA thành các trường.

    Hỗ trợ: UID|Pass|2FA|Cookie..., UID|Pass|Cookie|Token|Email|Date, UID|Cookie,
    hoặc chỉ chuỗi cookie (c_user=...; xs=...).

    Returns: {"uid", "password", "twofa", "cookie", "token", "email"}
    """
    raw = (raw or "").strip()
    out = {"uid": "", "password": "", "twofa": "", "cookie": "", "token": "", "email": ""}
    if not raw:
        return out

    m = re.search(r'c_user=(\d+)', raw)
    if m:
        out["uid"] = m.group(1)

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) > 1:
        if not out["uid"] and re.fullmatch(r'\d{5,20}', parts[0]):
            out["uid"] = parts[0]
        for i, p in enumerate(parts):
            if not p or i == 0:
                continue
            if "c_user=" in p or ("xs=" in p and ";" in p):
                out["cookie"] = p
                continue
            if p.startswith("EAA") and len(p) > 40:
                out["token"] = p
                continue
            if "@" in p and "=" not in p and not out["email"]:
                out["email"] = p
                continue
            compact = p.replace(" ", "").upper()
            # 2FA secret (base32) thường nằm ở vị trí thứ 3 trở đi
            if i >= 2 and not out["twofa"] and re.fullmatch(r'[A-Z2-7]{16,64}', compact):
                out["twofa"] = compact
                continue
        p1 = parts[1]
        if p1 and "=" not in p1 and not p1.startswith("EAA") and p1.replace(" ", "").upper() != out["twofa"]:
            out["password"] = p1

    if not out["cookie"]:
        out["cookie"] = raw
    return out


def generate_totp(secret: str, period: int = 30, digits: int = 6) -> str:
    """Sinh mã 2FA (TOTP RFC 6238) từ secret base32 của Facebook."""
    s = re.sub(r'[^A-Z2-7]', '', (secret or "").upper())
    if not s:
        return ""
    s += "=" * (-len(s) % 8)
    key = base64.b32decode(s)
    counter = int(time.time() // period)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


# ─── JS snippets ──────────────────────────────────────────────────────────────

# Tìm tọa độ nút Facebook trong modal đăng nhập Dola (không click trong JS — click bằng chuột thật)
_JS_FIND_DOLA_FB_BUTTON = r"""
() => {
    const center = (el) => {
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return null;
        return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    };
    // 1. SVG path logo Facebook (fill xanh FB hoặc path chuẩn)
    const fbPath = document.querySelector(
        'path[fill="#0068FF"], path[fill="#0068ff"], path[fill="#1877F2" i], path[fill="#0866FF" i], ' +
        'path[d*="M12 2C6.203"], path[d*="8.86 10.437v-7.383H7.693"]'
    );
    if (fbPath) {
        const btn = fbPath.closest('div[class*="clickable"]') ||
                    fbPath.closest('div[class*="btn"]') ||
                    fbPath.closest('div[class*="button"]') ||
                    fbPath.closest('[role="button"]') ||
                    fbPath.closest('button') ||
                    fbPath.closest('svg') || fbPath.parentElement;
        const c = btn && center(btn);
        if (c) return { x: c.x, y: c.y, method: 'svg_path' };
    }
    // 2. aria-label / text Facebook
    const all = Array.from(document.querySelectorAll('button, [role="button"], div, a'));
    for (const el of all) {
        const label = ((el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '')).toLowerCase();
        const txt = (el.innerText || '').trim().toLowerCase();
        if (label.includes('facebook') || txt === 'facebook' ||
            txt.includes('tiếp tục bằng facebook') || txt.includes('continue with facebook')) {
            const c = center(el);
            if (c) return { x: c.x, y: c.y, method: 'label_text' };
        }
    }
    // 3. Hàng 3 nút tròn dưới nút Google: [Điện thoại] [Facebook] [Apple] → nút giữa
    const cands = [];
    for (const el of all) {
        const r = el.getBoundingClientRect();
        if (r.width >= 32 && r.width <= 64 && Math.abs(r.width - r.height) <= 10 && r.y > 150 && r.y < 800) {
            cands.push({ el, r });
        }
    }
    cands.sort((a, b) => a.r.x - b.r.x);
    for (let i = 0; i < cands.length - 2; i++) {
        const a = cands[i], b = cands[i + 1], c = cands[i + 2];
        if (Math.abs(a.r.y - b.r.y) < 12 && Math.abs(b.r.y - c.r.y) < 12 &&
            b.r.x - a.r.x > 20 && c.r.x - b.r.x > 20) {
            const cc = center(b.el);
            if (cc) return { x: cc.x, y: cc.y, method: 'middle_round_icon' };
        }
    }
    return null;
}
"""

# Tìm nút xác nhận OAuth / Consent Facebook đa ngôn ngữ (trả về tọa độ)
_JS_FIND_FB_CONFIRM = r"""
() => {
    const ACTION = /(continuar\s+como|continue\s+as|tiếp\s+tục\s+dưới\s+tên|olarak\s+devam\s+et|fortfahren\s+als|continuer\s+en\s+tant|segui\s+come|continua\s+come|kontynuuj\s+jako|продолжить\s+как|として続行|继续|continuar|tiếp\s+tục|continue|devam\s+et|allow|cho\s+phép|đồng\s+ý|accept)/i;
    const EXCLUDE = /(cancelar|cancel|hủy|huỷ|iptal|abbrechen|annuler|annulla|отмена|fechar|close|đóng|saiba\s+mais|ver\s+acesso|learn\s+more|policy|chính\s+sách|terms|điều\s+khoản|switch\s+account|chuyển\s+tài\s+khoản|not\s+you|không\s+phải|edit|chỉnh\s+sửa)/i;
    const visible = (el) => {
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
    };
    const pack = (el, method) => {
        const r = el.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2,
                 text: (el.innerText || el.value || '').trim().slice(0, 60), method };
    };
    // 1. Selector đặc thù
    const special = document.querySelector(
        'button[name="__CONFIRM__"], input[name="__CONFIRM__"], [data-testid*="confirm" i], [data-testid*="platform_login_button" i]'
    );
    if (special && visible(special)) return pack(special, 'special');

    // 2. Từ khóa đa ngôn ngữ
    const clickables = Array.from(document.querySelectorAll(
        'button, div[role="button"], a[role="button"], input[type="submit"]'
    ));
    for (const b of clickables) {
        const t = (b.innerText || b.textContent || b.value || '').trim();
        if (!t || t.length > 80 || EXCLUDE.test(t) || !ACTION.test(t) || !visible(b)) continue;
        const r = b.getBoundingClientRect();
        if (r.width >= 60 && r.height >= 20 && r.height <= 100) return pack(b, 'keyword');
    }

    // 3. Nút nền xanh Facebook
    const isBlue = (c) => {
        const m = (c || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/i);
        if (!m) return false;
        const r = +m[1], g = +m[2], b = +m[3], a = m[4] !== undefined ? +m[4] : 1;
        return a >= 0.3 && b >= 150 && (b - r >= 40) && (b - g >= 10);
    };
    for (const el of Array.from(document.querySelectorAll('div, span, button, a'))) {
        try {
            if (!isBlue(getComputedStyle(el).backgroundColor)) continue;
            const btn = el.closest('button, div[role="button"], a[role="button"]') || el;
            const r = btn.getBoundingClientRect();
            const t = (btn.innerText || '').trim();
            if (r.width >= 100 && r.height >= 24 && r.height <= 90 && !EXCLUDE.test(t)) return pack(btn, 'blue_button');
        } catch (e) {}
    }
    return null;
}
"""

# Trạng thái trang Facebook trong popup / tab
_JS_FB_PAGE_STATE = r"""
() => {
    const url = location.href.toLowerCase();
    const q = (s) => document.querySelector(s);
    const vis = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    if (vis(q('input[name="approvals_code"]')) || vis(q('input[autocomplete="one-time-code"]')) ||
        url.includes('two_step_verification') || url.includes('two_factor')) return 'twofa';
    if (vis(q('input[name="pass"]')) || vis(q('input[type="password"]'))) return 'login_form';
    if (url.includes('/checkpoint')) return 'checkpoint';
    return 'other';
}
"""


class FBLoginAutomation:
    """Tự động login Facebook VIA → Dola."""

    def __init__(self):
        self._cancel = False
        self.last_error: str = ""          # Lý do thất bại gần nhất (hiển thị cho UI)
        self.last_fb_status: str = ""      # live | dead | checkpoint | unknown
        self.dola_user: Optional[dict] = None  # Thông tin user Dola sau khi login (passport API)
        self._via: dict = {}

    def cancel(self):
        self._cancel = True

    # ─── Facebook ────────────────────────────────────────────────────────

    async def inject_fb_cookies(self, context: BrowserContext, raw_cookie: str) -> bool:
        """Inject FB cookies vào browser context.

        Returns: True nếu inject thành công (có ít nhất c_user và xs)
        """
        parsed = parse_via_cookie_string(raw_cookie)
        if not parsed:
            log("FBLogin", "[X] Khong parse duoc cookie FB tu input")
            return False

        has_c_user = any(c["name"] == "c_user" for c in parsed)
        has_xs = any(c["name"] == "xs" for c in parsed)
        if not has_c_user or not has_xs:
            log("FBLogin", "[X] Cookie thieu c_user hoac xs — khong the login bang cookie")
            return False

        try:
            for c in parsed:
                c["httpOnly"] = c["name"] in ("xs", "fr", "datr", "sb")
                c["domain"] = ".facebook.com"
                c["path"] = "/"
                c["secure"] = True
                c["sameSite"] = "None"
                c["expires"] = int(time.time()) + 180 * 86400
            await context.add_cookies(parsed)
            log("FBLogin", f"[OK] Da inject {len(parsed)} FB cookies vao browser")
            return True
        except Exception as e:
            log("FBLogin", f"[X] Loi inject FB cookies: {e}")
            return False

    @staticmethod
    async def _fb_cookie_alive(context: BrowserContext) -> bool:
        """FB xóa c_user/xs khi session không hợp lệ → còn cả 2 cookie = còn phiên."""
        try:
            cks = await context.cookies("https://www.facebook.com")
            names = {c["name"] for c in cks if c.get("value")}
            return "c_user" in names and "xs" in names
        except Exception:
            return False

    async def check_fb_status(self, page: Page) -> str:
        """Mở facebook.com và phân loại: live | dead | checkpoint | unknown."""
        try:
            await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log("FBLogin", f"[?] Loi mo facebook.com: {e}")
            return "unknown"
        await asyncio.sleep(2.5)

        url = (page.url or "").lower()
        if "checkpoint" in url or "two_step_verification" in url or "/confirmemail" in url:
            return "checkpoint"
        if "/login" in url or "login.php" in url:
            return "dead"
        try:
            state = await page.evaluate(_JS_FB_PAGE_STATE)
        except Exception:
            state = "other"
        if state == "checkpoint":
            return "checkpoint"
        if state in ("login_form", "twofa"):
            return "dead"
        if not await self._fb_cookie_alive(page.context):
            return "dead"
        return "live"

    async def verify_fb_login(self, page: Page) -> bool:
        """Tương thích ngược: True nếu FB còn live."""
        self.last_fb_status = await self.check_fb_status(page)
        return self.last_fb_status == "live"

    async def _fill_fb_credentials(self, page: Page) -> str:
        """Điền form đăng nhập / 2FA nếu đang hiển thị. Returns: 'login' | 'twofa' | ''."""
        via = self._via or {}
        try:
            state = await page.evaluate(_JS_FB_PAGE_STATE)
        except Exception:
            return ""

        if state == "login_form" and via.get("password"):
            try:
                email_loc = page.locator('input[name="email"]').first
                if await email_loc.count() > 0 and await email_loc.is_visible():
                    cur = await email_loc.input_value()
                    if not cur:
                        await email_loc.fill(via.get("uid") or via.get("email") or "")
                pass_loc = page.locator('input[name="pass"], input[type="password"]').first
                await pass_loc.fill(via["password"])
                await asyncio.sleep(0.3)
                await pass_loc.press("Enter")
                log("FBLogin", "[OK] Da dien mat khau FB va gui form")
                return "login"
            except Exception as e:
                log("FBLogin", f"[!] Loi dien mat khau FB: {e}")
                return ""

        if state == "twofa" and via.get("twofa"):
            try:
                code = generate_totp(via["twofa"])
                loc = page.locator(
                    'input[name="approvals_code"], input[autocomplete="one-time-code"], '
                    'input[type="text"], input[type="number"], input[type="tel"]'
                ).first
                await loc.fill(code)
                await asyncio.sleep(0.3)
                await loc.press("Enter")
                log("FBLogin", f"[OK] Da dien ma 2FA ({code})")
                return "twofa"
            except Exception as e:
                log("FBLogin", f"[!] Loi dien 2FA: {e}")
        return ""

    async def _fb_password_login(self, page: Page) -> bool:
        """Đăng nhập FB bằng UID/Pass (+2FA) khi cookie đã die."""
        via = self._via or {}
        if not via.get("password"):
            return False
        log("FBLogin", "[...] Cookie FB die — thu dang nhap bang mat khau + 2FA...")
        try:
            await page.goto("https://www.facebook.com/login.php", wait_until="domcontentloaded", timeout=30000)
        except Exception:
            return False
        await asyncio.sleep(2)

        last_action_at = 0.0
        deadline = time.time() + 60
        while time.time() < deadline and not self._cancel:
            url = (page.url or "").lower()
            if await self._fb_cookie_alive(page.context) and "checkpoint" not in url and "two_step" not in url:
                return True
            if time.time() - last_action_at > 4:
                action = await self._fill_fb_credentials(page)
                if action:
                    last_action_at = time.time()
                else:
                    # Màn hình "Lưu trình duyệt" / "Tiếp tục" sau 2FA
                    await self._click_fb_confirm(page)
            await asyncio.sleep(1.5)
        return await self._fb_cookie_alive(page.context)

    async def _click_fb_confirm(self, fb_page: Page) -> bool:
        """Bấm nút xác nhận OAuth / Consent / Tiếp tục bằng chuột thật."""
        try:
            info = await fb_page.evaluate(_JS_FIND_FB_CONFIRM)
        except Exception:
            return False
        if not info:
            return False
        try:
            await fb_page.mouse.click(info["x"], info["y"])
            log("FBLogin", f"[OK] Da bam nut FB '{info.get('text', '')}' ({info.get('method')})")
            return True
        except Exception:
            return False

    # ─── Dola ────────────────────────────────────────────────────────────

    @staticmethod
    async def _has_dola_session(context: BrowserContext) -> bool:
        try:
            for c in await context.cookies():
                if ("dola" in (c.get("domain") or "").lower()
                        and c.get("name") in DOLA_AUTH_COOKIE_NAMES and c.get("value")):
                    return True
        except Exception:
            pass
        return False

    async def fetch_dola_account_info(self, context: BrowserContext) -> Optional[dict]:
        """Use Chrome's network route so extension proxy settings also cover the login check."""
        try:
            from urllib.parse import urlsplit
            page = next((p for p in context.pages if
                         (urlsplit(p.url).hostname or '') in ('www.dola.com', 'dola.com')), None)
            if page is None:
                return None  # Do not send profile credentials over an unrelated direct HTTP client.
            data = await page.evaluate('''async url => {
                const response = await fetch(url, {credentials:'include', cache:'no-store',
                    signal:AbortSignal.timeout(15000)});
                if (!response.ok) return {};
                return await response.json();
            }''', DOLA_ACCOUNT_INFO_URL)
            if data.get("message") == "success":
                d = data.get("data") or {}
                if d.get("user_id") and not d.get("is_visitor_account"):
                    return d
        except Exception as e:
            log("FBLogin", f"[?] Khong goi duoc passport API: {e}")
        return None

    async def _check_dola_logged_in(self, page: Page) -> bool:
        """Dola đã đăng nhập? (KHÔNG điều hướng trang). Dựa vào cookie sessionid + passport API."""
        context = page.context
        if not await self._has_dola_session(context):
            return False
        info = await self.fetch_dola_account_info(context)
        if info:
            self.dola_user = info
            log("FBLogin", f"[OK] Dola da dang nhap: {info.get('screen_name') or info.get('name')} "
                           f"(user_id={info.get('user_id_str') or info.get('user_id')})")
            return True
        return False

    async def _dola_modal_open(self, page: Page) -> bool:
        try:
            return await page.evaluate(r"""
                () => {
                    const t = document.body ? (document.body.innerText || '') : '';
                    return /Tiếp tục bằng Google|Continue with Google|Đăng nhập để mở khóa|Sign in to unlock|Log in to unlock/i.test(t);
                }
            """)
        except Exception:
            return False

    async def _click_dang_nhap_button(self, page: Page) -> bool:
        """Bấm nút 'Đăng nhập' ở header Dola và chờ modal. Returns True nếu modal mở."""
        if await self._dola_modal_open(page):
            return True
        log("FBLogin", "[...] Tim nut 'Dang nhap' trong header Dola...")
        selectors = [
            'button[class*="login-btn-header"]',
            'button[class*="login-btn"]',
            'button:has-text("Đăng nhập")',
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
            'a:has-text("Đăng nhập")',
            'div[role="button"]:has-text("Đăng nhập")',
        ]
        for attempt in range(3):
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(timeout=4000)
                        log("FBLogin", f"[OK] Da click nut 'Dang nhap': {sel}")
                        for _ in range(10):
                            await asyncio.sleep(0.5)
                            if await self._dola_modal_open(page):
                                return True
                        break
                except Exception:
                    continue
            if await self._dola_modal_open(page):
                return True
            await asyncio.sleep(1.5)
        log("FBLogin", "[X] Khong mo duoc modal dang nhap Dola")
        return False

    async def _click_facebook_icon_in_modal(self, page: Page, context: BrowserContext) -> tuple[bool, Optional[Page]]:
        """Bấm icon Facebook trong modal và bắt trang OAuth (popup hoặc redirect cùng tab).

        Returns: (clicked, oauth_page)
        """
        log("FBLogin", "[...] Bam icon Facebook trong modal...")
        info = None
        for _ in range(6):
            try:
                info = await page.evaluate(_JS_FIND_DOLA_FB_BUTTON)
            except Exception:
                info = None
            if info:
                break
            await asyncio.sleep(0.5)
        if not info:
            log("FBLogin", "[X] Khong tim thay icon Facebook trong modal")
            return False, None

        popup: Optional[Page] = None
        try:
            async with context.expect_page(timeout=10000) as page_info:
                await page.mouse.click(info["x"], info["y"])
                log("FBLogin", f"[OK] Da click icon Facebook ({info.get('method')})")
            popup = await page_info.value
        except Exception:
            popup = None

        if popup:
            return True, popup

        # Không có popup → Dola có thể redirect cùng tab sang facebook.com
        for _ in range(8):
            await asyncio.sleep(0.7)
            if "facebook.com" in (page.url or "").lower():
                log("FBLogin", "[OK] OAuth dang redirect cung tab")
                return True, page
            for p in context.pages:
                if p is not page and "facebook.com" in (p.url or "").lower():
                    return True, p
        return True, None

    async def _wait_page_navigated(self, p: Page, timeout: float = 20) -> bool:
        """Popup mới mở có URL rỗng/about:blank — chờ tới khi điều hướng thật sự."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                if p.is_closed():
                    return False
            except Exception:
                return False
            url = (p.url or "").lower()
            if url.startswith("http"):
                try:
                    await p.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                return True
            await asyncio.sleep(0.4)
        return False

    async def _handle_oauth_popup(self, page: Page, context: BrowserContext,
                                  popup: Optional[Page] = None) -> bool:
        """Xử lý trang OAuth Facebook (đa ngôn ngữ) và chờ Dola cấp session."""
        try:
            if popup is None:
                await asyncio.sleep(2)
                return await self._wait_dola_session(page, context, 15)

            if not await self._wait_page_navigated(popup, 20):
                log("FBLogin", "[...] Popup OAuth dong ngay (FB tu dong xac nhan) — cho Dola...")
                return await self._wait_dola_session(page, context, 20)

            log("FBLogin", f"[...] Dang xu ly OAuth Facebook: {popup.url[:120]}")
            last_click = 0.0
            last_fill = 0.0
            deadline = time.time() + 75
            while time.time() < deadline and not self._cancel:
                if await self._has_dola_session(context):
                    break
                try:
                    if popup.is_closed():
                        log("FBLogin", "[OK] Popup OAuth da dong")
                        break
                except Exception:
                    break

                url = (popup.url or "").lower()
                if "facebook.com" in url:
                    try:
                        state = await popup.evaluate(_JS_FB_PAGE_STATE)
                    except Exception:
                        state = "other"

                    if state in ("login_form", "twofa"):
                        if (state == "login_form" and not self._via.get("password")) or \
                           (state == "twofa" and not self._via.get("twofa")):
                            self.last_error = ("Facebook yeu cau dang nhap lai (cookie FB die)"
                                               if state == "login_form" else "Facebook yeu cau ma 2FA nhung VIA khong co 2FA")
                            log("FBLogin", f"[X] {self.last_error}")
                            return False
                        if time.time() - last_fill > 6:
                            await self._fill_fb_credentials(popup)
                            last_fill = time.time()
                    elif state == "checkpoint":
                        self.last_error = "Facebook bi checkpoint trong luc OAuth"
                        log("FBLogin", f"[X] {self.last_error}")
                        return False
                    elif time.time() - last_click > 2.5:
                        if await self._click_fb_confirm(popup):
                            last_click = time.time()
                elif "dola.com" in url and popup is page:
                    # Redirect cùng tab đã quay về Dola
                    break
                await asyncio.sleep(1.0)

            return await self._wait_dola_session(page, context, 25)

        except Exception as e:
            log("FBLogin", f"[X] Loi xu ly popup OAuth: {e}")
            return await self._has_dola_session(context)

    async def _wait_dola_session(self, page: Page, context: BrowserContext, seconds: float) -> bool:
        """Chờ cookie sessionid Dola, đồng thời tự dập modal xác nhận tuổi."""
        log("FBLogin", "[...] Dang cho Dola cap phien dang nhap (sessionid)...")
        end = time.time() + seconds
        while time.time() < end and not self._cancel:
            if await self._has_dola_session(context):
                await asyncio.sleep(1.0)
                await self._handle_age_verification_modal(page)
                log("FBLogin", "[OK] Phat hien cookie sessionid cua Dola!")
                return True
            await self._handle_age_verification_modal(page)
            await asyncio.sleep(1.2)
        return False

    async def _handle_age_verification_modal(self, page: Page) -> bool:
        """Tự động phát hiện và bấm nút 'Xác nhận' trên modal xác nhận tuổi 18+ của Dola AI."""
        try:
            if page.is_closed() or "dola.com" not in (page.url or ""):
                return False
            clicked = await page.evaluate(r"""
                () => {
                    const modals = Array.from(document.querySelectorAll(
                        'div[role="dialog"], div[class*="modal"], div[class*="dialog"]'
                    ));
                    for (const m of modals) {
                        const r = m.getBoundingClientRect();
                        if (r.width <= 0 || r.height <= 0) continue;
                        const txt = (m.innerText || '').toLowerCase();
                        if (!(txt.includes('tuổi') || txt.includes('18') || txt.includes(' age') || txt.includes('birth'))) continue;
                        const btns = Array.from(m.querySelectorAll('button, div[role="button"]'));
                        for (const b of btns) {
                            const t = (b.innerText || '').trim();
                            if (/^(Xác nhận|Confirm|Đồng ý|Yes|OK|Tôi đã đủ 18 tuổi|I am 18.*)$/i.test(t)) {
                                b.click();
                                return t;
                            }
                        }
                    }
                    return null;
                }
            """)
            if clicked:
                log("FBLogin", f"[OK] Da bam '{clicked}' xac nhan tuoi 18+ tren Dola")
                await asyncio.sleep(0.8)
                return True
        except Exception:
            pass
        return False

    async def click_fb_login_on_dola(self, page: Page) -> bool:
        """Luồng trên Dola: Đăng nhập → icon Facebook → xác nhận OAuth → chờ session."""
        context = page.context
        try:
            if not await self._click_dang_nhap_button(page):
                self.last_error = self.last_error or "Khong mo duoc modal dang nhap Dola"
                return False
            await asyncio.sleep(0.8)

            clicked, oauth_page = await self._click_facebook_icon_in_modal(page, context)
            if not clicked:
                self.last_error = "Khong tim thay icon Facebook trong modal Dola"
                return False

            return await self._handle_oauth_popup(page, context, popup=oauth_page)
        except Exception as e:
            log("FBLogin", f"[X] Loi click FB login tren Dola: {e}")
            return False

    async def _confirm_dola_login(self, page: Page) -> bool:
        """Xác nhận cuối cùng bằng passport API (lấy token/user_id)."""
        context = page.context
        if not await self._has_dola_session(context):
            return False
        info = await self.fetch_dola_account_info(context)
        if info:
            self.dola_user = info
            return True
        # Có sessionid nhưng API chưa trả lời — chờ thêm 1 nhịp rồi thử lại
        await asyncio.sleep(3)
        info = await self.fetch_dola_account_info(context)
        if info:
            self.dola_user = info
            return True
        self.last_error = "Co cookie sessionid nhung passport API bao session khong hop le"
        return False

    async def _open_dola(self, page: Page) -> bool:
        try:
            await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log("FBLogin", f"[?] Loi mo Dola: {e}")
            return False
        await asyncio.sleep(3)
        await self._handle_age_verification_modal(page)
        return True

    async def full_auto_login(
        self,
        context: BrowserContext,
        page: Page,
        raw_fb_cookie: str,
        on_progress: Optional[Callable] = None,
    ) -> bool:
        """Full flow: VIA → Facebook → Dola → session + token.

        Args:
            raw_fb_cookie: 1 dòng VIA (UID|Pass|2FA|Cookie... hoặc chuỗi cookie)
        Returns: True nếu Dola đã đăng nhập (có sessionid + passport API xác nhận)
        """
        self.last_error = ""
        self.last_fb_status = ""
        self.dola_user = None
        self._via = parse_via_fields(raw_fb_cookie)

        def progress(msg):
            log("FBLogin", msg)
            if on_progress:
                try:
                    on_progress(msg)
                except Exception:
                    pass

        # ─── BƯỚC 1: Inject Facebook cookies ───────────────────────
        progress("[1/5] Dang nap Facebook cookies tu chuoi VIA...")
        injected = await self.inject_fb_cookies(context, self._via.get("cookie") or raw_fb_cookie)
        if not injected and not self._via.get("password"):
            self.last_error = "VIA khong co cookie hop le (thieu c_user/xs) va khong co mat khau"
            progress(f"[X] {self.last_error}")
            return False

        # ─── BƯỚC 2: Kiểm tra Facebook ─────────────────────────────
        progress("[2/5] Kiem tra dang nhap Facebook...")
        status = await self.check_fb_status(page) if injected else "dead"
        if status != "live" and status != "checkpoint" and self._via.get("password"):
            if await self._fb_password_login(page):
                status = await self.check_fb_status(page)
        self.last_fb_status = status
        if status == "checkpoint":
            self.last_error = "Facebook bi checkpoint"
            progress(f"[X] {self.last_error}")
            return False
        if status == "dead":
            self.last_error = "Cookie Facebook da die (FB bat dang nhap lai)"
            progress(f"[X] {self.last_error}")
            return False
        if status == "unknown":
            progress("[!] Khong xac dinh duoc trang thai FB (mang cham?) — van thu tiep...")
        else:
            progress("[OK] Facebook dang nhap thanh cong!")

        # ─── BƯỚC 3: Mở Dola ngay lập tức ──────────────────────────
        progress("[3/5] Dang chuyen ngay qua Dola.com...")
        if not await self._open_dola(page):
            self.last_error = "Khong mo duoc dola.com"
            return False

        # ─── BƯỚC 4: Kiểm tra trạng thái Dola ───────────────────────
        progress("[4/5] Kiem tra trang thai Dola...")
        if await self._check_dola_logged_in(page):
            progress("[OK] Dola da dang nhap san!")
            return True

        # ─── BƯỚC 5: Đăng nhập Dola bằng Facebook (tối đa 2 lần) ────
        for attempt in (1, 2):
            if self._cancel:
                break
            if attempt == 2:
                progress("[...] Thu lai lan 2 (tai lai trang Dola)...")
                for p in list(context.pages):
                    if p is not page:
                        try:
                            await p.close()
                        except Exception:
                            pass
                if not await self._open_dola(page):
                    break
                if await self._check_dola_logged_in(page):
                    progress("[OK] Dola da dang nhap!")
                    return True

            progress(f"[5/5] Bam Dang nhap -> Facebook -> Xac nhan (lan {attempt})...")
            await self.click_fb_login_on_dola(page)
            if await self._confirm_dola_login(page):
                name = (self.dola_user or {}).get("screen_name") or (self.dola_user or {}).get("name") or ""
                progress(f"[OK] Dang nhap Dola thanh cong! User: {name}")
                return True
            # Lỗi chắc chắn (FB die / checkpoint) → không thử lại
            if self.last_error and ("checkpoint" in self.last_error or "dang nhap lai" in self.last_error
                                    or "2FA" in self.last_error):
                break

        if not self.last_error:
            self.last_error = "Khong the tu dong ket noi Dola qua Facebook"
        progress(f"[X] {self.last_error}")
        return False
