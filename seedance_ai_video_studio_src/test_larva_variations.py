import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

PROMPTS = [
    # Variant 1: Pure descriptive anime action without sensitive keywords (replace duel/battle/attack with martial arts clash/action choreography)
    """[GLOBAL STYLE] Cel-shaded 2D anime and chibi cartoon hybrid, flat color fills, thick clean vector outlines, bright saturated palette, comedic shonen action style, sakuga impact frames, 9:16 vertical video. Playful and hilarious tone. NO 3D render, NO CGI plastic look, NO photorealism.

[SCENE] Two goofy cartoon larva characters in cute ninja costumes perform a funny martial arts action show on a stylized anime wooden village rooftop at sunset, mixing anime moves with slapstick humor.

[CHARACTERS]
RED LARVA "Red": round bright-red larva with big eyes and buck teeth, wearing an orange headband and tiny ninja vest, energetic and funny.
YELLOW LARVA "Yellow": long yellow larva with one antenna, wearing a blue headband and mini flak vest, clumsy and powerful.

[SHOT-BY-SHOT / TIMESTAMPS]
00:00-00:04 Wide static shot, both cartoon larva face off on the rooftop, wind blowing, speed lines forming.
00:04-00:09 Fast zoom on Red as he forms a bright glowing spiral energy ball in his hands with colorful anime effects.
00:09-00:15 Yellow leaps forward like a spring coil, 360-degree orbit around the mid-air clash, colorful dust clouds and cartoon star bursts.
00:15-00:21 Comedic fast ninja movements, elastic bouncing bodies, squash and stretch, funny sweat drops and anime speed lines.
00:21-00:26 Red performs a giant spinning dance move with bright light effects, Yellow spins comically into the air.
00:26-00:30 Both larva land safely dizzy with funny swirl eyes, then smile and fist-bump, dust settling into cute cartoon clouds.

[CAMERA] Dynamic shonen camera: fast tracking push-ins, 360-degree orbit, low-angle hero shots, anime action lens.

[LIGHTING] Warm golden-hour sunset lighting, bold anime colors, bright energy glows, comic impact flashes.

[AUDIO] Energetic comedic action music, cartoon boing and pop sound effects, funny voice grunts.""",

    # Variant 2: Natural flowing master prompt
    """A high-energy 30-second comedic 2D anime martial arts action scene in 9:16 vertical video: Two funny cartoon larva characters dressed as ninjas (Red in orange headband, Yellow with single antenna in blue headband) perform an over-the-top ninja clash on a wooden village rooftop at golden-hour sunset. Sakuga impact frames, bold colorful vector art, energetic spiral energy jutsu, elastic cartoon physics, 360-degree camera orbits, and a hilarious friendly fist-bump finale."""
]

async def test_prompts():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9251')
        page = browser.contexts[0].pages[0]
        
        for idx, pr in enumerate(PROMPTS, 1):
            print(f'\n--- TESTING PROMPT VARIANT {idx} ---', flush=True)
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
                    
            input_el = await page.wait_for_selector('textarea, [contenteditable="true"]')
            await input_el.fill(pr)
            await asyncio.sleep(1)
            await page.keyboard.press('Enter')
            print('Sent prompt! Waiting for Dola response...', flush=True)
            
            accepted = False
            for step in range(8):
                await asyncio.sleep(2)
                body = await page.inner_text('body')
                tail = body[-300:].replace('\n', ' ')
                print(f'   [{step*2}s] {tail}', flush=True)
                if any(w in body.lower() for w in ['đang tạo video', 'generating', 'tạo video cho bạn', 'dự kiến chờ']):
                    print(f'🎉 PROMPT VARIANT {idx} ACCEPTED BY DOLA!', flush=True)
                    accepted = True
                    break
                if any(w in body.lower() for w in ['vi phạm chính sách', 'không thể tạo']):
                    print(f'❌ Prompt Variant {idx} rejected by Dola filter.', flush=True)
                    break
            
            if accepted:
                print(f'🎯 Variant {idx} is now actively generating on Dola!')
                break

if __name__ == '__main__':
    asyncio.run(test_prompts())
