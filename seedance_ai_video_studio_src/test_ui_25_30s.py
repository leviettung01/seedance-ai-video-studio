import asyncio, sys, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

async def test_ui_options():
    bm = BrowserManager()
    worker_id = 70
    account_name = 'tungkyluatbanthan'
    
    print(f"1. Launching browser for {account_name}...")
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    print("2. Injecting session...")
    await bm.inject_session_to_worker(worker_id, account_name)
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    
    # Dismiss cookie overlay
    try:
        ok_btn = await page.query_selector('button:has-text("OK")')
        if ok_btn: await ok_btn.click()
    except Exception: pass
    
    # 3. Click 'Tạo video'
    print("3. Clicking 'Tạo video'...")
    tv_btn = await page.wait_for_selector('button:has-text("Tạo video")', timeout=5000)
    if tv_btn:
        await tv_btn.click()
        await asyncio.sleep(1.5)
        
    # 4. Click Model dropdown
    print("4. Inspecting Model dropdown...")
    model_btn = None
    for sel in ['button:has-text("Model")', 'button:has-text("2.0")', 'button:has-text("2.5")']:
        el = await page.query_selector(sel)
        if el:
            model_btn = el
            break
            
    if model_btn:
        print(f"   Current Model text: '{await model_btn.inner_text()}'")
        await model_btn.click()
        await asyncio.sleep(1)
        
        # List all options in popover
        model_options = await page.evaluate("""
            (() => {
                const items = Array.from(document.querySelectorAll('div[role="option"], li, div[class*="item"], div[class*="option"], div[class*="menu"] *'));
                return items.map(e => (e.innerText || '').trim()).filter(t => t.length > 0 && t.length < 50);
            })()
        """)
        print(f"   Model Popover Options: {list(set(model_options))}")
        
        # Click 2.5
        clicked_25 = await page.evaluate("""
            (() => {
                const all = Array.from(document.querySelectorAll('*'));
                for (const el of all) {
                    const txt = (el.innerText || '').trim();
                    if (txt === 'Seedance 2.5' || txt === '2.5' || txt.includes('2.5')) {
                        el.click();
                        if (el.parentElement) el.parentElement.click();
                        return txt;
                    }
                }
                return null;
            })()
        """)
        print(f"   Clicked 2.5: {clicked_25}")
        await asyncio.sleep(1.5)
        print(f"   Model text after click: '{await model_btn.inner_text()}'")
        
    # 5. Inspect Duration dropdown
    print("\n5. Inspecting Duration dropdown...")
    dur_btn = None
    for sel in ['button:has-text("10s")', 'button:has-text("15s")', 'button:has-text("30s")', 'button:has-text("5s")']:
        el = await page.query_selector(sel)
        if el:
            dur_btn = el
            break
            
    if dur_btn:
        print(f"   Current Duration text: '{await dur_btn.inner_text()}'")
        await dur_btn.click()
        await asyncio.sleep(1)
        
        dur_options = await page.evaluate("""
            (() => {
                const items = Array.from(document.querySelectorAll('div[role="option"], li, div[class*="item"], div[class*="option"], div[class*="menu"] *'));
                return items.map(e => (e.innerText || '').trim()).filter(t => t.length > 0 && t.length < 30);
            })()
        """)
        print(f"   Duration Popover Options: {list(set(dur_options))}")
        
        # Click 30s
        clicked_30 = await page.evaluate("""
            (() => {
                const all = Array.from(document.querySelectorAll('*'));
                for (const el of all) {
                    const txt = (el.innerText || '').trim();
                    if (txt === '30s' || txt === '30 giây' || txt.includes('30s')) {
                        el.click();
                        if (el.parentElement) el.parentElement.click();
                        return txt;
                    }
                }
                return null;
            })()
        """)
        print(f"   Clicked 30s: {clicked_30}")
        await asyncio.sleep(1.5)
        print(f"   Duration text after click: '{await dur_btn.inner_text()}'")

    # Take screenshot of UI state
    ss_path = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_25_30s_ui.png"
    await page.screenshot(path=ss_path)
    print(f"\nScreenshot saved to: {ss_path}")
    
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(test_ui_options())
