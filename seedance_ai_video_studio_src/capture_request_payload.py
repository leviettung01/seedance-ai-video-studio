import asyncio, sys, os, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from browser_manager import BrowserManager
from config import DOLA_URL

async def capture():
    bm = BrowserManager()
    wid = 100
    account_name = 'tunggemini'
    
    print("1. Launching browser for request capture...")
    port = await bm.launch_temp_chrome(worker_id=wid, show_browser=True)
    browser = await bm.connect_worker(wid)
    page = browser.contexts[0].pages[0]
    
    # Listen to network requests
    captured_requests = []
    
    async def on_request(req):
        url = req.url
        if any(k in url for k in ['/completion', '/message', '/chain', '/chat', '/video', '/create', '/draft']):
            if req.method == 'POST':
                pd = req.post_data
                if pd and len(pd) > 10:
                    captured_requests.append({
                        "url": url,
                        "method": req.method,
                        "headers": req.headers,
                        "post_data": pd
                    })
                    print(f"\n📡 [CAPTURED POST] {url}")
                    try:
                        parsed = json.loads(pd)
                        print(json.dumps(parsed, indent=2, ensure_ascii=False)[:1500])
                    except Exception:
                        print(pd[:1500])
                        
    page.on("request", on_request)
    
    await bm.inject_session_to_worker(wid, account_name)
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    
    # Dismiss cookie overlay
    try:
        ok_btn = await page.query_selector('button:has-text("OK")')
        if ok_btn: await ok_btn.click()
    except Exception: pass
    
    # Click 'Tạo video'
    print("2. Clicking 'Tạo video'...")
    tv_btn = await page.wait_for_selector('button:has-text("Tạo video")', timeout=5000)
    if tv_btn:
        await tv_btn.click()
        await asyncio.sleep(1.5)
        
    # Click Model -> Select 2.5
    print("3. Selecting Model 2.5...")
    model_btn = await page.query_selector('button:has-text("Model"), button:has-text("2.0")')
    if model_btn:
        await model_btn.click()
        await asyncio.sleep(1)
        await page.evaluate('''() => {
            const menu = document.querySelector('[role="menu"], [data-radix-menu-content]');
            if (!menu) return;
            const items = Array.from(menu.querySelectorAll('[role="menuitem"], [data-slot="dropdown-menu-item"]'));
            for (const el of items) {
                if (el.innerText && el.innerText.includes('2.5')) {
                    el.click();
                    break;
                }
            }
        }''')
        await asyncio.sleep(1.5)
        
    # Input prompt
    print("4. Typing prompt...")
    input_box = await page.query_selector("textarea, [contenteditable='true']")
    if input_box:
        await input_box.fill("A majestic soaring phoenix over golden clouds, 8k render, cinematic 9:16")
        await asyncio.sleep(1)
        print("5. Sending prompt...")
        await page.keyboard.press("Enter")
        await asyncio.sleep(5)
        
    # Save captured requests to file
    with open(r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\captured_requests.json", "w", encoding="utf-8") as f:
        json.dump(captured_requests, f, indent=2, ensure_ascii=False)
        
    print(f"\n✅ Captured {len(captured_requests)} requests! Saved to captured_requests.json")
    await bm.cleanup_worker(wid)

if __name__ == '__main__':
    asyncio.run(capture())
