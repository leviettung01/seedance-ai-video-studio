"""
Inspect Create Video mode UI on leviettung05:
Click 'Tạo video', inspect Ratio buttons, Model buttons, Duration buttons.
"""
import asyncio, sys, os
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

async def inspect():
    bm = BrowserManager()
    worker_id = 21
    account_name = 'leviettung05'
    
    print(f"Launching worker #{worker_id} for {account_name}...")
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    await bm.inject_session_to_worker(worker_id, account_name)
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    
    # Dismiss cookie OK button if any
    try:
        ok_btn = await page.query_selector('button:has-text("OK")')
        if ok_btn:
            await ok_btn.click()
            await asyncio.sleep(1)
    except Exception:
        pass
        
    # Click 'Tạo video'
    print("Clicking 'Tạo video'...")
    tv_btn = await page.wait_for_selector('button:has-text("Tạo video")', timeout=5000)
    if tv_btn:
        await tv_btn.click()
        await asyncio.sleep(2)
        
    # Check all buttons now
    buttons = await page.evaluate("""
        (() => {
            const btns = Array.from(document.querySelectorAll('button, div[role="button"], div[role="option"]'));
            return btns.map(b => ({
                tag: b.tagName,
                text: (b.innerText || '').trim(),
                role: b.getAttribute('role') || '',
                class: b.className || '',
            })).filter(b => b.text.length > 0 && b.text.length < 80);
        })()
    """)
    print("\n--- BUTTONS AFTER CLICKING 'Tạo video' ---")
    for b in buttons:
        print(f"  [{b['tag']}] role='{b['role']}' text='{b['text'].replace(chr(10), ' | ')}'")
        
    # Check ratio dropdown
    print("\n--- Testing Ratio Dropdown ---")
    ratio_btn = None
    for sel in ['button:has-text("Tỉ lệ")', 'button:has-text("Tỷ lệ")', 'button:has-text("16:9")', 'button:has-text("9:16")', 'button:has-text("Ratio")']:
        try:
            el = await page.query_selector(sel)
            if el:
                ratio_btn = el
                print(f"Found ratio button with selector: {sel}, text: '{await el.inner_text()}'")
                break
        except Exception:
            pass
            
    if ratio_btn:
        await ratio_btn.click()
        await asyncio.sleep(1)
        # Check popover options
        options = await page.evaluate("""
            (() => {
                const els = Array.from(document.querySelectorAll('div, span, button, li'));
                return els.map(e => e.innerText ? e.innerText.trim() : '')
                          .filter(t => ['1:1', '3:4', '4:3', '9:16', '16:9', '21:9'].includes(t));
            })()
        """)
        print(f"Ratio options found: {options}")
        
        # Click 9:16 specifically
        opt_916 = await page.evaluate("""
            (() => {
                const all = Array.from(document.querySelectorAll('*'));
                for (const el of all) {
                    if (el.children.length === 0 && el.innerText && el.innerText.trim() === '9:16') {
                        el.click();
                        return 'clicked_leaf_9:16';
                    }
                }
                return 'not_found';
            })()
        """)
        print(f"Clicked 9:16: {opt_916}")
        await asyncio.sleep(1)
        
    # Check ratio button text after selection
    if ratio_btn:
        new_text = await ratio_btn.inner_text()
        print(f"Ratio button text after selection: '{new_text}'")

    # Take screenshot
    ss_path = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_create_video_mode.png"
    await page.screenshot(path=ss_path)
    print(f"\nScreenshot saved to: {ss_path}")
    
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(inspect())
