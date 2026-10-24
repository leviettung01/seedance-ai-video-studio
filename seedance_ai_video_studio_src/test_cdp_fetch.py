"""
Test CDP Fetch.enable + Fetch.requestPaused interception on CDP Chrome.
"""
import asyncio, sys, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

intercepted_count = 0

async def test():
    global intercepted_count
    bm = BrowserManager()
    worker_id = 11
    
    print("1. Launch Chrome...")
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    
    print("2. Connect Playwright via CDP...")
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    print("3. Inject session fb01...")
    await bm.inject_session_to_worker(worker_id, 'fb01')
    
    # 4. Use CDP session to enable Fetch interception
    print("4. Getting CDP session...")
    cdp = await page.context.new_cdp_session(page)
    
    # Enable Fetch domain with pattern matching
    print("5. Enabling CDP Fetch with patterns...")
    await cdp.send("Fetch.enable", {
        "patterns": [
            {"urlPattern": "*chat/completion*", "requestStage": "Request"},
            {"urlPattern": "*im/message*", "requestStage": "Request"},
            {"urlPattern": "*im/chain*", "requestStage": "Request"},
        ]
    })
    
    # Set up event handler
    async def on_request_paused(params):
        global intercepted_count
        request_id = params.get("requestId", "")
        url = params.get("request", {}).get("url", "")
        method = params.get("request", {}).get("method", "")
        post_data = params.get("request", {}).get("postData", "")
        
        intercepted_count += 1
        print(f"\n🎯 CDP INTERCEPTED #{intercepted_count}:")
        print(f"   URL: {url[:100]}")
        print(f"   Method: {method}")
        print(f"   PostData length: {len(post_data)}")
        
        if 'duration' in post_data:
            import re
            match = re.search(r'duration["\\\s:]*(\d+)', post_data)
            if match:
                print(f"   Duration found: {match.group(1)}")
        
        # Continue request without modification for now
        await cdp.send("Fetch.continueRequest", {"requestId": request_id})
    
    cdp.on("Fetch.requestPaused", on_request_paused)
    print("   ✅ CDP Fetch handlers installed")
    
    # 5. Navigate to Dola
    print("6. Navigate to Dola...")
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)
    
    print(f"7. Page loaded. Intercepted so far: {intercepted_count}")
    print("8. Waiting 15s for background requests...")
    await asyncio.sleep(15)
    
    print(f"\n=== Total intercepted: {intercepted_count} ===")
    
    # Cleanup
    try:
        await cdp.send("Fetch.disable")
    except Exception:
        pass
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(test())
