# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Browser Manager
Quản lý khởi chạy Chrome instances + kết nối Playwright qua CDP.
Hỗ trợ Cookie Session Pool: Chrome tạm + inject cookies (0 MB disk).
"""

import os
import asyncio
import shutil
import subprocess
import tempfile
from typing import Optional

import psutil
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

import json
from config import (
    CHROME_PATH, CHROME_DEBUG_PORT_START, CHROME_USER_DATA_BASE,
    CHROME_FLAGS, EXTENSION_DIR, DOLA_URL, OUTPUT_DIR,
)
from utils import log, log_info
from proxy_manager import get_bridge_manager


class BrowserManager:
    """Quản lý Chrome processes và Playwright CDP connections.
    
    Hỗ trợ 2 chế độ:
    1. Profile vĩnh viễn (cho login ban đầu)
    2. Temp profile + Cookie injection (cho tạo video — 0 MB disk)
    """

    def __init__(self):
        # account_name → {"process": subprocess.Popen, "port": int, "browser": Browser}
        self._sessions: dict[str, dict] = {}
        # worker_id → {"process", "port", "browser", "temp_dir", "account_name"}
        self._workers: dict[int, dict] = {}
        self._playwright = None
        self._port_counter = 0
        self.proxy_bridge_manager = get_bridge_manager()

    async def _ensure_playwright(self):
        """Đảm bảo Playwright instance đang chạy."""
        if self._playwright is None:
            pw = await async_playwright().start()
            self._playwright = pw
        return self._playwright

    def _get_port(self, account_name: str) -> int:
        """Lấy debug port cho account. Ưu tiên port của Chrome đang chạy, sau đó dùng hash cố định."""
        if account_name in self._sessions and self._sessions[account_name].get("port", 0) > 0:
            return self._sessions[account_name]["port"]

        # 1. Kiểm tra xem có Chrome nào đang mở cho account này không
        try:
            import psutil, re
            for p in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if "chrome" in (p.info["name"] or "").lower():
                        cmd = " ".join(p.info["cmdline"] or [])
                        if f"/{account_name}" in cmd or f"\\{account_name}" in cmd or f"={account_name}" in cmd:
                            if "--remote-debugging-port=" in cmd:
                                m = re.search(r'--remote-debugging-port=(\d+)', cmd)
                                if m:
                                    return int(m.group(1))
                except Exception:
                    pass
        except Exception:
            pass

        # 2. Port mặc định cho accounts đặc biệt
        accounts = ["fb01", "FB2", "fb3", "fb4", "gg1", "gg2", "gg3"]
        if account_name in accounts:
            return CHROME_DEBUG_PORT_START + accounts.index(account_name)

        # 3. Dùng zlib.crc32 để port luôn cố định và đồng nhất giữa các tiến trình Python
        import zlib
        return CHROME_DEBUG_PORT_START + (zlib.crc32(account_name.encode('utf-8')) % 50)

    def _get_worker_port(self, worker_id: int) -> int:
        """Lấy port worker từ 9350; tách khỏi profile cố định 9222–9271."""
        return 9350 + worker_id

    def _get_user_data_dir(self, account_name: str) -> str:
        """Tạo và trả về đường dẫn user-data-dir cho account."""
        path = os.path.join(CHROME_USER_DATA_BASE, account_name)
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def ensure_profile_preferences(user_data_dir: str, ext_id: str = "mikgdpblejoompnjdbmdpgicgikmblcn", download_dir: str = ""):
        """Cấu hình sẵn file Preferences của Chrome profile để:
        1. Ghim icon Extension lên thanh công cụ (pinned_extensions).
        2. Kích hoạt Developer Mode cho extensions (tránh cảnh báo/chặn).
        3. Thiết lập vị trí cửa sổ hợp lý, tắt bong bóng crash/restore.
        """
        try:
            default_dir = os.path.join(user_data_dir, "Default")
            os.makedirs(default_dir, exist_ok=True)
            pref_file = os.path.join(default_dir, "Preferences")
            pref_data = {}
            if os.path.isfile(pref_file):
                try:
                    with open(pref_file, "r", encoding="utf-8", errors="ignore") as f:
                        pref_data = json.load(f)
                except Exception:
                    pref_data = {}

            if not isinstance(pref_data, dict):
                pref_data = {}

            # 1. Pinned extensions & dev mode
            extensions = pref_data.setdefault("extensions", {})
            pinned = extensions.setdefault("pinned_extensions", [])
            if ext_id and ext_id not in pinned:
                pinned.append(ext_id)
            ui = extensions.setdefault("ui", {})
            ui["developer_mode"] = True

            # 2. Window placement
            browser = pref_data.setdefault("browser", {})
            browser["window_placement"] = {
                "bottom": 960, "left": 100, "right": 1380, "top": 80,
                "maximized": False, "work_area_bottom": 1080, "work_area_left": 0,
                "work_area_right": 1920, "work_area_top": 0
            }

            # 3. Clean exit
            profile = pref_data.setdefault("profile", {})
            profile["exit_type"] = "Normal"
            profile["exited_cleanly"] = True

            if download_dir:
                os.makedirs(download_dir, exist_ok=True)
                download = pref_data.setdefault("download", {})
                download["default_directory"] = os.path.abspath(download_dir)
                download["prompt_for_download"] = False

            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(pref_data, f, indent=2)
        except Exception:
            pass

    # ─── Temp Chrome (Cookie Session Pool) ─────────────────────────────────

    async def launch_temp_chrome(
        self,
        worker_id: int,
        proxy_url: Optional[str] = None,
        show_browser: bool = False,
        load_extension: bool = True,
    ) -> int:
        """Mở Chrome instance tạm (0 MB disk) cho 1 worker.
        
        Args:
            worker_id: ID worker (0-19, tối đa 20 workers)
            proxy_url: Proxy URL (http://ip:port hoặc http://user:pass@ip:port hoặc socks5://ip:port)
            show_browser: True = hiện cửa sổ Chrome xem trực tiếp, False = chạy ẩn / thu nhỏ
        
        Returns: debug port number
        """
        chrome_path = CHROME_PATH
        if not chrome_path or not os.path.isfile(chrome_path):
            raise FileNotFoundError("Không tìm thấy Chrome trên máy tính.")

        port = self._get_worker_port(worker_id)

        # Tạo thư mục tạm mới tinh 100% cho Chrome profile (đảm bảo không dính cookie/session cũ)
        temp_dir = tempfile.mkdtemp(prefix=f"seedance_worker_{worker_id}_")

        # Kill any existing process on this port
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "chrome" in (p.info["name"] or "").lower():
                    cmdline = " ".join(p.info["cmdline"] or [])
                    if f"--remote-debugging-port={port}" in cmdline:
                        p.kill()
            except Exception:
                pass

        # Cấu hình Preferences
        self.ensure_profile_preferences(temp_dir, download_dir=OUTPUT_DIR)

        # Build Chrome command
        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={temp_dir}",
            "--profile-directory=Default",
            "--lang=vi",
        ]

        # Load extension Dola_Bypass_30s (không dùng --disable-extensions-except)
        if load_extension and os.path.isdir(EXTENSION_DIR):
            ext_path = EXTENSION_DIR.replace("\\", "/")
            cmd.append(f"--load-extension={ext_path}")

        # Anti-detect flags
        cmd.extend(CHROME_FLAGS)

        # Proxy (hỗ trợ tự động Transparent Auth Bridge cho Tool Proxy VPN)
        bridge = None
        if proxy_url:
            chrome_proxy, bridge = await self.proxy_bridge_manager.prepare_chrome_proxy(
                proxy_url, session_key=f"worker_{worker_id}"
            )
            cmd.append(f"--proxy-server={chrome_proxy}")
            log("Worker", f"Worker #{worker_id} using proxy: {chrome_proxy} (target: {proxy_url})")

        # Window visibility
        if show_browser:
            # Sắp xếp các cửa sổ so le trên màn hình
            offset_x = 80 + (worker_id % 4) * 45
            offset_y = 60 + (worker_id % 4) * 35
            cmd.extend([
                f"--window-position={offset_x},{offset_y}",
                "--window-size=1280,860",
            ])
        else:
            # Minimized & off-screen (tiết kiệm màn hình)
            cmd.extend([
                "--window-position=-32000,-32000",
                "--window-size=1280,860",
                "--start-minimized",
            ])

        cmd.append("about:blank")

        # Launch
        from browser_capacity import reserve_browser, browser_started, release_reservation
        reserve_browser(temp_dir)
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            browser_started(temp_dir, process.pid)
        except Exception:
            release_reservation(temp_dir)
            raise

        self._workers[worker_id] = {
            "process": process,
            "port": port,
            "browser": None,
            "temp_dir": temp_dir,
            "account_name": None,
            "proxy": proxy_url,
            "proxy_bridge": bridge,
        }

        await asyncio.sleep(2)
        log("Worker", f"✅ Worker #{worker_id} Chrome launched on port {port} (temp dir: {temp_dir})")
        return port

    async def setup_extension_in_browser(
        self,
        browser: Browser,
        context: BrowserContext,
        open_popup_tab: bool = False,
    ) -> Optional[str]:
        """Đăng ký extension qua CDP và tiêm các script bypass vào mọi trang.
        
        Nếu open_popup_tab=True (khi mở Chrome tương tác), tự động mở tab
        Extension UI (chrome-extension://<id>/popup.html) để người dùng sử dụng ngay.
        """
        ext_id = None
        try:
            # 1. Thử nạp Unpacked Extension qua CDP (bắt buộc cho Chrome hiện đại)
            ext_loaded_via_cdp = False
            if os.path.isdir(EXTENSION_DIR):
                try:
                    client = await browser.new_browser_cdp_session()
                    ext_abs_path = os.path.abspath(EXTENSION_DIR)
                    res = await client.send("Extensions.loadUnpacked", {"path": ext_abs_path})
                    ext_id = res.get("id") or "mikgdpblejoompnjdbmdpgicgikmblcn"
                    log("CDP", f"✅ Extension loaded via CDP: {os.path.basename(EXTENSION_DIR)} (id={ext_id})")
                    ext_loaded_via_cdp = True
                except Exception as e:
                    log("CDP", f"Extension CDP load skipped (sẽ inject thủ công): {e}")

            # 2. Nếu mở interactive và có ext_id, kiểm tra và mở tab Extension UI nếu chưa có
            if open_popup_tab and ext_id:
                try:
                    popup_url = f"chrome-extension://{ext_id}/popup.html"
                    already_opened = any(popup_url in p.url for p in context.pages)
                    if not already_opened:
                        ext_page = await context.new_page()
                        await ext_page.goto(popup_url)
                        log("CDP", f"✅ Đã mở tab Extension Studio Pro: {popup_url}")
                except Exception as e:
                    log("CDP", f"Mở tab extension note: {e}")

            # 3. Mock chrome extension APIs (cho scripts extension chạy được trong MAIN world)
            if not ext_loaded_via_cdp:
                mock_apis_script = """
                (() => {
                    if (typeof chrome !== 'undefined' && chrome.storage) return; // Extension đã load
                    
                    // Mock chrome namespace
                    if (typeof chrome === 'undefined') window.chrome = {};
                    const c = window.chrome;
                    
                    // Mock chrome.storage.local
                    if (!c.storage) {
                        const _store = {};
                        c.storage = {
                            local: {
                                get: (keys, cb) => {
                                    const result = {};
                                    const keyList = Array.isArray(keys) ? keys : (typeof keys === 'string' ? [keys] : Object.keys(keys || {}));
                                    for (const k of keyList) result[k] = _store[k];
                                    if (cb) cb(result);
                                    return Promise.resolve(result);
                                },
                                set: (items, cb) => {
                                    Object.assign(_store, items);
                                    if (cb) cb();
                                    return Promise.resolve();
                                },
                                remove: (keys, cb) => {
                                    const keyList = Array.isArray(keys) ? keys : [keys];
                                    for (const k of keyList) delete _store[k];
                                    if (cb) cb();
                                    return Promise.resolve();
                                },
                                onChanged: { addListener: () => {} },
                            },
                            onChanged: { addListener: () => {} },
                        };
                    }
                    
                    // Mock chrome.runtime
                    if (!c.runtime) {
                        c.runtime = {
                            id: 'seedance-mock-extension',
                            lastError: null,
                            getURL: (path) => path,
                            sendMessage: (msg, cb) => { if (cb) cb({}); },
                            onMessage: { 
                                addListener: () => {}, 
                                removeListener: () => {},
                                hasListeners: () => false,
                            },
                            connect: () => ({
                                onMessage: { addListener: () => {} },
                                onDisconnect: { addListener: () => {} },
                                postMessage: () => {},
                            }),
                        };
                    }
                    
                    // Mock chrome.tabs
                    if (!c.tabs) {
                        c.tabs = {
                            query: (q, cb) => { if (cb) cb([]); },
                            sendMessage: (id, msg, cb) => { if (cb) cb({}); },
                        };
                    }
                    
                    // Mock chrome.downloads
                    if (!c.downloads) {
                        c.downloads = {
                            download: (opts, cb) => { if (cb) cb(0); },
                        };
                    }
                    
                    console.log('[Seedance] Chrome extension APIs mocked for injection mode');
                })();
                """
                try:
                    await context.add_init_script(mock_apis_script)
                    log("CDP", "✅ Chrome extension APIs mocked for script injection")
                except Exception as e:
                    log("CDP", f"Mock APIs warning: {e}")

            # 3. Inject extension scripts vào context (chạy tại document_start)
            if os.path.isdir(EXTENSION_DIR):
                scripts_to_add = [
                    os.path.join(EXTENSION_DIR, "image-attachment-main.js"),
                    os.path.join(EXTENSION_DIR, "without watermark", "extractor.js"),
                    os.path.join(EXTENSION_DIR, "inject.js"),
                    os.path.join(EXTENSION_DIR, "site-polish.js"),
                ]
                for sp in scripts_to_add:
                    if os.path.isfile(sp):
                        try:
                            with open(sp, "r", encoding="utf-8") as f:
                                code = f.read()
                            await context.add_init_script(code)
                        except Exception as e:
                            log("CDP", f"Init script warning ({os.path.basename(sp)}): {e}")

                # 4. Inject dock-polish.css qua init script
                css_path = os.path.join(EXTENSION_DIR, "dock-polish.css")
                if os.path.isfile(css_path):
                    try:
                        with open(css_path, "r", encoding="utf-8") as f:
                            css_content = f.read()
                        escaped_css = json.dumps(css_content)
                        css_script = f"""
                        (() => {{
                            try {{
                                const injectCss = () => {{
                                    if (document.getElementById('dola-dock-polish-css')) return;
                                    const style = document.createElement('style');
                                    style.id = 'dola-dock-polish-css';
                                    style.textContent = {escaped_css};
                                    (document.head || document.documentElement).appendChild(style);
                                }};
                                injectCss();
                                if (document.readyState === 'loading') {{
                                    document.addEventListener('DOMContentLoaded', injectCss);
                                }}
                            }} catch(e) {{}}
                        }})();
                        """
                        await context.add_init_script(css_script)
                    except Exception as e:
                        log("CDP", f"CSS init script warning: {e}")
        except Exception as e:
            log("CDP", f"Lỗi setup extension: {e}")
        return ext_id

    async def connect_worker(self, worker_id: int, setup_extension: bool = True) -> Optional[Browser]:
        """Kết nối Playwright tới Chrome worker qua CDP.

        setup_extension=False: KHÔNG tiêm script bypass Dola (inject.js...) vào context.
        Dùng cho luồng đăng nhập VIA FB — các script này không giới hạn hostname nên
        sẽ chạy cả trên popup OAuth facebook.com và có thể làm hỏng luồng đăng nhập.
        """
        worker = self._workers.get(worker_id)
        if not worker:
            return None

        port = worker["port"]
        pw = await self._ensure_playwright()

        for attempt in range(6):
            try:
                browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                worker["browser"] = browser
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                if setup_extension:
                    await self.setup_extension_in_browser(browser, context)
                return browser
            except Exception as e:
                if attempt < 5:
                    await asyncio.sleep(1.5)
                else:
                    log_info(f"Worker #{worker_id}: Không kết nối được CDP port {port}: {e}")
                    return None

    async def get_worker_page(self, worker_id: int) -> Optional[Page]:
        """Lấy page của worker."""
        worker = self._workers.get(worker_id)
        if not worker or not worker.get("browser"):
            return None

        browser = worker["browser"]
        contexts = browser.contexts
        if not contexts:
            return None

        pages = contexts[0].pages
        page = pages[0] if pages else await contexts[0].new_page()

        # Đảm bảo style CSS luôn có mặt trên page
        css_path = os.path.join(EXTENSION_DIR, "dock-polish.css")
        if os.path.isfile(css_path):
            try:
                with open(css_path, "r", encoding="utf-8") as f:
                    css_content = f.read()
                await page.add_style_tag(content=css_content)
            except Exception:
                pass
        return page

    async def get_worker_context(self, worker_id: int) -> Optional[BrowserContext]:
        """Lấy BrowserContext của worker."""
        worker = self._workers.get(worker_id)
        if not worker or not worker.get("browser"):
            return None
        contexts = worker["browser"].contexts
        return contexts[0] if contexts else None

    async def inject_session_to_worker(self, worker_id: int, account_name: str) -> bool:
        """Nạp Dola session cookies vào Chrome worker từ SessionStore.
        
        Returns: True nếu thành công và user đã login
        """
        from session_store import SessionStore
        ss = SessionStore()

        if not ss.has_session(account_name):
            log("Worker", f"❌ Worker #{worker_id}: Không có session cho '{account_name}'")
            return False

        context = await self.get_worker_context(worker_id)
        page = await self.get_worker_page(worker_id)
        if not context or not page:
            return False

        success = await ss.inject_to_browser(context, page, account_name)
        if success:
            self._workers[worker_id]["account_name"] = account_name
            log("Worker", f"✅ Worker #{worker_id}: Session '{account_name}' injected successfully!")
        return success

    async def cleanup_worker(self, worker_id: int):
        """Đóng Chrome worker + xóa sạch temp dir (0 MB disk)."""
        worker = self._workers.get(worker_id)
        if not worker:
            return

        # Disconnect Playwright
        browser = worker.get("browser")
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

        # Kill Chrome process
        process = worker.get("process")
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        # Xóa sạch temp dir
        temp_dir = worker.get("temp_dir")
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                log("Worker", f"🧹 Worker #{worker_id}: Cleaned up temp dir ({temp_dir})")
            except Exception:
                pass

        # Stop proxy bridge if any
        bridge = worker.get("proxy_bridge")
        if bridge:
            try:
                await bridge.stop()
            except Exception:
                pass

        del self._workers[worker_id]

    async def cleanup_all_workers(self):
        """Đóng tất cả workers."""
        for wid in list(self._workers.keys()):
            await self.cleanup_worker(wid)
        await self.proxy_bridge_manager.stop_all()

    def is_worker_running(self, worker_id: int) -> bool:
        """Kiểm tra worker có đang chạy không."""
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        process = worker.get("process")
        if process:
            return process.poll() is None
        return worker.get("browser") is not None

    # ─── Launch Chrome Interactive (Manual / Cookie Login) ────────────────

    async def launch_chrome_interactive(
        self,
        account_name: str,
        proxy_url: Optional[str] = None,
        start_url: str = DOLA_URL,
        fb_cookies_str: str = "",
    ) -> int:
        """Mở Chrome trực tiếp ở chế độ tương tác kèm Extension để người dùng nạp Cookie FB VIA và login Dola."""
        chrome_path = CHROME_PATH
        if not chrome_path or not os.path.isfile(chrome_path):
            raise FileNotFoundError("Không tìm thấy Chrome trên máy tính.")

        user_data_dir = self._get_user_data_dir(account_name)
        port = self._get_port(account_name)

        # 1. Cấu hình Preferences: ghim icon Extension lên toolbar, bật Developer mode, chống crash popup
        self.ensure_profile_preferences(user_data_dir)

        # 2. Build Chrome command
        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={user_data_dir}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            "--lang=vi",
            "--window-position=100,80",
            "--window-size=1280,900",
        ]
        cmd.extend(CHROME_FLAGS)

        # Load extension Dola_Bypass_30s (không dùng --disable-extensions-except)
        if os.path.isdir(EXTENSION_DIR):
            ext_path = EXTENSION_DIR.replace("\\", "/")
            cmd.append(f"--load-extension={ext_path}")

        bridge = None
        if proxy_url:
            chrome_proxy, bridge = await self.proxy_bridge_manager.prepare_chrome_proxy(
                proxy_url, session_key=f"account_{account_name}"
            )
            cmd.append(f"--proxy-server={chrome_proxy}")
            log_info(f"[Chrome] Using proxy: {chrome_proxy} for account '{account_name}'")

        cmd.append(DOLA_URL)

        # Clean up any existing process for this account
        if account_name in self._sessions:
            await self.close_chrome(account_name)

        log_info(f"[Chrome] Opening profile '{account_name}' with Extension + Dola...")

        process = subprocess.Popen(cmd)

        self._sessions[account_name] = {
            "process": process,
            "port": port,
            "browser": None,
            "proxy": proxy_url,
            "proxy_bridge": bridge,
            "minimized": False,
        }

        # Tự động nạp Extension qua CDP ngay sau khi Chrome mở, mở tab Extension UI, nạp cookies
        async def _setup_interactive():
            await asyncio.sleep(2.0)
            try:
                pw = await self._ensure_playwright()
                browser = None
                for attempt in range(8):
                    try:
                        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                        break
                    except Exception:
                        await asyncio.sleep(1.0)
                if not browser:
                    return

                if account_name in self._sessions:
                    self._sessions[account_name]["browser"] = browser
                context = browser.contexts[0] if browser.contexts else await browser.new_context()

                # Nạp extension qua CDP và mở tab Extension UI popup.html
                ext_id = await self.setup_extension_in_browser(browser, context, open_popup_tab=True)
                if ext_id:
                    log_info(f"[Chrome] ✅ Extension Studio Pro '{ext_id}' loaded & tab opened for '{account_name}'")

                # Nạp FB cookies nếu có
                if fb_cookies_str:
                    await self.inject_facebook_cookies(account_name, fb_cookies_str)

                # Nạp Dola session nếu đã lưu
                try:
                    from session_store import SessionStore
                    ss = SessionStore()
                    if ss.has_session(account_name):
                        dola_page = None
                        for p in context.pages:
                            if "dola.com" in p.url or "doubao.com" in p.url:
                                dola_page = p
                                break
                        if not dola_page:
                            dola_page = context.pages[0] if context.pages else await context.new_page()
                        await ss.inject_to_browser(context, dola_page, account_name)
                        log_info(f"[Chrome] ✅ Injected saved Dola session for '{account_name}'")
                except Exception as e:
                    log_info(f"[Chrome] Session injection note: {e}")

            except Exception as e:
                log_info(f"Setup interactive CDP note: {e}")

        asyncio.create_task(_setup_interactive())
        return process.pid

    async def inject_facebook_cookies(self, account_name: str, cookies_raw: str) -> int:
        """Nạp trực tiếp Cookie Facebook VIA vào Chrome profile qua CDP/Playwright."""
        from account_manager import parse_via_cookie_string
        cookies_list = parse_via_cookie_string(cookies_raw)
        if not cookies_list:
            log_info(f"⚠️ Không tìm thấy cookie hợp lệ trong chuỗi dán cho {account_name}")
            return 0

        pw = await self._ensure_playwright()
        port = self._get_port(account_name)

        try:
            browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            
            # Format cookies cho Playwright
            pw_cookies = []
            for c in cookies_list:
                pw_cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".facebook.com"),
                    "path": c.get("path", "/"),
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", True),
                    "sameSite": "None" if c.get("secure") else "Lax"
                })

            await context.add_cookies(pw_cookies)
            log_info(f"✅ Đã nạp thành công {len(pw_cookies)} Cookie Facebook vào profile '{account_name}'!")
            
            # Refresh trang facebook nếu đang mở
            for page in context.pages:
                if "facebook.com" in page.url:
                    try:
                        await page.reload(wait_until="domcontentloaded")
                    except Exception:
                        pass
            return len(pw_cookies)
        except Exception as e:
            log_info(f"⚠️ Lỗi nạp Cookie qua CDP cho '{account_name}': {e}")
            return 0

    # ─── Launch Chrome ────────────────────────────────────────────────────

    async def launch_chrome(
        self,
        account_name: str,
        proxy_url: Optional[str] = None,
        start_url: str = DOLA_URL,
        minimized: bool = True,
    ) -> int:
        """Khởi chạy Chrome process riêng với extension + proxy.
        
        Returns: debug port number.
        """
        chrome_path = CHROME_PATH
        if not chrome_path or not os.path.isfile(chrome_path):
            raise FileNotFoundError(
                f"Không tìm thấy Chrome. Hãy cài đặt hoặc cấu hình CHROME_PATH trong config.py"
            )

        port = self._get_port(account_name)
        user_data_dir = self._get_user_data_dir(account_name)

        # Reset window placement in Preferences nếu mở visible
        pref_file = os.path.join(user_data_dir, "Default", "Preferences")
        if os.path.isfile(pref_file):
            try:
                import json
                with open(pref_file, "r", encoding="utf-8", errors="ignore") as f:
                    pref_data = json.load(f)
                if "browser" in pref_data and "window_placement" in pref_data["browser"]:
                    if not minimized:
                        pref_data["browser"]["window_placement"] = {
                            "bottom": 960, "left": 100, "right": 1380, "top": 80,
                            "maximized": False, "work_area_bottom": 1080, "work_area_left": 0,
                            "work_area_right": 1920, "work_area_top": 0
                        }
                    with open(pref_file, "w", encoding="utf-8") as f:
                        json.dump(pref_data, f)
            except Exception:
                pass

        self.ensure_profile_preferences(user_data_dir)

        # Build command
        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={user_data_dir}",
            "--profile-directory=Default",
            "--lang=en",
        ]

        # Load extension Dola_Bypass_30s (không dùng --disable-extensions-except)
        if os.path.isdir(EXTENSION_DIR):
            ext_path = EXTENSION_DIR.replace("\\", "/")
            cmd.append(f"--load-extension={ext_path}")

        # Anti-detect flags
        cmd.extend(CHROME_FLAGS)

        # Proxy
        bridge = None
        if proxy_url:
            chrome_proxy, bridge = await self.proxy_bridge_manager.prepare_chrome_proxy(
                proxy_url, session_key=f"account_{account_name}"
            )
            cmd.append(f"--proxy-server={chrome_proxy}")
            log("Proxy", f"Chrome launched with proxy: --proxy-server={chrome_proxy} (target: {proxy_url})")

        # Window position & size
        if minimized:
            cmd.extend([
                "--window-position=-32000,-32000",
                "--window-size=1280,860",
                "--start-minimized",
            ])
        else:
            cmd.extend([
                "--window-position=80,80",
                "--window-size=1280,900",
            ])

        # Start URL
        cmd.append(start_url)

        # Clean up any dead / orphan Chrome processes using this port or user_data_dir
        if account_name in self._sessions:
            await self.close_chrome(account_name)

        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "chrome" in (p.info["name"] or "").lower():
                    cmdline = " ".join(p.info["cmdline"] or [])
                    if f"--remote-debugging-port={port}" in cmdline or user_data_dir in cmdline:
                        p.kill()
            except Exception:
                pass

        for lock in ["SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"]:
            lp = os.path.join(user_data_dir, lock)
            if os.path.exists(lp):
                try:
                    os.remove(lp)
                except Exception:
                    pass

        # Launch Chrome without suppressing GUI window
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._sessions[account_name] = {
            "process": process,
            "port": port,
            "browser": None,
            "proxy": proxy_url,
            "proxy_bridge": bridge,
            "minimized": minimized,
        }

        # Chờ Chrome khởi động
        await asyncio.sleep(2)
        return port

    # ─── Connect Playwright via CDP ───────────────────────────────────────

    async def connect_playwright(self, account_name: str) -> Optional[Browser]:
        """Kết nối Playwright tới Chrome đang chạy qua CDP (kèm retry)."""
        session = self._sessions.get(account_name)
        if not session:
            log_info(f"Không tìm thấy session cho account: {account_name}")
            return None

        port = session["port"]
        minimized = session.get("minimized", True)
        pw = await self._ensure_playwright()

        for attempt in range(6):
            try:
                browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                session["browser"] = browser

                # Nếu mở visible (không minimized), đưa cửa sổ về toạ độ hiển thị chính diện
                if not minimized:
                    try:
                        cdp = await browser.new_browser_cdp_session()
                        targets = await cdp.send("Target.getTargets")
                        for t in targets.get("targetInfos", []):
                            if t.get("type") == "page":
                                target_id = t.get("targetId")
                                win_info = await cdp.send("Browser.getWindowForTarget", {"targetId": target_id})
                                window_id = win_info.get("windowId")
                                if window_id:
                                    await cdp.send("Browser.setWindowBounds", {
                                        "windowId": window_id,
                                        "bounds": {
                                            "left": 80,
                                            "top": 80,
                                            "width": 1280,
                                            "height": 900,
                                            "windowState": "normal"
                                        }
                                    })
                                    break
                        await cdp.detach()
                    except Exception as e:
                        log("CDP", f"Window bounds note: {e}")

                return browser
            except Exception as e:
                if attempt < 5:
                    await asyncio.sleep(1.5)
                else:
                    log_info(f"Lỗi kết nối Playwright CDP port {port} (đã thử 6 lần): {e}")
                    return None

    async def reuse_existing_session(self, account_name: str, port: int) -> Optional[Browser]:
        """Kết nối lại tới Chrome đang mở sẵn (không launch mới)."""
        log("CDP", f"Phát hiện Chrome Dola đang mở ở port {port} ({account_name}), kết nối trực tiếp sử dụng lại session đăng nhập!")

        pw = await self._ensure_playwright()
        try:
            browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            self._sessions[account_name] = {
                "process": None,
                "port": port,
                "browser": browser,
                "proxy": None,
            }
            return browser
        except Exception as e:
            log_info(f"Không thể kết nối Chrome cũ: {e}")
            return None

    # ─── Get Page ─────────────────────────────────────────────────────────

    async def get_page(self, account_name: str) -> Optional[Page]:
        """Lấy page chính (tab đầu tiên) của browser context."""
        session = self._sessions.get(account_name)
        if not session or not session.get("browser"):
            return None

        browser = session["browser"]
        contexts = browser.contexts
        if not contexts:
            return None

        pages = contexts[0].pages
        if pages:
            return pages[0]

        # Tạo page mới nếu chưa có
        return await contexts[0].new_page()

    # ─── Navigate ─────────────────────────────────────────────────────────

    async def navigate_to_dola(self, page: Page):
        """Chuyển hướng tới trang Dola AI chat."""
        log_info("Đang chuyển hướng tới Dola AI chat...")
        try:
            await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log_info(f"Navigation error: {e}")
            # Thử lại
            await asyncio.sleep(2)
            await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)

    # ─── Close Chrome ─────────────────────────────────────────────────────

    async def close_chrome(self, account_name: str):
        """Đóng Chrome process cho account."""
        session = self._sessions.get(account_name)
        if not session:
            return

        # Disconnect Playwright
        browser = session.get("browser")
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

        # Kill Chrome process
        process = session.get("process")
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        # Stop proxy bridge if any
        bridge = session.get("proxy_bridge")
        if bridge:
            try:
                await bridge.stop()
            except Exception:
                pass

        del self._sessions[account_name]
        log_info(f"📡 Đã ngắt kết nối Playwright (Chrome vẫn sống).")

    async def force_kill_chrome(self, account_name: str):
        """Force kill Chrome process."""
        session = self._sessions.get(account_name)
        if not session:
            return

        port = session.get("port")
        process = session.get("process")

        # Kill process tree
        if process and process.pid:
            try:
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except Exception:
                pass

        # Cleanup
        if account_name in self._sessions:
            del self._sessions[account_name]

    def is_chrome_running(self, account_name: str) -> bool:
        """Kiểm tra Chrome có đang chạy cho account không."""
        session = self._sessions.get(account_name)
        if not session:
            return False
        process = session.get("process")
        if process:
            return process.poll() is None
        return session.get("browser") is not None

    # ─── Cleanup ──────────────────────────────────────────────────────────

    async def cleanup_all(self):
        """Đóng tất cả sessions."""
        for name in list(self._sessions.keys()):
            await self.close_chrome(name)

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
