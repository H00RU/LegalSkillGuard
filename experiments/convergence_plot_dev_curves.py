"""Plot native metrics from sealed DEV cells using ReportLab and Poppler."""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/legal_skill_convergence_20261117'
HANDOFF = BASE / 'handoff'
ARMS = (
    ('common_teacher_skill_learning', 'Ordinary teacher', '#545454', 'Circle', None),
    ('method_one_only', 'M1 only', '#3C78A8', 'Square', [5, 2]),
    ('method_two_only', 'M2 only', '#AA6281', 'Triangle', [1, 2]),
    ('both', 'M1 + M2', '#D6337F', 'Diamond', None),
    ('strongest_matched_external_baseline', 'PARSE', '#727D86', 'StarSix', [4, 2, 1, 2]),
)
PANELS = (
    ('OpenExempt EC F1', 'OpenExempt', 'EC', 16),
    ('OpenExempt EV F1', 'OpenExempt', 'EV', 16),
    ('Diversity balanced accuracy', 'LegalBench_Diversity', 'balanced', 16),
    ('ContractNLI accuracy', 'ContractNLI', 'all', 272),
    ('ContractNLI evidence F1', 'ContractNLI', 'evidence', 272),
    ('Airline exact cost', 'RuleArena_Airline', 'all', 16),
    ('MAUD ordinary-course', 'MAUD', 'Ordinary Course Covenant', 16),
    ('MAUD negative-interim', 'MAUD', 'Negative Interim Covenant', 16),
    ('MAUD knowledge definition', 'MAUD', 'Knowledge Definition', 16),
)
CHECKPOINTS = {0: 'formal_bootstrap_current.json', 1: 'formal_b1_dev_current.json',
               2: 'formal_B2_DEV_current.json', 4: 'formal_B4_DEV_current.json', 8: 'formal_B8_DEV_current.json'}


def _read(path):
    return json.loads(path.read_text())


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(record):
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _series(rows, labels):
    values = {}
    for name, dataset, view, count in PANELS:
        pool = [row for row in rows if row['dataset'] == dataset and (
            view in ('all', 'evidence', 'balanced') or row['view'].startswith(view))]
        if len(pool) != count:
            raise ValueError('Incomplete original DEV denominator for ' + name)
        if view == 'balanced':
            strata = [[row['grade'] for row in pool if labels[dataset][row['source']]['native']['answer'] == label]
                      for label in ('No', 'Yes')]
            if any(not v for v in strata) or sum(map(len, strata)) != count:
                raise ValueError('Use both of the original classes for Diversity balanced accuracy')
            value = mean(mean(group) for group in strata)
        elif view == 'evidence':
            value = mean(row['native_metrics'].get('evidence_f1', 0.) for row in pool
                         if labels[dataset][row['source']][row['view']].get('evidence') is not None)
        else:
            value = mean(row['grade'] for row in pool)
        if not 0 <= value <= 1:
            raise ValueError('Expected a native score in the declared metric range')
        values[name] = value
    return values


def collect(through):
    bootstrap = ROOT / _read(HANDOFF / CHECKPOINTS[0])['artifact_root']
    study = _read(bootstrap / 'binding.json')
    if bootstrap.name != _digest(study):
        raise ValueError('The original study binding changed')
    labels = {}
    for dataset in ('ContractNLI', 'LegalBench_Diversity'):
        path = study['grading_paths'][dataset]
        if (ROOT / path).parent.name != 'dev' or _sha(ROOT / path) != study['grading_file_sha256'][path]:
            raise ValueError('Use the unchanged DEV grading only')
        labels[dataset] = _read(ROOT / path)
    points = {}
    for batch, pointer in CHECKPOINTS.items():
        if batch > through:
            break
        stage = ROOT / _read(HANDOFF / pointer)['artifact_root']
        terminal = _read(stage / 'terminal.json')
        test_flag = 'TEST_opened' if batch else 'TEST_content_opened'
        sealed = terminal['cell_sha256' if batch else 'B0_cells']
        if terminal[test_flag] is not False or not terminal['status'].startswith('completed_'):
            raise ValueError('Each plotted point requires its settled DEV checkpoint')
        scored = {}
        for arm, *_ in ARMS:
            cell = _read(bootstrap / 'dev' / ('B' + str(batch)) / arm / 'scores.json')
            expected = cell.pop('cell_sha256')
            if (expected != _digest(cell) or cell['partition'] != 'dev' or cell['batch'] != batch
                    or cell['arm'] != arm or cell['study_binding'] != study
                    or cell['public_cohort_sha256'] != study['DEV_public_sha256']
                    or len({row['source'] for row in cell['source_scores']}) != 80
                    or len(cell['source_scores']) != 384 or sealed[arm] != expected):
                raise ValueError('Only the five frozen matched DEV cells can supply plot points')
            scored[arm] = {'cell_sha256': expected, 'metrics': _series(cell['source_scores'], labels)}
        points[batch] = {'TRAIN_mothers': 16 * batch, 'terminal_sha256': _sha(stage / 'terminal.json'),
                         'arms': scored}
    return points


