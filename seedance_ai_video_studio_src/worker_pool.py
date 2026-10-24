# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Worker Pool v2
Quản lý đa luồng tạo video song song (lên đến 20 workers).
Mỗi worker = 1 Chrome tạm + Cookie Session + Sticky Proxy.

Kiến trúc:
- Worker lấy Job từ Queue → Xoay Sticky Proxy 1 lần → Mở Chrome tạm →
  Inject Session → Tạo Video → Download → Đóng Chrome (giải phóng RAM) →
  Upscale 4K (FFmpeg nền) → Quay lại lấy Job tiếp.
- Worker ≠ Account: 1 Worker xử lý nhiều Accounts liên tiếp.
- Proxy sticky giữ nguyên IP trong suốt 1 phiên (5-15 phút).
"""

import asyncio
import time
import os
from dataclasses import dataclass, field
from typing import Optional, Callable

from config import DOLA_URL, OUTPUT_DIR
from utils import log, log_info


@dataclass
class VideoJob:
    """1 job tạo video trong queue."""
    id: str
    account_name: str
    prompt: str
    aspect_ratio: str = "9:16"
    model_version: str = "2.5"
    mode: str = "standard"
    duration_target: int = 31
    upscale: str = "4K"
    image_path: str = ""          # Ảnh tham chiếu (Fast mode upload cùng prompt)
    show_browser: bool = False    # True = hiện cửa sổ Chrome, False = chạy ẩn / thu nhỏ
    status: str = "queued"       # queued | running | downloading | upscaling | completed | failed
    worker_id: int = -1
    proxy_used: str = ""         # IP proxy đã dùng cho job này
    output_path: str = ""
    error: str = ""
    current_step: str = "Đang chờ..."
    retries: int = 0
    attempted_accounts: list[str] = field(default_factory=list)
    max_retries: int = 2
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0

    @property
    def elapsed(self) -> int:
        if self.started_at <= 0:
            return 0
        end = self.completed_at if self.completed_at > 0 else time.time()
        return max(0, int(end - self.started_at))

    @property
    def formatted_elapsed(self) -> str:
        """Định dạng thời gian chạy dạng mm:ss (ví dụ: 02:45 hoặc 00:15)."""
        el = self.elapsed
        mins = el // 60
        secs = el % 60
        return f"{mins:02d}:{secs:02d}"

    @property
    def status_display(self) -> str:
        """Chuỗi trạng thái thân thiện kèm emoji."""
        status_map = {
            "queued": "⏳ Đang chờ",
            "running": "🚀 Đang tạo",
            "downloading": "📥 Đang tải video",
            "upscaling": "✨ Upscale 4K",
            "completed": "✅ Hoàn thành",
            "failed": "❌ Thất bại",
            "cancelled": "⏹ Đã dừng",
        }
        badge = status_map.get(self.status, self.status)
        if self.status in ["running", "downloading", "upscaling"] and self.current_step:
            return f"{badge} ({self.current_step})"
        return badge


class WorkerPool:
    """Pool of workers chạy song song tạo video.
    
    Flow tối ưu RAM cho mỗi Worker:
    ┌─────────────────────────────────────────────────────────┐
    │ 1. Lấy Job từ Queue                                    │
    │ 2. Xoay Sticky Proxy (1 lần, giữ nguyên suốt phiên)   │
    │ 3. Mở Chrome tạm (~80MB RAM)                           │
    │ 4. Inject Dola Session Cookies (0.6s)                   │
    │ 5. Gửi prompt + Chờ video (3-10 phút, Chrome idle)     │
    │ 6. Download video                                       │
    │ 7. ĐÓng Chrome + Xóa temp → GIẢI PHÓNG 80MB RAM       │
    │ 8. Upscale 4K bằng FFmpeg (GPU, không cần Chrome)      │
    │ 9. Quay lại bước 1                                     │
    └─────────────────────────────────────────────────────────┘
    """

    MAX_WORKERS_LIMIT = 10  # Giới hạn cứng: 20 workers tối đa

    def __init__(self, max_workers: int = 10):
        self.max_workers = min(max_workers, self.MAX_WORKERS_LIMIT)
        self.job_queue: asyncio.Queue[VideoJob] = asyncio.Queue()
        self.active_jobs: dict[str, VideoJob] = {}     # job_id → VideoJob
        self.all_jobs: list[VideoJob] = []            # Toàn bộ jobs trong phiên để GUI theo dõi
        self.completed_jobs: list[VideoJob] = []
        self.failed_jobs: list[VideoJob] = []
        self._worker_tasks: dict[int, asyncio.Task] = {}
        self._running = False
        self._stop_task = None
        self._on_progress: Optional[Callable] = None   # Callback cho GUI
        self._on_job_done: Optional[Callable] = None
        self._stats = {
            "total_started": 0,
            "total_completed": 0,
            "total_failed": 0,
            "start_time": 0,
        }

    def set_callbacks(self, on_progress: Callable = None, on_job_done: Callable = None):
        """Đặt callbacks cho GUI."""
        self._on_progress = on_progress
        self._on_job_done = on_job_done

    def _notify_progress(self, worker_id: int, job_id: str, message: str):
        """Gửi thông báo tiến trình."""
        log("Worker", f"[W#{worker_id}] {message}")
        if job_id in self.active_jobs:
            self.active_jobs[job_id].current_step = message
        if self._on_progress:
            try:
                self._on_progress(worker_id, job_id, message)
            except Exception:
                pass

    # ─── Job Management ───────────────────────────────────────────────────

    def submit_job(
        self,
        account_name: str,
        prompt: str,
        aspect_ratio: str = "9:16",
        model_version: str = "2.5",
        mode: str = "standard",
        duration_target: int = 31,
        upscale: str = "4K",
        image_path: str = "",
        show_browser: bool = False,
        max_retries: int = 2,
    ) -> VideoJob:
        """Thêm job vào queue."""
        import uuid
        job = VideoJob(
            id=f"job_{uuid.uuid4().hex[:8]}",
            account_name=account_name,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            model_version=model_version,
            mode=mode,
            duration_target=duration_target,
            upscale=upscale,
            image_path=image_path,
            show_browser=show_browser,
            max_retries=max_retries,
            created_at=time.time(),
        )
        self.job_queue.put_nowait(job)
        self.active_jobs[job.id] = job
        self.all_jobs.append(job)
        log("WorkerPool", f"Job '{job.id}' queued for account '{account_name}' (show_browser={show_browser})")
        return job

    def submit_batch(
        self,
        accounts: list[str],
        prompt: str,
        aspect_ratio: str = "9:16",
        model_version: str = "2.5",
        upscale: str = "4K",
    ) -> list[VideoJob]:
        """Thêm batch jobs — mỗi account 1 job cùng prompt."""
        jobs = []
        for acc_name in accounts:
            job = self.submit_job(
                account_name=acc_name,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                model_version=model_version,
                upscale=upscale,
            )
            jobs.append(job)
        log("WorkerPool", f"Batch: {len(jobs)} jobs queued cho {len(accounts)} accounts")
        return jobs

    def submit_multi_prompt_batch(
        self,
        jobs_data: list[dict],
    ) -> list[VideoJob]:
        """Thêm batch jobs với nhiều prompt khác nhau.
        
        jobs_data: [{"account_name": "fb01", "prompt": "...", "aspect_ratio": "9:16", ...}, ...]
        """
        jobs = []
        for data in jobs_data:
            job = self.submit_job(**data)
            jobs.append(job)
        log("WorkerPool", f"Multi-prompt batch: {len(jobs)} jobs queued")
        return jobs

    # ─── Worker Loop ──────────────────────────────────────────────────────

    async def _worker_loop(self, worker_id: int):
        """Main loop cho 1 worker — xử lý jobs liên tục từ queue."""
        from browser_manager import BrowserManager
        from dola_automation import DolaAutomation
        from video_downloader import VideoDownloader
        from proxy_manager import ProxyManager
        from account_manager import AccountManager

        bm = BrowserManager()
        da = DolaAutomation()
        vd = VideoDownloader()
        pm = ProxyManager()
        am = AccountManager()

        log("Worker", f"Worker #{worker_id} started.")

        while self._running:
            try:
                # ── Lấy job từ queue ──
                try:
                    job = await asyncio.wait_for(self.job_queue.get(), timeout=3.0)
                except asyncio.TimeoutError:
                    continue

                job.status = "running"
                job.worker_id = worker_id
                job.started_at = time.time()
                if job.account_name not in job.attempted_accounts:
                    job.attempted_accounts.append(job.account_name)
                self._stats["total_started"] += 1

                self._notify_progress(worker_id, job.id,
                    f"Bat dau: {job.account_name} | {job.aspect_ratio} | Model {job.model_version}")

                raw_path = None  # Path video gốc (trước upscale)
                native_pro = job.duration_target in (15, 30)

                try:
                    # ── 1. Resolve Sticky Proxy cho phiên này (Hỗ trợ Tool VPN & 5Stars) ──
                    proxy_raw = am.get_proxy_for_account(job.account_name)
                    proxy_url = await pm.get_proxy_for_account(job.account_name, proxy_raw or "")
                    job.proxy_used = proxy_url or ""
                    if proxy_url:
                        self._notify_progress(worker_id, job.id, f"Proxy sticky: {proxy_url}")
                    else:
                        self._notify_progress(worker_id, job.id, "Proxy: Trực tiếp (không dùng proxy)")

                    # ── 2. Mở Chrome tạm ──
                    self._notify_progress(worker_id, job.id, "Mo Chrome tam...")
                    await bm.launch_temp_chrome(worker_id, proxy_url=proxy_url,
                                                show_browser=job.show_browser,
                                                load_extension=not native_pro)

                    # ── 3. Kết nối Playwright ──
                    browser = await bm.connect_worker(worker_id, setup_extension=not native_pro)
                    if not browser:
                        raise Exception("Khong ket noi duoc Playwright toi Chrome tam")

                    # ── 4. Inject session cookies ──
                    self._notify_progress(worker_id, job.id,
                        f"Inject session '{job.account_name}'...")
                    success = await bm.inject_session_to_worker(worker_id, job.account_name)
                    if not success:
                        raise Exception(f"Khong inject duoc session cho '{job.account_name}'. "
                                        f"Hay vao tab Tai Khoan -> Mo Chrome -> Login Dola -> Luu Session.")

                    # ── 5. Navigate to Dola & run generation ──
                    page = await bm.get_worker_page(worker_id)
                    if not page:
                        raise Exception("Khong co page trong Chrome")

                    await page.goto(DOLA_URL, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)

                    self._notify_progress(worker_id, job.id,
                        "Dang gui prompt toi Dola AI...")

                    if native_pro:
                        from native_video_automation import NativeVideoAutomation
                        da = NativeVideoAutomation()
                    else:
                        da = DolaAutomation()
                    video_url = await da.execute_generation_flow(
                        page=page,
                        prompt=job.prompt,
                        aspect_ratio=job.aspect_ratio,
                        image_path=job.image_path,
                        model_version=job.model_version,
                        mode=job.mode,
                        account_name=job.account_name,
                        duration_target=job.duration_target,
                        progress_callback=lambda msg: self._notify_progress(
                            worker_id, job.id, msg),
                    )

                    if not video_url:
                        if native_pro:
                            raise Exception(f'Dola chưa trả về video {job.duration_target} giây; không dùng file Downloads của job khác.')
                        # Fallback: Kiểm tra xem extension đã tự động tải video về các thư mục Downloads chưa
                        import glob
                        downloads_base = os.path.join(os.path.expanduser("~"), "Downloads")
                        for sub_folder in ["Dola_Videos_1080P", "ZDola_Videos", "Seedance_Videos"]:
                            dl_folder = os.path.join(downloads_base, sub_folder)
                            if os.path.exists(dl_folder):
                                recent_files = glob.glob(os.path.join(dl_folder, "**", "*.mp4"), recursive=True)
                                if recent_files:
                                    newest_file = max(recent_files, key=os.path.getmtime)
                                    if os.path.getmtime(newest_file) >= (job.started_at - 30):
                                        raw_path = newest_file
                                        self._notify_progress(worker_id, job.id, f"✅ Đã bắt video từ Extension Auto-Download: {os.path.basename(raw_path)}")
                                        break
                        
                        if not raw_path:
                            raise Exception("Dola AI không trả về video URL")

                    # ── 6. Download video nếu chưa có ──
                    if video_url and not raw_path:
                        job.status = "downloading"
                        self._notify_progress(worker_id, job.id, "Đang tải video...")
                        raw_path = await vd.download_video(
                            video_url,
                            output_filename=f"{job.id}.mp4",
                            output_dir=OUTPUT_DIR,
                        )

                    if not raw_path or not os.path.exists(raw_path):
                        raise Exception("Không tải được video từ Dola")
                    if native_pro:
                        info = await asyncio.to_thread(vd.get_video_info, raw_path)
                        actual_duration = float(info.get('duration') or 0)
                        if not info.get('width') or abs(actual_duration - job.duration_target) > 0.25:
                            raise Exception(
                                f'DURATION_MISMATCH: cần {job.duration_target}s, file thực tế {actual_duration:.3f}s. '
                                f'Giữ file để kiểm tra: {raw_path}; không tự gửi lại để tránh tốn credit.')

                except Exception as e:
                    err_msg = str(e)
                    
                    # ── Phân loại lỗi để quyết định retry ──
                    NOT_RETRYABLE_KEYWORDS = [
                        "safety policy", "content violation", "vi phạm chính sách",
                        "inappropriate content", "prompt rejected", "từ chối yêu cầu",
                        "vi phạm tiêu chuẩn", "không tuân thủ",
                        "giới hạn tạo video", "daily limit", "out of credits",
                        "hết credit", "hết điểm", "generation limit",
                        "limit reached", "insufficient credits",
                    ]
                    is_retryable = not any(kw in err_msg.lower() for kw in NOT_RETRYABLE_KEYWORDS)
                    if native_pro:
                        # Session/quota/backend errors need a different account;
                        # a billed but wrong-length result must not be resubmitted.
                        safety = ('safety policy', 'content violation', 'vi phạm chính sách', 'inappropriate content')
                        is_retryable = not any(kw in err_msg.lower() for kw in (*safety, 'duration_mismatch'))
                    
                    can_retry = is_retryable and (job.retries < job.max_retries) and self._running
                    
                    if can_retry:
                        job.retries += 1
                        job.error = err_msg
                        
                        # Thử đổi tài khoản nếu có tài khoản khác có session
                        from session_store import SessionStore
                        sessions = SessionStore()
                        am.load()
                        other_accs = [a['name'] for a in am.get_all()
                                      if a['name'] not in job.attempted_accounts
                                      and a.get('status') != 'error'
                                      and sessions.has_session(a['name'])]
                        if other_accs:
                            next_acc = other_accs[0]
                            old_acc = job.account_name
                            job.account_name = next_acc
                            self._notify_progress(worker_id, job.id,
                                f"🔄 RETRY {job.retries}/{job.max_retries}: {err_msg[:80]}... → đổi sang account '{next_acc}'")
                        else:
                            self._notify_progress(worker_id, job.id,
                                f"🔄 RETRY {job.retries}/{job.max_retries}: {err_msg[:80]}... → account '{job.account_name}'")
                        
                        job.status = "queued"
                        job.started_at = 0.0
                        await bm.cleanup_worker(worker_id)
                        await self.job_queue.put(job)
                        continue
                    else:
                        job.status = "failed"
                        job.error = err_msg
                        job.completed_at = time.time()
                        self._stats["total_failed"] += 1
                        if not is_retryable:
                            self._notify_progress(worker_id, job.id, 
                                f"❌ KHÔNG THỂ RETRY (policy/quota): {err_msg[:120]}")
                        else:
                            self._notify_progress(worker_id, job.id, 
                                f"❌ THẤT BẠI (đã thử {job.retries} lần): {err_msg[:120]}")
                        self.failed_jobs.append(job)

                finally:
                    # ── 7. ĐÓNG Chrome tạm TRƯỚC KHI upscale → Giải phóng ~80MB RAM ──
                    await bm.cleanup_worker(worker_id)

                # ── 8. Upscale 4K (KHÔNG cần Chrome, chỉ dùng FFmpeg/GPU) ──
                if job.status != "failed" and raw_path and os.path.exists(raw_path):
                    final_path = raw_path
                    if job.upscale != "off":
                        job.status = "upscaling"
                        self._notify_progress(worker_id, job.id,
                            f"Upscale {job.upscale} (FFmpeg GPU)...")
                        try:
                            upscaled = await vd.upscale_video(
                                raw_path, target=job.upscale, output_dir=OUTPUT_DIR)
                            if upscaled and os.path.exists(upscaled):
                                final_path = upscaled
                        except Exception as e:
                            self._notify_progress(worker_id, job.id,
                                f"Upscale loi (giu video goc): {e}")

                    job.status = "completed"
                    job.output_path = final_path
                    job.completed_at = time.time()
                    self._stats["total_completed"] += 1
                    self._notify_progress(worker_id, job.id,
                        f"HOAN THANH! {os.path.basename(final_path)} ({job.elapsed}s)")

                # ── Finalize job ──
                if job.id in self.active_jobs:
                    del self.active_jobs[job.id]
                if job.status == "completed":
                    self.completed_jobs.append(job)

                if self._on_job_done:
                    try:
                        self._on_job_done(job)
                    except Exception:
                        pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                log("Worker", f"Worker #{worker_id} unhandled error: {e}")
                await asyncio.sleep(2)

        await bm.cleanup_all()
        log("Worker", f"Worker #{worker_id} stopped.")

    # ─── Pool Control ─────────────────────────────────────────────────────

    async def start(self, num_workers: int = None):
        """Khởi động pool với N workers."""
        if num_workers is None:
            num_workers = self.max_workers
        num_workers = min(num_workers, self.max_workers, self.MAX_WORKERS_LIMIT)

        self._running = True
        self._stats["start_time"] = time.time()

        for wid in range(num_workers):
            task = asyncio.create_task(self._worker_loop(wid))
            self._worker_tasks[wid] = task

        log("WorkerPool", f"Started {num_workers} workers (max={self.max_workers}).")

    async def stop(self):
        """Dừng tất cả workers."""
        if self._stop_task is None or self._stop_task.done():
            self._stop_task = asyncio.create_task(self._stop_workers())
        await asyncio.shield(self._stop_task)

    async def _stop_workers(self):
        """Serialize UI-stop and natural pool shutdown so cleanup isn't canceled twice."""
        self._running = False

        # Chờ tối đa 5s cho workers dừng graceful
        for wid, task in self._worker_tasks.items():
            task.cancel()
        
        for wid, task in list(self._worker_tasks.items()):
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        self._worker_tasks.clear()
        for job in self.all_jobs:
            if job.status in ('queued', 'running', 'downloading', 'upscaling'):
                job.status = 'cancelled'
                job.completed_at = time.time()
        self.active_jobs.clear()
        while not self.job_queue.empty():
            try:
                self.job_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        elapsed = int(time.time() - self._stats["start_time"]) if self._stats["start_time"] > 0 else 0
        log("WorkerPool",
            f"All workers stopped. "
            f"Completed: {self._stats['total_completed']}, "
            f"Failed: {self._stats['total_failed']}, "
            f"Total time: {elapsed}s")

    def get_status(self) -> dict:
        """Trả về trạng thái pool."""
        return {
            "running": self._running,
            "num_workers": len(self._worker_tasks),
            "max_workers": self.max_workers,
            "total_jobs": len(self.all_jobs),
            "queue_size": self.job_queue.qsize(),
            "active_jobs": len(self.active_jobs),
            "completed_jobs": len(self.completed_jobs),
            "failed_jobs": len(self.failed_jobs),
            "stats": self._stats.copy(),
            "all_jobs": [
                {
                    "id": j.id,
                    "prompt": j.prompt,
                    "account": j.account_name,
                    "status": j.status,
                    "status_display": j.status_display,
                    "current_step": j.current_step,
                    "worker": j.worker_id,
                    "elapsed": j.elapsed,
                    "elapsed_str": j.formatted_elapsed,
                    "output_path": j.output_path,
                    "error": j.error,
                }
                for j in self.all_jobs
            ],
            "jobs": {
                jid: {
                    "account": j.account_name,
                    "status": j.status,
                    "status_display": j.status_display,
                    "current_step": j.current_step,
                    "worker": j.worker_id,
                    "proxy": j.proxy_used[:30] if j.proxy_used else "",
                    "elapsed": j.elapsed,
                    "elapsed_str": j.formatted_elapsed,
                }
                for jid, j in self.active_jobs.items()
            },
        }

    @property
    def is_idle(self) -> bool:
        """Pool đang rảnh (không có job nào đang chạy hoặc trong queue)."""
        return len(self.active_jobs) == 0 and self.job_queue.qsize() == 0
