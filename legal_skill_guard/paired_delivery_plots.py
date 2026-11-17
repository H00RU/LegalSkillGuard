"""Standalone unsmoothed DEV curves from complete native result tables."""
from collections import defaultdict
import hashlib
import importlib.util
from importlib.metadata import version
import os
from pathlib import Path
import sys


def plot_curves(rows, directory):
    isolated = Path(__file__).resolve().parents[1] / '.local-tools/paired-plotting'
    if importlib.util.find_spec('matplotlib') is None and isolated.is_dir():
        sys.path.insert(0, str(isolated))
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / '.local-tools/paired-plotting-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from legal_skill_guard.paired_interfaces.formal_design import ARMS, CURVES
    font = ('Georgia' if any(f.name == 'Georgia' for f in font_manager.fontManager.ttflist) else 'DejaVu Serif')
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    for row in rows:
        if row['partition'] != 'dev': raise ValueError('Learning curves use only the original DEV checkpoints')
        grouped[row['dataset']].append(row)
    if not grouped: raise ValueError('No actual curve points exist')
    colors = ['#777777', '#9EC2DD', '#3C78A8', '#D6337F', '#4C7D9D', '#AA6281', '#194B6B']
    markers = ['o', 's', '^', 'D', 'v', 'P', 'X']
    labels = dict(zip(ARMS, ['Direct', 'Teacher skills', 'SCOPE adaptation', 'M1',
                            'M2 (fixed)', 'M1 + replay', 'M1 + M2']))
    files, points = {}, []
    for dataset, values in sorted(grouped.items()):
        lookup = {(r['arm'], r['batch']): r for r in values}
        if len(values) != len(ARMS) * len(CURVES) or set(lookup) != {(a, b) for a in ARMS for b in CURVES}:
            raise ValueError('All seven systems and four fixed checkpoints must remain in each curve')
        with plt.rc_context({'font.family': font, 'font.size': 8, 'axes.spines.top': False,
                             'axes.spines.right': False, 'pdf.fonttype': 42}):
            figure, axis = plt.subplots(figsize=(5.3, 3.5), layout='constrained')
            for arm, color, marker in zip(ARMS, colors, markers):
                values = [lookup[arm, b] for b in CURVES]
                y = [r['mother_macro'] for r in values]
                lo = [r['mother_resampling']['interval'][0] for r in values]
                hi = [r['mother_resampling']['interval'][1] for r in values]
                axis.plot(CURVES, y, label=labels[arm], color=color, marker=marker, markersize=4, linewidth=1.2)
                axis.fill_between(CURVES, lo, hi, color=color, alpha=.07, linewidth=0)
                points.extend({'dataset': dataset, 'arm': arm, 'batch': b, 'value': value,
                    'resampling_interval': [lower, upper]} for b, value, lower, upper in zip(CURVES, y, lo, hi))
            axis.set(title=dataset, xlabel='Training batch', ylabel='Native mother macro')
            axis.set_xticks(CURVES); axis.set_ylim(-.02, 1.02)
            axis.grid(axis='y', alpha=.16)
            axis.legend(fontsize=7.5, loc='upper center', bbox_to_anchor=(.5, -.19), ncol=3, frameon=False)
            for suffix in ('pdf', 'png'):
                path = directory / (dataset + '_DEV.' + suffix)
                figure.savefig(path, dpi=600, metadata={'Creator': 'paired-delivery'} if suffix == 'pdf' else {})
                files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            plt.close(figure)
    return {'matplotlib_version': matplotlib.__version__, 'font': font,
        'plotting_dependencies': {name: version(name) for name in ('matplotlib', 'numpy', 'contourpy',
            'cycler', 'fonttools', 'kiwisolver', 'pillow', 'pyparsing', 'python-dateutil', 'six', 'packaging')},
        'Georgia_font_installed': font == 'Georgia', 'rendered_points': points,
        'point_values_and_checkpoint_locations_unchanged': True,
        'bands': '95 percent empirical mother-resampling intervals;conditional on fitted libraries and cohort',
        'five_run_or_rule_family_coverage_claimed': False, 'smoothing': False,
        'files_sha256': files}
