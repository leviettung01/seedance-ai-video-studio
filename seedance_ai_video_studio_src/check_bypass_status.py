import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9258')
        page = browser.contexts[0].pages[0]
        body = await page.inner_text('body')
        tail = body[-600:].replace('\n', ' ')
        print(f"URL: {page.url}")
        print(f"Tail: {tail}")

asyncio.run(check())
