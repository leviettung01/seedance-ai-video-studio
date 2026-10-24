# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Dola Automation Engine
Tự động hóa toàn bộ quy trình tạo video trên Dola AI chat.
Module cốt lõi: login, chọn model, ép duration, nhập prompt, chờ kết quả.
"""

import asyncio
import json
import os
import re
import time
from typing import Optional

from playwright.async_api import Page

from config import (
    DOLA_URL, VIDEO_WAIT_TIMEOUT, VIDEO_POLL_INTERVAL,
    EXTENSION_REACTIVATE_INTERVAL, EXTENSION_DIR,
)
from utils import log_info, log, truncate_text


class DolaAutomation:
    """Engine tự động hóa Dola AI — điều khiển toàn bộ flow tạo video."""

    def __init__(self):
        self._cancel_flag = False

    def cancel(self):
        """Đặt cờ hủy — vòng lặp polling sẽ dừng."""
        self._cancel_flag = True

    def reset(self):
        """Reset cờ hủy + CDP state."""
        self._cancel_flag = False
        self._cdp_fetch_enabled = False
        self._cdp_session = None
        self._bypass_active = False

    # ─── Dismiss Modals / Cookie Overlays ──────────────────────────────

    async def dismiss_modals_and_overlays(self, page: Page):
        """Đóng tất cả modal, popup cookie, overlay chặn pointer events.
        
        Dola dùng Semi UI → popup cookie có class 'semi-modal-wrap' che phủ toàn trang.
        Phải xóa bỏ qua JS vì Playwright không thể click qua overlay.
        """
        try:
            removed = await page.evaluate("""
                (() => {
                    let count = 0;
                    // Xóa tất cả semi-modal overlay (cookie consent, etc.)
                    document.querySelectorAll('.semi-modal-wrap, .semi-portal, .semi-modal-mask').forEach(el => {
                        el.remove();
                        count++;
                    });
                    // Xóa overlay có role="none" chặn pointer
                    document.querySelectorAll('div[role="none"]').forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' || style.position === 'absolute') {
                            el.remove();
                            count++;
                        }
                    });
                    // Xóa các cookie banner thông thường
                    document.querySelectorAll('[data-testid*="cookie"], [class*="cookie-banner"], [class*="consent"]').forEach(el => {
                        el.remove();
                        count++;
                    });
                    // Click nút Accept/OK nếu thấy
                    document.querySelectorAll('button').forEach(btn => {
                        const txt = btn.innerText.toLowerCase();
                        if (txt.includes('accept') || txt.includes('ok') || txt.includes('agree') || txt.includes('got it') || txt.includes('đồng ý')) {
                            btn.click();
                            count++;
                        }
                    });
                    return count;
                })();
            """)
            if removed > 0:
                log_info(f"🧹 Đã dọn dẹp {removed} modal/overlay chặn tương tác.")
                await asyncio.sleep(0.5)
        except Exception as e:
            log_info(f"⚠️ dismiss_modals error: {e}")

    # ─── Login Check ──────────────────────────────────────────────────────

    async def check_login_status(self, page: Page) -> str:
        """Kiểm tra trạng thái đăng nhập trên Dola.
        
        Returns: "logged_in" | "not_logged_in" | "unknown"
        """
        log_info("🔒 Kiểm tra trạng thái đăng nhập...")

        # Dọn modal/overlay trước khi kiểm tra
        await self.dismiss_modals_and_overlays(page)

        try:
            # 1. Kiểm tra xem có nút / text "Log In" hoặc "Sign in" (chưa đăng nhập)
            is_guest = await page.evaluate("""
                (() => {
                    // Kiểm tra các nút / link đăng nhập
                    const buttons = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
                    for (const b of buttons) {
                        const txt = (b.innerText || '').trim().toLowerCase();
                        if (txt === 'log in' || txt === 'sign in' || txt === 'đăng nhập') {
                            return true;
                        }
                    }
                    // Kiểm tra text trên toàn trang
                    const bodyText = document.body.innerText || '';
                    if (bodyText.includes('Video and image generation is not available for guests') ||
                        bodyText.includes('Log in to start creating')) {
                        return true;
                    }
                    return false;
                })()
            """)

            if is_guest:
                log_info("⚠️ Phát hiện tài khoản CHƯA ĐĂNG NHẬP (Dola đang ở chế độ Khách/Guest, có nút 'Log In')!")
                return "not_logged_in"

            # 2. Tìm khung chat Dola — nếu có và không có nút Log In nghĩa là đã đăng nhập
            chat_indicators = [
                'textarea', 
                '[contenteditable="true"]',
                '[data-testid="chat-input"]',
                'div[class*="chat"]',
                'div[class*="ChatInput"]',
                'div[class*="message-input"]',
            ]
            for selector in chat_indicators:
                try:
                    el = await page.wait_for_selector(selector, timeout=3000)
                    if el:
                        log_info("✅ Xác nhận đã đăng nhập thành công (Khung chat Dola đang mở sẵn)!")
                        return "logged_in"
                except Exception:
                    continue

            return "unknown"
        except Exception as e:
            log_info(f"⚠️ Lỗi kiểm tra đăng nhập: {e}")
            return "unknown"

    # ─── Extension Bypass Control ─────────────────────────────────────────

    async def activate_extension_bypass(self, page: Page, duration: int = 30, model: str = "2.5", aspect_ratio: str = "9:16"):
        """Kích hoạt Extension ép giây qua JavaScript evaluation và Event Dispatching.
        
        Gửi sự kiện PURZA_UPDATE_SETTINGS + SET_RATIO_OVERRIDE + DOLA_SET_SEEDANCE_CONFIG chuẩn như Extension.
        Đồng thời kích hoạt CDP Fetch Interceptor để đảm bảo 100% request mạng POST đều có duration 30s.
        """
        try:
            model_name = "Dreamina Seedance 2.5" if str(model) in ["2.5", "Dreamina Seedance 2.5"] else f"Seedance {model}"
            
            # 0. Đảm bảo các script extension và style được inject trên page
            from config import EXTENSION_DIR
            if os.path.isdir(EXTENSION_DIR):
                # Inject dock-polish.css
                css_path = os.path.join(EXTENSION_DIR, "dock-polish.css")
                if os.path.isfile(css_path):
                    try:
                        with open(css_path, "r", encoding="utf-8") as f:
                            css_code = f.read()
                        await page.add_style_tag(content=css_code)
                    except Exception:
                        pass

                # Inject inject.js, extractor.js, site-polish.js nếu chưa có
                has_injected = await page.evaluate("() => typeof window.__setDolaBypass === 'function'")
                if not has_injected:
                    for sfile in [os.path.join("without watermark", "extractor.js"), "inject.js", "site-polish.js"]:
                        sp = os.path.join(EXTENSION_DIR, sfile)
                        if os.path.isfile(sp):
                            try:
                                with open(sp, "r", encoding="utf-8") as f:
                                    code = f.read()
                                await page.evaluate(code)
                            except Exception:
                                pass

            # 1. Set localStorage keys + dispatch extension sync events
            await page.evaluate(f"""
                (() => {{
                    try {{
                        localStorage.setItem('__dolaDurBypass', '1');
                        localStorage.setItem('__dolaTargetDur', '{duration}');
                        localStorage.setItem('__dolaDur31', '1');
                        localStorage.setItem('__dolaDur15', '1');
                    }} catch(e) {{}}
                    
                    // Dispatch các sự kiện chuẩn của extension
                    try {{
                        window.postMessage({{ type: 'PURZA_UPDATE_SETTINGS', ratio: '{aspect_ratio}', duration: {duration}, model: '{model_name}' }}, '*');
                        window.postMessage({{ type: 'SET_RATIO_OVERRIDE', ratio: '{aspect_ratio}', duration: {duration}, model: '{model_name}' }}, '*');
                        window.dispatchEvent(new CustomEvent('DOLA_SET_SEEDANCE_CONFIG', {{ detail: {{ duration: {duration}, enabled: true }} }}));
                    }} catch(e) {{}}

                    // Kích hoạt bypass chính (nếu extension đã load)
                    if (typeof window.__setDolaBypass === 'function') {{
                        window.__setDolaBypass(true, {duration});
                    }}
                }})();
            """)
            
            # 2. Cài đặt CDP Fetch Interceptor nếu chưa cài
            if not getattr(self, '_cdp_fetch_enabled', False):
                await self._inject_manual_fetch_bypass(page, duration, model, aspect_ratio)
                self._cdp_fetch_enabled = True
                log_info(f"✅ Đã kích hoạt Bypass: Duration={duration}s, Model={model_name}, Ratio={aspect_ratio}")
            else:
                self._bypass_duration = duration
                self._bypass_model = model
                self._bypass_ratio = aspect_ratio

            # 3. Cài đặt window.fetch monkey-patch (lớp bypass thứ 2, MAIN world)
            await self._inject_fetch_bypass(page, duration, model, aspect_ratio)
        except Exception as e:
            log_info(f"⚠️ Lỗi kích hoạt Extension bypass: {e}")

    async def _inject_fetch_bypass(self, page: Page, duration: int = 30, model: str = "2.5", aspect_ratio: str = "9:16"):
        """Monkey-patch window.fetch trực tiếp trên page (MAIN world).
        
        Lớp bypass thứ 2 bên cạnh CDP Fetch Interceptor.
        Đảm bảo mọi POST request tới Dola API đều có duration = target.
        """
        try:
            await page.evaluate(f"""
                (() => {{
                    // Chỉ patch 1 lần, nhưng cập nhật config mỗi lần gọi
                    window.__dolaBypassConfig = {{
                        duration: {duration},
                        model: '{model}',
                        ratio: '{aspect_ratio}'
                    }};
                    
                    if (window.__dolaFetchPatched) return;
                    window.__dolaFetchPatched = true;
                    
                    const origFetch = window.fetch;
                    window.fetch = async function(input, init) {{
                        try {{
                            if (init && init.method === 'POST' && init.body && typeof init.body === 'string') {{
                                const url = typeof input === 'string' ? input : (input?.url || '');
                                const isTarget = ['/chat/completion', '/im/message', '/im/chain']
                                    .some(p => url.includes(p));
                                const isSkip = ['/upload', '/heartbeat', '/ping', '/config', '/setting', '/notification', '/history', '/list', '/search', '/recent_conv', '/rate_limit']
                                    .some(p => url.includes(p));
                                
                                if (isTarget && !isSkip && init.body.includes('duration')) {{
                                    const cfg = window.__dolaBypassConfig || {{ duration: {duration} }};
                                    const dur = cfg.duration;
                                    
                                    // Replace duration trong JSON body (plain + escaped)
                                    init.body = init.body
                                        .replace(/"duration"\s*:\s*\d+/g, '"duration":' + dur)
                                        .replace(/"video_duration"\s*:\s*\d+/g, '"video_duration":' + dur)
                                        .replace(/\\\\"duration\\\\"\s*:\s*\d+/g, '\\\\"duration\\\\":' + dur)
                                        .replace(/\\\\"video_duration\\\\"\s*:\s*\d+/g, '\\\\"video_duration\\\\":' + dur);
                                    
                                    console.log('[Dola Bypass] fetch intercepted: duration=' + dur + ' url=' + url.substring(0, 80));
                                }}
                            }}
                        }} catch(e) {{}}
                        return origFetch.apply(this, arguments);
                    }};
                    
                    console.log('[Dola Bypass] window.fetch patched successfully');
                }})();
            """)
        except Exception as e:
            log_info(f"⚠️ Fetch bypass inject warning: {e}")

    async def _inject_manual_fetch_bypass(self, page: Page, duration: int = 30, model: str = "2.5", aspect_ratio: str = "9:16"):
        """Intercept Dola API requests via Chrome DevTools Protocol (CDP) Fetch domain."""
        import re as _re
        
        self._bypass_duration = duration
        self._bypass_model = model
        self._bypass_ratio = aspect_ratio
        self._bypass_active = True
        self._captured_video_links = []
        
        try:
            # 1. Set localStorage keys
            await page.evaluate(f"""
                (() => {{
                    try {{
                        localStorage.setItem('__dolaDurBypass', '1');
                        localStorage.setItem('__dolaTargetDur', '{duration}');
                        localStorage.setItem('__dolaDur31', '1');
                        localStorage.setItem('__dolaDur15', '1');
                    }} catch(e) {{}}
                }})();
            """)
            
            # 2. Tạo CDP session
            cdp = await page.context.new_cdp_session(page)
            self._cdp_session = cdp
            
            # 3. Event handler cho Fetch.requestPaused
            async def on_request_paused(params):
                request_id = params.get("requestId", "")
                url = params.get("request", {}).get("url", "")
                method = params.get("request", {}).get("method", "")
                post_data = params.get("request", {}).get("postData", "")
                
                if method != "POST" or not post_data:
                    try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
                    except Exception: pass
                    return
                
                is_target = any(p in url for p in ['/chat/completion', '/im/message', '/im/chain'])
                is_skip = any(p in url for p in ['/recent_conv', '/history', '/list', '/search', '/config', '/setting', '/notification', '/upload', '/rate_limit', '/heartbeat', '/ping'])
                
                if not is_target or is_skip or not self._bypass_active:
                    try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
                    except Exception: pass
                    return
                
                if 'duration' not in post_data and 'ability_param' not in post_data:
                    try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
                    except Exception: pass
                    return
                
                modified_body = post_data
                
                # 1. Escaped JSON duration trong ability_param: \"duration\": 10 -> \"duration\": 31
                modified_body = _re.sub(r'(\\"duration\\")\s*:\s*(\d+)', rf'\g<1>:{duration}', modified_body)
                # 2. Escaped JSON video_duration: \"video_duration\": 10 -> \"video_duration\": 31
                modified_body = _re.sub(r'(\\"video_duration\\")\s*:\s*(\d+)', rf'\g<1>:{duration}', modified_body)
                # 3. Plain JSON duration: "duration": 10 -> "duration": 31
                modified_body = _re.sub(r'"duration"\s*:\s*(\d+)', rf'"duration":{duration}', modified_body)
                # 4. Plain JSON video_duration: "video_duration": 10 -> "video_duration": 31
                modified_body = _re.sub(r'"video_duration"\s*:\s*(\d+)', rf'"video_duration":{duration}', modified_body)
                
                # Ép Model theo yêu cầu
                if model == "2.5" or duration >= 30:
                    modified_body = _re.sub(r'"model"\s*:\s*"([^"]*?)2\.0([^"]*?)"', r'"model":"\g<1>2.5\g<2>"', modified_body)
                    modified_body = _re.sub(r'"model_version"\s*:\s*"2\.0"', '"model_version":"2.5"', modified_body)
                    modified_body = _re.sub(r'(\\"model_version\\")\s*:\s*(\\"2\.0\\")', r'\1:\"2.5\"', modified_body)
                    modified_body = modified_body.replace('seedance_v2.0', 'seedance_v2.5')
                    modified_body = modified_body.replace('seedance-2.0', 'seedance-2.5')
                    modified_body = modified_body.replace('seedance_2.0', 'seedance_2.5')
                elif model == "2.0":
                    modified_body = _re.sub(r'"model"\s*:\s*"([^"]*?)2\.5([^"]*?)"', r'"model":"\g<1>2.0\g<2>"', modified_body)
                    modified_body = _re.sub(r'"model_version"\s*:\s*"2\.5"', '"model_version":"2.0"', modified_body)
                    modified_body = modified_body.replace('seedance_v2.5', 'seedance_v2.0')
                    modified_body = modified_body.replace('seedance-2.5', 'seedance-2.0')
                    modified_body = modified_body.replace('seedance_2.5', 'seedance_2.0')
                
                # Ép Aspect Ratio
                if aspect_ratio:
                    modified_body = _re.sub(r'(\\*"?aspect_ratio\\*"?\s*:\s*\\*"?)[0-9]+:[0-9]+(\\*"?\s*)', rf'\g<1>{aspect_ratio}\g<2>', modified_body)
                    modified_body = _re.sub(r'(\\*"?ratio\\*"?\s*:\s*\\*"?)[0-9]+:[0-9]+(\\*"?\s*)', rf'\g<1>{aspect_ratio}\g<2>', modified_body)
                
                try:
                    await cdp.send("Fetch.continueRequest", {"requestId": request_id, "postData": modified_body})
                except Exception:
                    try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
                    except Exception: pass
            
            cdp.on("Fetch.requestPaused", on_request_paused)
            await cdp.send("Fetch.enable", {
                "patterns": [
                    {"urlPattern": "*chat/completion*", "requestStage": "Request"},
                    {"urlPattern": "*im/message*", "requestStage": "Request"},
                    {"urlPattern": "*im/chain*", "requestStage": "Request"},
                ]
            })
            
            log_info(f"✅ [CDP Bypass] Duration={duration}s, Model={model}, Ratio={aspect_ratio}")
        except Exception as e:
            log_info(f"⚠️ [CDP Bypass] Lỗi cài interceptor: {e}")

    async def clear_old_video_links(self, page: Page):
        """Dọn sạch danh sách video cũ trong Extension localStorage."""
        try:
            await page.evaluate("""
                (() => {
                    if (typeof window.__clearDolaWatermarkLinks === 'function') {
                        window.__clearDolaWatermarkLinks();
                    }
                    try {
                        localStorage.removeItem('__dolaWatermarkLinks');
                        localStorage.setItem('__lastDolaGenTime', String(Date.now()));
                    } catch(e) {}
                })();
            """)
            log_info("🧹 Đã dọn dẹp danh sách video cũ trong Extension (localStorage) trước khi tạo.")
        except Exception:
            pass

    # ─── UI Interaction: Create Video Mode ────────────────────────────────

    async def click_create_video_button(self, page: Page) -> bool:
        """Kích hoạt chế độ 'Create Video'/'Tạo video' trên Dola chat UI và xác nhận thành công."""
        log_info("Đang kích hoạt chế độ 'Tạo video' tại thanh công cụ Dola...")
        try:
            # 1. Kiểm tra xem UI đã ở sẵn trong chế độ Tạo video chưa (skill 17 hoặc nút Model/Tỷ lệ)
            is_already_active = await page.evaluate("""() => {
                const hasSkill17 = !!document.querySelector('[data-value="17"], [data-input-engine-action-source="actionbar"]');
                const hasModel = Array.from(document.querySelectorAll('button, div')).some(el => (el.innerText || '').trim().startsWith('Model'));
                const hasRatio = Array.from(document.querySelectorAll('button, div')).some(el => {
                    const t = (el.innerText || '').trim();
                    return t.startsWith('Tỷ lệ') || t.startsWith('Tỉ lệ') || t.startsWith('Ratio');
                });
                return hasSkill17 || (hasModel && hasRatio);
            }""")
            if is_already_active:
                log_info("✅ UI đã ở sẵn trong chế độ Tạo video.")
                return True

            # 2. Thử kích hoạt nút Tạo video bằng danh sách selector phong phú
            selectors = [
                'button.skill-bar-button:has-text("Tạo video")',
                '[data-value="17"]',
                'button:has-text("Tạo video")',
                'div[role="button"]:has-text("Tạo video")',
                'div[contenteditable="false"]:has-text("Tạo video")',
                'div:has-text("Tạo video")',
                'button:has-text("Create Video")',
                'div[role="button"]:has-text("Create Video")',
                '[data-testid*="video"]',
            ]
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        await asyncio.sleep(1.2)
                        
                        # Kiểm tra lại xem đã vào chế độ tạo video chưa
                        verified = await page.evaluate("""() => {
                            const hasSkill17 = !!document.querySelector('[data-value="17"]');
                            const hasModel = Array.from(document.querySelectorAll('button, div')).some(el => (el.innerText || '').trim().startsWith('Model'));
                            const hasRatio = Array.from(document.querySelectorAll('button, div')).some(el => (el.innerText || '').trim().startsWith('Tỷ lệ') || (el.innerText || '').trim().startsWith('Tỉ lệ'));
                            return hasSkill17 || hasModel || hasRatio;
                        }""")
                        if verified:
                            log_info("✅ Đã kích hoạt chế độ 'Create Video'/'Tạo video' thành công!")
                            return True
                except Exception:
                    continue

            # 3. Fallback: Nếu bấm ở trang chat không được, chuyển hướng trực tiếp sang Studio create-image
            log_info("🔄 Chuyển hướng trực tiếp sang https://www.dola.com/chat/create-image...")
            try:
                await page.goto("https://www.dola.com/chat/create-image", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)

                # Chọn tab Video nếu đang ở tab Hình ảnh
                await page.evaluate("""() => {
                    const isExcluded = el => Boolean(el.closest('header, nav, aside, [class*="sidebar" i], [class*="nav" i], [class*="menu" i]'));
                    const roleTabs = Array.from(document.querySelectorAll('[role="tablist"] [role="tab"], [role="tablist"] button, .semi-tabs-tab, div[role="tab"]'));
                    for (const t of roleTabs) {
                        if (isExcluded(t)) continue;
                        const txt = (t.innerText || t.textContent || '').trim().toLowerCase();
                        if (txt === 'video' || txt.includes('video')) {
                            t.click();
                            return;
                        }
                    }
                    const buttons = Array.from(document.querySelectorAll('main button, [class*="create" i] button, [class*="studio" i] button, button'));
                    for (const b of buttons) {
                        if (isExcluded(b)) continue;
                        const txt = (b.innerText || b.textContent || '').trim();
                        if (/^(?:tạo\s*)?video$/i.test(txt) || txt === 'Video' || txt === 'Tạo Video' || txt === 'Tạo video') {
                            b.click();
                            return;
                        }
                    }
                }""")
                await asyncio.sleep(1)
                log_info("✅ Đã chuyển sang trang Studio Tạo video (create-image).")
                return True
            except Exception as e:
                log_info(f"⚠️ Lỗi chuyển hướng create-image: {e}")

            # 4. Kiểm tra cuối cùng
            final_check = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button, div')).some(el => (el.innerText || '').trim().startsWith('Model') || (el.innerText || '').trim().startsWith('Tỷ lệ'));
            }""")
            if final_check:
                log_info("✅ UI đã sẵn sàng trong chế độ Tạo video.")
                return True

            log_info("❌ Lỗi: Không thể kích hoạt chế độ Tạo video trên Dola AI!")
            raise Exception("Không thể kích hoạt chế độ Tạo video trên Dola AI. Tránh gửi nhầm prompt vào ô chat thường.")
        except Exception as e:
            log_info(f"❌ Lỗi kích hoạt Create Video: {e}")
            raise

    async def select_ratio(self, page: Page, ratio: str = "9:16"):
        """Chọn tỉ lệ khung hình trên Dola UI."""
        log_info(f"🔄 [Step 3] Đang chọn Ratio trên Dola UI: {ratio}...")
        try:
            ratio_btn = None
            ratio_selectors = [
                'button:has-text("Tỷ lệ")', 'button:has-text("Tỉ lệ")', 'button:has-text("Ratio")',
                'button:has-text("16:9")', 'button:has-text("9:16")', 'button:has-text("1:1")',
                'button:has-text("3:4")', 'button:has-text("4:3")',
            ]
            for sel in ratio_selectors:
                el = await page.query_selector(sel)
                if el:
                    ratio_btn = el
                    break

            if not ratio_btn:
                log_info("⚠️ Không tìm thấy nút Ratio trên UI")
                return

            current_text = (await ratio_btn.inner_text()).strip()
            if ratio in current_text:
                log_info(f"✅ Ratio hiện tại đã là {ratio}")
                return

            await ratio_btn.click()
            await asyncio.sleep(0.8)

            clicked = await page.evaluate(f"""
                (() => {{
                    const all = Array.from(document.querySelectorAll('*'));
                    for (const el of all) {{
                        if (el.children.length === 0 && el.innerText && el.innerText.trim() === '{ratio}') {{
                            el.click();
                            if (el.parentElement) el.parentElement.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()
            """)

            await asyncio.sleep(0.5)
            log_info(f"✅ Đã chọn Ratio = {ratio} (clicked={clicked})")
        except Exception as e:
            log_info(f"⚠️ Lỗi chọn Ratio: {e}")

    async def select_model(self, page: Page, model: str = "2.0"):
        """Chọn model Seedance trên Dola UI (2.0 Nhanh hoặc 2.5)."""
        log_info(f"🔄 Đang chọn model: Seedance {model}...")
        try:
            model_btn = None
            for sel in ['button:has-text("Model")', 'button:has-text("2.0")', 'button:has-text("2.5")', 'button:has-text("1.0")']:
                el = await page.query_selector(sel)
                if el:
                    model_btn = el
                    break

            if not model_btn:
                log_info("⚠️ Không tìm thấy nút Model trên UI")
                return

            current_text = (await model_btn.inner_text()).strip()
            log_info(f"📋 Model hiện tại trên UI: '{current_text}' | Cần: '{model}'")
            if model in current_text and (model != "2.0" or "2.0" in current_text):
                log_info(f"✅ Model hiện tại đã là {model}, không cần chuyển.")
                return

            await model_btn.click()
            await asyncio.sleep(0.8)

            target_str = "2.0 Nhanh" if model == "2.0" else ("2.5" if model == "2.5" else model)
            clicked = await page.evaluate(f"""
                (() => {{
                    const menu = document.querySelector('[role="menu"], [data-radix-menu-content]');
                    if (!menu) {{
                        const all = Array.from(document.querySelectorAll('[role="menuitem"], [data-slot="dropdown-menu-item"], div, li'));
                        for (const el of all) {{
                            const txt = (el.innerText || '').trim();
                            if (txt.includes('Seedance {target_str}') || txt.includes('{target_str}')) {{
                                el.click();
                                return true;
                            }}
                        }}
                        return false;
                    }}
                    const items = Array.from(menu.querySelectorAll('[role="menuitem"], [data-slot="dropdown-menu-item"]'));
                    for (const el of items) {{
                        const txt = (el.innerText || '').trim();
                        if (txt.includes('{target_str}') || txt.includes('{model}')) {{
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()
            """)

            await asyncio.sleep(1.0)
            new_text = (await model_btn.inner_text()).strip() if model_btn else ""
            log_info(f"✅ Đã chọn model Seedance {model} (clicked={clicked}, UI text='{new_text}').")
        except Exception as e:
            log_info(f"⚠️ Lỗi chọn Model: {e}")

    async def select_duration_on_ui(self, page: Page, ui_duration: str = "30s"):
        """Chọn thời lượng trên Dola UI.
        
        QUAN TRỌNG: UI Dola thường chỉ hiện 5s/10s/15s (extension mới thêm 30s).
        Khi extension không load, ta chọn bất kỳ duration nào có trên UI.
        CDP Fetch Interceptor + window.fetch monkey-patch sẽ ép duration thành 30s
        trong POST body trước khi gửi tới server.
        """
        log_info(f"⏱️ Cấu hình thời lượng AI: target={ui_duration} (CDP sẽ ép trong request body)...")
        try:
            # 1. Tìm nút dropdown thời lượng hiện tại
            dur_btn = None
            for sel in ['button:has-text("30s")', 'button:has-text("15s")', 'button:has-text("10s")', 'button:has-text("5s")', 'button:has-text("Thời lượng")']:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    dur_btn = el
                    break
            
            if dur_btn:
                current_text = (await dur_btn.inner_text()).strip()
                
                # Nếu UI đã hiện 30s (extension đã load) → perfect
                if "30s" in current_text:
                    log_info(f"✅ Extension active: UI hiện {current_text} (30s)")
                    return
                
                # Thử mở menu và chọn 30s (nếu có)
                await dur_btn.click()
                await asyncio.sleep(0.6)
                
                clicked_30 = await page.evaluate("""(() => {
                    const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], [data-slot="dropdown-menu-item"], div, span, button'));
                    for (const it of items) {
                        const txt = (it.innerText || '').trim();
                        if (txt === '30s' || txt.startsWith('30s')) {
                            it.click();
                            return '30s';
                        }
                    }
                    return '';
                })()""")
                
                if clicked_30:
                    log_info(f"✅ Đã chọn 30s trên UI menu.")
                    return
                
                # 30s không có trong menu → chọn giá trị cao nhất có sẵn (15s > 10s > 5s)
                chosen = await page.evaluate("""(() => {
                    const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], [data-slot="dropdown-menu-item"], div, span, button'));
                    const durations = ['15s', '10s', '5s'];
                    for (const target of durations) {
                        for (const it of items) {
                            const txt = (it.innerText || '').trim();
                            if (txt === target || txt.startsWith(target)) {
                                it.click();
                                return target;
                            }
                        }
                    }
                    return '';
                })()""")
                
                if chosen:
                    log_info(f"⚡ UI chọn {chosen} (extension chưa load 30s) → CDP Fetch Interceptor sẽ ép thành {ui_duration} trong request body")
                    return
                else:
                    # Đóng menu nếu không chọn được gì
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)

            # 2. Không tìm thấy dropdown → Duration sẽ được ép hoàn toàn qua CDP
            log_info(f"⚡ [Bypass] Không tìm thấy nút duration trên UI → CDP Fetch Interceptor + Fetch Bypass sẽ ép {ui_duration} trong POST body")
        except Exception as e:
            log_info(f"⚠️ Duration UI note: {e} → CDP Bypass vẫn hoạt động")

    # ─── Upload Reference Image ──────────────────────────────────────────

    async def upload_reference_image(self, page: Page, image_path: str):
        """Upload ảnh tham chiếu cho video trên Dola UI.
        
        4 Strategy theo thứ tự ưu tiên:
        1. Tìm input[type=file] có sẵn → set_input_files()
        2. Click nút "+" / attach → chờ input[type=file] xuất hiện → set_input_files()
        3. Clipboard paste: đọc file → base64 → tạo Blob → dispatch paste event
        4. File chooser: click nút upload → page.expect_file_chooser()
        """
        if not image_path:
            return
        import os
        if not os.path.isfile(image_path):
            log_info(f"⚠️ File ảnh không tồn tại: {image_path}")
            return

        log_info(f"📎 Đang tải lên ảnh tham chiếu: {os.path.basename(image_path)}...")

        # ─── Strategy 1: input[type=file] có sẵn trong DOM ───
        try:
            file_inputs = await page.query_selector_all('input[type="file"]')
            if file_inputs:
                for fi in file_inputs:
                    try:
                        await fi.set_input_files(image_path)
                        await asyncio.sleep(3)
                        log_info("✅ Đã tải lên ảnh tham chiếu qua input[type=file] có sẵn!")
                        return
                    except Exception:
                        continue
        except Exception:
            pass

        # ─── Strategy 2: Click nút "+" / attach để trigger file input ───
        try:
            # Tìm nút attach gần ô chat
            attach_btn = await page.evaluate("""(() => {
                // Tìm textarea/chat input
                const chatBox = document.querySelector('textarea, [contenteditable="true"], [data-testid="chat-input"]');
                if (!chatBox) return '';
                
                // Tìm nút "+" hoặc attach gần chat box
                const parent = chatBox.closest('form, [class*="input"], [class*="chat"]') || chatBox.parentElement?.parentElement;
                if (!parent) return '';
                
                const btns = parent.querySelectorAll('button, div[role="button"], label');
                for (const btn of btns) {
                    const text = (btn.innerText || '').trim();
                    const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                    const hasIcon = btn.querySelector('svg, img, [class*="icon"]');
                    
                    if (text === '+' || text === '📎' || text === '➕' ||
                        ariaLabel.includes('upload') || ariaLabel.includes('attach') || 
                        ariaLabel.includes('file') || ariaLabel.includes('image') ||
                        ariaLabel.includes('ảnh') || ariaLabel.includes('tải') ||
                        (hasIcon && !text && btn.offsetWidth < 60)) {
                        // Trả về selector ID hoặc class để click
                        btn.setAttribute('data-seedance-attach', 'true');
                        return 'found';
                    }
                }
                return '';
            })()""")
            
            if attach_btn == 'found':
                btn_el = await page.query_selector('[data-seedance-attach="true"]')
                if btn_el:
                    await btn_el.click()
                    await asyncio.sleep(1.5)
                    
                    # Chờ input[type=file] xuất hiện sau khi click
                    try:
                        file_input = await page.wait_for_selector('input[type="file"]', timeout=5000)
                        if file_input:
                            await file_input.set_input_files(image_path)
                            await asyncio.sleep(3)
                            log_info("✅ Đã tải lên ảnh tham chiếu qua nút + attach!")
                            return
                    except Exception:
                        pass
        except Exception:
            pass

        # ─── Strategy 3: Clipboard paste (đọc file → blob → paste event) ───
        try:
            import base64
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            
            # Detect mime type
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", 
                       ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
            mime_type = mime_map.get(ext, "image/png")
            fname = os.path.basename(image_path)
            
            pasted = await page.evaluate(f"""(async () => {{
                try {{
                    // Decode base64 → Uint8Array → Blob → File
                    const b64 = '{img_b64}';
                    const binary = atob(b64);
                    const bytes = new Uint8Array(binary.length);
                    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                    const blob = new Blob([bytes], {{ type: '{mime_type}' }});
                    const file = new File([blob], '{fname}', {{ type: '{mime_type}', lastModified: Date.now() }});
                    
                    // Tạo DataTransfer + ClipboardEvent
                    const dt = new DataTransfer();
                    dt.items.add(file);
                    
                    // Tìm element target để paste
                    const target = document.querySelector('textarea') || 
                                   document.querySelector('[contenteditable="true"]') ||
                                   document.querySelector('[data-testid="chat-input"]') ||
                                   document.body;
                    
                    target.focus();
                    
                    // Dispatch paste event
                    const pasteEvent = new ClipboardEvent('paste', {{
                        bubbles: true,
                        cancelable: true,
                        clipboardData: dt
                    }});
                    target.dispatchEvent(pasteEvent);
                    
                    return 'pasted';
                }} catch(e) {{
                    return 'error:' + e.message;
                }}
            }})()""")
            
            if pasted == 'pasted':
                await asyncio.sleep(3)
                log_info("✅ Đã tải lên ảnh tham chiếu qua clipboard paste!")
                return
            else:
                log_info(f"📎 Clipboard paste result: {pasted}")
        except Exception as e:
            log_info(f"📎 Clipboard paste fallback: {e}")

        # ─── Strategy 4: page.expect_file_chooser + click các nút upload ───
        try:
            upload_selectors = [
                'button[aria-label*="upload" i]', 'button[aria-label*="attach" i]',
                'button[aria-label*="image" i]', 'button[aria-label*="ảnh" i]',
                '[class*="upload"] button', '[class*="attach"] button',
                'div[class*="upload"]', 'div[class*="attach"]',
                'label[for*="file"]', 'label[for*="upload"]',
            ]
            for sel in upload_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await el.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(image_path)
                        await asyncio.sleep(3)
                        log_info(f"✅ Đã tải lên ảnh tham chiếu qua file chooser ({sel})!")
                        return
                except Exception:
                    continue
        except Exception:
            pass

        log_info("⚠️ Không tìm thấy cách upload ảnh tham chiếu trên Dola UI (sẽ tạo video không ảnh)")

    # ─── Input Prompt & Send ─────────────────────────────────────────────

    @staticmethod
    def sanitize_prompt_for_dola(prompt: str) -> str:
        """Lọc bỏ các từ khóa cấm/nhạy cảm và định dạng khiến Dola AI từ chối hoặc hỏi lại."""
        import re as _re
        banned_patterns = [
            # Violence / Gore
            (r'\bgore\b', ''),
            (r'\bblood\b', ''),
            (r'\bno blood\b', ''),
            (r'\bcorpse\b', ''),
            (r'\bmurder\b', ''),
            (r'\bkill(?:ing|s|ed)?\b', ''),
            (r'\bweapon(?:s)?\b', 'prop'),
            (r'\bsword(?:s)?\b', 'staff'),
            (r'\bgun(?:s)?\b', 'toy'),
            (r'\bknife\b', ''),
            (r'\bknives\b', ''),
            (r'\bexplosion(?:s)?\b', 'burst effect'),
            (r'\bexplode(?:s|d)?\b', 'burst'),
            
            # Combat / Fighting
            (r'\bbattle each other in an over-the-top comedic ninja duel\b', 'perform an over-the-top comedic martial arts choreography'),
            (r'\bninja duel\b', 'martial arts choreography'),
            (r'\bninja strike(?:s)?\b', 'martial arts move'),
            (r'\bninja move(?:s)?\b', 'martial arts move'),
            (r'\bduel(?:s|ing)?\b', 'choreography'),
            (r'\bbattle(?:s|d)?\b', 'action performance'),
            (r'\bfight(?:s|ing)?\b', 'dance'),
            (r'\bcombat\b', 'action performance'),
            (r'\bwar\b', 'adventure'),
            (r'\bstrike(?:s)?\b', 'move'),
            (r'\bpunch(?:es|ed|ing)?\b', 'gesture'),
            (r'\bkick(?:s|ed|ing)?\b', 'gesture'),
            (r'\bslap(?:s|ped)?\b', 'tap'),
            (r'\bhit(?:s|ting)?\b', 'tap'),
            (r'\bsmash(?:es|ed|ing)?\b', 'bump'),
            (r'\bcrash(?:es|ed|ing)?\b', 'bump'),
            (r'\bcollide(?:s|d)?\b', 'meet'),
            (r'\bcollision\b', 'meeting'),
            (r'\bimpact\b', 'effect'),
            (r'\bclash(?:es|ed|ing)?\b', 'performance'),
            (r'\battack(?:s|ed|ing)?\b', 'performance move'),
            (r'\bspinning energy attack(?:s)?\b', 'spinning energy move'),
            (r'\bcharged spinning attack\b', 'charged spinning move'),
            (r'\bget(?:s)? comically launched\b', 'gets comically bounced'),
            
            # Ninja - sometimes flagged
            (r'\bcosplaying as ninjas\b', 'cosplaying as martial artists'),
            (r'\bninja(?:s)?\b', 'martial artist'),
            
            # Negative prompts (can trigger safety)
            (r'\[NEGATIVE\].*$', '', _re.MULTILINE),
            (r'\bno gore\b', ''),
            
            # Timestamps and duration text
            (r'\b30-second\b', ''),
            (r'\b30 seconds\b', ''),
            (r'\b15-second\b', ''),
            (r'\b15 seconds\b', ''),
            (r'\b\d{2}:\d{2}-\d{2}:\d{2}\b', ''),  # 00:00-00:04
            (r'\b\d{2}:\d{2}\b', ''),  # 00:04
            
            # Section headers that confuse Dola into text-only response
            (r'\[SHOT-BY-SHOT\s*/\s*TIMESTAMPS?\]', ''),
            (r'\[CAMERA\s*/\s*OPTICS\]', ''),
            (r'\[PHYSICS\]', ''),
            (r'\[LIGHTING\]', ''),
            (r'\[AUDIO\]', ''),
            (r'\[GLOBAL STYLE\]', ''),
            (r'\[SCENE\]', ''),
            (r'\[CHARACTERS?\]', ''),
            (r'\[LOCATION\]', ''),
            (r'\[FIRST FRAME.*?\]', ''),
        ]
        cleaned = prompt
        for item in banned_patterns:
            pat = item[0]
            rep = item[1]
            flags = item[2] if len(item) > 2 else _re.IGNORECASE
            cleaned = _re.sub(pat, rep, cleaned, flags=flags)
        cleaned = _re.sub(r',\s*,', ',', cleaned)
        cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    async def input_prompt_and_send(self, page: Page, prompt: str):
        """Nhập prompt vào ô chat Dola và gửi.
        
        Dùng JS evaluate để bypass modal overlay chặn pointer events.
        """
        prompt = self.sanitize_prompt_for_dola(prompt)
        log_info(f"Nhập prompt video: '{truncate_text(prompt, 80)}'")
        log_info("Đang nhập prompt vào ô chat Dola...")

        # Dọn modal trước khi nhập
        await self.dismiss_modals_and_overlays(page)

        try:
            # Strategy 1: Dùng JS evaluate để nhập trực tiếp (bypass overlay)
            prompt_escaped = prompt.replace('\\', '\\\\').replace("'", "\\'")
            prompt_escaped = prompt_escaped.replace('\n', '\\n')
            
            injected = await page.evaluate(f"""
                (() => {{
                    // Tìm textarea
                    let input = document.querySelector('textarea');
                    if (!input) input = document.querySelector('[contenteditable="true"]');
                    if (!input) input = document.querySelector('[data-testid="chat-input"]');
                    if (!input) input = document.querySelector('div[role="textbox"]');
                    if (!input) return false;
                    
                    // Focus element
                    input.focus();
                    
                    if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {{
                        // Native input: set value + dispatch events
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value'
                        )?.set || Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        )?.set;
                        if (nativeInputValueSetter) {{
                            nativeInputValueSetter.call(input, '{prompt_escaped}');
                        }} else {{
                            input.value = '{prompt_escaped}';
                        }}
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }} else {{
                        // ContentEditable div
                        input.innerText = '{prompt_escaped}';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                    return true;
                }})();
            """)

            if injected:
                log_info("✅ Đã nhập prompt qua JS evaluate thành công.")
                await asyncio.sleep(0.5)
                return

            # Strategy 2: Fallback — Playwright fill() sau khi dọn modal
            log_info("⚠️ JS inject thất bại, thử Playwright fill()...")
            input_selectors = [
                'textarea',
                '[contenteditable="true"]',
                '[data-testid="chat-input"]',
                'div[role="textbox"]',
            ]
            for sel in input_selectors:
                try:
                    input_el = await page.wait_for_selector(sel, timeout=3000)
                    if input_el:
                        await input_el.fill(prompt)
                        log_info("✅ Đã nhập prompt qua fill() thành công.")
                        await asyncio.sleep(0.5)
                        return
                except Exception:
                    continue

            log_info("❌ Không tìm thấy ô nhập prompt!")

        except Exception as e:
            log_info(f"⚠️ Lỗi nhập prompt: {e}")

    async def send_prompt(self, page: Page):
        """Bấm nút gửi của Dola (#flow-end-msg-send) chuẩn pointer/mouse events như Extension."""
        log_info("Gửi lệnh tạo video qua nút gửi #flow-end-msg-send...")
        try:
            clicked = await page.evaluate("""
                (() => {
                    const triggerFullClick = (el) => {
                        if (!el) return false;
                        try {
                            el.focus();
                            const opts = { bubbles: true, cancelable: true, view: window };
                            el.dispatchEvent(new PointerEvent('pointerdown', opts));
                            el.dispatchEvent(new MouseEvent('mousedown', opts));
                            el.dispatchEvent(new PointerEvent('pointerup', opts));
                            el.dispatchEvent(new MouseEvent('mouseup', opts));
                            el.dispatchEvent(new MouseEvent('click', opts));
                            if (typeof el.click === 'function') el.click();
                            return true;
                        } catch(e) { return false; }
                    };
                    
                    const sendButtons = [
                        '#flow-end-msg-send',
                        '#channa-create-btn',
                        '.studio-relay-create-btn',
                        '#create-video-btn',
                        '.create-video-btn',
                        '#btn-create-video',
                        'button[type="submit"]',
                        'button[aria-label*="Create Video" i]',
                        'button[title*="Create Video" i]',
                        'button[aria-label*="Send" i]',
                        'button[title*="Send" i]'
                    ];
                    for (const sel of sendButtons) {
                        const btn = document.querySelector(sel);
                        if (btn && btn.offsetParent !== null) {
                            return triggerFullClick(btn);
                        }
                    }
                    return false;
                })()
            """)
            if clicked:
                log_info("✅ Đã kích hoạt nút gửi (#flow-end-msg-send) thành công.")
                await asyncio.sleep(1)
                return 0
        except Exception as e:
            log_info(f"⚠️ Lỗi click nút gửi: {e}")

        # Fallback: Bấm Enter
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)
        log_info("✅ Đã bấm phím Enter gửi lệnh (fallback).")
        return 0

    # ─── Wait for Video Completion ────────────────────────────────────────

    async def wait_for_video_completion(
        self,
        page: Page,
        timeout: int = VIDEO_WAIT_TIMEOUT,
        duration_target: int = 31,
        model: str = "2.5",
    ) -> Optional[str]:
        """Polling loop chờ Dola tạo xong video.
        
        Đọc ĐÚNG vùng chat messages (không đọc sidebar "Tìm kiếm...").
        Phát hiện trạng thái qua DOM elements: spinner, video, error text.
        
        Returns: URL video hoặc None nếu timeout/thất bại.
        """
        log_info("⏳ Đang chờ Dola AI tạo video...")
        start_time = time.time()
        video_accepted = False
        last_extension_reactivate = 0
        last_status_log = 0

        while not self._cancel_flag:
            elapsed = int(time.time() - start_time)

            # Timeout
            if elapsed > timeout:
                log_info("🔍 Quét DOM lần cuối tìm video...")
                url = await self._extract_video_url(page)
                if url:
                    return url
                url = await self._extract_video_from_dom(page)
                if url:
                    return url
                log_info("❌ Timeout: Không tìm thấy video sau thời gian chờ.")
                raise Exception(f"Timeout {timeout}s: Dola AI không trả về video. Thử lại hoặc kiểm tra tài khoản.")

            # Re-activate extension bypass periodically
            if time.time() - last_extension_reactivate >= EXTENSION_REACTIVATE_INTERVAL:
                try:
                    await self.activate_extension_bypass(page, duration_target, model)
                except Exception:
                    pass
                last_extension_reactivate = time.time()

            # ─── Đọc trạng thái từ chat container (KHÔNG đọc body/sidebar) ───
            gen_status = await self._get_chat_generation_status(page)
            
            # Log trạng thái mỗi 15s hoặc khi có thay đổi
            if time.time() - last_status_log >= 15:
                log_info(f"[{elapsed}s] 📊 Status: spinner={gen_status['has_spinner']} | "
                         f"video={gen_status['has_video']} | error={gen_status['has_error']} | "
                         f"accepted={video_accepted} | chat='{truncate_text(gen_status['last_chat_text'], 120)}'")
                last_status_log = time.time()

            # ─── Kiểm tra lỗi từ chat messages ───
            chat_text = gen_status.get("last_chat_text", "")
            chat_lower = chat_text.lower()
            
            try:
                # 1. Duration refusal
                duration_refusal = [
                    "supports durations", "supported duration", "nearest supported duration",
                    "hỗ trợ độ dài", "thời lượng từ", "please confirm if you want to proceed",
                    "vui lòng xác nhận", "bạn có muốn tiếp tục", "độ dài tối đa", "chỉ hỗ trợ độ dài",
                    "supports durations from 4 to 15 seconds", "supported duration of 15 seconds"
                ]
                for kw in duration_refusal:
                    if kw in chat_lower:
                        err_msg = f"Dola AI từ chối duration: '{truncate_text(chat_text, 140)}'"
                        log_info(f"❌ {err_msg}")
                        raise Exception(err_msg)

                # 2. Safety policy / content refusal
                refusal_kw = [
                    "content violation", "safety policy", "vi phạm chính sách", "prompt rejected",
                    "không thể tạo nội dung", "thử gì đó khác", "cannot generate content", "try something else",
                    "không thể hỗ trợ yêu cầu này", "inappropriate content", "vi phạm tiêu chuẩn",
                    "từ chối yêu cầu", "không tuân thủ nguyên tắc"
                ]
                for kw in refusal_kw:
                    if kw in chat_lower:
                        err_msg = f"Prompt bị Dola AI từ chối: '{truncate_text(chat_text, 140)}'"
                        log_info(f"❌ {err_msg}")
                        raise Exception(err_msg)

                # 3. Guest error
                if "not available for guests" in chat_lower or "log in to start creating" in chat_lower:
                    raise Exception("Tài khoản chưa đăng nhập Dola AI.")

                # 4. Quota/credit limit
                quota_kw = [
                    "limit reached", "out of credits", "insufficient credits", "bạn đã hết điểm",
                    "đạt giới hạn tạo video", "giới hạn tạo video hằng ngày", "thử lại vào ngày mai",
                    "daily limit reached", "generation limit", "đạt giới hạn"
                ]
                if any(kw in chat_lower for kw in quota_kw):
                    raise Exception("Tài khoản đã đạt giới hạn tạo video hằng ngày. Chuyển sang tài khoản khác.")

                # 5. Generic error trong chat
                if gen_status.get("has_error"):
                    generic_kw = ["đã xảy ra lỗi", "vui lòng thử lại", "an error occurred", "something went wrong"]
                    if any(kw in chat_lower for kw in generic_kw):
                        raise Exception(f"Dola AI báo lỗi: '{truncate_text(chat_text, 100)}'")
            except Exception as err:
                err_str = str(err)
                if any(k in err_str for k in ["Tài khoản", "Prompt", "Dola", "từ chối", "Timeout", "giới hạn"]):
                    raise

            # ─── Kiểm tra Dola đã chấp nhận tạo video chưa ───
            if not video_accepted:
                if gen_status.get("has_spinner"):
                    video_accepted = True
                    log_info("✅ Nhận diện loading spinner — Dola đang tạo video!")
                elif any(kw in chat_lower for kw in ["generating", "creating", "đang tạo", "processing", "please wait", "xin chờ"]):
                    video_accepted = True
                    log_info("✅ Nhận diện text 'đang tạo' — Dola đã chấp nhận!")

            # ─── Kiểm tra video đã tạo xong ───
            # 1. DOM có <video> element
            if gen_status.get("has_video"):
                log_info("🎬 Phát hiện <video> element trên DOM! Đang trích xuất URL...")
                await asyncio.sleep(2)  # Chờ video load source
                
                video_url = await self._extract_video_from_dom(page)
                if video_url:
                    return video_url
                    
                video_url = await self._extract_video_url(page)
                if video_url:
                    return video_url

            # 2. Extension localStorage / window.__dolaChatVideos
            video_url = await self._extract_video_url(page)
            if video_url:
                return video_url

            # 3. DOM scan (video elements, performance resources)
            video_url = await self._extract_video_from_dom(page)
            if video_url:
                return video_url

            # Poll interval
            await asyncio.sleep(VIDEO_POLL_INTERVAL)

        return None  # Cancelled

    async def _get_chat_generation_status(self, page: Page) -> dict:
        """Đọc trạng thái tạo video từ vùng chat messages (KHÔNG đọc sidebar).
        
        Returns: {
            'has_spinner': bool,   # Có loading indicator
            'has_video': bool,     # Có <video> element 
            'has_error': bool,     # Có text lỗi
            'last_chat_text': str, # Text tin nhắn gần nhất
        }
        """
        try:
            return await page.evaluate("""(() => {
                // ─── Tìm vùng chat container (loại trừ sidebar) ───
                let chatContainer = null;
                
                // Strategy 1: Tìm main content area
                const mainSelectors = [
                    'main', '[role="main"]',
                    '[class*="chat-content"]', '[class*="chatContent"]',
                    '[class*="message-list"]', '[class*="messageList"]',
                    '[class*="conversation-content"]', '[class*="conversationContent"]',
                    '[class*="chat-container"]', '[class*="chatContainer"]',
                    '[class*="right-panel"]', '[class*="rightPanel"]',
                ];
                for (const sel of mainSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetWidth > 300) {
                        chatContainer = el;
                        break;
                    }
                }
                
                // Strategy 2: Tìm container chứa textarea (ô chat)
                if (!chatContainer) {
                    const textarea = document.querySelector('textarea, [contenteditable="true"]');
                    if (textarea) {
                        let parent = textarea.parentElement;
                        for (let i = 0; i < 8 && parent; i++) {
                            if (parent.offsetWidth > 400 && parent.offsetHeight > 300) {
                                chatContainer = parent;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }
                }
                
                const searchArea = chatContainer || document.body;
                
                // ─── Kiểm tra loading spinner ───
                const hasSpinner = !!(searchArea.querySelector(
                    '[class*="loading"], [class*="spinner"], [class*="generating"],' +
                    '.lottie-animation, svg[class*="spin"], [class*="progress"],' +
                    '[class*="Loading"], [class*="Spinner"], [class*="dots"]'
                ));
                
                // ─── Kiểm tra video element ───
                const videos = searchArea.querySelectorAll('video');
                let hasVideo = false;
                for (const v of videos) {
                    const src = v.currentSrc || v.src || '';
                    if (src.startsWith('http') || v.querySelector('source[src]')) {
                        hasVideo = true;
                        break;
                    }
                }
                // Cũng kiểm tra video cover/block (Dola hiện poster trước khi play)
                if (!hasVideo) {
                    hasVideo = !!(searchArea.querySelector(
                        '[class*="video-player"], [class*="videoPlayer"],' +
                        '[class*="block-video"], [class*="blockVideo"],' +
                        '[class*="cover-"][class*="video"]'
                    ));
                }
                
                // ─── Đọc tin nhắn chat gần nhất (loại trừ sidebar) ───
                const msgSelectors = [
                    '[class*="message"]', '[class*="bubble"]', 
                    '[class*="content-block"]', '[class*="contentBlock"]',
                    '[class*="chat-msg"]', '[class*="chatMsg"]',
                    '[class*="reply"]', 'p',
                ];
                let allMsgs = [];
                for (const sel of msgSelectors) {
                    const els = searchArea.querySelectorAll(sel);
                    for (const el of els) {
                        const t = (el.innerText || '').trim();
                        if (t && t.length > 5 && t.length < 2000 && 
                            !t.startsWith('Tìm kiếm') && !t.startsWith('Ctrl')) {
                            allMsgs.push(t);
                        }
                    }
                    if (allMsgs.length >= 3) break;
                }
                
                // Lấy 3 tin nhắn gần nhất
                const recentMsgs = allMsgs.slice(-3);
                const lastText = recentMsgs.join(' ');
                
                // ─── Kiểm tra error ───
                const hasError = lastText.toLowerCase().includes('lỗi') || 
                                 lastText.toLowerCase().includes('error') ||
                                 lastText.toLowerCase().includes('thất bại') || 
                                 lastText.toLowerCase().includes('failed') ||
                                 lastText.toLowerCase().includes('không thể') ||
                                 lastText.toLowerCase().includes('vi phạm');
                
                return {
                    has_spinner: hasSpinner,
                    has_video: hasVideo,
                    has_error: hasError,
                    last_chat_text: lastText.substring(0, 500),
                };
            })()""")
        except Exception as e:
            return {
                "has_spinner": False,
                "has_video": False,
                "has_error": False,
                "last_chat_text": f"[DOM read error: {e}]",
            }

    async def _extract_video_url(self, page: Page) -> Optional[str]:
        """Trích xuất URL video master không watermark từ window.__dolaChatVideos hoặc extractor.js."""
        try:
            # 1. Ưu tiên số 1: Trích xuất trực tiếp từ window.__dolaChatVideos (global cache của extractor.js)
            url = await page.evaluate("""
                (() => {
                    if (window.__dolaChatVideos && Array.isArray(window.__dolaChatVideos)) {
                        const fallbackList = window.__dolaChatVideos.filter(v => v && v.source === 'fallback_api' && v.url);
                        if (fallbackList.length > 0) {
                            return fallbackList[fallbackList.length - 1].url;
                        }
                    }
                    return '';
                })()
            """)
            if url and isinstance(url, str) and url.startswith('http'):
                log_info("🎯 Bắt được link video Master sạch không logo từ window.__dolaChatVideos")
                return self._to_clean_url(url)

            # 2. Ưu tiên số 2: Gửi sự kiện DOLA_GET_CHAT_MEDIA hỏi extractor.js
            extracted_url = await page.evaluate("""
                (() => {
                    return new Promise(resolve => {
                        let settled = false;
                        const onRes = (e) => {
                            if (settled) return;
                            settled = true;
                            window.removeEventListener('DOLA_CHAT_MEDIA_RESPONSE', onRes);
                            const vids = e?.detail?.videos || [];
                            const unwatermarked = vids.filter(v => v?.source === 'fallback_api' && v.url);
                            if (unwatermarked.length > 0) {
                                resolve(unwatermarked[unwatermarked.length - 1].url);
                            } else if (vids.length > 0 && vids[vids.length - 1].url) {
                                resolve(vids[vids.length - 1].url);
                            } else {
                                resolve('');
                            }
                        };
                        window.addEventListener('DOLA_CHAT_MEDIA_RESPONSE', onRes, { once: true });
                        window.dispatchEvent(new CustomEvent('DOLA_GET_CHAT_MEDIA'));
                        setTimeout(() => {
                            if (!settled) {
                                settled = true;
                                window.removeEventListener('DOLA_CHAT_MEDIA_RESPONSE', onRes);
                                resolve('');
                            }
                        }, 500);
                    });
                })()
            """)
            if extracted_url and isinstance(extracted_url, str) and extracted_url.startswith('http'):
                log_info("🎯 Bắt được link video qua DOLA_CHAT_MEDIA_RESPONSE")
                return self._to_clean_url(extracted_url)

            # 2. Ưu tiên số 2: Đọc từ Extension localStorage
            links_json = await page.evaluate("""
                (() => {
                    try {
                        const sources = [
                            localStorage.getItem('__dolaWatermarkLinks'),
                            localStorage.getItem('__seedanceLinks'),
                        ];
                        for (const raw of sources) {
                            if (raw) {
                                const parsed = JSON.parse(raw);
                                if (Array.isArray(parsed) && parsed.length > 0) return JSON.stringify(parsed);
                            }
                        }
                    } catch(e) {}
                    return '[]';
                })();
            """)
            links = json.loads(links_json)
            if links:
                for link in links:
                    if isinstance(link, dict):
                        url = link.get('url', '')
                        if link.get('isHQ') or 'lr=unwatermarked' in url or 'lr=cici_ai' in url:
                            return self._to_clean_url(url)
                    elif isinstance(link, str) and link.startswith('http'):
                        if 'lr=unwatermarked' in link or 'lr=cici_ai' in link:
                            return self._to_clean_url(link)

                first = links[0]
                if isinstance(first, dict):
                    return self._to_clean_url(first.get('url', ''))
                elif isinstance(first, str):
                    return self._to_clean_url(first)

        except Exception:
            pass
        return None

    @staticmethod
    def _to_clean_url(url: str) -> str:
        """Chuẩn hóa URL → lr=unwatermarked + download=true."""
        if not url:
            return ''
        import re as _re
        clean = url.replace('\\u0026', '&').replace('&amp;', '&').strip()
        for wm in ['lr=video_gen_watermark_dyn', 'lr=video_gen_watermark', 'lr=watermarked', 'lr=cici_ai']:
            clean = clean.replace(wm, 'lr=unwatermarked')
        if 'lr=' not in clean:
            sep = '&' if '?' in clean else '?'
            clean = f"{clean}{sep}lr=unwatermarked"
        if 'download=true' not in clean:
            clean = f"{clean}&download=true"
        return clean

    async def _extract_video_from_dom(self, page: Page) -> Optional[str]:
        """Quét DOM tìm video element trực tiếp và kích hoạt video player nếu cần."""
        try:
            video_url = await page.evaluate("""
                (() => {
                    // 1. Nếu có video cover / block, click để kích hoạt player
                    const cover = document.querySelector('.cover-u1rIsU') || 
                                  document.querySelector('.block-video-MzfWVN') || 
                                  document.querySelector('.video-player-wrapper-IZ7Zoq');
                    if (cover) {
                        try { cover.click(); } catch(e) {}
                    }
                    
                    // 2. Scan video elements
                    const videos = document.querySelectorAll('video');
                    for (const v of videos) {
                        const src = v.currentSrc || v.src;
                        if (src && src.startsWith('http') && (src.includes('lr=') || src.includes('video/tos') || src.includes('.mp4') || src.includes('dola.com'))) {
                            return src;
                        }
                    }
                    // 3. Scan source elements
                    const sources = document.querySelectorAll('video source');
                    for (const s of sources) {
                        const src = s.src;
                        if (src && src.startsWith('http') && (src.includes('lr=') || src.includes('video/tos') || src.includes('.mp4') || src.includes('dola.com'))) {
                            return src;
                        }
                    }
                    // 4. Scan performance resource timing
                    try {
                        const perf = performance.getEntriesByType('resource')
                            .map(r => r.name)
                            .filter(n => n.startsWith('http') && (n.includes('video/tos') || n.includes('.mp4') || n.includes('tos-mya-ve')));
                        if (perf.length > 0) {
                            return perf[perf.length - 1];
                        }
                    } catch(e) {}
                    
                    return null;
                })();
            """)
            if video_url:
                return self._to_clean_url(video_url)
        except Exception:
            pass
        return None

    # ─── Main Execution Flow ─────────────────────────────────────────────

    async def execute_generation_flow(
        self,
        page: Page,
        prompt: str,
        aspect_ratio: str = "16:9",
        image_path: str = "",
        mode: str = "standard",          # "standard" | "pro_15s"
        duration_target: int = 31,
        model_version: str = "2.5",
        progress_callback=None,          # Callback(message: str)
    ) -> Optional[str]:
        """Orchestrator chính — chạy toàn bộ flow tạo video.
        
        Returns: URL video gốc không watermark, hoặc None nếu thất bại.
        """
        self.reset()

        def _progress(msg):
            if progress_callback:
                progress_callback(msg)

        log_info(f"🔍 [DEBUG] _execute_generation_flow nhận "
                 f"aspect_ratio = '{aspect_ratio}' | "
                 f"prompt gốc = '{truncate_text(prompt, 100)}'")

        if duration_target >= 30:
            log_info(f"⚡ [Ép {duration_target - 1}s {model_version} No Logo] "
                     f"Sử dụng Seedance {model_version} ép {duration_target - 1}s qua extension. "
                     f"Ratio: {aspect_ratio} (chọn trên UI)")

        # 1. Navigate tới Dola chat
        _progress("Đang chuyển sang Dola AI chat...")
        log_info("Đang chuyển sang Dola AI chat...")
        try:
            current_url = page.url
            if DOLA_URL not in current_url:
                log_info("🔄 Đang chuyển hướng sang trang chat trực tiếp...")
                await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
        except Exception:
            pass

        # 2. Kiểm tra đăng nhập
        login_status = await self.check_login_status(page)
        if login_status != "logged_in":
            err_msg = "Tài khoản chưa đăng nhập Dola AI! Hãy vào tab 'Tài khoản' -> bấm nút '🌐 Mở' để đăng nhập Google/Facebook trên Chrome profile."
            _progress(f"⚠️ {err_msg}")
            log_info(f"❌ {err_msg}")
            raise Exception(err_msg)

        # 3. Kích hoạt Extension bypass
        await self.activate_extension_bypass(page, duration_target, model_version, aspect_ratio)

        # 4. F5 refresh để đảm bảo Extension active
        log_info("🔄 F5 làm mới trình duyệt để kích hoạt Extension & giao diện...")
        await page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(3)
        log_info("✅ Trang web đã tải xong sau khi F5.")

        # 4b. Dọn modal/cookie overlay sau khi reload
        await self.dismiss_modals_and_overlays(page)
        await asyncio.sleep(1)
        await self.dismiss_modals_and_overlays(page)  # Lần 2 để chắc chắn

        # 5. Re-activate bypass sau F5
        await self.activate_extension_bypass(page, duration_target, model_version, aspect_ratio)

        # 6. Dọn video cũ
        await self.clear_old_video_links(page)

        # 7. Re-activate bypass
        await self.activate_extension_bypass(page, duration_target, model_version, aspect_ratio)

        if mode == "pro_15s":
            # ─── Pro 15s Mode ────────────────────────────────────
            return await self._execute_pro_15s_flow(
                page, prompt, aspect_ratio, image_path,
                duration_target, model_version, _progress
            )
        else:
            # ─── Standard 30s Mode ───────────────────────────────
            return await self._execute_standard_flow(
                page, prompt, aspect_ratio, image_path,
                duration_target, model_version, _progress
            )

    async def _execute_standard_flow(
        self, page, prompt, aspect_ratio, image_path,
        duration_target, model_version, _progress
    ) -> Optional[str]:
        """Flow chuẩn: chọn UI → nhập prompt → chờ kết quả."""
        _progress("Đang kích hoạt Create Video...")

        # Dọn modal trước mỗi bước UI
        await self.dismiss_modals_and_overlays(page)

        # Click Create Video
        await self.click_create_video_button(page)

        # Dọn modal trước khi chọn
        await self.dismiss_modals_and_overlays(page)

        # Chọn Ratio
        await self.select_ratio(page, aspect_ratio)

        # Chọn Model
        await self.select_model(page, model_version)

        # Chọn Duration trên UI
        await self.select_duration_on_ui(page, f"{duration_target}s" if duration_target else "30s")

        # Re-activate bypass
        await self.activate_extension_bypass(page, duration_target, model_version, aspect_ratio)

        # Upload ảnh tham chiếu nếu có
        if image_path:
            await self.dismiss_modals_and_overlays(page)
            await self.upload_reference_image(page, image_path)

        # Nhập prompt thô trực tiếp (raw prompt)
        await self.input_prompt_and_send(page, prompt)

        # Re-activate bypass ngay trước khi gửi
        log_info(f"⚡ [Extension {duration_target}s] Tái kích hoạt ô {duration_target}s ngầm ngay trước khi gửi prompt...")
        await self.activate_extension_bypass(page, duration_target, model_version, aspect_ratio)

        # Send qua nút #flow-end-msg-send
        _progress("Đang gửi prompt...")
        await self.send_prompt(page)

        # Polling chờ video
        _progress("Đang chờ Dola AI tạo video...")
        video_url = await self.wait_for_video_completion(
            page, VIDEO_WAIT_TIMEOUT, duration_target, model_version
        )

        return video_url

    async def _execute_pro_15s_flow(
        self, page, prompt, aspect_ratio, image_path,
        duration_target, model_version, _progress
    ) -> Optional[str]:
        """Flow Pro 30s: Sử dụng flow trực tiếp chuẩn như Extension (raw prompt, không bọc chat bot)."""
        _progress("Đang kích hoạt tạo video Pro 30s...")
        log_info(f"⚡ [Pro Mode] Gửi prompt thô trực tiếp qua Extension Bypass 30s (Seedance {model_version}).")
        return await self._execute_standard_flow(
            page, prompt, aspect_ratio, image_path,
            duration_target, model_version, _progress
        )

