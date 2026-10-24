import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        # Get all interactive buttons / cards in the chat
        info = await page.evaluate("""
            (() => {
                const results = [];
                // Look for cards, buttons, images, download buttons
                document.querySelectorAll('div, button, a').forEach(el => {
                    const text = (el.innerText || '').trim();
                    const cl = el.className || '';
                    if (text.includes('Đã tạo xong') || text.includes('Tải') || text.includes('Xem') || text.includes('Phát') || text.includes('Play') || text.includes('Download') || cl.includes('video') || cl.includes('card')) {
                        results.push({
                            tag: el.tagName,
                            text: text.substring(0, 100),
                            className: cl.substring(0, 100),
                            html: el.outerHTML.substring(0, 200)
                        });
                    }
                });
                return results.slice(-15);
            })()
        """)
        for item in info:
            print(f"[{item['tag']}] text: {item['text']} | class: {item['className']}")
            print(f"   html: {item['html']}\n")

if __name__ == '__main__':
    asyncio.run(inspect())
