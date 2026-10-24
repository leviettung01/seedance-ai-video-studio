"""
Test v5: 30s bypass with gg1 - FIXED video URL detection (exclude monitoring URLs).
"""
import asyncio, sys, os, json, subprocess, time, re
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from browser_manager import BrowserManager
from config import OUTPUT_DIR

CREATE_IMAGE_URL = "https://www.dola.com/chat/create-image"
OUTDIR = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed"

def is_real_video_url(url):
    """Only match actual video CDN URLs, NOT monitoring/analytics."""
    if not url or not url.startswith('http'): return False
    # Exclude monitoring/analytics
    if 'monitor_browser' in url: return False
    if '/collect/batch' in url: return False
    if 'analytics' in url: return False
    # Must be a video CDN URL
    return ('video/tos' in url or 
            ('ibytedtos.com' in url and 'video' in url) or
            ('dola.com' in url and 'video' in url and 'mime_type=video' in url))

async def test_30s_gg1():
    bm = BrowserManager()
    wid = 701
    account_name = 'gg1'
    
    print("=" * 60)
    print(f"  TEST v5: 30s bypass with {account_name} (FIXED detection)")
    print("=" * 60)
    
    port = await bm.launch_temp_chrome(worker_id=wid, show_browser=True)
    browser = await bm.connect_worker(wid)
    page = browser.contexts[0].pages[0]
    await bm.inject_session_to_worker(wid, account_name)
    
    await page.goto(CREATE_IMAGE_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(4)
    
    # Dismiss modals
    for sel in ['button:has-text("OK")', 'button:has-text("Got it")', '[aria-label="close"]']:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible(): await el.click()
        except: pass
    await asyncio.sleep(1)
    
    # Click Video tab
    for selector in ['button:has-text("Video")']:
        try:
            el = await page.wait_for_selector(selector, timeout=5000)
            if el:
                await el.click()
                print("✅ Clicked Video tab")
                break
        except: continue
    await asyncio.sleep(2)
    
    # Activate extension bypass
    await page.evaluate("""() => {
        localStorage.setItem('__dolaDurBypass', '1');
        localStorage.setItem('__dolaDur31', '1');
        localStorage.setItem('__dolaDur15', '0');
        localStorage.setItem('__dolaTargetDur', '31');
        if (typeof window.__setDolaBypass === 'function') window.__setDolaBypass(true, 31);
        localStorage.removeItem('__dolaWatermarkLinks');
        localStorage.removeItem('__seedanceLinks');
    }""")
    print("✅ Extension bypass activated")
    
    # Setup CDP interceptor
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
        
        if 'ability_param' not in post_data and 'duration' not in post_data:
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
            print(f"🎯 BYPASS: {', '.join(changes)}")
            # Verify
            idx = modified.find('ability_param')
            if idx >= 0:
                snippet = modified[idx:idx+150]
                print(f"   → {snippet}...")
            try: await cdp.send("Fetch.continueRequest", {"requestId": request_id, "postData": modified}); return
            except: pass
        try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
        except: pass
    
    cdp.on("Fetch.requestPaused", on_request_paused)
    await cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*chat/completion*", "requestStage": "Request"}]})
    print("✅ CDP interceptor ready")
    
    # Network listener - FIXED: only real video URLs
    async def on_response(response):
        url = response.url
        try:
            if is_real_video_url(url) and url not in captured_video_urls:
                captured_video_urls.append(url)
                print(f"📹 Network video: {url[:120]}...")
        except: pass
        try:
            if 'chat/completion' in url:
                body = await response.text()
                if body and len(body) > 100:
                    # Extract real video URLs from SSE data
                    all_urls = re.findall(r'https?://[^\s"\\,\}]+', body)
                    for u in all_urls:
                        if is_real_video_url(u) and u not in captured_video_urls:
                            captured_video_urls.append(u)
                            print(f"📹 SSE video: {u[:120]}...")
        except: pass
    
    page.on("response", on_response)
    
    # Type prompt
    prompt_text = "A tiny cute glowing baby dragon eating glowing berry in mystical forest, cinematic 4k, 9:16 vertical"
    for sel in ['[contenteditable="true"]', 'textarea']:
        try:
            el = await page.wait_for_selector(sel, timeout=3000)
            if el and await el.is_visible():
                await el.click()
                await asyncio.sleep(0.3)
                await page.keyboard.type(prompt_text, delay=10)
                print(f"✅ Typed prompt ({len(prompt_text)} chars)")
                break
        except: continue
    
    # Re-activate bypass
    await page.evaluate("""() => {
        localStorage.setItem('__dolaDurBypass', '1');
        localStorage.setItem('__dolaDur31', '1');
        localStorage.setItem('__dolaTargetDur', '31');
        if (typeof window.__setDolaBypass === 'function') window.__setDolaBypass(true, 31);
    }""")
    
    # Send
    print("📤 Sending prompt...")
    await page.keyboard.press("Enter")
    await asyncio.sleep(8)
    
    # Check quota
    body_text = await page.evaluate("document.body.innerText")
    if 'giới hạn' in body_text.lower():
        print("❌ QUOTA EXHAUSTED!")
        await page.screenshot(path=os.path.join(OUTDIR, 'v5_gg1_quota.png'))
        await bm.cleanup_worker(wid)
        return
    
    await page.screenshot(path=os.path.join(OUTDIR, 'v5_gg1_accepted.png'))
    print("✅ Request accepted! Video rendering...")
    
    # Wait for video (8 min max)
    start = time.time()
    video_url = None
    
    while time.time() - start < 480:
        elapsed = int(time.time() - start)
        
        # Check network captures (filtered)
        if captured_video_urls:
            video_url = captured_video_urls[0]
            print(f"\n🎉 Video captured via network! ({elapsed}s)")
            break
        
        # Check localStorage
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
                    print(f"\n🎉 Extension captured! ({elapsed}s)")
                    break
        except: pass
        
        # Check <video> elements
        try:
            vids = await page.evaluate("Array.from(document.querySelectorAll('video')).map(v => v.currentSrc || v.src).filter(s => s && s.startsWith('http'))")
            if vids:
                video_url = vids[0]
                print(f"\n🎉 <video> element! ({elapsed}s)")
                break
        except: pass
        
        # DOM scan every 10s
        if elapsed > 0 and elapsed % 10 == 0:
            try:
                html_urls = await page.evaluate("""() => {
                    const html = document.body.innerHTML;
                    const m = html.match(/https?:\\/\\/[^"'\\s]+video\\/tos[^"'\\s]*/g);
                    return m || [];
                }""")
                if html_urls:
                    video_url = html_urls[0]
                    print(f"\n🎉 DOM video URL! ({elapsed}s)")
                    break
            except: pass
        
        # Error check every 60s
        if elapsed > 30 and elapsed % 60 == 0:
            text = await page.evaluate("document.body.innerText.substring(0, 1000)")
            if 'giới hạn' in text.lower() or 'thất bại' in text.lower():
                print(f"\n❌ Error on page ({elapsed}s)")
                break
        
        if elapsed % 30 == 0:
            print(f"  [{elapsed}s] Waiting...")
        await asyncio.sleep(3)
    
    await page.screenshot(path=os.path.join(OUTDIR, 'v5_gg1_result.png'))
    
    if video_url:
        print(f"\n✅ VIDEO URL: {video_url[:150]}...")
        
        # Convert to unwatermarked
        clean = video_url
        for p in ['lr=video_gen_watermark_dyn', 'lr=video_gen_watermark', 'lr=watermarked', 'lr=cici_ai']:
            clean = clean.replace(p, 'lr=unwatermarked')
        
        out_path = os.path.join(OUTPUT_DIR, 'test_30s_gg1_v5.mp4')
        print(f"Downloading to {out_path}...")
        import requests as req
        r = req.get(clean, timeout=120)
        with open(out_path, 'wb') as f: f.write(r.content)
        print(f"Downloaded: {len(r.content)} bytes")
        
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size',
                   '-show_entries', 'stream=width,height,duration,codec_name', '-of', 'json', out_path]
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(f"\n📊 FFprobe:\n{r.stdout}")
            try:
                info = json.loads(r.stdout)
                dur = float(info.get('format', {}).get('duration', 0))
                streams = info.get('streams', [])
                video_stream = [s for s in streams if s.get('codec_name') in ('hevc', 'h264', 'vp9')]
                res = f"{video_stream[0].get('width','?')}x{video_stream[0].get('height','?')}" if video_stream else "?"
                
                print(f"\n📊 Duration: {dur:.1f}s | Resolution: {res}")
                if dur >= 25:
                    print(f"\n🎉🎉🎉 SUCCESS! 30s VIDEO BYPASS WORKS! Duration: {dur:.1f}s")
                else:
                    print(f"\n⚠️ Video is {dur:.1f}s — bypass may not have worked on server side")
            except Exception as e:
                print(f"  FFprobe parse error: {e}")
        else:
            print(f"  ⚠️ File too small or missing: {os.path.getsize(out_path) if os.path.exists(out_path) else 'N/A'} bytes")
    else:
        print("\n❌ No video URL captured after timeout")
    
    await bm.cleanup_worker(wid)
    print("\nDone!")

if __name__ == '__main__':
    asyncio.run(test_30s_gg1())
