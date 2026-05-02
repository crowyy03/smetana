#!/usr/bin/env python3
"""Создать static/logo.png (заглушка)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    static = ROOT / "static"
    static.mkdir(parents=True, exist_ok=True)
    out = static / "logo.png"
    img = Image.new("RGB", (200, 80), color=(220, 220, 220))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    draw.text((10, 30), "VILINS LOGO", fill=(80, 80, 80), font=font)
    img.save(out, format="PNG")
    print(f"Written {out}")


if __name__ == "__main__":
    main()
