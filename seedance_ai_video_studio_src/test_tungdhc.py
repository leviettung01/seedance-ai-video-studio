import asyncio, sys, os
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from browser_manager import BrowserManager
from dola_automation import DolaAutomation
from config import DOLA_URL

async def test():
    bm = BrowserManager()
    dola = DolaAutomation()
    wid = 96
    print("Launching browser for tungdhc...")
    port = await bm.launch_temp_chrome(worker_id=wid, show_browser=True)
    browser = await bm.connect_worker(wid)
    page = browser.contexts[0].pages[0]
    await bm.inject_session_to_worker(wid, 'tungdhc')
    await page.goto(DOLA_URL, wait_until='domcontentloaded', timeout=30000)
    await asyncio.sleep(3)
    
    # Try submit
    res = await dola.execute_generation_flow(
        page=page,
        prompt='A tiny cute glowing baby dragon eating glowing berry in mystical forest, 8k render, cinematic 9:16.',
        aspect_ratio='9:16',
        image_path='',
        mode='standard',
        duration_target=31,
        model_version='2.5',
        progress_callback=lambda m: print(f"  [Progress] {m}")
    )
    print('Result URL:', res)
    await page.screenshot(path=r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_tungdhc_gen.png")
    await bm.cleanup_worker(wid)

if __name__ == '__main__':
    asyncio.run(test())
