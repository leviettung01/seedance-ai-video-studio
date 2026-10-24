"""Quick check: which accounts have credits left by navigating to create-image page."""
import asyncio, sys, os
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from browser_manager import BrowserManager

CREATE_IMAGE_URL = "https://www.dola.com/chat/create-image"
ACCOUNTS = ['tungdhc', 'leviettung04', 'leviettung05']

async def check_credits():
    bm = BrowserManager()
    
    for i, account in enumerate(ACCOUNTS):
        wid = 110 + i
        print(f"\n--- Checking '{account}' (worker {wid}) ---")
        try:
            port = await bm.launch_temp_chrome(worker_id=wid, show_browser=False)
            browser = await bm.connect_worker(wid)
            page = browser.contexts[0].pages[0]
            await bm.inject_session_to_worker(wid, account)
            await page.goto(CREATE_IMAGE_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
            
            # Check page text for quota info
            body_text = await page.evaluate("document.body.innerText.substring(0, 500)")
            if 'giới hạn' in body_text.lower() or 'limit' in body_text.lower():
                print(f"  ❌ QUOTA EXHAUSTED")
            else:
                print(f"  ✅ Appears to have credits")
            
            # Check for login
            if 'đăng nhập' in body_text.lower() or 'login' in body_text.lower() or 'sign in' in body_text.lower():
                print(f"  ⚠️ NOT LOGGED IN")
            
            # Look for credit indicators
            credit_info = await page.evaluate("""() => {
                const els = document.querySelectorAll('span, div, p');
                const results = [];
                for (const el of els) {
                    const t = (el.textContent || '').trim();
                    if ((t.includes('điểm') || t.includes('credit') || t.includes('tín dụng') || t.includes('lượt')) && t.length < 100) {
                        results.push(t);
                    }
                }
                return results.slice(0, 5);
            }""")
            if credit_info:
                for info in credit_info:
                    print(f"  💰 {info}")
            
            await bm.cleanup_worker(wid)
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            try: await bm.cleanup_worker(wid)
            except: pass

if __name__ == '__main__':
    asyncio.run(check_credits())
