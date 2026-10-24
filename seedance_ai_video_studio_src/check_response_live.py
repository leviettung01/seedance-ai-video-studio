"""Check Dola response text on port 9281."""
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9290')
        page = browser.contexts[0].pages[0]
        body = await page.inner_text('body')
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        tail = " | ".join(lines[-20:])
        print(f"Tail: {tail}")

if __name__ == '__main__':
    asyncio.run(check())
