# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio v5.0 — Job Tracker
Theo dõi và mapping video ↔ request.
Mỗi video tạo ra được gán TrackedJob chứa đầy đủ metadata.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from config import DATA_DIR, OUTPUT_DIR
from utils import log, get_timestamp


JOB_HISTORY_FILE = os.path.join(DATA_DIR, "job_history.json")


@dataclass
class TrackedJob:
    """1 job tạo video đã/đang được theo dõi."""
    job_id: str
    stt: int                    # Số thứ tự trong batch
    prompt: str                 # Prompt gốc
    account_name: str           # Nick tạo
    model: str = "2.5"          # Seedance 2.0/2.5
    duration: int = 30          # 5/10/15/20/25/30s
    aspect_ratio: str = "9:16"  # 9:16, 16:9, etc.
    status: str = "queued"      # queued/running/completed/failed
    video_url: str = ""         # URL video từ Dola
    output_file: str = ""       # Tên file local
    output_path: str = ""       # Full path file local
    thumbnail_path: str = ""    # Path thumbnail
    created_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TrackedJob":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def generate_video_filename(job_index: int, prompt: str, video_number: int = 0) -> str:
    """Tạo tên file video theo format PR{index}_video_{nn}_{keywords}.mp4

    Ví dụ:
    - PR7_video_07_create_a_continuous_30_second_cinematic.mp4
    - PR1_canh_1_dem_mua_bao_lon.mp4

    Args:
        job_index: Số thứ tự job trong batch (1, 2, 3...)
        prompt: Prompt gốc
        video_number: Số thứ tự video global (nếu 0 → dùng job_index)
    """
    vn = video_number if video_number > 0 else job_index

    # Sanitize prompt → keywords
    # Bỏ ký tự đặc biệt, giữ chữ và số
    words = re.sub(r'[^\w\s]', '', prompt).split()[:8]
    slug = '_'.join(w.lower() for w in words)[:60]

    if not slug:
        slug = f"video_{vn:02d}"

    return f"PR{job_index}_video_{vn:02d}_{slug}.mp4"


class JobTracker:
    """Quản lý lịch sử và mapping video ↔ request."""

    def __init__(self):
        self._history: list[dict] = []
        self._current_batch: list[TrackedJob] = []
        self._batch_counter: int = 0
        self.load()

    def load(self):
        """Đọc lịch sử jobs từ file."""
        if os.path.isfile(JOB_HISTORY_FILE):
            try:
                with open(JOB_HISTORY_FILE, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except Exception:
                self._history = []
        count = len(self._history)
        if count:
            log("JobTracker", f"Loaded {count} historical jobs from disk.")

    def save(self):
        """Ghi lịch sử jobs ra file."""
        try:
            os.makedirs(os.path.dirname(JOB_HISTORY_FILE), exist_ok=True)
            with open(JOB_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log("JobTracker", f"Error saving history: {e}")

    # ─── Batch Management ────────────────────────────────────────────

    def start_batch(self, prompts: list[str], account_names: list[str],
                    model: str, duration: int, aspect_ratio: str) -> list[TrackedJob]:
        """Tạo batch mới từ danh sách prompts.

        Returns: list[TrackedJob] đã tạo
        """
        self._batch_counter += 1
        self._current_batch = []

        for i, prompt in enumerate(prompts):
            stt = i + 1
            acc = account_names[i % len(account_names)] if account_names else "unknown"
            filename = generate_video_filename(stt, prompt, stt)

            job = TrackedJob(
                job_id=f"batch{self._batch_counter}_job{stt}",
                stt=stt,
                prompt=prompt,
                account_name=acc,
                model=model,
                duration=duration,
                aspect_ratio=aspect_ratio,
                output_file=filename,
                output_path=os.path.join(OUTPUT_DIR, filename),
                created_at=time.time(),
            )
            self._current_batch.append(job)

        log("JobTracker", f"Created batch #{self._batch_counter} with {len(self._current_batch)} jobs")
        return self._current_batch

    def update_job_status(self, job_id: str, status: str, **kwargs):
        """Cập nhật trạng thái job."""
        for job in self._current_batch:
            if job.job_id == job_id:
                job.status = status
                for k, v in kwargs.items():
                    if hasattr(job, k):
                        setattr(job, k, v)
                if status == "completed":
                    job.completed_at = time.time()
                break

    def complete_job(self, job_id: str, video_url: str = "",
                     output_path: str = "", thumbnail_path: str = ""):
        """Đánh dấu job hoàn thành."""
        self.update_job_status(
            job_id, "completed",
            video_url=video_url,
            output_path=output_path,
            thumbnail_path=thumbnail_path,
        )
        # Lưu vào history
        for job in self._current_batch:
            if job.job_id == job_id:
                self._history.append(job.to_dict())
                break
        self.save()

    def fail_job(self, job_id: str, error: str = ""):
        """Đánh dấu job thất bại."""
        self.update_job_status(job_id, "failed", error=error)
        for job in self._current_batch:
            if job.job_id == job_id:
                self._history.append(job.to_dict())
                break
        self.save()

    # ─── Query ───────────────────────────────────────────────────────

    def get_current_batch(self) -> list[TrackedJob]:
        """Lấy batch hiện tại."""
        return self._current_batch

    def get_job_by_id(self, job_id: str) -> Optional[TrackedJob]:
        """Tìm job theo ID."""
        for job in self._current_batch:
            if job.job_id == job_id:
                return job
        return None

    def lookup_by_filename(self, filename: str) -> Optional[dict]:
        """Tra ngược từ tên file → metadata job."""
        for item in reversed(self._history):
            if item.get("output_file") == filename:
                return item
        return None

    def get_batch_summary(self) -> dict:
        """Thống kê batch hiện tại."""
        total = len(self._current_batch)
        completed = sum(1 for j in self._current_batch if j.status == "completed")
        running = sum(1 for j in self._current_batch if j.status == "running")
        failed = sum(1 for j in self._current_batch if j.status == "failed")
        queued = sum(1 for j in self._current_batch if j.status == "queued")

        return {
            "total": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "queued": queued,
        }

    def get_history(self, limit: int = 100) -> list[dict]:
        """Lấy lịch sử gần nhất."""
        return self._history[-limit:]

    def export_csv(self, filepath: str):
        """Xuất lịch sử ra CSV."""
        import csv
        fieldnames = ["job_id", "stt", "prompt", "account_name", "model",
                       "duration", "aspect_ratio", "status", "output_file",
                       "video_url", "created_at", "completed_at", "error"]
        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in self._history:
                    row = {k: item.get(k, "") for k in fieldnames}
                    writer.writerow(row)
            log("JobTracker", f"Exported {len(self._history)} jobs to {filepath}")
        except Exception as e:
            log("JobTracker", f"Error exporting CSV: {e}")
