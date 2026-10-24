import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def test_input():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        # Click 'Tạo video'
        for sel in ['button:has-text("Tạo video")', 'div:has-text("Tạo video")', 'button:has-text("Create Video")']:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    await el.click()
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass
            
        test_prompt = "Two goofy cartoon larva characters cosplaying as ninjas doing a funny martial arts action on a stylized anime wooden village rooftop at sunset, cel-shaded 2D anime style, vibrant colors, sakuga impact frames, hilarious comedic shonen anime, 9:16 vertical video"
        
        input_el = await page.wait_for_selector('textarea, [contenteditable="true"]')
        await input_el.fill(test_prompt)
        await asyncio.sleep(1)
        await page.keyboard.press('Enter')
        print('Sent test prompt!', flush=True)
        
        for i in range(10):
            await asyncio.sleep(3)
            body = await page.inner_text('body')
            print(f'[{i*3}s] Response tail:', flush=True)
            print(body[-300:], flush=True)
            if any(w in body.lower() for w in ['generating', 'creating', 'đang tạo', '%']):
                print('🎉 SUCCESS: DOLA ACCEPTED AND IS GENERATING VIDEO!', flush=True)
                break

if __name__ == '__main__':
    asyncio.run(test_input())
