import asyncio, sys, os
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from config import DOLA_URL

async def inspect():
    bm = BrowserManager()
    port = await bm.launch_temp_chrome(worker_id=86, show_browser=True)
    browser = await bm.connect_worker(86)
    page = browser.contexts[0].pages[0]
    await bm.inject_session_to_worker(86, 'tungkyluatbanthan')
    await page.goto(DOLA_URL, wait_until='domcontentloaded', timeout=30000)
    await asyncio.sleep(3)
    
    # Click 'Video cyberpunk'
    cyber_item = await page.wait_for_selector('text="Video cyberpunk"', timeout=5000)
    if cyber_item:
        await cyber_item.click()
        await asyncio.sleep(4)
        
    await page.screenshot(path=r'C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\inspect_cyberpunk_chat.png')
    
    # Check if there is video in this chat
    html = await page.content()
    print('Contains video tag:', '<video' in html)
    print('Contains mp4:', '.mp4' in html)
    print('Contains cici_ai:', 'cici_ai' in html)
    print('Contains tos:', 'tos' in html)
    
    # Extract all links and sources
    urls = await page.evaluate("""
        (() => {
            const list = [];
            document.querySelectorAll('video, source, a, img').forEach(el => {
                if (el.src) list.push(el.src);
                if (el.href) list.push(el.href);
            });
            return list;
        })()
    """)
    print("Found elements with URLs:")
    for u in urls:
        if 'video' in u or 'tos' in u or 'mp4' in u:
            print("  Video URL found:", u)
            
    await bm.cleanup_worker(86)

if __name__ == '__main__':
    asyncio.run(inspect())
