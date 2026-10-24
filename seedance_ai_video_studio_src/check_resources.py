"""Check performance resource timing on port 9281 to see if video URL loaded."""
import asyncio, sys, json
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9281')
        page = browser.contexts[0].pages[0]
        
        # Check all resource entries
        resources = await page.evaluate("""
            (() => {
                const entries = performance.getEntriesByType('resource');
                return entries.map(e => ({
                    name: e.name.substring(0, 150),
                    initiatorType: e.initiatorType,
                    transferSize: e.transferSize,
                    duration: e.duration,
                })).filter(e => e.name.includes('video') || e.name.includes('tos') || e.name.includes('.mp4') || e.name.includes('im/'));
            })()
        """)
        print(f"Matching network resources: {len(resources)}")
        for r in resources[-10:]:
            print(f"  {r}")

if __name__ == '__main__':
    asyncio.run(check())
