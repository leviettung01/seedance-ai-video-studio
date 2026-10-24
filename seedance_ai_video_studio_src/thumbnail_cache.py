# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Thumbnail Cache
Trích xuất thumbnail từ video bằng FFmpeg, cache trong .thumbnails/
"""

import os
import subprocess
import hashlib
from typing import Optional

from config import OUTPUT_DIR

THUMB_DIR = os.path.join(OUTPUT_DIR, ".thumbnails")
THUMB_WIDTH = 320
THUMB_HEIGHT = 180


def ensure_thumb_dir():
    os.makedirs(THUMB_DIR, exist_ok=True)


def get_thumb_path(video_path: str) -> str:
    """Trả về đường dẫn thumbnail cho video."""
    basename = os.path.basename(video_path)
    name_hash = hashlib.md5(basename.encode()).hexdigest()[:10]
    return os.path.join(THUMB_DIR, f"{name_hash}.jpg")


def extract_thumbnail(video_path: str, force: bool = False) -> Optional[str]:
    """Trích xuất frame đầu tiên từ video làm thumbnail.
    
    Returns: Đường dẫn ảnh thumbnail, hoặc None nếu lỗi.
    """
    ensure_thumb_dir()
    thumb_path = get_thumb_path(video_path)

    if os.path.isfile(thumb_path) and not force:
        return thumb_path

    if not os.path.isfile(video_path):
        return None

    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", "00:00:01",
            "-vframes", "1",
            "-vf", f"scale={THUMB_WIDTH}:{THUMB_HEIGHT}:force_original_aspect_ratio=decrease,"
                   f"pad={THUMB_WIDTH}:{THUMB_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-q:v", "3",
            thumb_path,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if os.path.isfile(thumb_path):
            return thumb_path
    except Exception:
        pass

    return None


def extract_all_thumbnails(video_dir: str = OUTPUT_DIR) -> dict[str, str]:
    """Trích xuất thumbnail cho tất cả video trong thư mục.
    
    Returns: dict {video_path: thumb_path}
    """
    results = {}
    if not os.path.isdir(video_dir):
        return results

    for fname in os.listdir(video_dir):
        if fname.lower().endswith((".mp4", ".webm", ".mkv")):
            vpath = os.path.join(video_dir, fname)
            thumb = extract_thumbnail(vpath)
            if thumb:
                results[vpath] = thumb

    return results


def get_video_info(video_path: str) -> dict:
    """Lấy thông tin video (duration, resolution, size) bằng ffprobe."""
    info = {
        "duration": 0,
        "width": 0,
        "height": 0,
        "size_mb": 0,
        "codec": "",
    }

    if not os.path.isfile(video_path):
        return info

    info["size_mb"] = round(os.path.getsize(video_path) / (1024 * 1024), 1)

    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            info["duration"] = round(float(fmt.get("duration", 0)))

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    info["width"] = int(stream.get("width", 0))
                    info["height"] = int(stream.get("height", 0))
                    info["codec"] = stream.get("codec_name", "")
                    break
    except Exception:
        pass

    return info
