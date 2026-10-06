import threading

import cv2
import numpy as np
from rapidocr import RapidOCR

# Only text whose box centre sits in the bottom part of the frame counts as a subtitle; text higher up is
# left alone so a title card or sign in the middle of the picture can't shrink the frame to nothing.
SUBTITLE_ZONE = 0.6
# Gap kept between a crop edge and any text box, as a fraction of frame height.
MARGIN = 0.02
# Detection score at or above which text left in the cropped frame triggers a second, text-avoiding crop.
# The detector itself keeps boxes from 0.5 up; clear burned-in subtitles score around 0.8.
TEXT_SCORE = 0.7
# Re-detection rounds after the text-avoiding crop, in case a smaller frame surfaces text missed before.
MAX_ROUNDS = 3
# The detector occasionally returns one box spanning most of the frame on text-free footage; a real
# line of text never covers this much of the picture, so such boxes are ignored.
MAX_BOX_AREA = 0.5
JPEG_QUALITY = 90

_engine = None
_lock = threading.Lock()


def _detect(image: np.ndarray) -> list[tuple[np.ndarray, float]]:
    """PaddleOCR (PP-OCR) text detection via RapidOCR/onnxruntime; returns (4-point box, score), no recognition."""
    global _engine
    with _lock:  # one shared model; loading is slow and inference isn't worth parallelising here
        if _engine is None:
            _engine = RapidOCR(params={"Global.use_cls": False, "Global.use_rec": False})
        result = _engine(image, use_det=True, use_cls=False, use_rec=False)
    if result.boxes is None:
        return []
    max_area = image.shape[0] * image.shape[1] * MAX_BOX_AREA
    return [
        (box, score)
        for box, score in zip(result.boxes, result.scores)
        if np.ptp(box[:, 0]) * np.ptp(box[:, 1]) <= max_area
    ]


def _largest_text_free_rect(
    width: int, height: int, obstacles: list[tuple[float, float, float, float]], aspect: float
) -> tuple[int, int, int, int]:
    """Largest (x, y, w, h) with w / h == aspect inside width x height that overlaps no obstacle.

    Any optimal rectangle can be slid left and up until it touches the frame edge or an obstacle, so its
    left edge is 0 or an obstacle's right edge and its top edge is 0 or an obstacle's bottom edge. For each
    such corner, grow the rectangle down-right until the frame or an obstacle stops it.
    """
    xs = [0.0] + [x2 for _, _, x2, _ in obstacles if x2 < width]
    ys = [0.0] + [y2 for _, _, _, y2 in obstacles if y2 < height]
    best = (0, 0, 0, 0)
    for x in xs:
        for y in ys:
            h = min(height - y, (width - x) / aspect)
            for ox1, oy1, ox2, oy2 in obstacles:
                if ox2 > x and oy2 > y:
                    # The grown rectangle hits this obstacle only once it is past it both horizontally and vertically.
                    h = min(h, max((ox1 - x) / aspect, oy1 - y))
            if h > best[3]:
                best = (x, y, h * aspect, h)
    # Snap to whole pixels by shrinking inward, so rounding can never push an edge into an obstacle.
    x, y, w, h = best
    left, top = int(np.ceil(x)), int(np.ceil(y))
    max_w, max_h = int(x + w) - left, int(y + h) - top
    h = min(max_h, int(max_w / aspect))
    return left, top, min(round(h * aspect), max_w), h


def crop_subtitles(png: bytes) -> tuple[bytes, bool, bool]:
    """Cut text out of the frame, keeping the original aspect ratio (e.g. 16:9).

    1. Subtitles: cut just above the highest text box near the bottom, then trim both sides equally.
    2. If confident text is still visible, crop to the largest same-shape area that avoids every text box.
    Returns (jpeg, was_cropped, text_free).
    """
    image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    height, width = image.shape[:2]
    aspect = width / height
    margin = height * MARGIN
    detections = _detect(image)
    cropped = False

    tops = [box[:, 1].min() for box, _ in detections if box[:, 1].mean() > height * SUBTITLE_ZONE]
    if tops:
        new_height = max(int(min(tops) - margin), 1)
        new_width = round(new_height * aspect)
        left = (width - new_width) // 2
        image = image[:new_height, left : left + new_width]
        detections = _detect(image)
        cropped = True

    for _ in range(MAX_ROUNDS):
        texts = [box for box, score in detections if score >= TEXT_SCORE]
        if not texts:
            break
        h, w = image.shape[:2]
        obstacles = [
            (box[:, 0].min() - margin, box[:, 1].min() - margin, box[:, 0].max() + margin, box[:, 1].max() + margin)
            for box in texts
        ]
        x, y, rw, rh = _largest_text_free_rect(w, h, obstacles, aspect)
        if rw < 2 or rh < 2:  # text everywhere: keep the frame rather than return nothing
            break
        image = image[y : y + rh, x : x + rw]
        detections = _detect(image)
        cropped = True

    text_free = not any(score >= TEXT_SCORE for _, score in detections)
    ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return jpeg.tobytes(), cropped, text_free
