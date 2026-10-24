import asyncio, sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright
from video_downloader import VideoDownloader
from config import OUTPUT_DIR

async def click_cover():
    vd = VideoDownloader()
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        # 1. Click the video cover element using page.evaluate to dispatch a click event directly
        print('Dispatching click to video elements...')
        clicked = await page.evaluate("""
            (() => {
                const el = document.querySelector('.cover-u1rIsU') || document.querySelector('.block-video-MzfWVN') || document.querySelector('.video-player-wrapper-IZ7Zoq');
                if (el) {
                    el.click();
                    return true;
                }
                return false;
            })()
        """)
        print('Clicked via JS:', clicked)
        await asyncio.sleep(4)
        
        # 2. Check DOM video tags
        videos = await page.evaluate("""
            (() => {
                const list = [];
                document.querySelectorAll('video').forEach(v => {
                    const s = v.src || v.currentSrc;
                    if (s) list.push(s);
                });
                document.querySelectorAll('source').forEach(s => {
                    if (s.src) list.push(s.src);
                });
                return list;
            })()
        """)
        print('DOM Video tags:', json.dumps(videos, indent=2))
        
        # 3. Check performance entries
        perf = await page.evaluate("""
            (() => {
                return performance.getEntriesByType('resource')
                    .map(r => r.name)
                    .filter(n => n.includes('.mp4') || n.includes('video/tos') || n.includes('mime_type=video') || n.includes('tos-mya-ve'));
            })()
        """)
        print('Network MP4 resources:', json.dumps(perf, indent=2))
        
        # 4. Check extension storage for captured links
        ext_links = await page.evaluate("""
            (() => {
                return {
                    seedance: localStorage.getItem('__seedanceLinks'),
                    dola: localStorage.getItem('__dolaWatermarkLinks')
                };
            })()
        """)
        print('LocalStorage links:', json.dumps(ext_links, indent=2))
        
        # 5. Find valid video URL
        all_candidates = videos + perf
        if ext_links.get('seedance'):
            all_candidates.insert(0, ext_links['seedance'])
            
        video_url = None
        for cand in all_candidates:
            if cand and cand.startswith('http'):
                video_url = cand
                break
                
        if video_url:
            print(f'🎯 FOUND VIDEO URL: {video_url}')
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            raw_path = await vd.download_video(
                video_url,
                output_filename="larva_ninja_anime_30s_raw.mp4",
                output_dir=OUTPUT_DIR
            )
            print(f'✅ Downloaded raw video: {raw_path} ({os.path.getsize(raw_path):,} bytes)')
            
            print('✨ Starting 4K Upscale with FFmpeg...')
            upscaled = await vd.upscale_video(raw_path, target="4K", output_dir=OUTPUT_DIR)
            final_file = upscaled if (upscaled and os.path.exists(upscaled)) else raw_path
            print(f'🏆 FINAL PRODUCED 4K VIDEO: {final_file} ({os.path.getsize(final_file):,} bytes)')
        else:
            print('⚠️ No video URL found yet.')

if __name__ == '__main__':
    asyncio.run(click_cover())
