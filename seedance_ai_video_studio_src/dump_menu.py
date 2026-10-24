import asyncio, sys, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

async def dump():
    bm = BrowserManager()
    port = await bm.launch_temp_chrome(worker_id=73, show_browser=True)
    browser = await bm.connect_worker(73)
    page = browser.contexts[0].pages[0]
    await bm.inject_session_to_worker(73, 'tungkyluatbanthan')
    await page.goto(DOLA_URL, wait_until='domcontentloaded', timeout=30000)
    await asyncio.sleep(3)
    
    try:
        ok_btn = await page.query_selector('button:has-text("OK")')
        if ok_btn: await ok_btn.click()
    except Exception: pass
    
    tv_btn = await page.wait_for_selector('button:has-text("Tạo video")', timeout=5000)
    if tv_btn:
        await tv_btn.click()
        await asyncio.sleep(1.5)
    
    # 1. Click Model button
    model_btn = await page.query_selector('button:has-text("Model"), button:has-text("2.0")')
    if model_btn:
        print("Clicking Model button...")
        await model_btn.click()
        await asyncio.sleep(1)
        
        items = await page.evaluate('''() => {
            const menu = document.querySelector('[role="menu"], [data-radix-menu-content]');
            if (!menu) return [];
            return Array.from(menu.querySelectorAll('[role="menuitem"], [data-slot="dropdown-menu-item"]')).map(el => ({
                text: el.innerText ? el.innerText.trim() : '',
                tag: el.tagName,
                role: el.getAttribute('role'),
                slot: el.getAttribute('data-slot'),
                class: el.className
            }));
        }''')
        print("MENU ITEMS IN MODEL DROPDOWN:")
        for it in items:
            print(f"  [{it['tag']}] role={it['role']} text={repr(it['text'])}")
            
        # Click the 2.5 item
        clicked = await page.evaluate('''() => {
            const menu = document.querySelector('[role="menu"], [data-radix-menu-content]');
            if (!menu) return null;
            const items = Array.from(menu.querySelectorAll('[role="menuitem"], [data-slot="dropdown-menu-item"]'));
            for (const el of items) {
                if (el.innerText && el.innerText.includes('2.5')) {
                    el.click();
                    return el.innerText.trim();
                }
            }
            return null;
        }''')
        print(f"\n--> Clicked Model 2.5: {repr(clicked)}")
        await asyncio.sleep(2)
        
        new_model_text = await model_btn.inner_text()
        print(f"--> Model button text after selection: {repr(new_model_text)}")

    # 2. Click Duration button
    print("\nInspecting Duration button...")
    dur_btn = await page.query_selector('button:has-text("10s"), button:has-text("5s"), button:has-text("15s"), button:has-text("30s"), button:has-text("Thời lượng")')
    if dur_btn:
        print(f"Current duration text: {repr(await dur_btn.inner_text())}")
        await dur_btn.click()
        await asyncio.sleep(1)
        
        dur_items = await page.evaluate('''() => {
            const menu = document.querySelector('[role="menu"], [data-radix-menu-content]');
            if (!menu) return [];
            return Array.from(menu.querySelectorAll('[role="menuitem"], [data-slot="dropdown-menu-item"]')).map(el => ({
                text: el.innerText ? el.innerText.trim() : '',
                tag: el.tagName,
                role: el.getAttribute('role')
            }));
        }''')
        print("MENU ITEMS IN DURATION DROPDOWN:")
        for it in dur_items:
            print(f"  [{it['tag']}] role={it['role']} text={repr(it['text'])}")
            
    await page.screenshot(path=r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_real_25.png")
    await bm.cleanup_worker(73)

if __name__ == '__main__':
    asyncio.run(dump())
