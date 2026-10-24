"""Check video elements and localStorage on port 9281."""
import asyncio, sys, json
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9281')
        page = browser.contexts[0].pages[0]
        
        # Check videos
        videos = await page.evaluate("""
            (() => {
                const vids = Array.from(document.querySelectorAll('video'));
                return vids.map(v => ({
                    src: v.src,
                    currentSrc: v.currentSrc,
                    duration: v.duration,
                    videoWidth: v.videoWidth,
                    videoHeight: v.videoHeight,
                }));
            })()
        """)
        print(f"Videos in DOM: {len(videos)}")
        for v in videos:
            print(f"  {v}")
            
        # Check localStorage
        ls = await page.evaluate("""
            (() => ({
                dolaLinks: localStorage.getItem('__dolaWatermarkLinks'),
                seedanceLinks: localStorage.getItem('__seedanceLinks'),
            }))()
        """)
        print(f"LocalStorage links: {ls}")

if __name__ == '__main__':
    asyncio.run(check())
