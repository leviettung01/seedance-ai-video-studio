import asyncio, sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright
from dola_automation import DolaAutomation
from video_downloader import VideoDownloader
from config import OUTPUT_DIR

async def poll_and_download():
    da = DolaAutomation()
    vd = VideoDownloader()
    
    print('1. Connecting to running Chrome on port 9250...', flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        print('2. Polling for video completion on Dola...', flush=True)
        start_t = time.time()
        video_url = None
        
        while time.time() - start_t < 600:
            elapsed = int(time.time() - start_t)
            
            # Check Extension localStorage
            video_url = await da._extract_video_url(page)
            if video_url:
                print(f'[{elapsed}s] 🎯 Found video URL from Extension: {video_url}', flush=True)
                break
                
            # Check DOM video element
            video_url = await da._extract_video_from_dom(page)
            if video_url:
                print(f'[{elapsed}s] 🎯 Found video URL from DOM: {video_url}', flush=True)
                break
                
            if elapsed % 15 == 0:
                body = await page.inner_text('body')
                print(f'[{elapsed}s] ⏳ Still generating... (body: {body[-150:].replace(chr(10), " ")})', flush=True)
                
            await asyncio.sleep(5)
            
        if not video_url:
            print('❌ Timeout waiting for video!', flush=True)
            return
            
        print(f'3. Downloading unwatermarked video from: {video_url}', flush=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        raw_file = os.path.join(OUTPUT_DIR, "demo_cat_anime_30s_raw.mp4")
        
        dl_path = await vd.download_video(video_url, output_filename="demo_cat_anime_30s_raw.mp4", output_dir=OUTPUT_DIR)
        print(f'✅ Downloaded raw video to: {dl_path} ({os.path.getsize(dl_path)} bytes)', flush=True)
        
        print('4. Upscaling video to 4K (NVENC/FFmpeg)...', flush=True)
        upscaled = await vd.upscale_video(dl_path, target="4K", output_dir=OUTPUT_DIR)
        final_video = upscaled if (upscaled and os.path.exists(upscaled)) else dl_path
        print(f'🏆 5. SUCCESS! Final 4K Video: {final_video} ({os.path.getsize(final_video)} bytes)', flush=True)

if __name__ == '__main__':
    asyncio.run(poll_and_download())
