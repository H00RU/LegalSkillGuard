"""Render the method overview with deterministic vector text and lines."""

import argparse
from pathlib import Path
import subprocess

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


WIDTH = 540
HEIGHT = 280
MARGIN = 16
COLUMN_WIDTH = 156
COLUMN_GAP = 20
INK = HexColor('#252525')
MUTED = HexColor('#4C5158')
LINE = HexColor('#CED1D4')
BLUE = HexColor('#3C78A8')
ROSE = HexColor('#AA6281')


def register_fonts():
    for style, name in (('Regular', 'MethodSerif'), ('Bold', 'MethodSerifBold')):
        filename = subprocess.check_output(
            ['fc-match', '-f', '%{file}', f'Georgia:style={style}'], text=True).strip()
        pdfmetrics.registerFont(TTFont(name, filename))


def label(canvas, text, x, y, size=9.5, color=INK, bold=False, limit=None):
    font = 'MethodSerifBold' if bold else 'MethodSerif'
    if limit is not None and pdfmetrics.stringWidth(text, font, size) > limit:
        raise ValueError(f'Figure label exceeds the available width: {text}')
    canvas.setFont(font, size)
    canvas.setFillColor(color)
    canvas.drawString(x, y, text)


def arrow(canvas, left, right, y):
    canvas.setLineWidth(0.8)
    canvas.setStrokeColor(MUTED)
    canvas.line(left, y, right, y)
    canvas.line(right - 4, y + 2.5, right, y)
    canvas.line(right - 4, y - 2.5, right, y)


def lane(canvas, name, top, accent, steps, example):
    label(canvas, name, MARGIN, top, 12, accent, bold=True)
    card_top = top - 10
    card_height = 63
    for index, (title, lines) in enumerate(steps):
        x = MARGIN + index * (COLUMN_WIDTH + COLUMN_GAP)
        canvas.setFillColor(HexColor('#F8F9FA'))
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.rect(x, card_top - card_height, COLUMN_WIDTH, card_height, fill=1)
        label(canvas, title, x + 9, card_top - 16, 10, bold=True, limit=COLUMN_WIDTH - 18)
        for line_index, line in enumerate(lines):
            label(canvas, line, x + 9, card_top - 30 - line_index * 12, limit=COLUMN_WIDTH - 18)
        if index < len(steps) - 1:
            arrow(canvas, x + COLUMN_WIDTH + 2, x + COLUMN_WIDTH + COLUMN_GAP - 3, card_top - 31)
    heading, lines = example
    label(canvas, heading, MARGIN, card_top - card_height - 15, bold=True, color=MUTED)
    for index, line in enumerate(lines):
        label(canvas, line, MARGIN, card_top - card_height - 28 - 13 * index,
              limit=WIDTH - 2 * MARGIN)


def render(output):
    register_fonts()
    output.mkdir(parents=True, exist_ok=True)
    pdf = output / 'METHOD_OVERVIEW.pdf'
    canvas = Canvas(str(pdf), pagesize=(WIDTH, HEIGHT), invariant=1)
    canvas.setTitle('Consumer-preserving interfaces and shared-interpretation supervision')
    lane(canvas, 'M1  Consumer-preserving interface learning', 259, BLUE, (
        ('Certify readers', ('Fix the legal consumer.', 'Verify each decoder’s', 'consumer outputs.')),
        ('Compare paired reads', ('Run the frozen model.', 'Check local source fidelity', 'and native answers.')),
        ('Reuse the interface', ('Save the reader template.', 'Select by source structure.', 'Decode with the fixed rule.')),
    ), ('Illustrative Diversity claim', (
        'One plaintiff claims $40,000 and $50,000 from the same defendant.',
        'Both the amount fields and the relation “total exceeds $75,000” preserve the consumer’s decision.',
    )))
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, 140, WIDTH - MARGIN, 140)
    lane(canvas, 'M2  Shared-interpretation supervision', 125, ROSE, (
        ('Build source variants', ('Edit an allowed source fact.', 'Keep unedited facts shared.', 'Recompute derived values.')),
        ('Measure both programs', ('Run on the same cases.', 'Record literal evidence', 'and native utility.')),
        ('Check update eligibility', ('Compare shared and', 'independent assignments.', 'Check gain and evidence.')),
    ), ('Illustrative OpenExempt allocations', (
        'Read the forwarded component for amount A and the withheld component for edited amount B.',
        'Shared title permits (A, 0) or (0, B). Independent completions also permit (A, B) and (0, 0).',
    )))
    canvas.save()
    subprocess.run(['pdftoppm', '-r', '600', '-png', '-singlefile', str(pdf), str(pdf.with_suffix(''))],
                   check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='Directory for the vector PDF and 600 dpi PNG')
    render(parser.parse_args().output)
