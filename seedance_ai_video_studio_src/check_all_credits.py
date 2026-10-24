import asyncio, sys, os
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL
from session_store import SessionStore

async def check_account_credits():
    bm = BrowserManager()
    ss = SessionStore()
    
    accounts = ['tungdhc', 'tunggemini', 'leviettung04', 'via_61593678305632', 'fb01']
    
    for idx, acc in enumerate(accounts):
        if not ss.has_session(acc):
            continue
        wid = 90 + idx
        print(f"\n--- Checking Account: '{acc}' (Worker #{wid}) ---")
        try:
            port = await bm.launch_temp_chrome(worker_id=wid, show_browser=True)
            browser = await bm.connect_worker(wid)
            page = browser.contexts[0].pages[0]
            
            await bm.inject_session_to_worker(wid, acc)
            await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            
            # Click 'Tạo video'
            tv_btn = await page.wait_for_selector('button:has-text("Tạo video")', timeout=5000)
            if tv_btn:
                await tv_btn.click()
                await asyncio.sleep(1.5)
                
            # Click Model
            model_btn = await page.query_selector('button:has-text("Model"), button:has-text("2.0"), button:has-text("2.5")')
            if model_btn:
                await model_btn.click()
                await asyncio.sleep(1)
                
                # Check credits info in popover or body
                body_text = await page.inner_text("body")
                lines = [l.strip() for l in body_text.splitlines() if any(w in l.lower() for w in ['tín dụng', 'điểm', 'còn', 'credit', 'seedance'])]
                print("   Credits / Model Info on UI:")
                for l in set(lines):
                    print(f"     * {l}")
                    
            await page.screenshot(path=rf"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_credits_{acc}.png")
            await bm.cleanup_worker(wid)
        except Exception as e:
            print(f"   Error checking {acc}: {e}")
            await bm.cleanup_worker(wid)

if __name__ == '__main__':
    asyncio.run(check_account_credits())
