"""Re-encode wiki upload images (clean PNG, size limits, valid structure)."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent / "upload"
LOGO_IN = ROOT / "logo-source.png"
BANNER_IN = ROOT / "banner-source.jpg"

LOGO_OUT = ROOT / "PhazeOut.png"
BANNER_OUT = ROOT / "PhazeOut Banner.jpg"

# Infobox / wiki-friendly limits (keep under common 2 MiB caps)
LOGO_MAX = 512
BANNER_MAX_WIDTH = 1200


def save_png(im: Image.Image, path: Path) -> None:
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    im.save(path, format="PNG", optimize=True)


def main() -> None:
    logo = Image.open(LOGO_IN)
    logo.load()
    logo = logo.convert("RGBA")
    logo.thumbnail((LOGO_MAX, LOGO_MAX), Image.Resampling.LANCZOS)
    save_png(logo, LOGO_OUT)

    banner = Image.open(BANNER_IN)
    banner.load()
    banner = banner.convert("RGB")
    w, h = banner.size
    if w > BANNER_MAX_WIDTH:
        nh = max(1, int(h * BANNER_MAX_WIDTH / w))
        banner = banner.resize((BANNER_MAX_WIDTH, nh), Image.Resampling.LANCZOS)
    banner.save(BANNER_OUT, format="JPEG", quality=88, optimize=True, progressive=True)

    for p in (LOGO_OUT, BANNER_OUT):
        im = Image.open(p)
        im.verify()
        print(p.name, p.stat().st_size, "bytes", im.size)


if __name__ == "__main__":
    main()
