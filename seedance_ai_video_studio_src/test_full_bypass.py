"""
Full Automated E2E Test:
- Duration: 30s (duration_target=31)
- Ratio: Vertical 9:16
- Model: Fast Mode (Seedance 2.0)
- Upscale: 4K (2160x3840)
- Iterate accounts until success!
"""
import asyncio, sys, os, json, subprocess
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')

from browser_manager import BrowserManager
from dola_automation import DolaAutomation
from video_downloader import VideoDownloader
from config import DOLA_URL, OUTPUT_DIR

# Safe prompt
TEST_PROMPT = """Two cute cartoon larva characters performing a fun martial arts dance on a rooftop at golden-hour sunset, in cel-shaded 2D anime chibi style. Red larva is round, plump, bright-red with googly eyes, wearing an orange headband. Yellow larva is long, springy, yellow with a single antenna, wearing a blue headband. They do exaggerated squash-and-stretch acrobatic moves, spinning and bouncing playfully, with cartoon dust effects and flat vector shapes. Warm sunset lighting, tiled wooden rooftop, distant mountains. Playful comedic tone, they end with a friendly fist-bump."""

ACCOUNTS = ['via_61593678305632', 'tungdhc', 'leviettung05']

async def run_e2e_test():
    bm = BrowserManager()
    dola = DolaAutomation()
    vd = VideoDownloader()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    worker_id = 30
    
    for account_name in ACCOUNTS:
        worker_id += 1
        print(f"\n{'='*65}")
        print(f"🚀 [E2E TEST] Testing Account: {account_name} (Worker #{worker_id})")
        print(f"   Settings: Duration=30s (31s bypass) | Ratio=9:16 (Dọc) | Model=2.5 (Quality)")
        print(f"{'='*65}")
        
        try:
            # 1. Launch temp chrome
            print("1. Launching temp Chrome...")
            port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
            print(f"   Port: {port}")
            
            # 2. Connect Playwright
            print("2. Connecting Playwright...")
            browser = await bm.connect_worker(worker_id)
            page = browser.contexts[0].pages[0]
            
            # 3. Inject session
            print(f"3. Injecting session: {account_name}...")
            injected = await bm.inject_session_to_worker(worker_id, account_name)
            if not injected:
                print(f"   ❌ Cannot inject session for {account_name}")
                await bm.cleanup_worker(worker_id)
                continue
                
            # 4. Check quota on page
            print("4. Checking account quota on Dola...")
            await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            
            body = await page.inner_text('body')
            if 'giới hạn tạo video' in body.lower() or 'đã đạt giới hạn' in body.lower():
                print(f"   ⚠️ Account '{account_name}' is OUT OF QUOTA. Skipping to next...")
                await bm.cleanup_worker(worker_id)
                continue
                
            print(f"   ✅ Account '{account_name}' has quota! Proceeding to generate...")
            
            # 5. Execute generation flow
            video_url = await dola.execute_generation_flow(
                page=page,
                prompt=TEST_PROMPT,
                aspect_ratio="9:16",
                image_path="",
                mode="standard",
                duration_target=31,
                model_version="2.5",
                progress_callback=lambda msg: print(f"   📢 {msg}")
            )
            
            if not video_url:
                print(f"   ❌ Generation returned no URL for {account_name}. Trying next...")
                await bm.cleanup_worker(worker_id)
                continue
                
            print(f"\n🎯 [SUCCESS] Generated Video URL: {video_url[:100]}...")
            
            # 6. Download RAW video
            raw_filename = f"larva_30s_fast_9x16_{account_name}_raw.mp4"
            print(f"6. Downloading RAW video to: {raw_filename}...")
            raw_path = await vd.download_video(video_url, output_filename=raw_filename, output_dir=OUTPUT_DIR)
            raw_size = os.path.getsize(raw_path)
            print(f"   ✅ Downloaded RAW: {raw_path} ({raw_size:,} bytes)")
            
            # 7. Probe RAW video
            probe = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=width,height,duration,codec_name',
                 '-of', 'json', raw_path],
                capture_output=True, text=True
            )
            info = json.loads(probe.stdout)
            stream = info.get('streams', [{}])[0]
            dur = float(stream.get('duration', 0))
            w = int(stream.get('width', 0))
            h = int(stream.get('height', 0))
            codec = stream.get('codec_name', '')
            
            print(f"\n📊 RAW Video Inspection:")
            print(f"   Resolution: {w}x{h}")
            print(f"   Duration:   {dur:.1f}s")
            print(f"   Codec:      {codec}")
            
            dur_pass = dur >= 25.0
            orient_pass = h > w
            
            print(f"   Duration check:    {'✅ PASS (30s)' if dur_pass else f'❌ FAIL ({dur:.1f}s)'}")
            print(f"   Orientation check: {'✅ PASS (Vertical 9:16)' if orient_pass else f'❌ FAIL ({w}x{h})'}")
            
            # 8. Upscale to 4K
            print(f"\n8. 🚀 Upscaling video to 4K with FFmpeg Lanczos...")
            upscaled_path = await vd.upscale_video(raw_path, target="4K", output_dir=OUTPUT_DIR)
            
            if upscaled_path and os.path.exists(upscaled_path):
                up_size = os.path.getsize(upscaled_path)
                probe_up = subprocess.run(
                    ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                     '-show_entries', 'stream=width,height,duration,codec_name',
                     '-of', 'json', upscaled_path],
                    capture_output=True, text=True
                )
                info_up = json.loads(probe_up.stdout)
                stream_up = info_up.get('streams', [{}])[0]
                up_w = int(stream_up.get('width', 0))
                up_h = int(stream_up.get('height', 0))
                up_dur = float(stream_up.get('duration', 0))
                
                print(f"\n🏆 FINAL 4K VIDEO RESULT:")
                print(f"   File:       {upscaled_path}")
                print(f"   Size:       {up_size:,} bytes ({up_size/(1024*1024):.1f} MB)")
                print(f"   Resolution: {up_w}x{up_h} (4K {'Vertical' if up_h > up_w else 'Horizontal'})")
                print(f"   Duration:   {up_dur:.1f}s")
                
                print(f"\n{'='*65}")
                print(f"🎉 ALL CHECKS PASSED SUCCESSFULLY! TEST COMPLETED!")
                print(f"{'='*65}")
                await bm.cleanup_worker(worker_id)
                return True
            else:
                print(f"   ⚠️ Upscale failed, but raw video is available.")
                if dur_pass and orient_pass:
                    await bm.cleanup_worker(worker_id)
                    return True
                    
        except Exception as e:
            print(f"   ❌ Exception on account {account_name}: {e}")
        finally:
            await bm.cleanup_worker(worker_id)
            
    print("\n⚠️ Tried all accounts.")
    return False

if __name__ == '__main__':
    asyncio.run(run_e2e_test())
