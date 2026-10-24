import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from dola_automation import DolaAutomation
from session_store import SessionStore
from config import DOLA_URL

async def test():
    bm = BrowserManager()
    da = DolaAutomation()
    ss = SessionStore()

    account_name = 'leviettung04'
    print(f'1. Launching temp Chrome for {account_name}...', flush=True)
    port = await bm.launch_temp_chrome(0, show_browser=True)
    print(f'   Port: {port}', flush=True)

    print('2. Connecting via Playwright...', flush=True)
    browser = await bm.connect_worker(0)
    if not browser:
        print('   Failed to connect browser!', flush=True)
        return

    print('3. Injecting session...', flush=True)
    ok = await bm.inject_session_to_worker(0, account_name)
    print(f'   Injected: {ok}', flush=True)

    page = await bm.get_worker_page(0)
    print('4. Navigating to Dola...', flush=True)
    await page.goto(DOLA_URL, wait_until='domcontentloaded', timeout=30000)
    await asyncio.sleep(3)

    print('5. Checking login status...', flush=True)
    st = await da.check_login_status(page)
    print(f'   Status: {st}', flush=True)

    print('6. Testing UI interactions (Create Video, Ratio, Model)...', flush=True)
    await da.dismiss_modals_and_overlays(page)
    
    # Check what buttons exist on Dola UI
    buttons_info = await page.evaluate("""
        (() => {
            return Array.from(document.querySelectorAll('button, div[role="button"]')).map(b => (b.innerText || '').trim()).filter(t => t.length > 0);
        })()
    """)
    print(f'   Found {len(buttons_info)} buttons: {buttons_info[:15]}', flush=True)

    screenshot_path = os.path.abspath('scratch_test_dola.png')
    await page.screenshot(path=screenshot_path)
    print(f'   Screenshot saved to: {screenshot_path}', flush=True)

    await bm.cleanup_worker(0)

if __name__ == '__main__':
    asyncio.run(test())
