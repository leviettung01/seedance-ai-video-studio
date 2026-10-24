import asyncio, sys, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

async def test_select_25_and_check_duration():
    bm = BrowserManager()
    worker_id = 71
    account_name = 'tungkyluatbanthan'
    
    print(f"1. Launching browser for {account_name}...")
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    print("2. Injecting session...")
    await bm.inject_session_to_worker(worker_id, account_name)
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    
    try:
        ok_btn = await page.query_selector('button:has-text("OK")')
        if ok_btn: await ok_btn.click()
    except Exception: pass
    
    print("3. Clicking 'Tạo video'...")
    tv_btn = await page.wait_for_selector('button:has-text("Tạo video")', timeout=5000)
    if tv_btn:
        await tv_btn.click()
        await asyncio.sleep(1.5)
        
    print("4. Clicking Model dropdown...")
    model_btn = None
    for sel in ['button:has-text("Model")', 'button:has-text("2.0")', 'button:has-text("2.5")']:
        el = await page.query_selector(sel)
        if el:
            model_btn = el
            break
            
    if model_btn:
        await model_btn.click()
        await asyncio.sleep(1)
        
        # Click exact item for 'Dreamina Seedance 2.5'
        clicked = await page.evaluate("""
            (() => {
                const candidates = Array.from(document.querySelectorAll('div, li, span, button'));
                for (const el of candidates) {
                    if (el.innerText && el.innerText.includes('Dreamina Seedance 2.5')) {
                        el.click();
                        return el.innerText;
                    }
                }
                return null;
            })()
        """)
        print(f"   Clicked on 2.5 item: {clicked}")
        await asyncio.sleep(2)
        print(f"   Model button text now: '{await model_btn.inner_text()}'")
        
    # Check Duration dropdown now
    print("\n5. Checking Duration dropdown when Model is 2.5...")
    dur_btn = None
    for sel in ['button:has-text("10s")', 'button:has-text("15s")', 'button:has-text("30s")', 'button:has-text("5s")', 'button:has-text("Thời lượng")']:
        el = await page.query_selector(sel)
        if el:
            dur_btn = el
            break
            
    if dur_btn:
        print(f"   Duration button text: '{await dur_btn.inner_text()}'")
        await dur_btn.click()
        await asyncio.sleep(1)
        
        dur_options = await page.evaluate("""
            (() => {
                const items = Array.from(document.querySelectorAll('div, li, span, button'));
                return items.map(e => (e.innerText || '').trim())
                            .filter(t => ['5s', '10s', '15s', '20s', '25s', '30s', '60s'].includes(t) || t.includes('giây') || t.includes('s'));
            })()
        """)
        print(f"   Duration options available for Seedance 2.5: {list(set(dur_options))}")
        
    ss_path = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_25_selected.png"
    await page.screenshot(path=ss_path)
    print(f"Screenshot saved: {ss_path}")
    
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(test_select_25_and_check_duration())
