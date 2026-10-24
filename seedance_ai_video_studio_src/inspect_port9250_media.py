import asyncio, sys, json
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        res = await page.evaluate("""
            (() => {
                const list = [];
                document.querySelectorAll('img, video, source, [class*="video"], [class*="player"]').forEach(el => {
                    list.push({
                        tag: el.tagName,
                        src: el.src || el.getAttribute('src') || '',
                        className: (el.className || '').toString()
                    });
                });
                return list;
            })()
        """)
        print('Media elements in DOM:', json.dumps(res, indent=2))

if __name__ == '__main__':
    asyncio.run(inspect())
