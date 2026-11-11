"""Explain completed Full TEST paths without feeding them back to learning."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def main():
    folder = ROOT / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'
    done = json.loads((folder / 'TEST_completed.json').read_text())
    for name, expected in done['result_file_sha256'].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Completed TEST summary changed: ' + name)
    counts, errors, terminal = (defaultdict(Counter) for _ in range(3))
    parents = list((folder / 'predictions/Full').glob('*.json'))
    if len(parents) != 160:raise ValueError('The completed Full parent cohort is missing')
    for path in parents:
        parent = json.loads(path.read_text());dataset = parent['dataset'];row = counts[dataset]
        for view in parent['views']:
            if view['controlled']:continue
            value = view['execution'];row['native_views'] += 1
            row['core_views'] += bool(value['core_executed'])
            row['fallback_views'] += bool(value['fallback'])
            row['unresolved_views'] += not value['core_executed'] and not value['fallback']
            if not value['fallback']:continue
            row['fallback_no_retrieved_skill'] += not value.get('retrieved')
            classes = set()
            for failed in value.get('failed_candidates', []):
                message = failed['error'];kind = message.split(':', 1)[0]
                classes.add(kind);errors[dataset][kind] += 1
                terminal[dataset][message.rstrip().splitlines()[-1]] += 1
            for kind in classes:row['fallback_views_with_' + kind] += 1
    if sum(v['native_views'] for v in counts.values()) != 352:
        raise ValueError('Native view denominator changed')
    result = {'scope': 'Descriptive analysis of completed fixed Full TEST; no method changes, no new calls. Failure classes can overlap within a view.',
        'new_model_calls': 0, 'datasets': {k: dict(v) for k, v in counts.items()},
        'failed_candidate_counts_by_error_class': {k: dict(v) for k, v in errors.items()},
        'failed_candidate_counts_by_terminal_error': {k: dict(v) for k, v in terminal.items()}}
    (REPORT / 'Full_TEST_path_failure_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'independent_parents': len(parents), 'native_views': 352,
        'new_model_calls': 0, 'method_or_library_changes': False}))


if __name__ == '__main__':main()
