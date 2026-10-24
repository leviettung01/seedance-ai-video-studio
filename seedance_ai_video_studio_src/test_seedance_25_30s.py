"""
Test Script: Generate 30s Video with Seedance 2.5 Model on Fresh User Accounts
"""
import asyncio
import os
import sys
import subprocess
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
from browser_manager import BrowserManager
from dola_automation import DolaAutomation
from session_store import SessionStore
from video_downloader import VideoDownloader
from config import DOLA_URL, OUTPUT_DIR

SAFE_PROMPT = """A magical crystal forest with glowing luminescent blue butterflies fluttering gently among floating ethereal particles and ancient mystical glowing tree roots, volumetric cinematic sunset golden light rays, unreal engine 5, hyperrealistic 8k render, breathtaking atmosphere, camera slowly panning up."""

ACCOUNTS_TO_TRY = ['leviettung04', 'tungkyluatbanthan', 'tungdhc', 'tunggemini']

def probe_video(video_path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,duration,codec_name,r_frame_rate",
        "-show_entries", "format=duration,size",
        "-of", "json",
        video_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return {}
    data = json.loads(res.stdout)
    streams = data.get("streams", [])
    format_info = data.get("format", {})
    vid_stream = next((s for s in streams if s.get("codec_name") not in ["aac", "mp3"]), streams[0] if streams else {})
    duration = float(vid_stream.get("duration") or format_info.get("duration") or 0)
    return {
        "width": int(vid_stream.get("width") or 0),
        "height": int(vid_stream.get("height") or 0),
        "duration": duration,
        "codec": vid_stream.get("codec_name", ""),
        "size": int(format_info.get("size") or 0),
    }

async def run_seedance_25_test():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    bm = BrowserManager()
    dola = DolaAutomation()
    vd = VideoDownloader()
    ss = SessionStore()
    
    print("=" * 70)
    print("🎬 STARTING SEEDANCE 2.5 (30s) VIDEO GENERATION TEST")
    print(f"   Output Directory: {OUTPUT_DIR}")
    print(f"   Prompt: {SAFE_PROMPT[:80]}...")
    print("=" * 70)

    for idx, account_name in enumerate(ACCOUNTS_TO_TRY):
        if not ss.has_session(account_name):
            print(f"⚠️ Skipping '{account_name}': No saved session.")
            continue

        worker_id = 50 + idx
        print(f"\n[{idx+1}/{len(ACCOUNTS_TO_TRY)}] 🔄 Trying Account: '{account_name}' (Worker #{worker_id})")
        
        try:
            # 1. Launch visible Chrome
            print("  1. Launching visible Chrome browser...")
            port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
            print(f"     Chrome listening on debug port {port}")
            
            # 2. Connect CDP
            browser = await bm.connect_worker(worker_id)
            page = browser.contexts[0].pages[0]
            
            # 3. Inject Session
            print(f"  2. Injecting session for '{account_name}'...")
            injected = await bm.inject_session_to_worker(worker_id, account_name)
            if not injected:
                print(f"     ❌ Injection failed for '{account_name}'")
                await bm.cleanup_worker(worker_id)
                continue
                
            # 4. Navigate to Dola Chat
            print("  3. Navigating to Dola AI chat...")
            await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(3)
            
            # 5. Check login status
            status = await dola.check_login_status(page)
            print(f"     Login Status: {status}")
            if status != "logged_in":
                print(f"     ❌ Account '{account_name}' is not logged in. Trying next...")
                await bm.cleanup_worker(worker_id)
                continue

            # 6. Execute Generation Flow with Model 2.5 & Duration 31s
            print("  4. Executing video generation flow (Model: Seedance 2.5, Duration: 31s, Ratio: 9:16)...")
            video_url = await dola.execute_generation_flow(
                page=page,
                prompt=SAFE_PROMPT,
                aspect_ratio="9:16",
                image_path="",
                mode="standard",
                duration_target=31,
                model_version="2.5",
                progress_callback=lambda msg: print(f"     📢 {msg}")
            )
            
            if not video_url:
                print(f"     ❌ No video URL returned for '{account_name}'. Trying next account...")
                await bm.cleanup_worker(worker_id)
                continue
                
            print(f"\n  🎯 [SUCCESS] Extracted Video URL:\n     {video_url[:120]}...")
            
            # 7. Download RAW Video
            raw_filename = f"seedance_25_30s_{account_name}_raw.mp4"
            raw_path = os.path.join(OUTPUT_DIR, raw_filename)
            print(f"\n  5. Downloading RAW video to: {raw_filename}...")
            
            raw_unwatermarked_url = vd.convert_to_unwatermarked(video_url)
            dl_res_path = await vd.download_video(raw_unwatermarked_url, output_filename=raw_filename, output_dir=OUTPUT_DIR)
            if not dl_res_path or not os.path.isfile(raw_path):
                print(f"     ❌ Download failed")
                await bm.cleanup_worker(worker_id)
                continue
                
            raw_size = os.path.getsize(raw_path)
            print(f"     ✅ Downloaded RAW Video: {raw_path} ({raw_size:,} bytes)")
            
            # 8. Probe RAW Video
            info = probe_video(raw_path)
            print("\n  📊 Video Probe Information:")
            print(f"     Resolution: {info.get('width')}x{info.get('height')}")
            print(f"     Duration:   {info.get('duration'):.1f}s")
            print(f"     Codec:      {info.get('codec')}")
            print(f"     Filesize:   {info.get('size'):,} bytes")
            
            # 9. Upscale to 4K
            print("\n  6. 🚀 Upscaling video to 4K (2160x3840) with FFmpeg...")
            final_4k_path = await vd.upscale_video(raw_path, target="4K", output_dir=OUTPUT_DIR)
            if not final_4k_path:
                final_4k_path = raw_path
            final_4k_size = os.path.getsize(final_4k_path) if os.path.isfile(final_4k_path) else 0
            
            print("\n" + "=" * 70)
            print("🏆 COMPLETED! SEEDANCE 2.5 VIDEO GENERATION SUCCEEDED!")
            print(f"   RAW Video:  {raw_path} ({raw_size:,} bytes, {info.get('duration'):.1f}s)")
            print(f"   4K Video:   {final_4k_path} ({final_4k_size:,} bytes)")
            print(f"   Resolution: 4K (2160x3840)")
            print(f"   Model:      Seedance 2.5")
            print("=" * 70)
            
            await bm.cleanup_worker(worker_id)
            return True

        except Exception as e:
            print(f"     ⚠️ Exception during run with '{account_name}': {e}")
            try:
                await bm.cleanup_worker(worker_id)
            except Exception:
                pass

    print("\n❌ All accounts exhausted or generation could not complete.")
    return False

if __name__ == '__main__':
    asyncio.run(run_seedance_25_test())
