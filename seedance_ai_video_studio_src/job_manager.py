# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Job Manager
Quản lý hàng đợi công việc tạo video: tạo, polling, cancel, lifecycle.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable

from config import OUTPUT_DIR, EXTENSION_DIR
from utils import generate_job_id, get_timestamp, log_info, log


@dataclass
class Job:
    """Mô hình dữ liệu 1 job tạo video."""
    id: str = ""
    status: str = "queued"             # "queued" | "running" | "completed" | "failed" | "cancelled"
    prompt: str = ""
    aspect_ratio: str = "16:9"         # "16:9" | "9:16" | "1:1"
    mode: str = "standard"             # "standard" | "pro_15s"
    duration_target: int = 31          # 31 cho 30s, 15 cho 15s
    model_version: str = "2.5"         # "2.0" | "2.5"
    enable_upscale: bool = True
    upscale_target: str = "2K"         # "2K" | "4K"
    image_path: str = ""               # Ảnh tham chiếu (optional)
    account_name: str = ""             # Account được assign
    progress: str = ""                 # Message tiến độ hiện tại
    output_path: str = ""              # Đường dẫn file video đầu ra
    video_url: str = ""                # URL video gốc đã tải
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class JobManager:
    """Quản lý job queue và lifecycle."""

    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        # Các dependency sẽ được inject từ api_server
        self.account_manager = None
        self.proxy_manager = None
        self.browser_manager = None
        self.dola_automation = None
        self.video_downloader = None

    def inject_dependencies(
        self, account_manager, proxy_manager,
        browser_manager, dola_automation, video_downloader
    ):
        """Inject dependencies sau khi tất cả managers được khởi tạo."""
        self.account_manager = account_manager
        self.proxy_manager = proxy_manager
        self.browser_manager = browser_manager
        self.dola_automation = dola_automation
        self.video_downloader = video_downloader

    # ─── CRUD ─────────────────────────────────────────────────────────────

    def create_job(self, **kwargs) -> Job:
        """Tạo job mới."""
        job = Job(
            id=generate_job_id(),
            created_at=get_timestamp(),
            **kwargs,
        )
        self.jobs[job.id] = job
        log("Upscale", f"Job {job.id}: enable_upscale={job.enable_upscale}, target={job.upscale_target}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Lấy thông tin job."""
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> list[dict]:
        """Trả về tất cả jobs dạng dict, mới nhất trước."""
        jobs = list(self.jobs.values())
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs]

    def update_job(self, job_id: str, **kwargs):
        """Cập nhật trạng thái job."""
        job = self.jobs.get(job_id)
        if not job:
            return
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

    def cancel_job(self, job_id: str) -> bool:
        """Hủy job."""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in ("queued", "running"):
            job.status = "cancelled"
            job.completed_at = get_timestamp()

            # Cancel Dola automation
            if self.dola_automation:
                self.dola_automation.cancel()

            # Cancel asyncio task
            task = self._tasks.get(job_id)
            if task and not task.done():
                task.cancel()

            log_info(f"🚫 Job {job_id} đã bị hủy.")
            return True
        return False

    # ─── Job Execution ────────────────────────────────────────────────────

    async def run_job(self, job_id: str):
        """Thực thi toàn bộ flow tạo video cho 1 job.
        
        Flow:
        1. Chọn account → Xoay proxy → Launch Chrome
        2. Setup Extension → Navigate Dola
        3. Chạy dola_automation.execute_generation_flow()
        4. Download video → Upscale nếu cần
        5. Cập nhật trạng thái → Đóng Chrome
        """
        job = self.jobs.get(job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = get_timestamp()
        account_name = ""

        try:
            # 1. Chọn account
            account = self.account_manager.get_available_account()
            if not account:
                raise Exception("Không có tài khoản nào sẵn sàng (tất cả đã hết quota hoặc đang cooldown)")

            account_name = account.name
            job.account_name = account_name
            self.account_manager.reserve_quota(account_name)
            log_info(f"Khởi tạo phiên Chrome chính chủ: {account_name}")

            # 2. Xoay proxy
            job.progress = "Đang xoay proxy..."
            proxy_url = await self.proxy_manager.get_proxy_for_account(
                account_name, account.proxy
            )
            if proxy_url:
                log_info(f"[🔗 Proxy Final] Account '{account_name}' → {proxy_url}...")

            # 3. Launch Chrome
            job.progress = "Đang khởi động Chrome..."
            port = await self.browser_manager.launch_chrome(
                account_name, proxy_url=proxy_url, minimized=True
            )
            await asyncio.sleep(3)

            # 4. Kết nối Playwright
            browser = await self.browser_manager.connect_playwright(account_name)
            if not browser:
                raise Exception("Không thể kết nối Playwright tới Chrome")

            page = await self.browser_manager.get_page(account_name)
            if not page:
                raise Exception("Không có page nào mở trong Chrome")

            # 5. Setup Extension
            job.progress = "Đang cài đặt Extension..."
            from cdp_helper import CDPHelper
            await CDPHelper.full_extension_setup(page, EXTENSION_DIR, account_name)

            # 6. Navigate tới Dola
            await self.browser_manager.navigate_to_dola(page)
            await asyncio.sleep(3)

            # 7. Chạy automation flow
            job.progress = "Đang tạo video trên Dola AI..."

            def progress_callback(msg):
                job.progress = msg

            video_url = await self.dola_automation.execute_generation_flow(
                page=page,
                prompt=job.prompt,
                aspect_ratio=job.aspect_ratio,
                image_path=job.image_path,
                mode=job.mode,
                duration_target=job.duration_target,
                model_version=job.model_version,
                progress_callback=progress_callback,
            )

            if not video_url:
                log_info("Quét DOM lần cuối tìm video...")
                log_info(f"🔍 Finally block: video_found_path = None")
                raise Exception("Quá thời gian tạo video hoặc không lấy được kết quả.")

            job.video_url = video_url

            # 8. Download video
            job.progress = "Đang tải video..."
            output_filename = "Scene_1.mp4"
            output_path = await self.video_downloader.download_video(
                video_url, output_filename, OUTPUT_DIR
            )

            if not output_path:
                raise Exception("Không thể tải video từ URL")

            log_info(f"🔍 Finally block: video_found_path = {output_path}")
            log_info(f"✅ Video đã tải thành công: {output_path} — Chrome sẽ được api_server tắt sau.")

            # 9. Upscale nếu cần
            if job.enable_upscale and output_path:
                job.progress = f"Đang nâng cấp video lên {job.upscale_target}..."
                upscaled_path = await self.video_downloader.upscale_video(
                    output_path, job.upscale_target, OUTPUT_DIR
                )
                if upscaled_path and upscaled_path != output_path:
                    # Cleanup file tạm
                    upscaled_filename = os.path.basename(upscaled_path)
                    self.video_downloader.cleanup_temp_downloads(
                        OUTPUT_DIR, upscaled_filename
                    )
                    output_path = upscaled_path

            job.output_path = output_path
            job.status = "completed"
            job.completed_at = get_timestamp()
            job.progress = "Hoàn thành!"

            # Trừ quota
            if job.duration_target >= 30:
                self.account_manager.deduct_quota(account_name, 2)
            else:
                self.account_manager.deduct_quota(account_name, 1)

            log_info(f"Hoàn thành! Video đã tải về: {os.path.basename(output_path)}")

        except asyncio.CancelledError:
            job.status = "cancelled"
            job.completed_at = get_timestamp()
            job.progress = "Đã hủy"
            log_info(f"🚫 Job {job_id} bị hủy.")

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = get_timestamp()
            job.progress = f"Lỗi: {e}"
            log_info(f"Lỗi: {e}")

        finally:
            # Release reservation
            if account_name:
                self.account_manager.release_reservation(account_name)

            # Đóng Chrome
            if account_name:
                if job.status == "failed":
                    log_info("❌ Video không tải được — đang tắt Chrome...")
                    await self.browser_manager.force_kill_chrome(account_name)
                    log_info("🔒 Tạo video thất bại — đã tắt Chrome.")
                else:
                    log_info("📡 Đã ngắt kết nối Playwright (Chrome vẫn sống).")
                    await self.browser_manager.close_chrome(account_name)

    def start_job(self, job_id: str):
        """Khởi chạy job trong asyncio task nền."""
        task = asyncio.create_task(self.run_job(job_id))
        self._tasks[job_id] = task
        return task
