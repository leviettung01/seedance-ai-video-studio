# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Video Downloader & FFmpeg Upscale
Tải video từ URL, convert unwatermarked, và upscale 2K/4K.
"""

import asyncio
import json
import os
import re
import subprocess
from fractions import Fraction
from typing import Optional

import httpx

from config import (
    OUTPUT_DIR, DOWNLOAD_DIR, SEEN_URLS_FILE,
    FFMPEG_PATH, FFPROBE_PATH, UPSCALE_ENCODER_PRIORITY,
)
from utils import safe_json_load, safe_json_save, log_info, log, format_bytes, get_timestamp


class VideoDownloader:
    """Tải video + Upscale FFmpeg."""

    def __init__(self):
        self._seen_urls: list[str] = []
        self._load_seen_urls()

    def _load_seen_urls(self):
        """Đọc danh sách URL đã tải."""
        data = safe_json_load(SEEN_URLS_FILE, [])
        if isinstance(data, list):
            self._seen_urls = data

    def _save_seen_urls(self):
        """Ghi danh sách URL đã tải."""
        safe_json_save(SEEN_URLS_FILE, self._seen_urls)

    def _add_seen_url(self, url: str):
        """Thêm URL vào danh sách đã tải."""
        if url not in self._seen_urls:
            self._seen_urls.append(url)
            # Giữ tối đa 100 URL gần nhất
            if len(self._seen_urls) > 100:
                self._seen_urls = self._seen_urls[-100:]
            self._save_seen_urls()

    def is_seen(self, url: str) -> bool:
        """Kiểm tra URL đã từng tải chưa."""
        return url in self._seen_urls

    # ─── URL Conversion ──────────────────────────────────────────────────

    @staticmethod
    def convert_to_unwatermarked(url: str) -> Optional[str]:
        """Chuyển URL watermarked → unwatermarked (lr=unwatermarked / lr=cici_ai + download=true).
        
        Dola/ByteDance CDN sử dụng lr=unwatermarked / lr=cici_ai cho master stream không logo,
        và download=true để tải file master chất lượng cao nhất.
        """
        if not url:
            return url
        
        result = url
        # Thay thế mọi biến thể watermark sang unwatermarked
        for wm_param in ['lr=video_gen_watermark_dyn', 'lr=video_gen_watermark', 'lr=watermarked', 'lr=cici_ai']:
            result = result.replace(wm_param, 'lr=unwatermarked')
            
        if 'lr=' not in result:
            sep = '&' if '?' in result else '?'
            result = f"{result}{sep}lr=unwatermarked"
        
        # Thêm download=true nếu chưa có
        if 'download=true' not in result:
            sep = '&' if '?' in result else '?'
            result = f"{result}{sep}download=true"
        
        return result

    @staticmethod
    def is_high_quality_url(url: str) -> bool:
        """Kiểm tra URL có phải video gốc không watermark không."""
        return 'lr=unwatermarked' in url or 'lr=cici_ai' in url or 'fallback_api' in url

    # ─── Download ─────────────────────────────────────────────────────────

    async def download_video(
        self,
        url: str,
        output_filename: str = "Scene_1.mp4",
        output_dir: str = OUTPUT_DIR,
    ) -> Optional[str]:
        """Tải video từ URL về thư mục output.
        
        Returns: Đường dẫn file output hoặc None nếu lỗi.
        """
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://www.dola.com/",
            }
            async with httpx.AsyncClient(headers=headers, timeout=120, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    if response.status_code not in (200, 206):
                        log_info(f"❌ Lỗi tải video: HTTP {response.status_code}")
                        return None

                    expected_size = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    with open(output_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)

            # Verify
            actual_size = os.path.getsize(output_path)
            if expected_size > 0:
                log("Download OK", f"{format_bytes(actual_size)} bytes / {format_bytes(expected_size)} expected")

            log_info(f"✅ Tải video thành công! ({format_bytes(actual_size)} bytes)")

            # Kiểm tra video gốc không logo
            if self.is_high_quality_url(url):
                log_info("✨ Đã tải video từ URL CDN/master. Tham số URL không chứng minh video không có watermark.")

            # Ghi nhận URL đã tải
            self._add_seen_url(url)

            return output_path

        except Exception as e:
            log_info(f"❌ Lỗi tải video: {e}")
            return None

    # ─── FFmpeg Upscale ───────────────────────────────────────────────────

    @staticmethod
    def get_video_info(filepath: str) -> dict:
        """Lấy thông tin video (width, height, fps) bằng ffprobe."""
        try:
            cmd = [
                FFPROBE_PATH,
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-show_format",
                filepath,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    try:
                        fps = float(Fraction(stream.get("r_frame_rate", "30/1")))
                    except (ValueError, ZeroDivisionError):
                        fps = 30.0
                    return {
                        "width": int(stream.get("width", 0)),
                        "height": int(stream.get("height", 0)),
                        "fps": fps,
                        "codec": stream.get("codec_name", ""),
                        "duration": float(stream.get("duration") or data.get("format", {}).get("duration") or 0),
                    }
        except Exception as e:
            log_info(f"⚠️ Lỗi ffprobe: {e}")

        return {"width": 0, "height": 0, "fps": 30, "codec": "", "duration": 0.0}

    @staticmethod
    def detect_encoder() -> str:
        """Detect encoder khả dụng: GPU trước, CPU fallback."""
        for encoder in UPSCALE_ENCODER_PRIORITY:
            try:
                cmd = [FFMPEG_PATH, "-hide_banner", "-encoders"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if encoder in result.stdout:
                    return encoder
            except Exception:
                continue
        return "libx264"  # Fallback mặc định

    async def upscale_video(
        self,
        input_path: str,
        target: str = "2K",
        output_dir: str = OUTPUT_DIR,
    ) -> Optional[str]:
        """Nâng cấp video lên 2K hoặc 4K bằng FFmpeg.
        
        Returns: Đường dẫn file output hoặc None nếu lỗi.
        """
        log_info(f"⬆️ [Upscale] Bắt đầu nâng cấp video lên {target}...")

        info = self.get_video_info(input_path)
        orig_w, orig_h = info["width"], info["height"]
        if orig_w == 0 or orig_h == 0:
            log_info("⚠️ Không thể xác định resolution gốc. Bỏ qua upscale.")
            return input_path

        # Tính resolution mới
        if target == "4K":
            scale_factor = 3
        else:  # 2K
            scale_factor = 2

        new_w = orig_w * scale_factor
        new_h = orig_h * scale_factor

        # Đảm bảo chia hết cho 2
        new_w = new_w if new_w % 2 == 0 else new_w + 1
        new_h = new_h if new_h % 2 == 0 else new_h + 1

        # Xác định orientation
        orientation = "Dọc" if orig_h > orig_w else "Ngang"
        aspect = f"{orig_w}:{orig_h}"
        if orig_w == orig_h:
            aspect = "1:1"
        elif abs(orig_w / orig_h - 16 / 9) < 0.1:
            aspect = "16:9"
        elif abs(orig_h / orig_w - 16 / 9) < 0.1:
            aspect = "9:16"

        # Detect encoder
        encoder = self.detect_encoder()

        # Build output filename
        ts = int(get_timestamp())
        import random
        rand = random.randint(1000, 9999)
        output_filename = f"dola_vid_{ts}_{rand}_Upscale_{target}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        log_info(f"🎬 [Upscale] Đang nâng cấp video {orig_w}x{orig_h} → {new_w}x{new_h} "
                 f"{aspect} ({orientation}) ({encoder})...")

        # FFmpeg command
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", f"scale={new_w}:{new_h}:flags=lanczos",
            "-c:v", encoder,
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path,
        ]

        # Thêm GPU-specific options
        if "nvenc" in encoder:
            # Thay preset cho NVENC
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-i", input_path,
                "-vf", f"scale={new_w}:{new_h}:flags=lanczos",
                "-c:v", encoder,
                "-preset", "p4",
                "-rc", "vbr",
                "-cq", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path,
            ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="ignore")[-500:]
                log_info(f"❌ [Upscale] FFmpeg error: {err_msg}")

                # Fallback: thử lại với libx264 nếu GPU encoder thất bại
                if encoder != "libx264":
                    log_info("🔄 [Upscale] Thử lại với encoder libx264...")
                    cmd_fallback = [
                        FFMPEG_PATH, "-y",
                        "-i", input_path,
                        "-vf", f"scale={new_w}:{new_h}:flags=lanczos",
                        "-c:v", "libx264",
                        "-preset", "medium",
                        "-crf", "18",
                        "-c:a", "aac", "-b:a", "192k",
                        output_path,
                    ]
                    process2 = await asyncio.create_subprocess_exec(
                        *cmd_fallback,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await process2.communicate()
                    if process2.returncode != 0:
                        return input_path
                    encoder = "libx264"
                else:
                    return input_path

            # Verify output
            orig_size = os.path.getsize(input_path)
            new_size = os.path.getsize(output_path)

            log_info(f"✅ [Upscale] Nâng cấp thành công! {orig_w}x{orig_h} → {new_w}x{new_h} "
                     f"({format_bytes(orig_size)} → {format_bytes(new_size)} bytes, "
                     f"encoder={encoder})")
            log_info(f"✅ [Upscale] Nâng cấp video lên {target} thành công! File: {output_filename}")

            return output_path

        except Exception as e:
            log_info(f"❌ [Upscale] Lỗi: {e}")
            return input_path

    @staticmethod
    def cleanup_temp_downloads(download_dir: str = DOWNLOAD_DIR, filename: str = ""):
        """Dọn dẹp file tạm sau khi upscale."""
        if filename:
            filepath = os.path.join(download_dir, filename)
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    log_info(f"🧹 Đã dọn dẹp file tạm downloads: {filename}")
            except Exception:
                pass

    # ─── List Videos ──────────────────────────────────────────────────────

    @staticmethod
    def list_output_videos(output_dir: str = OUTPUT_DIR) -> list[dict]:
        """Liệt kê tất cả video đã tạo trong thư mục output."""
        videos = []
        try:
            for filename in os.listdir(output_dir):
                if filename.lower().endswith((".mp4", ".webm", ".mov")):
                    filepath = os.path.join(output_dir, filename)
                    stat = os.stat(filepath)
                    videos.append({
                        "filename": filename,
                        "path": filepath,
                        "size": stat.st_size,
                        "created_at": stat.st_ctime,
                    })
            videos.sort(key=lambda x: x["created_at"], reverse=True)
        except Exception:
            pass
        return videos
