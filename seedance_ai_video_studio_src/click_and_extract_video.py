import asyncio, sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright
from video_downloader import VideoDownloader
from config import OUTPUT_DIR

async def click_and_extract():
    vd = VideoDownloader()
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        # 1. Hover and click the video container
        cards = await page.query_selector_all('.block-video-MzfWVN, [class*="block-video"], [class*="video-player"]')
        print(f'Found {len(cards)} video cards')
        if cards:
            await cards[-1].hover()
            await asyncio.sleep(1)
            await cards[-1].click()
            await asyncio.sleep(2)
            
        # 2. Check DOM video sources
        videos = await page.evaluate("""
            (() => {
                const list = [];
                document.querySelectorAll('video').forEach(v => {
                    list.push(v.src || v.currentSrc);
                });
                document.querySelectorAll('video source').forEach(s => {
                    list.push(s.src);
                });
                return list;
            })()
        """)
        print('DOM Video sources:', json.dumps(videos, indent=2))
        
        # 3. Check performance entries for newly loaded video requests
        perf_videos = await page.evaluate("""
            (() => {
                return performance.getEntriesByType('resource')
                    .map(r => r.name)
                    .filter(n => (n.includes('tos-') || n.includes('video') || n.includes('.mp4') || n.includes('lr=')) && !n.endsWith('.js') && !n.endsWith('.css') && !n.endsWith('.png'));
            })()
        """)
        print('Network video URLs:', json.dumps(perf_videos, indent=2))
        
        # 4. Check if we found a video URL
        video_url = None
        for v in (videos + perf_videos):
            if v and v.startswith('http') and ('tos' in v or 'video' in v or 'mp4' in v):
                video_url = v
                break
                
        if video_url:
            print(f'🎯 Found valid video URL: {video_url}')
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            dl_path = await vd.download_video(
                video_url,
                output_filename="completed_cat_anime_30s_raw.mp4",
                output_dir=OUTPUT_DIR
            )
            print(f'✅ Video downloaded successfully: {dl_path} ({os.path.getsize(dl_path)} bytes)')
            
            print('✨ Starting 4K Upscale with FFmpeg...')
            upscaled = await vd.upscale_video(dl_path, target="4K", output_dir=OUTPUT_DIR)
            final_file = upscaled if (upscaled and os.path.exists(upscaled)) else dl_path
            print(f'🏆 FINAL PRODUCED 4K VIDEO: {final_file} ({os.path.getsize(final_file)} bytes)')
        else:
            print('⚠️ Video URL not yet found, taking screenshot...')
            await page.screenshot(path='inspect_after_click.png')

if __name__ == '__main__':
    asyncio.run(click_and_extract())
