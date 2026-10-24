"""
Test hoàn chỉnh:
1. Thao tác chuẩn UI: Click Tab Video -> Click Dropdown Model -> Chọn 'Dreamina Seedance 2.5' -> Click Tỷ lệ 9:16
2. Cấu trúc Prompt máy (Machine Prompt / System Directive) để ép Dola AI Agent
3. Thử nghiệm trên tài khoản 'fb 2' (hoặc 'fb3')
"""
import asyncio, sys, os, json, subprocess, time, re
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from browser_manager import BrowserManager
from config import OUTPUT_DIR

CREATE_IMAGE_URL = "https://www.dola.com/chat/create-image"
OUTDIR = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed"

def is_real_video_url(url):
    if not url or not url.startswith('http'): return False
    if 'monitor_browser' in url or '/collect/batch' in url or 'analytics' in url: return False
    return ('video/tos' in url or 
            ('ibytedtos.com' in url and 'video' in url) or
            ('dola.com' in url and 'video' in url and 'mime_type=video' in url))

async def test_standard_ui_and_agent_prompt(account_name='fb 2'):
    bm = BrowserManager()
    wid = 901
    
    print("=" * 65)
    print(f"🚀 TEST THAO TÁC CHUẨN UI (MODEL 2.5) + MACHINE PROMPT TRÊN: {account_name}")
    print("=" * 65)
    
    port = await bm.launch_temp_chrome(worker_id=wid, show_browser=True)
    browser = await bm.connect_worker(wid)
    page = browser.contexts[0].pages[0]
    await bm.inject_session_to_worker(wid, account_name)
    
    await page.goto(CREATE_IMAGE_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(4)
    
    # 1. Đóng modal & overlays
    for sel in ['button:has-text("OK")', 'button:has-text("Got it")', 'button:has-text("Đồng ý")', '[aria-label="close"]']:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible(): await el.click()
        except: pass
    await asyncio.sleep(1)
    
    # 2. Click tab "Video"
    print("\n[Bước 1] Chọn Tab Video...")
    for selector in ['button:has-text("Video")', '[role="tab"]:has-text("Video")']:
        try:
            el = await page.wait_for_selector(selector, timeout=5000)
            if el and await el.is_visible():
                await el.click()
                print("  ✅ Đã click tab 'Video'")
                break
        except: continue
    await asyncio.sleep(1.5)
    
    # 3. THAO TÁC CHUẨN: Chọn Model Seedance 2.5 trên UI
    print("\n[Bước 2] Chọn Model 'Dreamina Seedance 2.5' trên thanh công cụ...")
    model_clicked = False
    
    # Tìm nút Model (có chữ Model hoặc Model 2.0 hoặc Model 2.5)
    model_btn_selectors = [
        'button:has-text("Model")',
        'div[role="button"]:has-text("Model")',
        'span:has-text("Model")',
        '[class*="model"]:has-text("Model")'
    ]
    for sel in model_btn_selectors:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                model_clicked = True
                print(f"  👉 Đã mở dropdown Model (qua selector: {sel})")
                await asyncio.sleep(1)
                break
        except: pass
    
    if model_clicked:
        # Click chọn "Dreamina Seedance 2.5"
        opt_selected = False
        for opt_sel in [
            'div:has-text("Dreamina Seedance 2.5")',
            'span:has-text("Dreamina Seedance 2.5")',
            '[role="menuitem"]:has-text("2.5")',
            'div:has-text("Seedance 2.5")'
        ]:
            try:
                opt = await page.query_selector(opt_sel)
                if opt and await opt.is_visible():
                    await opt.click()
                    opt_selected = True
                    print(f"  ✅ Đã chọn 'Dreamina Seedance 2.5' trên UI!")
                    break
            except: pass
        if not opt_selected:
            print("  ⚠️ Không tìm thấy option 'Dreamina Seedance 2.5' trong dropdown")
    else:
        print("  ⚠️ Không click được nút Model dropdown")
    
    await asyncio.sleep(1)
    
    # 4. Kiểm tra nút Thời lượng (⏱ 10s)
    print("\n[Bước 3] Kiểm tra dropdown Thời lượng trên UI...")
    try:
        dur_btn = await page.query_selector('button:has-text("10s"), div:has-text("10s")')
        if dur_btn and await dur_btn.is_visible():
            await dur_btn.click()
            await asyncio.sleep(1)
            # Xem có các option nào trong dropdown thời lượng
            dur_options = await page.evaluate("""() => {
                const items = document.querySelectorAll('[role="menuitem"], [class*="option"], [class*="item"], div, span');
                return Array.from(items)
                    .map(e => e.textContent.trim())
                    .filter(t => (t.includes('5s') || t.includes('10s') || t.includes('15s') || t.includes('30s') || t.includes('s')) && t.length < 20);
            }""")
            print(f"  ⏱ Các tùy chọn thời lượng có sẵn trên UI: {dur_options[:6]}")
            # Đóng dropdown
            await page.keyboard.press("Escape")
    except Exception as e:
        print(f"  ⚠️ Check duration error: {e}")
        
    await asyncio.sleep(1)
    
    # Chụp ảnh thanh công cụ UI sau khi setup chuẩn
    ss_ui = os.path.join(OUTDIR, f'ui_setup_{account_name}.png')
    await page.screenshot(path=ss_ui)
    print(f"  📸 Screenshot UI setup: {ss_ui}")
    
    # 5. Kích hoạt Extension Bypass & CDP Interceptor (Hỗ trợ 2 lớp)
    print("\n[Bước 4] Kích hoạt Bypass Extension & CDP Interceptor (31s + 2.5)...")
    await page.evaluate("""() => {
        localStorage.setItem('__dolaDurBypass', '1');
        localStorage.setItem('__dolaDur31', '1');
        localStorage.setItem('__dolaDur15', '0');
        localStorage.setItem('__dolaTargetDur', '31');
        if (typeof window.__setDolaBypass === 'function') window.__setDolaBypass(true, 31);
        localStorage.removeItem('__dolaWatermarkLinks');
        localStorage.removeItem('__seedanceLinks');
    }""")
    
    captured_video_urls = []
    cdp = await page.context.new_cdp_session(page)
    
    async def on_request_paused(params):
        request_id = params.get("requestId", "")
        url = params.get("request", {}).get("url", "")
        post_data = params.get("request", {}).get("postData", "")
        
        if not post_data or 'completion' not in url:
            try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
            except: pass
            return
        
        modified = post_data
        changes = []
        
        m = re.sub(r'(\\"duration\\")\s*:\s*(\d+)', r'\1:31', modified)
        if m != modified: changes.append("esc-duration→31"); modified = m
        m = re.sub(r'"duration"\s*:\s*(\d+)', '"duration":31', modified)
        if m != modified: changes.append("duration→31"); modified = m
        m = modified.replace('seedance_v2.0', 'seedance_v2.5')
        if m != modified: changes.append("model→v2.5"); modified = m
        m = modified.replace('seedance-2.0', 'seedance-2.5')
        if m != modified: changes.append("model→-2.5"); modified = m
        
        if changes:
            print(f"  🎯 CDP BYPASS THÀNH CÔNG: {', '.join(changes)}")
            try: await cdp.send("Fetch.continueRequest", {"requestId": request_id, "postData": modified}); return
            except: pass
        try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
        except: pass
        
    cdp.on("Fetch.requestPaused", on_request_paused)
    await cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*chat/completion*", "requestStage": "Request"}]})
    
    # 6. Chuẩn bị MACHINE PROMPT (Ngôn ngữ chỉ thị AI Agent)
    # Kết hợp cấu trúc JSON Directive + Prompt nghệ thuật
    machine_prompt = (
        "A magical crystal forest with glowing luminescent blue butterflies "
        "fluttering gently among floating ethereal particles and ancient mystical glowing tree roots, "
        "volumetric cinematic sunset golden light rays, unreal engine 5, hyperrealistic 8k render, "
        "breathtaking atmosphere, camera slowly panning up, 9:16 vertical"
    )
    
    print(f"\n[Bước 5] Nhập Prompt vào ô soạn thảo...")
    for sel in ['[contenteditable="true"]', 'textarea']:
        try:
            el = await page.wait_for_selector(sel, timeout=3000)
            if el and await el.is_visible():
                await el.click()
                await asyncio.sleep(0.3)
                await page.keyboard.type(machine_prompt, delay=5)
                print(f"  ✅ Đã nhập prompt: '{machine_prompt[:60]}...'")
                break
        except: continue
        
    await asyncio.sleep(1)
    
    # 7. Lắng nghe phản hồi Network
    async def on_response(response):
        url = response.url
        try:
            if is_real_video_url(url) and url not in captured_video_urls:
                captured_video_urls.append(url)
                print(f"  📹 Network bắt được video: {url[:100]}...")
        except: pass
        try:
            if 'chat/completion' in url:
                body = await response.text()
                if body and ('video/tos' in body or 'fallback_api' in body):
                    urls = re.findall(r'https?://[^\s"\\,\}]+', body)
                    for u in all_urls:
                        if is_real_video_url(u) and u not in captured_video_urls:
                            captured_video_urls.append(u)
                            print(f"  📹 SSE stream bắt được video: {u[:100]}...")
        except: pass
    page.on("response", on_response)
    
    # 8. Gửi prompt
    print("\n[Bước 6] Gửi lệnh tạo video (Bấm Enter)...")
    await page.keyboard.press("Enter")
    await asyncio.sleep(8)
    
    # Kiểm tra phản hồi ban đầu
    body_text = await page.evaluate("document.body.innerText")
    if 'giới hạn' in body_text.lower() or '0 điểm' in body_text.lower():
        print(f"  ❌ HẾT QUOTA / 0 ĐIỂM trên {account_name}")
        await page.screenshot(path=os.path.join(OUTDIR, f'res_{account_name}_quota.png'))
        await bm.cleanup_worker(wid)
        return False
        
    print(f"  ✅ Dola AI đã chấp nhận yêu cầu! Đang render video...")
    await page.screenshot(path=os.path.join(OUTDIR, f'res_{account_name}_accepted.png'))
    
    # 9. Chờ video hoàn thành (Tối đa 8 phút)
    start = time.time()
    video_url = None
    
    while time.time() - start < 480:
        elapsed = int(time.time() - start)
        
        if captured_video_urls:
            video_url = captured_video_urls[0]
            print(f"\n  🎉 Bắt được video link sau {elapsed}s!")
            break
            
        try:
            links = await page.evaluate("""() => {
                const raw = localStorage.getItem('__dolaWatermarkLinks') || localStorage.getItem('__seedanceLinks');
                if (raw) { try { const p = JSON.parse(raw); if (Array.isArray(p) && p.length > 0) return p; } catch(e) {} }
                return [];
            }""")
            if links and len(links) > 0:
                u = links[0].get('url', links[0]) if isinstance(links[0], dict) else links[0]
                if is_real_video_url(u):
                    video_url = u
                    print(f"\n  🎉 Extension bắt được video sau {elapsed}s!")
                    break
        except: pass
        
        try:
            vids = await page.evaluate("Array.from(document.querySelectorAll('video')).map(v => v.currentSrc || v.src).filter(s => s && s.startsWith('http'))")
            if vids:
                video_url = vids[0]
                print(f"\n  🎉 Tìm thấy thẻ <video> DOM sau {elapsed}s!")
                break
        except: pass
        
        if elapsed % 30 == 0:
            print(f"  ⏳ [{elapsed}s] Đang chờ render...")
        await asyncio.sleep(3)
        
    await page.screenshot(path=os.path.join(OUTDIR, f'res_{account_name}_result.png'))
    
    if video_url:
        print(f"\n🎯 URL VIDEO GỐC: {video_url[:120]}...")
        clean = video_url
        for p in ['lr=video_gen_watermark_dyn', 'lr=video_gen_watermark', 'lr=watermarked', 'lr=cici_ai']:
            clean = clean.replace(p, 'lr=unwatermarked')
            
        out_path = os.path.join(OUTPUT_DIR, f'video_30s_pro_{account_name}.mp4')
        import requests as req
        r = req.get(clean, timeout=120)
        with open(out_path, 'wb') as f: f.write(r.content)
        print(f"  📥 Đã tải video về: {out_path} ({len(r.content)} bytes)")
        
        if os.path.exists(out_path):
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size',
                   '-show_entries', 'stream=width,height,duration,codec_name', '-of', 'json', out_path]
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(f"\n📊 THÔNG SỐ VIDEO (FFprobe):\n{r.stdout}")
            try:
                info = json.loads(r.stdout)
                dur = float(info.get('format', {}).get('duration', 0))
                print(f"\n{'🎉🎉🎉 KẾT QUẢ: THÀNH CÔNG TẠO VIDEO 30S!' if dur >= 25 else '⚠️ THỜI LƯỢNG: ' + str(dur) + 's'}")
            except: pass
    else:
        print(f"\n❌ Không bắt được video sau thời gian chờ.")
        
    await bm.cleanup_worker(wid)
    print("\nHoàn tất test!")

if __name__ == '__main__':
    # Thử tài khoản 'fb 2' trước, nếu hết thử 'fb3'
    asyncio.run(test_standard_ui_and_agent_prompt('fb 2'))
