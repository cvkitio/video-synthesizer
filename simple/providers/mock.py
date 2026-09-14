"""Local stand-in provider for tests and dry-runs.

Draws a deterministic placeholder PNG that looks roughly like a CCTV still
(black background, timestamp, frame counter, prompt excerpt). Useful for
exercising the pipeline end-to-end without burning API credits.
"""

from __future__ import annotations

import hashlib
import io
import os
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

from simple.providers.base import ImageProvider, ImageRequest, ImageResult


class MockProvider(ImageProvider):
    """Render a placeholder PNG locally — no network calls."""

    name = "mock"

    def __init__(self, *, model: str = "mock/cctv", noise: bool = True) -> None:
        self.model = model
        self.noise = noise

    def generate(self, request: ImageRequest) -> ImageResult:
        width, height = request.width, request.height
        # Slight per-frame drift based on seed so stitched MP4s aren't static.
        seed = request.seed if request.seed is not None else 0
        tint = (10 + (seed % 12), 12 + (seed % 9), 14 + (seed % 7))
        img = Image.new("RGB", (width, height), tint)
        draw = ImageDraw.Draw(img)

        if self.noise:
            _sprinkle_noise(img, seed)

        font = _load_font(int(height * 0.04))
        small = _load_font(int(height * 0.025))

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        draw.text((12, 10), f"CAM-01  {ts}", fill=(220, 220, 220), font=font)
        draw.text(
            (12, height - int(height * 0.06)),
            f"frame seed={seed}",
            fill=(180, 180, 180),
            font=small,
        )
        # Prompt excerpt, wrapped naively.
        excerpt = (request.prompt[:90] + "…") if len(request.prompt) > 90 else request.prompt
        draw.text(
            (12, int(height * 0.45)),
            excerpt,
            fill=(200, 200, 200),
            font=small,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return ImageResult(
            png_bytes=buf.getvalue(),
            provider=self.name,
            model=self.model,
            request=request,
            raw_response=None,
        )


def _sprinkle_noise(img: Image.Image, seed: int) -> None:
    """Cheap, deterministic 'sensor noise' speckle without numpy."""
    h = hashlib.sha256(f"noise-{seed}".encode()).digest()
    width, height = img.size
    pixels = img.load()
    # Place ~250 specks; positions are deterministic per seed.
    for i in range(250):
        bx = h[(i * 2) % len(h)]
        by = h[(i * 2 + 1) % len(h)]
        x = (bx * 257 + i * 13 + seed) % width
        y = (by * 257 + i * 31 + seed) % height
        v = 40 + ((bx + by) % 60)
        pixels[x, y] = (v, v, v)


def _load_font(size: int) -> ImageFont.ImageFont:
    """Best-effort TTF lookup; falls back to PIL's bitmap default font."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",  # macOS
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",  # Linux
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()
