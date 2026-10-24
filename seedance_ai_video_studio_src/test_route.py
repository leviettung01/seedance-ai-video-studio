"""
Quick test: Can page.route() intercept requests on a CDP-connected Chrome?
"""
import asyncio, sys
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

intercepted = []

async def test():
    bm = BrowserManager()
    worker_id = 10
    
    print("1. Launch Chrome...")
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    
    print("2. Connect Playwright via CDP...")
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    print("3. Inject session fb01...")
    await bm.inject_session_to_worker(worker_id, 'fb01')
    
    # 4. Install route handler
    async def test_handler(route):
        req = route.request
        url = req.url
        method = req.method
        body = req.post_data or ""
        
        is_target = any(p in url for p in ['/chat/completion', '/im/message', '/im/chain'])
        
        if is_target and method == "POST":
            intercepted.append({
                'url': url[:100],
                'method': method,
                'bodyLen': len(body),
                'bodyPreview': body[:300],
                'hasDuration': 'duration' in body,
            })
            print(f"🎯 INTERCEPTED: {method} {url[:80]} (body: {len(body)} chars)")
            if 'duration' in body:
                import re
                match = re.search(r'duration["\\\s:]*(\d+)', body)
                if match:
                    print(f"   Duration found: {match.group(1)}")
                    # Ép duration
                    modified = re.sub(r'(\\*"?duration\\*"?\s*:\s*\\*"?\s*)(\d+)', 
                                     lambda m: m.group(1) + '31', body)
                    print(f"   Modified body: ...{modified[max(0,body.find('duration')-20):body.find('duration')+40]}...")
                    await route.continue_(post_data=modified)
                    return
        
        await route.continue_()
    
    print("4. Installing page.route() handlers...")
    try:
        await page.route("**/*chat/completion*", test_handler)
        await page.route("**/*im/message*", test_handler) 
        await page.route("**/*im/chain*", test_handler)
        print("   ✅ Routes installed")
    except Exception as e:
        print(f"   ❌ Route install failed: {e}")
    
    # 5. Navigate to Dola
    print("5. Navigate to Dola...")
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    
    print("6. Waiting 10s for any background requests...")
    await asyncio.sleep(10)
    
    print(f"\n=== Intercepted {len(intercepted)} target requests ===")
    for r in intercepted:
        print(f"  {r}")
    
    print("\n🏁 Done.")
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(test())
