import asyncio, sys, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

async def inspect_dropdown_dom():
    bm = BrowserManager()
    worker_id = 72
    account_name = 'tungkyluatbanthan'
    
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    await bm.inject_session_to_worker(worker_id, account_name)
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    
    try:
        ok_btn = await page.query_selector('button:has-text("OK")')
        if ok_btn: await ok_btn.click()
    except Exception: pass
    
    tv_btn = await page.wait_for_selector('button:has-text("Tạo video")', timeout=5000)
    if tv_btn:
        await tv_btn.click()
        await asyncio.sleep(1.5)
        
    model_btn = None
    for sel in ['button:has-text("Model")', 'button:has-text("2.0")', 'button:has-text("2.5")']:
        el = await page.query_selector(sel)
        if el:
            model_btn = el
            break
            
    if model_btn:
        await model_btn.click()
        await asyncio.sleep(1)
        
        # Dump all popup menu items in detail
        details = await page.evaluate("""
            (() => {
                const results = [];
                // Look for popover/dropdown containers
                const popovers = document.querySelectorAll('[class*="popover"], [class*="dropdown"], [class*="menu"], [class*="select"], [role="listbox"], [role="menu"]');
                popovers.forEach(p => {
                    results.push({
                        popoverClass: p.className,
                        html: p.outerHTML.substring(0, 1500)
                    });
                });
                return results;
            })()
        """)
        print("POPOVER DETAILS:")
        print(json.dumps(details, indent=2, ensure_ascii=False))
        
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(inspect_dropdown_dom())
