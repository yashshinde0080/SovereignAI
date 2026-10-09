"""Generate the Windows app icon when the repo has none.

Run once (build_windows.ps1 does this when electron/assets/icon.ico is missing):

    backend/.venv/Scripts/python.exe electron/assets/make_icon.py

Writes icon.ico (16-256px, what electron-builder needs) and icon.png (window
icon) next to this file.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
BRAND = (60, 52, 137, 255)       # --brand  #3C3489
ACCENT = (29, 158, 117, 255)     # --brand-accent #1D9E75
SIZE = 256


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=BRAND)
    # accent arc: the "edge" the product is named for
    d.arc([size * 0.14, size * 0.14, size * 0.86, size * 0.86], start=205, end=335,
          fill=ACCENT, width=max(2, int(size * 0.055)))

    text = "S"
    font = None
    for name in ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, int(size * 0.52))
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    d.text((size / 2, size / 2), text, font=font, fill=(255, 255, 255, 255), anchor="mm")
    return img


def main() -> int:
    base = draw(SIZE)
    base.save(OUT / "icon.png")
    base.save(OUT / "icon.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    print(f"wrote {OUT / 'icon.ico'} and {OUT / 'icon.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