def render(points, output):
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.shapes import Drawing, Line, String
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.graphics import renderPDF
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas

    font = 'Times-Roman'
    try:
        match = subprocess.check_output(['fc-match', '-f', '%{family}\n%{file}', 'Georgia'], text=True)
        family, filename = match.splitlines()
        if family in ('Georgia', 'DejaVu Serif'):
            pdfmetrics.registerFont(TTFont('PlotSerif', filename))
            font = 'PlotSerif'
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass
    width, height = 520, 382
    figure = Drawing(width, height)
    ink, muted, grid = map(HexColor, ('#292929', '#595959', '#DEDEDE'))
    figure.add(String(14, height - 13, 'Native score (%)', fontName=font, fontSize=9, fillColor=ink))
    for index, (_, title, color, marker, dash) in enumerate(ARMS):
        x, y = 16 + index * 102, height - 33
        style = HexColor(color)
        figure.add(Line(x, y + 3, x + 15, y + 3, strokeColor=style, strokeWidth=1.2, strokeDashArray=dash))
        figure.add(makeMarker(marker, x=x + 7, y=y + 3, size=4, strokeColor=style, fillColor=style))
        figure.add(String(x + 19, y, title, fontName=font, fontSize=8.5, fillColor=ink))
    ticks = [row['TRAIN_mothers'] for row in points.values()]
    for index, (title, *_) in enumerate(PANELS):
        col, row = index % 3, index // 3
        x, y = 32 + 172 * col, 37 + 102 * (2 - row)
        figure.add(String(x, y + 79, '{}  {}'.format(chr(ord('a') + index), title),
                          fontName=font, fontSize=8.5, fillColor=ink))
        chart = LinePlot()
        chart.x, chart.y, chart.width, chart.height = x, y, 128, 66
        chart.xValueAxis.valueMin, chart.xValueAxis.valueMax = -1, ticks[-1] + 2
        chart.xValueAxis.valueSteps = ticks
        chart.yValueAxis.valueMin, chart.yValueAxis.valueMax = 0, 100
        chart.yValueAxis.valueSteps = [0, 25, 50, 75, 100]
        for axis in (chart.xValueAxis, chart.yValueAxis):
            axis.labels.fontName, axis.labels.fontSize, axis.labels.fillColor = font, 8, muted
            axis.strokeColor = grid
        chart.yValueAxis.visibleGrid, chart.yValueAxis.gridStrokeColor = 1, grid
        chart.data = [[(v['TRAIN_mothers'], 100 * v['arms'][arm]['metrics'][title])
                       for v in points.values()] for arm, *_ in ARMS]
        for position, (_, _, color, marker, dash) in enumerate(ARMS):
            style = chart.lines[position]
            style.strokeColor, style.strokeWidth, style.strokeDashArray = HexColor(color), 1.2, dash
            style.symbol = makeMarker(marker, size=3.6, strokeColor=HexColor(color), fillColor=None)
        figure.add(chart)
    figure.add(String(width / 2, 8, 'TRAIN mother sources observed', textAnchor='middle',
                      fontName=font, fontSize=9, fillColor=ink))
    output.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(output / 'dev_curves.pdf'), pagesize=(width, height))
    pdf.setTitle('Fixed development learning curves')
    renderPDF.draw(figure, pdf, 0, 0)
    pdf.save()
    subprocess.run(['pdftoppm', '-r', '600', '-png', '-singlefile', str(output / 'dev_curves.pdf'),
                    str(output / 'dev_curves')], check=True)
    (output / 'sealed_metric_points.json').write_text(json.dumps(points, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--through', type=int, choices=(2, 4, 8), required=True)
    args = parser.parse_args()
    folder = BASE / 'dev_curve_figures' / ('B' + str(args.through))
    render(collect(args.through), folder)
    print(folder / 'dev_curves.pdf')
