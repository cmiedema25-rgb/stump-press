"""Lightweight image quality stats with Pillow (optional)."""

from __future__ import annotations

from io import BytesIO
from typing import Any


def analyze_image_bytes(data: bytes) -> dict[str, Any]:
    """Contrast/brightness stats and a crude 'hard scan' flag. No torch."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return {"available": False, "reason": "pillow_missing"}

    try:
        im = Image.open(BytesIO(data))
        im = im.convert("L")
        # Downscale for speed
        im.thumbnail((512, 512))
        stat = ImageStat.Stat(im)
        mean = float(stat.mean[0])
        stddev = float(stat.stddev[0])
        extrema = im.getextrema()
        lo, hi = float(extrema[0]), float(extrema[1])
        # Histogram entropy-ish / stretch
        hist = im.histogram()
        total = sum(hist) or 1
        # fraction of near-white / near-black (washed or muddy)
        dark = sum(hist[:25]) / total
        bright = sum(hist[230:]) / total
        hard = False
        reasons = []
        if stddev < 28:
            hard = True
            reasons.append("low_contrast")
        if mean < 70 or mean > 200:
            hard = True
            reasons.append("bad_brightness")
        if dark > 0.45 or bright > 0.55:
            hard = True
            reasons.append("clipped_tones")
        if (hi - lo) < 80:
            hard = True
            reasons.append("narrow_dynamic_range")
        return {
            "available": True,
            "width": im.size[0],
            "height": im.size[1],
            "mean_brightness": round(mean, 2),
            "contrast_stddev": round(stddev, 2),
            "min": lo,
            "max": hi,
            "dark_fraction": round(dark, 4),
            "bright_fraction": round(bright, 4),
            "hard_scan": hard,
            "reasons": reasons,
        }
    except Exception as exc:  # noqa: BLE001 — demo-friendly
        return {"available": False, "reason": f"analyze_failed:{type(exc).__name__}"}
