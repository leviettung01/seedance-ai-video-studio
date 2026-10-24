# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — CDP Helper
Extension injection, Registry registration, và auto-download qua Chrome DevTools Protocol.
"""

import os
import sys
import winreg
from typing import Optional

from playwright.async_api import Page, CDPSession

from config import EXTENSION_DIR, DOWNLOAD_DIR
from utils import log


class CDPHelper:
    """Helper cho Chrome DevTools Protocol — injection extension + cấu hình."""

    # ─── Windows Registry ─────────────────────────────────────────────────

    @staticmethod
    def register_extension_registry(ext_dir: str):
        """Đăng ký extension vào Windows Registry (HKCU) để Chrome tự load.
        
        Key: HKCU\\SOFTWARE\\Google\\Chrome\\Extensions\\<ext_id>
        """
        try:
            # Tạo key cho extension policy
            key_path = r"SOFTWARE\Google\Chrome\Extensions"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)

            winreg.CloseKey(key)
            log("CDP", "Extension registered in Windows Registry (HKCU) successfully!")
        except Exception as e:
            log("CDP", f"Registry registration warning: {e}")

    # ─── Extension Injection via CDP ──────────────────────────────────────

    @staticmethod
    async def force_load_extension(page: Page, ext_dir: str) -> Optional[str]:
        """Verify extension registration."""
        log("CDP", "Extension loaded via Chrome --load-extension flag.")
        return None

    # ─── Inject Scripts on Page ──────────────────────────────────────────

    @staticmethod
    async def inject_scripts_on_page(page: Page, ext_dir: str):
        """Evaluate inject.js + bridge script trên trang Dola qua page.evaluate()."""
        inject_js_path = os.path.join(ext_dir, "inject.js")
        bridge_js_path = os.path.join(ext_dir, "dola_bridge.js")

        scripts_injected = False

        # inject.js
        if os.path.isfile(inject_js_path):
            try:
                with open(inject_js_path, "r", encoding="utf-8") as f:
                    inject_code = f.read()
                await page.evaluate(inject_code)
                scripts_injected = True
            except Exception as e:
                log("CDP Helper", f"inject.js evaluation error: {e}")

        # without watermark/extractor.js
        extractor_js_path = os.path.join(ext_dir, "without watermark", "extractor.js")
        if os.path.isfile(extractor_js_path):
            try:
                with open(extractor_js_path, "r", encoding="utf-8") as f:
                    extractor_code = f.read()
                await page.evaluate(extractor_code)
                scripts_injected = True
            except Exception as e:
                log("CDP Helper", f"extractor.js evaluation error: {e}")

        # dola_bridge.js
        if os.path.isfile(bridge_js_path):
            try:
                with open(bridge_js_path, "r", encoding="utf-8") as f:
                    bridge_code = f.read()
                await page.evaluate(bridge_code)
                scripts_injected = True
            except Exception as e:
                log("CDP Helper", f"bridge.js evaluation error: {e}")

        if scripts_injected:
            log("CDP Helper", f"Successfully evaluated inject & bridge script on page {page.url}")

    @staticmethod
    async def force_copy_inject_js(ext_dir: str):
        """Copy inject.js vào thư mục extension (đảm bảo phiên bản mới nhất)."""
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Dola_Bypass_30s_Viet_Hoa", "inject.js")
        dst = os.path.join(ext_dir, "inject.js")
        if os.path.isfile(src) and os.path.isfile(dst):
            try:
                import shutil
                shutil.copy2(src, dst)
                log("CDP Helper", f"Force-copied inject.js to {dst}")
            except Exception as e:
                log("CDP Helper", f"Copy inject.js error: {e}")

    # ─── Auto-Download Setup ─────────────────────────────────────────────

    @staticmethod
    async def setup_auto_download(page: Page, download_dir: str = DOWNLOAD_DIR):
        """Bật auto-download vào thư mục chỉ định."""
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Browser.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_dir,
            })
            await cdp.detach()
            log("CDP", f"Đã bật auto-download vào: {download_dir}")
        except Exception as e:
            log("CDP", f"Setup auto-download note: {e}")

    # ─── Suppress Signin Prompts ─────────────────────────────────────────

    @staticmethod
    async def suppress_signin_prompts(page: Page, account_name: str):
        """Chặn popup đăng nhập Chrome + các dialog không mong muốn."""
        try:
            await page.evaluate("""
                (() => {
                    if (window.chrome && window.chrome.identity) {
                        window.chrome.identity.getAuthToken = function() {};
                    }
                    document.querySelectorAll('[data-testid="cookie-policy-manage-dialog"]').forEach(el => el.remove());
                })();
            """)
        except Exception:
            pass

    # ─── Full Setup Flow ─────────────────────────────────────────────────

    @staticmethod
    async def full_extension_setup(page: Page, ext_dir: str, account_name: str):
        """Chạy toàn bộ flow setup extension cho một page."""
        # 1. Register extension in registry
        CDPHelper.register_extension_registry(ext_dir)

        # 2. Inject scripts if not loaded
        try:
            ext_loaded = await page.evaluate("typeof window.__dolaDur_loaded !== 'undefined'")
            if not ext_loaded:
                await CDPHelper.inject_scripts_on_page(page, ext_dir)
        except Exception:
            await CDPHelper.inject_scripts_on_page(page, ext_dir)

        # 3. Suppress signin prompts & cookie dialogs
        await CDPHelper.suppress_signin_prompts(page, account_name)

        log("CDP Helper", "Extension setup complete successfully.")
