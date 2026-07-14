"""Build a transparent, alternating-bounce loader from the project logo."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "onmyoji-auto-assistant-loading-sheet.png"
OUTPUT = ROOT / "assets" / "onmyoji-auto-assistant-loading.gif"
FRAME_COUNT = 32
FRAME_DURATION_MS = 50
CANVAS_SIZE = 256


def sprite_from_half(image: Image.Image, left: bool) -> Image.Image:
    midpoint = image.width // 2
    crop = image.crop((0, 0, midpoint + 1, image.height) if left else (midpoint, 0, image.width, image.height))
    bounds = crop.getbbox()
    if bounds is None:
        raise ValueError("The logo half is empty.")
    return crop.crop(bounds)


def paste_bouncing(frame: Image.Image, sprite: Image.Image, x: int, phase: float) -> None:
    bounce = math.sin(math.pi * phase) ** 2
    scale = 108 / sprite.width
    width = sprite.width * scale * (1.07 - 0.10 * bounce)
    height = sprite.height * scale * (0.90 + 0.16 * bounce)
    resized = sprite.resize((round(width), round(height)), Image.Resampling.LANCZOS)
    baseline = 214
    y = baseline - resized.height - round(40 * bounce)
    frame.alpha_composite(resized, (round(x + (108 - resized.width) / 2), y))


def main() -> None:
    logo = Image.open(SOURCE).convert("RGBA")
    black = sprite_from_half(logo, left=True)
    white = sprite_from_half(logo, left=False)
    frames: list[Image.Image] = []

    for index in range(FRAME_COUNT):
        phase = index / FRAME_COUNT
        frame = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
        paste_bouncing(frame, black, 14, phase)
        paste_bouncing(frame, white, 134, (phase + 0.5) % 1)
        frames.append(frame)

    frames[0].save(
        OUTPUT,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        disposal=2,
        transparency=0,
        optimize=False,
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: {FRAME_COUNT} frames, {FRAME_DURATION_MS} ms each")


if __name__ == "__main__":
    main()
