import asyncio, sys, os, time
sys.stdout.reconfigure(encoding='utf-8')

from worker_pool import WorkerPool
from config import OUTPUT_DIR

LARVA_PROMPT = """Two funny cartoon larva characters cosplaying as ninjas in orange and blue headbands perform an over-the-top ninja martial arts choreography on a wooden village rooftop at golden-hour sunset. Glowing spiral energy jutsu, colorful anime clouds, sakuga impact frames, bright saturated palette, 2D anime cel-shaded style, elastic cartoon bounce, 360-degree camera orbit, and a hilarious friendly fist-bump finale."""

async def run_test():
    wp = WorkerPool()
    
    # Progress callback
    def on_progress(w_id, job_id, msg):
        print(f"[{time.strftime('%H:%M:%S')}] [Worker #{w_id}] [Job {job_id[:8]}] {msg}", flush=True)
        
    wp.set_callbacks(on_progress=on_progress)
    
    print('1. Starting WorkerPool with 1 worker...', flush=True)
    await wp.start(num_workers=1)
    
    print('2. Submitting Job for leviettung04 (Model 2.5, Ratio 9:16, 31s, 4K)...', flush=True)
    job = wp.submit_job(
        account_name="leviettung04",
        prompt=LARVA_PROMPT,
        aspect_ratio="9:16",
        image_path="",
        model_version="2.5",
        mode="standard",
        duration_target=31,
        upscale="4K",
        show_browser=True
    )
    
    print(f'3. Job submitted (ID: {job.id}). Waiting for job to complete...', flush=True)
    start_t = time.time()
    while job.status in ["queued", "running", "downloading", "upscaling"]:
        await asyncio.sleep(5)
        elapsed = int(time.time() - start_t)
        if elapsed % 30 == 0:
            st = wp.get_status()
            print(f"⏳ [{elapsed}s] Active: {st['active_jobs']}, Completed: {st['completed_jobs']}, Failed: {st['failed_jobs']}", flush=True)
            
    print(f'\n========================================')
    print(f'🏁 Job finished with status: {job.status.upper()}')
    if job.status == "completed":
        print(f'🏆 Video output: {job.output_path}')
        if job.output_path and os.path.exists(job.output_path):
            print(f'📦 File size: {os.path.getsize(job.output_path):,} bytes')
    else:
        print(f'❌ Job error: {job.error}')
    print(f'========================================\n')
    
    await wp.stop()

if __name__ == '__main__':
    asyncio.run(run_test())
