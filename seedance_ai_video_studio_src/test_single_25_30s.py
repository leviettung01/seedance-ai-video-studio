import asyncio
import os
import sys
import subprocess
import json

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")

from browser_manager import BrowserManager
from dola_automation import DolaAutomation
from session_store import SessionStore
from video_downloader import VideoDownloader
from config import DOLA_URL, OUTPUT_DIR

SAFE_PROMPT = """A glowing cyberpunk futuristic city with neon holographic flying cars soaring through volumetric rainy night sky, hyperrealistic 8k render, unreal engine 5, cinematic slow camera movement."""

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

async def run_single():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    bm = BrowserManager()
    dola = DolaAutomation()
    vd = VideoDownloader()
    
    account_name = "tungkyluatbanthan"
    worker_id = 80
    
    print(f"🎬 [TEST] Generating 30s Video on Seedance 2.5 Pro for '{account_name}'", flush=True)
    
    # 1. Launch Chrome
    print("1. Launching visible Chrome browser...", flush=True)
    port = await bm.launch_temp_chrome(worker_id=worker_id, show_browser=True)
    browser = await bm.connect_worker(worker_id)
    page = browser.contexts[0].pages[0]
    
    # 2. Inject Session
    print(f"2. Injecting session for '{account_name}'...", flush=True)
    await bm.inject_session_to_worker(worker_id, account_name)
    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=35000)
    await asyncio.sleep(3)
    
    # 3. Check login
    status = await dola.check_login_status(page)
    print(f"   Login Status: {status}", flush=True)
    if status != "logged_in":
        print("❌ Login failed. Exiting.", flush=True)
        await bm.cleanup_worker(worker_id)
        return
        
    # 4. Generate video with Model 2.5
    print("3. Executing Generation Flow with Model 2.5 & Duration 31s...", flush=True)
    video_url = await dola.execute_generation_flow(
        page=page,
        prompt=SAFE_PROMPT,
        aspect_ratio="9:16",
        image_path="",
        mode="standard",
        duration_target=31,
        model_version="2.5",
        progress_callback=lambda msg: print(f"   📢 {msg}", flush=True)
    )
    
    if not video_url:
        print("❌ No video URL returned.", flush=True)
        await bm.cleanup_worker(worker_id)
        return
        
    print(f"\n🎯 [SUCCESS] Extracted Video URL: {video_url[:120]}...", flush=True)
    
    # 5. Download Video
    raw_filename = f"seedance_25_30s_test_raw.mp4"
    raw_path = os.path.join(OUTPUT_DIR, raw_filename)
    raw_unwatermarked_url = vd.convert_to_unwatermarked(video_url)
    print(f"4. Downloading clean video to {raw_path}...", flush=True)
    await vd.download_video(raw_unwatermarked_url, output_filename=raw_filename, output_dir=OUTPUT_DIR)
    
    # 6. Probe video
    if os.path.isfile(raw_path):
        info = probe_video(raw_path)
        print("\n📊 Video Probe Information:", flush=True)
        print(f"   Resolution: {info.get('width')}x{info.get('height')}", flush=True)
        print(f"   Duration:   {info.get('duration'):.1f}s", flush=True)
        print(f"   Filesize:   {info.get('size'):,} bytes", flush=True)
        
        # 7. 4K Upscale
        print("\n5. Running 4K Upscale...", flush=True)
        final_4k = await vd.upscale_video(raw_path, target="4K", output_dir=OUTPUT_DIR)
        print(f"   ✅ Upscale 4K finished: {final_4k}", flush=True)
        
    await bm.cleanup_worker(worker_id)
    print("\n🏁 Test completed successfully!", flush=True)

if __name__ == '__main__':
    asyncio.run(run_single())
