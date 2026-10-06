import base64
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import yt_dlp

from app.text_crop import crop_subtitles

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}

# Progressive/DASH over plain HTTP(S) so ffmpeg can seek straight to a timestamp; HLS is a last resort.
FORMAT = "bv*[height<=720][protocol^=http]/b[height<=720][protocol^=http]/bv*[height<=720]/b"


class ScreenshotError(Exception):
    pass


def is_youtube_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in YOUTUBE_HOSTS


def _extract_stream(url: str) -> dict:
    opts = {"format": FORMAT, "quiet": True, "no_warnings": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise ScreenshotError(str(e).removeprefix("ERROR: ")) from e

    if info.get("is_live"):
        raise ScreenshotError("Live streams are not supported")
    if not info.get("duration"):
        raise ScreenshotError("Could not determine the video duration")
    # A merged selection (video+audio) lists its parts in requested_formats; take the video one.
    fmt = (info.get("requested_formats") or [info])[0]
    return {
        "title": info.get("title"),
        "duration": info["duration"],
        "stream_url": fmt["url"],
        "headers": fmt.get("http_headers") or info.get("http_headers") or {},
    }


def _slots(end: float, count: int) -> list[tuple[float, float]]:
    """Split [0, end] into `count` equal slots, each narrowed to its middle half.

    One frame comes from each slot, so the screenshots spread evenly over the video and neighbours
    can't meet at a shared slot boundary.
    """
    slot = end / count
    return [(i * slot + slot / 4, i * slot + slot * 3 / 4) for i in range(count)]


def _grab_frame(stream_url: str, headers: dict, timestamp: float) -> bytes:
    header_arg = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", f"{timestamp:.3f}",  # before -i: fast input seek
        "-headers", header_arg,
        "-i", stream_url,
        # Lossless PNG: the frame is cropped and only then compressed to JPEG once.
        "-frames:v", "1", "-f", "image2", "-c:v", "png", "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0 or not result.stdout:
        raise ScreenshotError(f"ffmpeg failed at {timestamp:.1f}s: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def random_screenshots(url: str, count: int) -> dict:
    stream = _extract_stream(url)
    duration = stream["duration"]
    # Stay clear of the very end, where seeking can land past the last frame.
    slots = _slots(max(duration - 1, 0.1), count)

    def capture(slot: tuple[float, float]) -> dict:
        t = random.uniform(*slot)
        jpg, cropped, text_free = crop_subtitles(_grab_frame(stream["stream_url"], stream["headers"], t))
        return {
            "timestamp": t,
            "cropped": cropped,
            "text_free": text_free,
            "image": "data:image/jpeg;base64," + base64.b64encode(jpg).decode(),
        }

    with ThreadPoolExecutor(max_workers=count) as pool:
        screenshots = list(pool.map(capture, slots))

    return {"title": stream["title"], "duration": duration, "screenshots": screenshots}
