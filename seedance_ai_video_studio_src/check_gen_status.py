import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9258')
        page = browser.contexts[0].pages[0]
        body = await page.inner_text('body')
        for kw in ['Đang tạo', 'generating', 'creating', 'giới hạn', 'Seedance 2.5', '4 lượt', 'chờ', 'video']:
            lower_body = body.lower()
            lower_kw = kw.lower()
            idx = lower_body.find(lower_kw)
            if idx >= 0:
                snippet = body[max(0,idx-30):idx+60].replace('\n', ' ')
                print(f'Found "{kw}" → ...{snippet}...')

asyncio.run(check())
