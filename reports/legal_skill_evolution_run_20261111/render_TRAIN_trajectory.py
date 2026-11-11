"""Export observed task, paired gain, library, fallback and cost trajectories."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPORT = Path(__file__).resolve().parent
STYLES = {'NoSkill': ('#333333', '.', '--'), 'FreeEvolution': ('#777777', 'x', '--'),
    'LiftOnly': ('#77A4C8', 's', '-.'), 'CoRevOnly': ('#3C78A8', '^', ':'),
    'Full': ('#D6337F', 'o', '-'), 'Lift+GenericJoint': ('#B38400', 'D', ':'),
    'AllPorts+CoRev': ('#2C967F', 'v', '--')}


def main():
    source = REPORT / 'formal_TRAIN_trajectory.json'
    data = json.loads(source.read_text());points = data['points']
    plt.rcParams.update({'font.size': 8, 'axes.titlesize': 9, 'pdf.fonttype': 42})
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 5.8), sharex=True)
    titles = ['New TRAIN cases: native mean before update', 'Same-case difference from NoSkill',
        'Accepted skills after update', 'Learned co-revision patterns after update',
        'Native fallback rate before update', 'Referenced TRAIN requests, cumulative']
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title);axis.set_xlim(.8, 8.2);axis.set_xticks(range(1, 9))
        axis.grid(axis='y', alpha=.2, linewidth=.5);axis.spines[['right', 'top']].set_visible(False)
    for arm, (color, marker, line) in STYLES.items():
        observed = sorted((p for p in points if p['arm'] == arm), key=lambda p: p['batch'])
        values = [[] for _ in titles]
        for p in observed:
            counts = [r['path_counts'] for r in p['metrics']['source_rows']]
            count = sum(r['native_views'] for r in counts)
            footprint = p.get('response_footprint') or {}
            cost = (footprint.get('cumulative_initial_and_learning_response_footprint') or {}).get('physical_requests')
            v = [p['metrics']['equal_five_dataset_macro'], p['paired_NoSkill']['equal_five_dataset_difference'],
                p['skills_after'] if p['update_complete'] else None,
                p['patterns_after'] if p['update_complete'] else None,
                sum(r.get('fallback_views', 0) for r in counts) / count if count else None,
                cost if p['update_complete'] else None]
            for panel, value in enumerate(v):
                if value is not None:values[panel].append((p['batch'], value))
        for axis, pairs in zip(axes.flat, values):
            axis.plot([p[0] for p in pairs], [p[1] for p in pairs], color=color, marker=marker,
                      linestyle=line, markersize=3.5, linewidth=1, label=arm)
    axes.flat[0].set_ylim(-.02, 1.02);axes.flat[4].set_ylim(-.02, 1.02)
    axes.flat[1].axhline(0, color='#444444', linewidth=.5)
    for i in (2, 3, 5):axes.flat[i].set_ylim(bottom=-.05)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False)
    fig.supxlabel('Batch (16 fixed TRAIN parents; different cases in each batch)', fontsize=9, y=.065)
    fig.text(.5, .018, 'Costs exclude DEV and deduplicate referenced responses per arm; shared arms are not added. Unfinished updates are omitted.',
             ha='center', fontsize=7)
    fig.tight_layout(rect=(0, .09, 1, .9), h_pad=1.4, w_pad=1.6)
    fig.savefig(REPORT / 'formal_TRAIN_learning_trajectory.pdf', bbox_inches='tight')
    fig.savefig(REPORT / 'formal_TRAIN_learning_trajectory.png', dpi=600, bbox_inches='tight')
    plt.close(fig)
    (REPORT / 'formal_TRAIN_plot_provenance.json').write_text(json.dumps({
        'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'new_model_calls': 0,
        'actual_batches_by_arm': {a: [p['batch'] for p in points if p['arm'] == a] for a in STYLES},
        'unfinished_update_points_in_library_or_cost_panels': False, 'future_points_extrapolated': False,
        'TRAIN_batch_scores_are_descriptive_not_fixed_cohort_DEV': True, 'TEST_opened': False}, indent=2) + '\n')
    print(json.dumps({'TRAIN_trajectory_plotted': True, 'new_model_calls': 0, 'PDF_vector': True, 'PNG_dpi': 600}))


if __name__ == '__main__':main()
