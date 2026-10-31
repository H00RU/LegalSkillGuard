#!/usr/bin/python3
"""Render the immutable eight-batch first-answer data, without model calls."""

import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

import cairo
import gi

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg


HERE = Path(__file__).resolve().parent
DATA = HERE / "source_data.json"
EXPECTED_DATA = "99e6c9e386c1b267f12f88cfb0d022033100d7d76b3fdc68afa5b638ff467779"
WIDTH, HEIGHT = 1440, 820
FONT = "Georgia, DejaVu Serif, serif"
ARMS = [
    ("skills", "Evolving library", "#AA6281"),
    ("frozen_after_B1", "Fixed B1 library", "#4C7D9D"),
    ("empty", "Empty library", "#92979F"),
]
PANELS = [
    ("a", "EC", "f1", "Native F1", 90, 100),
    ("b", "EV", "f1", "Native F1", 800, 100),
    ("c", "EC", "full_output_f1", "Complete-output F1", 90, 485),
    ("d", "EV", "full_output_f1", "Complete-output F1", 800, 485),
]


def text(x, y, value, size=19, anchor="start", weight="normal"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{value}</text>')


def png_with_dpi(surface, path, dpi):
    """Write the rendered PNG with physical-resolution metadata, no resampling."""
    import io

    out = io.BytesIO()
    surface.write_to_png(out)
    raw = out.getvalue()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    ppm = round(dpi / 0.0254)
    payload = struct.pack(">IIB", ppm, ppm, 1)
    chunk = b"pHYs" + payload
    insert = struct.pack(">I", len(payload)) + chunk
    insert += struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
    # IHDR is the first 25-byte chunk after the eight-byte PNG signature.
    path.write_bytes(raw[:33] + insert + raw[33:])


def main():
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == EXPECTED_DATA
    data = json.loads(DATA.read_text())
    assert [r["batch"] for r in data["series"]] == list(range(1, 9))
    assert all(r["n_sources"] == 16 for r in data["series"])
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
           '<title>Chronological first-answer performance on all eight training batches</title>',
           f'<desc>Source SHA256 {EXPECTED_DATA}. All points are 16-case means. Fixed B1 begins at batch 2. No smoothing or post-label replay.</desc>',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<g font-family="{FONT}" fill="#20252B">']
    for n, (arm, name, color) in enumerate(ARMS):
        x = 290 + n * 340
        dash = ' stroke-dasharray="8 5"' if arm == "empty" else ""
        svg.append(f'<path d="M{x} 30h40" fill="none" stroke="{color}" stroke-width="3"{dash}/>')
        svg.append(text(x + 52, 36, name, 20))
    for label, task, metric, title, left, top in PANELS:
        pw, ph = 570, 245
        xx = lambda batch: left + (batch - 1) * pw / 7
        yy = lambda score: top + ph * (100 - score) / 60
        svg.append(text(left, top - 27, f"({label}) {task} · {title}", 22, weight="bold"))
        for tick in (40, 60, 80, 100):
            y = yy(tick)
            svg.append(f'<path d="M{left} {y}h{pw}" stroke="#E5E8EC" stroke-width="1"/>')
            svg.append(text(left - 16, y + 6, str(tick), 18, "end"))
        svg.append(f'<path d="M{left} {top}v{ph}h{pw}" fill="none" stroke="#515861" stroke-width="1.3"/>')
        for batch in range(1, 9):
            x = xx(batch)
            svg.append(f'<path d="M{x} {top+ph}v5" stroke="#515861"/>')
            svg.append(text(x, top + ph + 27, str(batch), 18, "middle"))
        svg.append(text(left + pw / 2, top + ph + 58, "New-case batch", 20, "middle"))
        svg.append(f'<text transform="translate({left-60},{top+ph/2}) rotate(-90)" text-anchor="middle" font-size="19">F1 (%)</text>')
        # Draw the gray and blue references first; retain every observed point.
        for arm, name, color in reversed(ARMS):
            rows = [r for r in data["series"] if arm != "frozen_after_B1" or r["batch"] >= 2]
            points = [(xx(r["batch"]), yy(r["percent"][arm][task][metric])) for r in rows]
            path = " ".join(("M" if j == 0 else "L") + f"{x:.9f},{y:.9f}" for j, (x, y) in enumerate(points))
            dash = ' stroke-dasharray="8 5"' if arm == "empty" else ""
            svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"{dash}/>')
            for x, y in points:
                if arm == "frozen_after_B1":
                    svg.append(f'<rect x="{x-4:.9f}" y="{y-4:.9f}" width="8" height="8" fill="{color}"/>')
                else:
                    fill = "white" if arm == "empty" else color
                    svg.append(f'<circle cx="{x:.9f}" cy="{y:.9f}" r="4.2" fill="{fill}" stroke="{color}" stroke-width="1.6"/>')
    svg.extend(["</g>", "</svg>"])
    svg_path = HERE / "learning_curves.svg"
    svg_path.write_text("\n".join(svg) + "\n")
    handle = Rsvg.Handle.new_from_file(str(svg_path))
    rect = Rsvg.Rectangle()
    rect.x, rect.y, rect.width, rect.height = 0, 0, WIDTH, HEIGHT
    pdf = cairo.PDFSurface(str(HERE / "learning_curves.pdf"), 576, 576 * HEIGHT / WIDTH)
    ctx = cairo.Context(pdf)
    ctx.scale(576 / WIDTH, 576 / WIDTH)
    handle.render_document(ctx, rect)
    pdf.finish()
    for name, scale, dpi in [("learning_curves_600dpi.png", 4800 / WIDTH, 600),
                             ("learning_curves_preview.png", 1, 180)]:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, math.ceil(WIDTH * scale), math.ceil(HEIGHT * scale))
        ctx = cairo.Context(surface)
        ctx.scale(scale, scale)
        handle.render_document(ctx, rect)
        png_with_dpi(surface, HERE / name, dpi)
        surface.finish()
    print(json.dumps({"source_data_sha256": EXPECTED_DATA, "panels": 4,
                      "observed_points": 4 * (8 + 8 + 7), "fixed_B1_starts_at_batch": 2,
                      "no_model_calls": True, "no_data_smoothing": True}))


if __name__ == "__main__":
    main()
