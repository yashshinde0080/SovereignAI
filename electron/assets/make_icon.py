"""Generate the Windows application icon from the SovereignAI logo.

Source: the first of these that exists in the repo root (see Get-LogoPng in
scripts/portable_lib.ps1 -- keep the two lists in sync):

    sovereignai.png, sovereign.png

Run by build_windows.ps1 before PyInstaller/electron-builder, or by hand:

    backend/.venv/Scripts/python.exe electron/assets/make_icon.py

Writes icon.ico (16-256px, what electron-builder's win.icon and rcedit need)
and icon.png (window/taskbar icon, see electron/main.js) next to this file.
With no logo in the repo root it draws the placeholder brand mark instead.
Pillow is build-time only -- it is never bundled into the shipped app.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]                      # electron/assets -> repo root
LOGO_CANDIDATES = ("sovereignai.png", "sovereign.png")
SIZES = (16, 24, 32, 48, 64, 128, 256)     # icon.ico frames
SIZE = 256                                 # icon.png / master size
BRAND = (60, 52, 137, 255)                 # --brand  #3C3489
ACCENT = (29, 158, 117, 255)               # --brand-accent #1D9E75


def find_logo():
    for name in LOGO_CANDIDATES:
        path = ROOT / name
        if path.is_file():
            return path
    return None


def from_logo(path: Path) -> Image.Image:
    """Square the logo (centred, transparent padding) and scale it to SIZE."""
    img = Image.open(path).convert("RGBA")
    side = max(img.size)
    if img.size != (side, side):
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        img = canvas
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def draw(size: int) -> Image.Image:
    """Placeholder brand mark, used only when the repo root has no logo."""
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
    logo = find_logo()
    base = from_logo(logo) if logo else draw(SIZE)
    base.save(OUT / "icon.png")
    base.save(OUT / "icon.ico", sizes=[(n, n) for n in SIZES])
    source = str(logo) if logo else "built-in placeholder (no logo in repo root)"
    print(f"wrote {OUT / 'icon.ico'} and {OUT / 'icon.png'} from {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
