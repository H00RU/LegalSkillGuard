"""Render the edited native SVG with the existing system Rsvg/Cairo stack."""
import hashlib
import json
from pathlib import Path

import cairo
import gi

gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg

ROOT = Path(__file__).resolve().parents[3]
directory = ROOT / 'paper/figures/utility_method_overview_20261030'
svg = directory / 'method_overview.svg'
handle = Rsvg.Handle.new_from_file(str(svg))
viewport = Rsvg.Rectangle()
viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, 1140, 660
for name, width in [('method_overview_preview.png', 1140),
                    ('method_overview_600dpi.png', 4800)]:
    scale = width / 1140
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, round(660 * scale))
    context = cairo.Context(surface)
    context.scale(scale, scale)
    handle.render_document(context, viewport)
    surface.write_to_png(str(directory / name))
    surface.finish()
surface = cairo.PDFSurface(str(directory / 'method_overview.pdf'), 576, 333.473684)
context = cairo.Context(surface)
context.scale(576 / 1140, 576 / 1140)
handle.render_document(context, viewport)
surface.finish()
receipt = {'source': str(svg.relative_to(ROOT)), 'new_model_calls': 0,
           'rendered_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in directory.iterdir()
                              if p.suffix in ('.svg', '.png', '.pdf')}}
Path(__file__).with_name('revised_figure_receipt.json').write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt))
