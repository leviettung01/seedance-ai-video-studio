import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from dola_automation import DolaAutomation
from session_store import SessionStore
from config import DOLA_URL

TEST_PROMPT = """[GLOBAL STYLE] Cel-shaded 2D anime + chibi cartoon hybrid, flat color fills, thick clean vector outlines, bright saturated palette, comedic shonen action style, sakuga impact frames, 16:9. Playful and hilarious tone. NO 3D render, NO CGI plastic look, NO photorealism, NO volumetric lighting.

[SCENE] Two goofy cartoon larva characters cosplaying as ninjas battle each other in an over-the-top comedic ninja duel on a rooftop at sunset, mixing epic anime action with slapstick humor.

[CHARACTERS]
RED LARVA "Red": a round plump bright-red larva with big googly eyes and buck teeth, wearing an orange ninja headband with a metal plate, a tiny orange ninja jacket, energetic and cocky.
YELLOW LARVA "Yellow": a long springy yellow larva with a single antenna, wearing a blue ninja headband and a mini flak vest, clumsy but powerful.
Only these two characters exist. Consistent design, colors and outfits across all shots.

[LOCATION] A stylized anime rooftop of a wooden ninja village at golden-hour sunset, tiled roofs, distant mountains, warm orange sky with flat anime clouds. No readable text, no logos.

[FIRST FRAME & BLOCKING] Red stands screen-left in a fighting pose, Yellow screen-right coiled ready to spring, both glaring at each other across the rooftop. They never swap sides.

[SHOT-BY-SHOT / TIMESTAMPS]
00:00-00:04 Wide static shot, both larva face off on the rooftop, wind blowing, tension building, speed lines forming. Hard cut.
00:04-00:09 Fast push-in on Red as he winds up and shouts, forming a glowing spiral energy ball in his stubby arms (comedic "spinning ball" jutsu), impact frame flash. Hard cut.
00:09-00:15 Yellow springs forward like a spring coil, 360-degree high-speed orbit around the mid-air clash, dust and debris flying as flat vector shapes, both collide in a big cartoon impact star. Hard cut.
00:15-00:21 Rapid exchange of comedic ninja strikes, both bounce and stretch elastically, speed lines, exaggerated squash-and-stretch, small comic-relief sweat drops, sound-effect kanji-style bursts. Hard cut.
00:21-00:26 Red does a giant charged spinning attack, screen fills with light, Yellow gets comically launched into the sky spinning. Hard cut.
00:26-00:30 Slow-motion landing, both larva plop down dizzy with swirl eyes, then grin and fist-bump, dust settling into flat vector clouds. Freeze on final funny pose.

[CAMERA / OPTICS] Dynamic shonen camera: fast tracking push-ins, whip pans on strikes, one 360-degree orbit on the clash, low-angle hero shots, slow-motion on the finish. Anime lens feel, no real-world optics.

[PHYSICS] Cartoon physics: heavy squash-and-stretch, elastic bouncy bodies, exaggerated momentum, debris and dust as flat 2D vector shapes, hair/antenna and cloth lag on fast moves. No blood.

[LIGHTING] Flat anime cel lighting, warm golden-hour key, hard-edged shadow shapes, glowing energy effects with flat color, comic impact flashes. No realistic shadow falloff, no ambient occlusion.

[AUDIO] Energetic comedic action music, whooshes on strikes, cartoon boing and pop sound effects, big impact booms, funny voice grunts (no real words), crowd-less. 

[NEGATIVE] 3D render, CGI texture, plastic skin, photorealism, volumetric light, ray tracing, ambient occlusion, realistic shadows, motion blur smear, extra characters, duplicated character, readable text, logos, gore."""

async def test():
    bm = BrowserManager()
    da = DolaAutomation()

    account_name = 'leviettung04'
    print(f'1. Launching visible Chrome for {account_name}...', flush=True)
    await bm.launch_temp_chrome(0, show_browser=True)

    browser = await bm.connect_worker(0)
    await bm.inject_session_to_worker(0, account_name)
    page = await bm.get_worker_page(0)

    print('2. Executing standard flow (Model 2.5, Ratio 9:16, Duration 31s)...', flush=True)
    video_url = await da.execute_generation_flow(
        page=page,
        prompt=TEST_PROMPT,
        aspect_ratio="9:16",
        image_path="",
        mode="standard",
        duration_target=31,
        model_version="2.5",
        progress_callback=lambda msg: print(f"   [Flow Progress] {msg}", flush=True)
    )

    print(f'3. Result Video URL: {video_url}', flush=True)

    await page.screenshot(path='scratch_test_after_send.png')
    print('   Screenshot saved: scratch_test_after_send.png', flush=True)

    # Let Chrome stay open for 30s to observe
    print('4. Waiting 30s before cleanup...', flush=True)
    await asyncio.sleep(30)
    await bm.cleanup_worker(0)

if __name__ == '__main__':
    asyncio.run(test())
