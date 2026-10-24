"""
Inspect Dola UI for account leviettung05: check quota, controls, model options, ratio options, fast mode.
"""
import asyncio, sys, os
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

async def inspect():
    bm = BrowserManager()
    worker_id = 20
    account_name = 'leviettung05'
    
    print(f"Launching worker #{worker_id} for {account_name}...")
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    print(f"Injecting session {account_name}...")
    injected = await bm.inject_session_to_worker(worker_id, account_name)
    print(f"Injected: {injected}")
    
    print("Navigating to Dola...")
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(4)
    
    # Check body text for quota and buttons
    body = await page.inner_text('body')
    print("\n--- BODY SNIPPET ---")
    print(body[-1000:].replace('\n', ' | '))
    
    # Check all buttons
    buttons = await page.evaluate("""
        (() => {
            const btns = Array.from(document.querySelectorAll('button, div[role="button"], a'));
            return btns.map(b => ({
                tag: b.tagName,
                text: (b.innerText || '').trim(),
                aria: b.getAttribute('aria-label') || '',
                class: b.className || '',
            })).filter(b => b.text.length > 0 && b.text.length < 50);
        })()
    """)
    print("\n--- ALL BUTTONS ON PAGE ---")
    for b in buttons:
        print(f"  [{b['tag']}] '{b['text']}' (aria: {b['aria']})")
        
    # Take screenshot
    ss_path = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_leviettung05.png"
    await page.screenshot(path=ss_path)
    print(f"\nScreenshot saved to: {ss_path}")
    
    await bm.cleanup_worker(worker_id)

if __name__ == '__main__':
    asyncio.run(inspect())
