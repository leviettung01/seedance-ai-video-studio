"""
Detailed debug: Check if inject.js is ACTUALLY hooking window.fetch properly.
Launch Chrome, inject, navigate, and test with a mock fetch.
"""
import asyncio, sys, os, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL, EXTENSION_DIR

async def debug():
    bm = BrowserManager()
    worker_id = 9
    
    print("1. Launch Chrome...")
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    print(f"   Port: {port}")
    
    print("2. Connect Playwright...")
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    print("3. Inject session for fb01...")
    await bm.inject_session_to_worker(worker_id, 'fb01')
    
    # 4. Set localStorage BEFORE inject
    print("4. Navigate to Dola...")
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    
    # 5. Set localStorage
    print("5. Set localStorage keys...")
    await page.evaluate("""
        (() => {
            localStorage.setItem('__dolaDurBypass', '1');
            localStorage.setItem('__dolaTargetDur', '31');
            localStorage.setItem('__dolaDur31', '1');
            localStorage.setItem('__dolaDur15', '1');
        })()
    """)
    
    # 6. Read and inject inject.js file
    inject_path = os.path.join(EXTENSION_DIR, "inject.js")
    print(f"6. Reading inject.js from: {inject_path}")
    with open(inject_path, "r", encoding="utf-8") as f:
        inject_content = f.read()
    print(f"   inject.js size: {len(inject_content)} chars")
    
    # Also add_init_script for future navigations
    await page.context.add_init_script(path=inject_path)
    
    # Evaluate inject.js directly on current page
    print("7. Evaluating inject.js on current page...")
    try:
        await page.evaluate(inject_content)
        print("   ✅ inject.js evaluated successfully")
    except Exception as e:
        print(f"   ❌ inject.js evaluate error: {e}")
    
    # 8. Set bypass
    print("8. Calling __setDolaBypass(true, 31)...")
    await page.evaluate("""
        (() => {
            if (typeof window.__setDolaBypass === 'function') {
                window.__setDolaBypass(true, 31);
                console.log('__setDolaBypass(true, 31) called');
            } else {
                console.log('__setDolaBypass NOT found!');
            }
        })()
    """)
    
    # 9. Check flags
    check = await page.evaluate("""
        (() => ({
            dolaDur_loaded: !!window.__dolaDur_loaded,
            setDolaBypass: typeof window.__setDolaBypass,
            fetchIsHooked: window.fetch.toString().includes('originalFetch') || window.fetch.toString().includes('isTargetUrl') || window.fetch.toString().length > 200,
            fetchLength: window.fetch.toString().length,
            fetchStart: window.fetch.toString().substring(0, 200),
        }))()
    """)
    print(f"9. Extension flags: {json.dumps(check, indent=2)}")
    
    # 10. F5 reload to test add_init_script
    print("10. F5 reload...")
    await page.reload(wait_until="domcontentloaded")
    await asyncio.sleep(3)
    
    # Re-activate bypass
    await page.evaluate("""
        (() => {
            if (typeof window.__setDolaBypass === 'function') {
                window.__setDolaBypass(true, 31);
            }
            localStorage.setItem('__dolaDurBypass', '1');
            localStorage.setItem('__dolaTargetDur', '31');
            localStorage.setItem('__dolaDur31', '1');
            localStorage.setItem('__dolaDur15', '1');
        })()
    """)
    
    check2 = await page.evaluate("""
        (() => ({
            dolaDur_loaded: !!window.__dolaDur_loaded,
            setDolaBypass: typeof window.__setDolaBypass,
            fetchIsHooked: window.fetch.toString().includes('originalFetch') || window.fetch.toString().includes('isTargetUrl') || window.fetch.toString().length > 200,
            fetchLength: window.fetch.toString().length,
            fetchStart: window.fetch.toString().substring(0, 200),
            bypassLS: localStorage.getItem('__dolaDurBypass'),
            durLS: localStorage.getItem('__dolaTargetDur'),
        }))()
    """)
    print(f"11. After reload: {json.dumps(check2, indent=2)}")
    
    # 12. Mock test: create a fetch request with duration and check if it gets modified
    print("12. Mock test: intercept a fake /chat/completion request...")
    mock_result = await page.evaluate("""
        (async () => {
            // Override fetch temporarily to capture the modified body
            const lastModifiedBody = [];
            const hookedFetch = window.fetch;
            
            // We can't easily test the hook without actually sending, but we can check console
            // Let's check if the hook function code mentions duration replacement
            const hookCode = hookedFetch.toString();
            
            return {
                hookCodeLength: hookCode.length,
                hasDurationRegex: hookCode.includes('duration'),
                hasOriginalFetch: hookCode.includes('originalFetch'),
                hasIsTargetUrl: hookCode.includes('isTargetUrl'),
                hasGetBypassActive: hookCode.includes('getBypassActive') || hookCode.includes('bypassActive'),
                hookCodePreview: hookCode.substring(0, 500),
            };
        })()
    """)
    print(f"   Mock result: {json.dumps(mock_result, indent=2)}")
    
    # Cleanup
    print("\n🏁 Done. Closing...")
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(debug())
