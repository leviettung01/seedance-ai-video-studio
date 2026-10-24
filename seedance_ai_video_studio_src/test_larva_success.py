import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def test_larva_clean():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9251')
        page = browser.contexts[0].pages[0]
        
        await page.goto('https://www.dola.com/chat/', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(2)
        
        # Click Tạo video
        for sel in ['button:has-text("Tạo video")', 'div:has-text("Tạo video")']:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    await el.click()
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass
                
        prompt = "Two funny cartoon larva characters cosplaying as ninjas in orange and blue headbands perform an over-the-top ninja martial arts choreography on a wooden village rooftop at golden-hour sunset. Glowing spiral energy jutsu, colorful anime clouds, sakuga impact frames, bright saturated palette, 2D anime cel-shaded style, elastic cartoon bounce, 360-degree camera orbit, and a hilarious friendly fist-bump finale."
        
        input_el = await page.wait_for_selector('textarea, [contenteditable="true"]')
        await input_el.fill(prompt)
        await asyncio.sleep(1)
        await page.keyboard.press('Enter')
        print('Sent cleaned larva ninja prompt!', flush=True)
        
        for i in range(8):
            await asyncio.sleep(2)
            body = await page.inner_text('body')
            tail = body[-300:].replace('\n', ' ')
            print(f'[{i*2}s] {tail}', flush=True)
            if any(w in body.lower() for w in ['đang tạo video', 'generating', 'tạo video cho bạn', 'dự kiến chờ']):
                print('🎉 SUCCESS: LARVA NINJA VIDEO IS NOW GENERATING ON DOLA WITH MODEL 2.5!', flush=True)
                break

if __name__ == '__main__':
    asyncio.run(test_larva_clean())
