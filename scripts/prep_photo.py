"""Prepare the GitHub avatar for ASCII conversion.

Steps:
1. Load the source photo (default: data/avatar.png).
2. Remove the background: flood-fill from the four corners with a colour
   tolerance, so any background connected to the edges becomes white.
   (If the optional `rembg` package is installed it is used instead.)
3. Boost local contrast (CLAHE-like via Pillow autocontrast + equalize blend).
4. Composite on white and save as data/portrait.png (grayscale).

Usage:
    python scripts/prep_photo.py [input] [output]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, ImageFilter

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/avatar.png")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/portrait.png")


def remove_background(img: Image.Image) -> Image.Image:
    """Return an RGBA image with the background made transparent."""
    try:  # best quality when available (heavy dependency, optional)
        from rembg import remove  # type: ignore

        return remove(img.convert("RGBA"))
    except Exception:
        pass

    rgb = img.convert("RGB")
    # Work on a slightly blurred copy so JPEG noise does not stop the fill.
    work = rgb.filter(ImageFilter.GaussianBlur(1))
    w, h = work.size
    marker = (255, 0, 255)  # a colour unlikely to be in the photo
    tol = 48
    px = work.load()

    # Background colour = median of the border pixels. Seeds are border
    # pixels close to that colour, so a subject touching the edge (shoulders
    # at the bottom of a headshot) is never used as a seed.
    border = [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)] + \
             [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)]
    bg = tuple(int(sorted(c[i] for c in border)[len(border) // 2]) for i in range(3))

    def near(c):
        return sum(abs(a - b) for a, b in zip(c, bg)) <= tol

    seeds = [(x, 0) for x in range(0, w, 8)] + [(x, h - 1) for x in range(0, w, 8)] + \
            [(0, y) for y in range(0, h, 8)] + [(w - 1, y) for y in range(0, h, 8)]
    for xy in seeds:
        if px[xy] != marker and near(px[xy]):
            ImageDraw.floodfill(work, xy, marker, thresh=tol)

    mask = Image.new("L", (w, h), 255)
    px_work = work.load()
    px_mask = mask.load()
    for y in range(h):
        for x in range(w):
            if px_work[x, y] == marker:
                px_mask[x, y] = 0
    # Soften the edge so the silhouette does not look cut with scissors.
    mask = mask.filter(ImageFilter.GaussianBlur(1.5))

    out = rgb.convert("RGBA")
    out.putalpha(mask)
    return out


def main() -> None:
    img = Image.open(SRC)
    img = ImageOps.exif_transpose(img)
    cut = remove_background(img)

    white = Image.new("RGBA", cut.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(white, cut).convert("L")

    # Contrast: blend a histogram-equalised copy with an autocontrast copy.
    eq = ImageOps.equalize(flat)
    ac = ImageOps.autocontrast(flat, cutoff=1)
    flat = Image.blend(ac, eq, 0.35)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    flat.save(OUT)
    print(f"wrote {OUT} ({flat.size[0]}x{flat.size[1]})")


if __name__ == "__main__":
    main()
