#!/usr/bin/env python3
"""Create the corrected Figure 3 raster from an existing manuscript.

The source figure is embedded as ``word/media/rId39.png``. Only the obsolete
"8 predeclared case pairs" line is repainted; the rest of the scientific
diagram remains pixel-identical.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFont

MEDIA_PATH = "word/media/rId39.png"
EXPECTED_SIZE = (3240, 2015)
BACKGROUND = (252, 247, 233, 255)
FOREGROUND = (36, 50, 67, 255)
FONT_PATH = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")
REPAINT_BOX = (150, 1575, 1040, 1640)
TEXT_CENTRE = (594, 1608)
TEXT = "16 predeclared case pairs"


def build(source_docx: Path, destination_png: Path) -> None:
    if not source_docx.is_file():
        raise FileNotFoundError(source_docx)
    if not FONT_PATH.is_file():
        raise FileNotFoundError(FONT_PATH)

    with ZipFile(source_docx) as archive:
        image = Image.open(BytesIO(archive.read(MEDIA_PATH))).convert("RGBA")
        image.load()

    if image.size != EXPECTED_SIZE:
        raise RuntimeError(
            f"Unexpected Figure 3 size {image.size}; expected {EXPECTED_SIZE}"
        )
    if image.getpixel((300, 1560)) != BACKGROUND:
        raise RuntimeError("Unexpected Figure 3 background; refusing raster patch")

    draw = ImageDraw.Draw(image)
    draw.rectangle(REPAINT_BOX, fill=BACKGROUND)
    font = ImageFont.truetype(str(FONT_PATH), 54)
    width, line_height = font.getsize(TEXT)
    offset_x, offset_y = font.getoffset(TEXT)
    glyph_height = line_height - offset_y
    x = TEXT_CENTRE[0] - width / 2 - offset_x
    y = TEXT_CENTRE[1] - glyph_height / 2 - offset_y
    draw.text((x, y), TEXT, font=font, fill=FOREGROUND)

    destination_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination_png, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_docx", type=Path)
    parser.add_argument("destination_png", type=Path)
    args = parser.parse_args()
    build(args.source_docx, args.destination_png)


if __name__ == "__main__":
    main()
