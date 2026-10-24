"""
Debug script: Kiểm tra tại sao video chỉ 10s, ngang, không model 2.5.
"""
import asyncio, sys, os, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from session_store import SessionStore
from config import DOLA_URL

async def debug():
    bm = BrowserManager()
    ss = SessionStore()
    
    # 1. Launch temp Chrome with extension
    print("1. Launching temp Chrome with extension...")
    port = await bm.launch_temp_chrome(worker_id=5, show_browser=True)
    print(f"   Port: {port}")
    
    # 2. Connect via Playwright
    print("2. Connecting Playwright...")
    browser = await bm.connect_worker(5)
    page = browser.contexts[0].pages[0]
    
    # 3. Inject session
    account_name = 'tunggemini'
    print(f"3. Injecting session for: {account_name}")
    await bm.inject_session_to_worker(5, account_name)
    
    # 4. Navigate to Dola
    print("4. Navigating to Dola...")
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(4)
    
    # 5. Check if extension inject.js loaded
    print("5. Checking extension inject.js...")
    check = await page.evaluate("""
        (() => {
            return {
                dolaDur_loaded: !!window.__dolaDur_loaded,
                setDolaBypass: typeof window.__setDolaBypass,
                clearDolaLinks: typeof window.__clearDolaWatermarkLinks,
                bypassActive_localStorage: localStorage.getItem('__dolaDurBypass'),
                targetDur_localStorage: localStorage.getItem('__dolaTargetDur'),
                dolaDur31_localStorage: localStorage.getItem('__dolaDur31'),
            };
        })()
    """)
    print(f"   Extension status: {json.dumps(check, indent=2)}")
    
    # 6. Activate bypass
    print("6. Activating bypass (31s, model 2.5)...")
    await page.evaluate("""
        (() => {
            if (typeof window.__setDolaBypass === 'function') {
                window.__setDolaBypass(true, 31);
                console.log('[DEBUG] __setDolaBypass(true, 31) CALLED OK');
            } else {
                console.log('[DEBUG] __setDolaBypass NOT FOUND!');
            }
            try {
                localStorage.setItem('__dolaDurBypass', '1');
                localStorage.setItem('__dolaTargetDur', '31');
                localStorage.setItem('__dolaDur31', '1');
                localStorage.setItem('__dolaDur15', '1');
            } catch(e) {}
        })()
    """)
    
    # 7. F5 reload to apply
    print("7. F5 reload to apply extension hooks...")
    await page.reload(wait_until="domcontentloaded")
    await asyncio.sleep(4)
    
    # 8. Re-check after reload
    check2 = await page.evaluate("""
        (() => {
            return {
                dolaDur_loaded: !!window.__dolaDur_loaded,
                setDolaBypass: typeof window.__setDolaBypass,
                bypassActive_localStorage: localStorage.getItem('__dolaDurBypass'),
                targetDur_localStorage: localStorage.getItem('__dolaTargetDur'),
                dolaDur31_localStorage: localStorage.getItem('__dolaDur31'),
            };
        })()
    """)
    print(f"   After reload: {json.dumps(check2, indent=2)}")
    
    # 9. Re-activate after reload
    print("9. Re-activate bypass after reload...")
    await page.evaluate("""
        (() => {
            if (typeof window.__setDolaBypass === 'function') {
                window.__setDolaBypass(true, 31);
            }
            try {
                localStorage.setItem('__dolaDurBypass', '1');
                localStorage.setItem('__dolaTargetDur', '31');
                localStorage.setItem('__dolaDur31', '1');
                localStorage.setItem('__dolaDur15', '1');
            } catch(e) {}
        })()
    """)
    
    check3 = await page.evaluate("""
        (() => {
            return {
                dolaDur_loaded: !!window.__dolaDur_loaded,
                setDolaBypass: typeof window.__setDolaBypass,
                bypassActive_localStorage: localStorage.getItem('__dolaDurBypass'),
                targetDur_localStorage: localStorage.getItem('__dolaTargetDur'),
                dolaDur31_localStorage: localStorage.getItem('__dolaDur31'),
            };
        })()
    """)
    print(f"   Final: {json.dumps(check3, indent=2)}")
    
    # 10. Check page UI
    print("10. Checking page UI for Create Video mode buttons...")
    ui = await page.evaluate("""
        (() => {
            const result = [];
            document.querySelectorAll('button, div[role="button"], div[role="option"], span').forEach(el => {
                const t = (el.innerText || '').trim();
                if (t.length < 40 && (
                    t.includes('16:9') || t.includes('9:16') || t.includes('1:1') ||
                    t.includes('2.0') || t.includes('2.5') ||
                    t.includes('10s') || t.includes('5s') ||
                    t.includes('Create') || t.includes('Tạo video') ||
                    t.includes('Ratio') || t.includes('Tỷ lệ') ||
                    t.includes('Video') || t.includes('Model') ||
                    t === 'Nhanh' || t === 'Mới'
                )) {
                    result.push({tag: el.tagName, text: t});
                }
            });
            return result.slice(0, 30);
        })()
    """)
    print(f"   UI elements: {json.dumps(ui, indent=2, ensure_ascii=False)}")
    
    # 11. Clean up
    print("\n🏁 Debug complete. Closing worker Chrome...")
    await bm.cleanup_worker(5)

if __name__ == '__main__':
    asyncio.run(debug())
