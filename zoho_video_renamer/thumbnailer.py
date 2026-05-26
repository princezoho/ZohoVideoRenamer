"""Generate thumbnails for stills and extract representative frames from videos.

Tries the bundled imageio-ffmpeg binary first (so the desktop app Just Works
without requiring users to install ffmpeg manually), then falls back to a
system-installed ffmpeg/ffprobe on PATH if imageio-ffmpeg isn't available.
Stills are downsized with Pillow (no external binary needed).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from PIL import Image


def safe_id(s: str, maxlen: int = 200) -> str:
    """Convert an arbitrary string into a filesystem-safe filename stem."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", s)[:maxlen]


def _bundled_ffmpeg() -> Optional[str]:
    """Return path to the imageio-ffmpeg-bundled ffmpeg binary, if installed."""
    try:
        import imageio_ffmpeg  # noqa: F401
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return None


def check_ffmpeg() -> Optional[str]:
    """Return path to ffmpeg, preferring the bundled binary then system PATH."""
    return _bundled_ffmpeg() or shutil.which("ffmpeg")


def check_ffprobe() -> Optional[str]:
    """Return path to ffprobe. Only available if user has system ffmpeg installed;
    imageio-ffmpeg bundles ffmpeg only, not ffprobe. For our thumbnail use case
    we don't actually need ffprobe — extract_video_frame works with ffmpeg alone."""
    return shutil.which("ffprobe")


def _ffmpeg_cmd() -> str:
    """Return the ffmpeg executable to invoke. Bundled binary preferred."""
    return check_ffmpeg() or "ffmpeg"


def get_video_duration(path: str, timeout: float = 10.0) -> Optional[float]:
    """Return duration in seconds via ffprobe, or None on failure."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return float(r.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return None


def make_still_thumb(src: str, dst: str, max_width: int = 400, quality: int = 78) -> bool:
    """Create a JPEG thumbnail of a still image. Returns True on success."""
    if os.path.exists(dst):
        return True
    try:
        with Image.open(src) as im:
            im.thumbnail((max_width, max_width), Image.LANCZOS)
            if im.mode in ("RGBA", "P", "LA"):
                im = im.convert("RGB")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            im.save(dst, "JPEG", quality=quality)
        return True
    except Exception:
        return False


def extract_video_frame(
    src: str,
    dst: str,
    seek_seconds: float = 0.5,
    max_width: int = 400,
    quality: int = 5,
    timeout: float = 30.0,
) -> bool:
    """Extract a single frame from a video at seek_seconds. Resizes to max_width.

    quality is ffmpeg's -q:v (lower is better, 2-5 is good range).
    """
    if os.path.exists(dst):
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cmd = [
        _ffmpeg_cmd(), "-y", "-loglevel", "error",
        "-ss", str(seek_seconds), "-i", src,
        "-frames:v", "1",
        "-vf", f"scale={max_width}:-2",
        "-q:v", str(quality), dst,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0 and os.path.exists(dst)
    except (subprocess.TimeoutExpired, OSError):
        return False


def extract_video_frame_full(
    src: str,
    dst: str,
    seek_seconds: float = 0.5,
    timeout: float = 30.0,
) -> bool:
    """Extract a single frame at the video's native resolution as PNG."""
    if os.path.exists(dst):
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cmd = [
        _ffmpeg_cmd(), "-y", "-loglevel", "error",
        "-ss", str(seek_seconds), "-i", src,
        "-frames:v", "1",
        "-q:v", "1", dst,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0 and os.path.exists(dst)
    except (subprocess.TimeoutExpired, OSError):
        return False


def batch_make_still_thumbs(
    tasks: list[tuple[str, str]],
    max_workers: int = 4,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> tuple[int, int]:
    """tasks: list of (src, dst). Returns (ok_count, fail_count)."""
    ok = 0
    fail = 0
    total = len(tasks)
    # Pillow releases the GIL during many image ops; ThreadPool is fine.
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(make_still_thumb, s, d): (s, d) for s, d in tasks}
        for fut in as_completed(futures):
            if fut.result():
                ok += 1
            else:
                fail += 1
            if on_progress:
                on_progress(ok + fail, total)
    return ok, fail


def batch_extract_video_frames(
    tasks: list[tuple[str, str, float]],
    max_workers: int = 4,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> tuple[int, int]:
    """tasks: list of (src, dst, seek_seconds). Returns (ok_count, fail_count)."""
    ok = 0
    fail = 0
    total = len(tasks)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(extract_video_frame, s, d, t): (s, d) for s, d, t in tasks}
        for fut in as_completed(futures):
            if fut.result():
                ok += 1
            else:
                fail += 1
            if on_progress:
                on_progress(ok + fail, total)
    return ok, fail
