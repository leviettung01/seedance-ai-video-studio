# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio v4.0 — Pro Mode Automation Engine
Tự động hóa tạo video qua AI Agent Dola ở chế độ Pro.
Không tốn credit, AI Agent tự tạo số lượng lớn video 15s.
"""

import asyncio
import json
import re
import time
from typing import Optional, Callable, List

from playwright.async_api import Page

from config import (
    DOLA_URL, PRO_PROMPT_TEMPLATE, PRO_POLL_INTERVAL, PRO_TIMEOUT,
    ASPECT_RATIO_LABELS,
)
from utils import log_info, log, truncate_text


class ProModeAutomation:
    """Engine tạo video qua AI Agent Dola Pro.
    
    Flow:
    1. Mở Chrome (1 instance duy nhất, duy trì suốt)
    2. Chuyển Dola sang chế độ Pro
    3. Upload ảnh tham chiếu (nếu có)
    4. Gửi prompt lệnh đặc biệt (template + list prompts)
    5. Monitor: Extension Sniffer bắt video URLs khi AI Agent hoàn thành
    6. Tự động tải video về thư mục riêng
    """

    def __init__(self):
        self._cancel_flag = False
        self._videos_found: list[dict] = []
        self._on_video_found: Optional[Callable] = None

    def cancel(self):
        """Đặt cờ hủy — vòng lặp monitor sẽ dừng."""
        self._cancel_flag = True

    def reset(self):
        """Reset state cho phiên mới."""
        self._cancel_flag = False
        self._videos_found = []

    # ─── Build Pro Prompt ─────────────────────────────────────────────────

    def build_pro_prompt(
        self,
        prompts: List[str],
        skill: str = "",
        count: int = 0,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Xây dựng prompt lệnh Pro từ template.
        
        Args:
            prompts: Danh sách prompt (mỗi dòng = 1 video)
            skill: Skill instruction (nếu không có prompts)
            count: Số lượng video muốn tạo
            aspect_ratio: Tỉ lệ khung hình (9:16, 16:9, 1:1)
        
        Returns: Full prompt string để gửi cho Dola Pro
        """
        # Xác định số lượng
        if count <= 0:
            count = max(len(prompts), 1)

        # Xác định format text
        format_map = {
            "9:16": "dọc",
            "16:9": "ngang",
            "1:1": "vuông",
            "3:4": "dọc nhẹ",
            "4:3": "ngang nhẹ",
            "21:9": "siêu rộng",
        }
        format_text = format_map.get(aspect_ratio, "dọc")

        # Xây dựng prompt list
        prompt_list = ""
        if prompts:
            numbered = [f"{i+1}. {p.strip()}" for i, p in enumerate(prompts) if p.strip()]
            prompt_list = "\n".join(numbered)

        # Xây dựng skill instruction
        skill_instruction = skill.strip() if skill else "(Không có Skill, chỉ dùng List prompt ở trên)"

        # Format template
        full_prompt = PRO_PROMPT_TEMPLATE.format(
            count=count,
            format=format_text,
            prompt_list=prompt_list or "(Không có list prompt, dùng Skill ở dưới)",
            skill_instruction=skill_instruction,
        )

        log_info(f"[Pro Mode] Đã xây dựng prompt lệnh: {count} video, format={format_text}")
        return full_prompt

    # ─── Switch to Pro Mode ───────────────────────────────────────────────

    async def switch_to_pro_mode(self, page: Page) -> bool:
        """Click chuyển Dola chat sang chế độ Pro.
        
        Dola UI có dropdown "Nhanh" / "Pro" ở dưới textbox chat.
        """
        log_info("[Pro Mode] Đang chuyển Dola chat sang chế độ Pro...")

        try:
            # 1. Tìm nút chuyển mode (Nhanh/Pro)
            mode_selectors = [
                'button:has-text("Pro")',
                'div[role="button"]:has-text("Pro")',
                'span:has-text("Pro")',
                'button:has-text("Nhanh")',  # Click nút Nhanh để mở dropdown
            ]

            for sel in mode_selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=3000)
                    if el:
                        text = (await el.text_content() or "").strip()
                        if "Pro" in text and "Nhanh" not in text:
                            # Nếu đã thấy nút "Pro", có thể đã ở chế độ Pro
                            # Hoặc cần click để chuyển
                            log_info(f"[Pro Mode] Tìm thấy nút: '{text}'")
                            
                            # Kiểm tra xem đã ở Pro chưa
                            is_active = await page.evaluate("""
                                (() => {
                                    const els = document.querySelectorAll('button, div[role="button"], span');
                                    for (const el of els) {
                                        const t = (el.innerText || '').trim();
                                        if (t.includes('Pro') && !t.includes('Nhanh')) {
                                            // Kiểm tra xem element có class active/selected
                                            const cls = el.className || '';
                                            const parentCls = (el.parentElement?.className || '');
                                            if (cls.includes('active') || cls.includes('selected') || 
                                                parentCls.includes('active') || parentCls.includes('selected') ||
                                                el.getAttribute('aria-selected') === 'true') {
                                                return true;
                                            }
                                        }
                                    }
                                    return false;
                                })()
                            """)
                            
                            if not is_active:
                                await el.click()
                                await asyncio.sleep(1)
                            
                            log_info("✅ [Pro Mode] Đã chuyển sang chế độ Pro!")
                            return True
                except Exception:
                    continue

            # 2. Fallback: tìm dropdown menu
            log_info("[Pro Mode] Tìm dropdown mode...")
            try:
                # Click "Nhanh" button trước để mở dropdown
                nhanh_btn = await page.wait_for_selector(
                    'button:has-text("Nhanh"), div:has-text("Nhanh")', timeout=3000)
                if nhanh_btn:
                    await nhanh_btn.click()
                    await asyncio.sleep(0.8)
                    
                    # Chọn "Pro" trong dropdown
                    pro_opt = await page.wait_for_selector(
                        'div:has-text("Pro"):not(:has(div))', timeout=2000)
                    if pro_opt:
                        await pro_opt.click()
                        await asyncio.sleep(1)
                        log_info("✅ [Pro Mode] Đã chuyển sang chế độ Pro qua dropdown!")
                        return True
            except Exception:
                pass

            # 3. Fallback JS: click trực tiếp
            switched = await page.evaluate("""
                (() => {
                    const allEls = document.querySelectorAll('button, div[role="button"], span, div');
                    for (const el of allEls) {
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === 'pro' || t === '⚙️ pro' || t.includes('mô hình pro')) {
                            el.click();
                            return true;
                        }
                    }
                    // Tìm trong menu dropdown
                    for (const el of allEls) {
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === 'nhanh' || t.includes('nhanh')) {
                            el.click();
                            return 'opened_dropdown';
                        }
                    }
                    return false;
                })()
            """)

            if switched == 'opened_dropdown':
                await asyncio.sleep(0.8)
                await page.evaluate("""
                    (() => {
                        const allEls = document.querySelectorAll('div, span, button');
                        for (const el of allEls) {
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t === 'pro' || t.includes('mô hình pro')) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                """)
                await asyncio.sleep(1)
                log_info("✅ [Pro Mode] Đã chuyển sang chế độ Pro qua JS!")
                return True
            elif switched:
                log_info("✅ [Pro Mode] Đã chuyển sang chế độ Pro qua JS!")
                return True

            log_info("⚠️ [Pro Mode] Không tìm thấy nút chuyển Pro. Sẽ thử gửi prompt trực tiếp.")
            return False

        except Exception as e:
            log_info(f"⚠️ [Pro Mode] Lỗi chuyển Pro: {e}")
            return False

    # ─── Upload Reference Image ───────────────────────────────────────────

    async def upload_reference_image(self, page: Page, image_path: str):
        """Upload ảnh tham chiếu vào chat Pro."""
        if not image_path:
            return
        log_info(f"[Pro Mode] Đang tải lên ảnh tham chiếu: {image_path}")
        try:
            # Tìm nút upload / input file
            # Dola Pro có nút "+" hoặc biểu tượng đính kèm
            plus_btn = None
            for sel in ['button:has-text("+")', '[aria-label*="attach"]', '[aria-label*="upload"]',
                        'button[class*="upload"]', 'button[class*="attach"]']:
                try:
                    el = await page.wait_for_selector(sel, timeout=2000)
                    if el:
                        plus_btn = el
                        break
                except Exception:
                    continue

            if plus_btn:
                await plus_btn.click()
                await asyncio.sleep(1)

            # Set file vào input[type=file]
            file_input = await page.wait_for_selector('input[type="file"]', timeout=5000)
            if file_input:
                await file_input.set_input_files(image_path)
                await asyncio.sleep(3)
                log_info("✅ [Pro Mode] Đã tải lên ảnh tham chiếu thành công!")
            else:
                log_info("⚠️ [Pro Mode] Không tìm thấy input file upload")
        except Exception as e:
            log_info(f"⚠️ [Pro Mode] Lỗi upload ảnh: {e}")

    # ─── Send Pro Command ─────────────────────────────────────────────────

    async def send_pro_command(self, page: Page, full_prompt: str):
        """Gửi prompt lệnh Pro vào chat Dola.
        
        Dùng JS evaluate để bypass modal overlay.
        """
        log_info(f"[Pro Mode] Đang gửi lệnh Pro ({len(full_prompt)} ký tự)...")

        try:
            # Nhập prompt qua JS
            prompt_escaped = full_prompt.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')

            injected = await page.evaluate(f"""
                (() => {{
                    let input = document.querySelector('textarea');
                    if (!input) input = document.querySelector('[contenteditable="true"]');
                    if (!input) input = document.querySelector('[data-testid="chat-input"]');
                    if (!input) input = document.querySelector('div[role="textbox"]');
                    if (!input) return false;
                    
                    input.focus();
                    
                    if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {{
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
                        input.innerText = '{prompt_escaped}';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                    return true;
                }})();
            """)

            if injected:
                log_info("✅ [Pro Mode] Đã nhập prompt lệnh Pro thành công.")
                await asyncio.sleep(1)
                
                # Bấm Enter để gửi
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)
                log_info("✅ [Pro Mode] Đã gửi lệnh Pro! AI Agent sẽ bắt đầu tạo video...")
            else:
                log_info("❌ [Pro Mode] Không nhập được prompt!")

        except Exception as e:
            log_info(f"⚠️ [Pro Mode] Lỗi gửi lệnh Pro: {e}")

    # ─── Monitor Video Creation ───────────────────────────────────────────

    async def monitor_video_creation(
        self,
        page: Page,
        expected_count: int,
        on_video_found: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
    ) -> list[dict]:
        """Polling loop theo dõi AI Agent tạo video.
        
        Kết hợp 3 nguồn:
        1. Extension Sniffer (chrome.storage.local → captured_videos)
        2. DOM scanning (video elements trên trang)
        3. Performance API entries
        
        Args:
            page: Playwright Page đang mở Dola
            expected_count: Số video mong đợi
            on_video_found: Callback khi tìm thấy video mới
            on_progress: Callback cho progress update
            
        Returns: Danh sách video đã bắt được
        """
        log_info(f"[Pro Monitor] Bắt đầu theo dõi {expected_count} video từ AI Agent...")
        
        start_time = time.time()
        seen_keys = set()
        found_videos = []
        last_count = 0

        while not self._cancel_flag:
            elapsed = int(time.time() - start_time)

            # Timeout
            if elapsed > PRO_TIMEOUT:
                log_info(f"[Pro Monitor] ⏰ Timeout sau {elapsed}s. Đã bắt được {len(found_videos)}/{expected_count} video.")
                break

            # Đủ số lượng
            if len(found_videos) >= expected_count:
                log_info(f"[Pro Monitor] 🎉 Đã bắt đủ {len(found_videos)} video!")
                break

            # 1. Đọc từ Extension captured_videos (storage)
            try:
                storage_videos = await page.evaluate("""
                    (() => {
                        try {
                            // Đọc từ localStorage (inject.js lưu)
                            const raw = localStorage.getItem('__dolaWatermarkLinks') || 
                                        localStorage.getItem('__seedanceLinks');
                            if (raw) {
                                const parsed = JSON.parse(raw);
                                if (Array.isArray(parsed)) return parsed;
                            }
                        } catch(e) {}
                        return [];
                    })()
                """)

                for v in (storage_videos or []):
                    url = v.get('url', v) if isinstance(v, dict) else str(v)
                    if url and url.startswith('http'):
                        # Normalize: ép lr=cici_ai
                        key = self._extract_video_key(url)
                        if key and key not in seen_keys:
                            seen_keys.add(key)
                            video_info = {
                                'url': self._to_clean_url(url),
                                'key': key,
                                'index': len(found_videos) + 1,
                                'ts': time.time(),
                                'source': 'extension_storage',
                            }
                            found_videos.append(video_info)
                            if on_video_found:
                                on_video_found(video_info)
                            log_info(f"[Pro Monitor] 🎯 #{len(found_videos)} Video bắt được từ Extension: {url[:80]}...")
            except Exception:
                pass

            # 2. Scan video elements trên DOM
            try:
                dom_videos = await page.evaluate("""
                    (() => {
                        const found = [];
                        document.querySelectorAll('video').forEach(v => {
                            const src = v.currentSrc || v.src;
                            if (src && src.startsWith('http') && (src.includes('video/tos') || src.includes('lr='))) {
                                found.push(src);
                            }
                        });
                        document.querySelectorAll('video source').forEach(s => {
                            const src = s.src;
                            if (src && src.startsWith('http') && (src.includes('video/tos') || src.includes('lr='))) {
                                found.push(src);
                            }
                        });
                        return found;
                    })()
                """)

                for url in (dom_videos or []):
                    key = self._extract_video_key(url)
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        video_info = {
                            'url': self._to_clean_url(url),
                            'key': key,
                            'index': len(found_videos) + 1,
                            'ts': time.time(),
                            'source': 'dom_scan',
                        }
                        found_videos.append(video_info)
                        if on_video_found:
                            on_video_found(video_info)
                        log_info(f"[Pro Monitor] 🎯 #{len(found_videos)} Video bắt được từ DOM: {url[:80]}...")
            except Exception:
                pass

            # Progress update
            current_count = len(found_videos)
            if current_count != last_count or elapsed % 60 == 0:
                msg = f"[{elapsed}s] ⏳ Đã bắt {current_count}/{expected_count} video..."
                log_info(f"[Pro Monitor] {msg}")
                if on_progress:
                    on_progress(msg)
                last_count = current_count

            # Kiểm tra AI Agent đang làm gì
            if elapsed % 120 == 0 and elapsed > 0:
                try:
                    # Kiểm tra nếu AI Agent bị kẹt
                    body_text = await page.evaluate("document.body.innerText.substring(0, 500)")
                    if any(kw in body_text.lower() for kw in ["xác nhận", "confirm", "bạn có muốn"]):
                        log_info("[Pro Monitor] 🔄 Phát hiện AI Agent hỏi xác nhận! Đang gửi 'Có, tiếp tục'...")
                        await page.evaluate("""
                            (() => {
                                let input = document.querySelector('textarea');
                                if (!input) input = document.querySelector('[contenteditable="true"]');
                                if (input) {
                                    input.focus();
                                    if (input.tagName === 'TEXTAREA') {
                                        input.value = 'Có, tiếp tục tạo video.';
                                    } else {
                                        input.innerText = 'Có, tiếp tục tạo video.';
                                    }
                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                }
                            })()
                        """)
                        await asyncio.sleep(0.5)
                        await page.keyboard.press("Enter")
                        log_info("[Pro Monitor] ✅ Đã gửi xác nhận.")
                except Exception:
                    pass

            # Poll interval
            await asyncio.sleep(PRO_POLL_INTERVAL)

        self._videos_found = found_videos
        return found_videos

    # ─── Execute Full Pro Flow ────────────────────────────────────────────

    async def execute_pro_flow(
        self,
        page: Page,
        prompts: List[str],
        skill: str = "",
        count: int = 0,
        aspect_ratio: str = "9:16",
        image_path: str = "",
        on_video_found: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
    ) -> list[dict]:
        """Orchestrator chính cho Pro Mode.
        
        Returns: Danh sách video đã tạo
        """
        self.reset()

        # 1. Navigate tới Dola
        try:
            current_url = page.url
            if DOLA_URL not in current_url:
                await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
        except Exception:
            pass

        # 2. Chuyển sang Pro mode
        await self.switch_to_pro_mode(page)
        await asyncio.sleep(2)

        # 3. Upload ảnh tham chiếu (nếu có)
        if image_path:
            await self.upload_reference_image(page, image_path)

        # 4. Build và gửi prompt
        effective_count = count if count > 0 else max(len(prompts), 1)
        full_prompt = self.build_pro_prompt(prompts, skill, effective_count, aspect_ratio)
        await self.send_pro_command(page, full_prompt)

        # 5. Monitor video creation
        if on_progress:
            on_progress(f"🧠 AI Agent đang tạo {effective_count} video. Theo dõi tự động...")

        videos = await self.monitor_video_creation(
            page, effective_count, on_video_found, on_progress
        )

        return videos

    # ─── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_video_key(url: str) -> str:
        """Trích xuất mã định danh duy nhất từ URL video."""
        if not url:
            return ''
        clean = url.replace('\\u0026', '&').replace('&amp;', '&')
        
        # TOS key: tos-mya-ve-.../o4BixbYk...
        tos_match = re.search(r'tos-[a-z0-9\-]+/[a-zA-Z0-9_\-]+', clean, re.IGNORECASE)
        if tos_match:
            return tos_match.group(0).lower()

        # MD5 hash: v16-dola.dola.com/<md5>/<hash>
        md5_match = re.search(r'v\d+-dola\.dola\.com/([a-f0-9]{32})/([a-f0-9]+)', clean, re.IGNORECASE)
        if md5_match:
            return f"{md5_match.group(1)}_{md5_match.group(2)}".lower()

        # Fallback: pathname
        try:
            from urllib.parse import urlparse
            parsed = urlparse(clean)
            return parsed.path.lower()
        except Exception:
            return clean.split('?')[0].lower()

    @staticmethod
    def _to_clean_url(url: str) -> str:
        """Chuẩn hóa URL → bản sạch lr=cici_ai + download=true."""
        if not url:
            return ''
        clean = url.replace('\\u0026', '&').replace('&amp;', '&').replace('\\/', '/').strip()
        
        # Ép lr=cici_ai
        import re as _re
        clean = _re.sub(r'lr=[^&]+', 'lr=cici_ai', clean)
        if 'lr=' not in clean:
            sep = '&' if '?' in clean else '?'
            clean = f"{clean}{sep}lr=cici_ai"
        
        # Thêm download=true
        if 'download=true' not in clean:
            clean = f"{clean}&download=true"
        
        return clean
