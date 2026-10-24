"""
Debug: Capture FULL request body from /chat/completion to see exact JSON structure.
"""
import asyncio, sys, os, json, re, time
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from browser_manager import BrowserManager

CREATE_IMAGE_URL = "https://www.dola.com/chat/create-image"
OUTDIR = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed"

async def capture_request():
    bm = BrowserManager()
    wid = 301
    account_name = 'tungdhc'
    
    print("=" * 60)
    print("  DEBUG: Capture /chat/completion request body")
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
    for selector in ['button:has-text("Video")', '[role="tab"]:has-text("Video")']:
        try:
            el = await page.wait_for_selector(selector, timeout=3000)
            if el:
                text = (await el.text_content() or "").strip()
                if len(text) < 30 and "Video" in text:
                    await el.click()
                    print(f"✅ Clicked Video tab")
                    break
        except: continue
    await asyncio.sleep(2)
    
    # DO NOT activate bypass - let it send naturally first to see default body
    # But DO set up CDP to CAPTURE (not modify) the full body
    print("Setting up CDP to capture request body (NO modification)...")
    captured_bodies = []
    
    cdp = await page.context.new_cdp_session(page)
    
    async def on_request_paused(params):
        request_id = params.get("requestId", "")
        url = params.get("request", {}).get("url", "")
        post_data = params.get("request", {}).get("postData", "")
        
        if post_data and ('completion' in url or 'samantha' in url or 'generate' in url):
            print(f"\n{'='*60}")
            print(f"🔍 CAPTURED REQUEST TO: {url[:100]}")
            print(f"   Body length: {len(post_data)} chars")
            captured_bodies.append({"url": url, "body": post_data})
            
            # Pretty print the body (try to parse as JSON)
            try:
                body_json = json.loads(post_data)
                print(f"\n📋 PARSED JSON BODY:")
                # Print key fields
                for key in body_json:
                    val = body_json[key]
                    if isinstance(val, str) and len(val) > 200:
                        print(f"   {key}: (string, {len(val)} chars)")
                        # Check if it's nested JSON
                        if val.startswith('{') or val.startswith('['):
                            try:
                                nested = json.loads(val)
                                print(f"     → Nested JSON with keys: {list(nested.keys()) if isinstance(nested, dict) else 'array'}")
                                if isinstance(nested, dict):
                                    for nk in nested:
                                        nv = nested[nk]
                                        if isinstance(nv, str) and len(nv) > 200:
                                            print(f"       {nk}: (string, {len(nv)} chars)")
                                            if nv.startswith('{'):
                                                try:
                                                    nn = json.loads(nv)
                                                    print(f"         → Nested JSON keys: {list(nn.keys()) if isinstance(nn, dict) else 'array'}")
                                                    # Look for duration
                                                    if 'duration' in str(nn):
                                                        print(f"         🎯 CONTAINS DURATION! Full: {json.dumps(nn, indent=4)[:500]}")
                                                except: pass
                                        elif 'duration' in str(nv).lower():
                                            print(f"       {nk}: {str(nv)[:200]}")
                                        else:
                                            print(f"       {nk}: {str(nv)[:100]}")
                            except: pass
                        # Check for duration in the string
                        if 'duration' in val:
                            # Find the context around "duration"
                            idx = val.find('duration')
                            start = max(0, idx - 50)
                            end = min(len(val), idx + 100)
                            print(f"     🎯 CONTAINS 'duration': ...{val[start:end]}...")
                    elif isinstance(val, (dict, list)):
                        val_str = json.dumps(val)
                        if 'duration' in val_str:
                            print(f"   {key}: 🎯 CONTAINS DURATION")
                            print(f"     {val_str[:500]}")
                        else:
                            print(f"   {key}: {val_str[:200]}")
                    else:
                        print(f"   {key}: {val}")
            except:
                # Not JSON, print raw
                print(f"\n📋 RAW BODY (first 1000 chars):")
                print(post_data[:1000])
            
            # Search for ALL occurrences of "duration" in body
            duration_matches = list(re.finditer(r'(?:duration["\s:]+\d+|"duration"\s*:\s*\d+|\\+"duration\\+"\s*:\s*\d+)', post_data))
            if duration_matches:
                print(f"\n🎯 DURATION MATCHES ({len(duration_matches)}):")
                for m in duration_matches:
                    ctx_start = max(0, m.start() - 30)
                    ctx_end = min(len(post_data), m.end() + 30)
                    print(f"   [{m.start()}]: ...{post_data[ctx_start:ctx_end]}...")
            else:
                print(f"\n⚠️ NO 'duration' FOUND in body!")
            
            print(f"{'='*60}\n")
        
        # Continue without modification
        try: await cdp.send("Fetch.continueRequest", {"requestId": request_id})
        except: pass
    
    cdp.on("Fetch.requestPaused", on_request_paused)
    await cdp.send("Fetch.enable", {
        "patterns": [
            {"urlPattern": "*chat/completion*", "requestStage": "Request"},
            {"urlPattern": "*samantha*", "requestStage": "Request"},
            {"urlPattern": "*generate*", "requestStage": "Request"},
            {"urlPattern": "*creation*", "requestStage": "Request"},
        ]
    })
    print("✅ CDP capture active")
    
    # Type a simple short prompt (to not waste credits, use 5s default)
    prompt_text = "A cute baby dragon in forest, 9:16"
    
    for sel in ['[contenteditable="true"]', 'textarea']:
        try:
            el = await page.wait_for_selector(sel, timeout=3000)
            if el and await el.is_visible():
                await el.click()
                await page.keyboard.type(prompt_text, delay=10)
                print(f"✅ Typed prompt: '{prompt_text}'")
                break
        except: continue
    
    await asyncio.sleep(0.5)
    
    # Send
    print("Sending prompt...")
    await page.keyboard.press("Enter")
    
    # Wait a few seconds for the request to fire
    await asyncio.sleep(10)
    
    # Save captured bodies
    out_file = os.path.join(OUTDIR, "captured_completion_body.json")
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(captured_bodies, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved {len(captured_bodies)} captured bodies to: captured_completion_body.json")
    
    # Also save raw body to text file for analysis
    for i, cap in enumerate(captured_bodies):
        raw_file = os.path.join(OUTDIR, f"raw_body_{i}.txt")
        with open(raw_file, 'w', encoding='utf-8') as f:
            f.write(cap['body'])
        print(f"💾 Saved raw body {i} ({len(cap['body'])} chars)")
    
    await asyncio.sleep(3)
    await bm.cleanup_worker(wid)
    print("\nDone!")

if __name__ == '__main__':
    asyncio.run(capture_request())
