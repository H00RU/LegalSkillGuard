"""Render all pages for layout inspection using existing CPU-only tools."""
import json
import math
import subprocess
from pathlib import Path

import cairo

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPORT = ROOT / 'artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104'
OUT = HERE / 'visual_review_v16'
OUT.mkdir(exist_ok=True)
for language in ('en', 'zh'):
    pdf = EXPORT / ('utility_v6_working_' + language + '.pdf')
    info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
    count = int(next(line for line in info.splitlines() if line.startswith('Pages:')).split(':')[1])
    prefix = OUT / language
    subprocess.run(['pdftoppm', '-scale-to', '450', '-png', str(pdf), str(prefix)], check=True)
    pages = sorted(OUT.glob(language + '-*.png'))
    assert len(pages) == count
    columns, cell_w, cell_h = 4, 330, 480
    image = cairo.ImageSurface(cairo.FORMAT_RGB24, columns * cell_w, math.ceil(count / columns) * cell_h)
    ctx = cairo.Context(image)
    ctx.set_source_rgb(.86, .86, .86)
    ctx.paint()
    ctx.set_font_size(13)
    for index, page in enumerate(pages):
        thumb = cairo.ImageSurface.create_from_png(str(page))
        x, y = (index % columns) * cell_w, (index // columns) * cell_h
        ctx.save()
        ctx.translate(x + 6, y + 18)
        ctx.set_source_surface(thumb, 0, 0)
        ctx.paint()
        ctx.restore()
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(x + 6, y + 14)
        ctx.show_text(language + ' page ' + str(index + 1))
    image.write_to_png(str(OUT / (language + '_all_pages.png')))
    image.finish()
    key_pages = ([1, 4, 8, 9, 14, 16, 17, 18, 19, 20, 21, 25, 26, 27, 28]
                 if language == 'en' else [1, 4, 7, 8, 12, 14, 15, 16, 17, 18, 22, 23, 24, 25])
    for number in key_pages:
        if number <= count:
            subprocess.run(['pdftoppm', '-f', str(number), '-l', str(number), '-scale-to', '1400',
                            '-png', '-singlefile', str(pdf), str(OUT / (language + '_key_' + str(number)))], check=True)
    print(json.dumps({'language': language, 'pages': count, 'key_pages_rendered': key_pages}))
