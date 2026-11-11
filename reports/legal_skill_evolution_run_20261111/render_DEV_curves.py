"""Export fixed DEV evidence with standard plotting tools; never invent points."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPORT = Path(__file__).resolve().parent
STYLES = {'FreeEvolution': ('#777777', 'x', '--'), 'LiftOnly': ('#77A4C8', 's', '-.'),
          'CoRevOnly': ('#3C78A8', '^', ':'), 'Full': ('#D6337F', 'o', '-')}


def main():
    source = REPORT / 'formal_DEV_summary.json'
    data = json.loads(source.read_text())
    points = data['points']
    if not any(sum(p['arm'] == arm for p in points) >= 2 for arm in STYLES):
        print(json.dumps({'plot_created': False, 'reason': 'No observed post-update curve point yet', 'new_model_calls': 0}))
        return
    plt.rcParams.update({'font.size': 9, 'axes.titlesize': 10, 'pdf.fonttype': 42, 'ps.fonttype': 42})
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.1), sharex=True, sharey=True)
    panels = [('equal_five_dataset_macro', 'Equal five-dataset mean'), ('OpenExempt', 'OpenExempt'),
              ('SARA_v2_Binary', 'SARA'), ('ContractNLI', 'ContractNLI'),
              ('RuleArena_Airline', 'Airline'), ('MAUD', 'MAUD')]
    for ax, (key, title) in zip(axes.flat, panels):
        for arm, (color, marker, linestyle) in STYLES.items():
            observed = sorted((p for p in points if p['arm'] == arm), key=lambda p: p['batch'])
            observed = [p for p in observed if (p['metrics']['equal_five_dataset_macro'] if key == 'equal_five_dataset_macro'
                         else p['metrics']['datasets'][key]['native_parent_mean']) is not None]
            x = [p['batch'] for p in observed]
            y = [p['metrics']['equal_five_dataset_macro'] if key == 'equal_five_dataset_macro'
                 else p['metrics']['datasets'][key]['native_parent_mean'] for p in observed]
            bounds = [p['source_uncertainty']['intervals_95_percent'][key] for p in observed]
            ax.fill_between(x, [b[0] for b in bounds], [b[1] for b in bounds], color=color, alpha=.065, linewidth=0)
            ax.plot(x, y, color=color, marker=marker, linestyle=linestyle, markersize=4, linewidth=1.3, label=arm)
        ax.set_title(title)
        ax.set_xlim(-.15, 8.15);ax.set_ylim(-.02, 1.02)
        ax.set_xticks(range(9));ax.set_yticks([0, .25, .5, .75, 1])
        ax.grid(axis='y', color='#BBBBBB', alpha=.3, linewidth=.5)
        ax.spines[['right', 'top']].set_visible(False)
    fig.supxlabel('Batch (16 TRAIN parents per batch)', fontsize=9)
    fig.supylabel('Native parent mean', fontsize=9)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(.5, 1.015))
    fig.tight_layout(rect=(.015, .025, 1, .955), h_pad=.9, w_pad=.8)
    fig.savefig(REPORT / 'formal_DEV_learning_curves.pdf', bbox_inches='tight')
    fig.savefig(REPORT / 'formal_DEV_learning_curves.png', dpi=600, bbox_inches='tight')
    plt.close(fig)
    (REPORT / 'formal_DEV_plot_provenance.json').write_text(json.dumps({
        'summary_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'new_model_calls': 0,
        'points_plotted': {a: [p['batch'] for p in points if p['arm'] == a] for a in STYLES},
        'unobserved_points_interpolated_or_extrapolated': False,
        'bands': '95% source bootstrap, stratified by dataset; not training seed variation or a paired-difference interval',
        'fixed_single_model_seed': 45, 'TEST_opened': False,
        'other_strong_controls_only_have_registered_B0_and_B8_points': True}, indent=2) + '\n')
    print(json.dumps({'plot_created': True, 'PNG_dpi': 600, 'PDF_vector': True, 'new_model_calls': 0}))


if __name__ == '__main__':main()
