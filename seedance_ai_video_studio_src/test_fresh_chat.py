import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def test_fresh():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        # Navigate to a fresh new chat
        print('1. Navigating to fresh https://www.dola.com/chat/ ...', flush=True)
        await page.goto('https://www.dola.com/chat/', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)
        
        # Click 'Tạo video'
        print('2. Clicking Tạo video button...', flush=True)
        for sel in ['button:has-text("Tạo video")', 'div:has-text("Tạo video")', 'button:has-text("Create Video")']:
            try:
                el = await page.wait_for_selector(sel, timeout=3000)
                if el:
                    await el.click()
                    print(f'   Clicked {sel}', flush=True)
                    await asyncio.sleep(1)
                    break
            except Exception as e:
                print(f'   Error clicking {sel}: {e}', flush=True)
                
        # Check UI controls visible (Ratio, Model, Duration)
        buttons = await page.evaluate("""
            (() => Array.from(document.querySelectorAll('button, div[role="button"]')).map(b => (b.innerText || '').trim()).filter(t => t.length > 0))()
        """)
        print('3. Buttons on UI after clicking Tạo video:', buttons[:15], flush=True)
        
        # Type prompt
        test_prompt = "Một chú mèo con lông vàng đang chơi đùa với quả bóng len nhiều màu sắc trong phòng khách ấm cúng tràn ngập ánh nắng mặt trời, phong cách anime hoạt hình dễ thương 4K"
        print(f'4. Typing test prompt: {test_prompt}...', flush=True)
        
        input_el = await page.wait_for_selector('textarea, [contenteditable="true"]')
        await input_el.fill(test_prompt)
        await asyncio.sleep(1)
        await page.keyboard.press('Enter')
        print('5. Pressed Enter to send!', flush=True)
        
        # Monitor response
        for i in range(15):
            await asyncio.sleep(2)
            body = await page.inner_text('body')
            last_text = body[-400:].replace('\n', ' ')
            print(f'[{i*2}s] Body tail: {last_text}', flush=True)
            if any(w in body.lower() for w in ['generating', 'creating', 'đang tạo', '%', 'render']):
                print('🎉 SUCCESS: DOLA IS GENERATING VIDEO!', flush=True)
                break
                
        await page.screenshot(path='fresh_chat_result.png')
        print('Screenshot saved to fresh_chat_result.png', flush=True)

if __name__ == '__main__':
    asyncio.run(test_fresh())
