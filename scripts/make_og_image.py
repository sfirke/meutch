"""Build app/static/img/og_default.png, the link preview image for SMS, Slack, etc.

Usage: python scripts/make_og_image.py

Downloads the Outfit and Figtree fonts (OFL) from the google/fonts repo.
Colors are the STYLE_GUIDE.md values.
"""

import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "app/static/img/logo_m.png"
OUT = ROOT / "app/static/img/og_default.png"

FONT_URLS = {
    "outfit": "https://github.com/google/fonts/raw/main/ofl/outfit/Outfit%5Bwght%5D.ttf",
    "figtree": "https://github.com/google/fonts/raw/main/ofl/figtree/Figtree%5Bwght%5D.ttf",
}

INK = "#1d2a2e"
PAPER = "#fff9ef"
TANGERINE = "#f6ad55"

W, H = 1200, 630
S = 2  # draw at 2x, then downscale for smooth edges


def font(name, size, weight):
    data = urllib.request.urlopen(FONT_URLS[name], timeout=30).read()
    f = ImageFont.truetype(io.BytesIO(data), size * S)
    f.set_variation_by_axes([weight])
    return f


def logo_tile(size):
    """The landing-page logo tile: ink border, rounded corners, hard ink shadow, tilted 3deg."""
    border, radius, shadow = 6 * S, 22 * S, 10 * S
    logo = Image.open(LOGO).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=255)

    canvas = Image.new("RGBA", (size + shadow, size + shadow), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((shadow, shadow, size + shadow - 1, size + shadow - 1), radius, fill=INK)
    canvas.paste(logo, (0, 0), mask)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius, outline=INK, width=border)
    return canvas.rotate(-3, resample=Image.BICUBIC, expand=True)


def main():
    img = Image.new("RGB", (W * S, H * S), PAPER)
    d = ImageDraw.Draw(img)

    # Keep everything in a small central block: Slack crops the image to the
    # centre square, and iMessage on iOS trims the top and bottom.
    tile = logo_tile(200 * S)
    img.paste(tile, ((W * S - tile.width) // 2, 128 * S), tile)

    # The tagline is left out because apps show it as the card's title.
    wordmark = font("outfit", 96, 700)
    d.text((W * S // 2, 372 * S), "Meutch", font=wordmark, fill=INK, anchor="mt")

    # Running stitch: 14px on, 9px off, 3px tall on the site; doubled here.
    y, n = 486 * S, 7
    x0 = (W * S - (n * 46 - 18) * S) // 2
    for i in range(n):
        sx = x0 + i * 46 * S
        d.rectangle((sx, y, sx + 28 * S - 1, y + 6 * S - 1), fill=TANGERINE)

    # Plain sRGB PNG with no gamma/chromaticity/metadata chunks.
    img.resize((W, H), Image.LANCZOS).save(OUT, optimize=True)
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
