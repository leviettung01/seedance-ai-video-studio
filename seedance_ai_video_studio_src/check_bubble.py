"""Check full text of the latest response bubble."""
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9281')
        page = browser.contexts[0].pages[0]
        bubbles = await page.evaluate("""
            (() => {
                const els = Array.from(document.querySelectorAll("[class*='message'], [class*='content'], [class*='bubble'], p"));
                return els.map(e => e.innerText ? e.innerText.trim() : '').filter(t => t.length > 20);
            })()
        """)
        print(f"Total bubbles: {len(bubbles)}")
        for b in bubbles[-3:]:
            print(f"--- BUBBLE ---\n{b}")

if __name__ == '__main__':
    asyncio.run(check())
