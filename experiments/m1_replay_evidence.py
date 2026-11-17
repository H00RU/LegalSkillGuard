"""Replay the published M1 packet. No client, network, training or TEST access."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.reference_wire import reference_wire
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'reports/two_method_followthrough_20261116/M1_evidence_20261117'


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def replay(packet=DEFAULT):
    manifest = load(packet / 'manifest.json')
    for name, expected in manifest['files_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    for name, asset in manifest['materialized_assets'].items():
        body = gzip.decompress((ROOT / asset['gzip']).read_bytes())
        assert hashlib.sha256(body).hexdigest() == asset['sha256']
        target = ROOT/name
        if target.exists():
            assert target.read_bytes() == body
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    cases = load(packet / 'chain_cases.json.gz')
    counts = {'cases': len(cases), 'real_response_replays': 0,
              'reference_probes': 0, 'native_grade_checks': 0}
    for row in cases:
        source, view, plan = row['source_public'], row['actor_view'], row['plan_asset']
        for name, response in [('real', row['response']), ('reference', {
                'content': json.dumps(reference_wire(source['dataset'], plan,
                    row['source_review'], view['source_units'])), 'finish_reason': 'stop'})]:
            result = decode_response(source, view, plan, response)
            assert result == row['expected_current'][name], (row['identity'], name)
            counts['real_response_replays' if name == 'real' else 'reference_probes'] += 1
            # Only TRAIN development/calibration annotations are included.
            assert row['role'] in ('development', 'calibration')
            for task, value in result['native'].items():
                grade = (grade_view(source['dataset'], row['native_views'][task],
                    row['D_C_annotation'][task], value['answer'], value['evidence_sentence_ids'])
                    if value['handled'] else {'grade': 0.0, 'unresolved_or_failed': True})
                assert grade == row['expected_grades'][name][task], (row['identity'], name, task)
                counts['native_grade_checks'] += 1
    # Saved per-source pilot scores are reaggregated, not represented as new calls.
    scores = load(packet / 'pilot_native_scores.json')
    assert len(scores) == 228
    selected = [r for r in scores if r['plan'] == 'columns']
    assert len(selected) == 76 and all(r['grade'] == 0 for r in selected)
    counts.update(fixed_pilot_sources=len({r['source'] for r in scores}),
                  fixed_pilot_native_task_candidate_rows=len(scores),
                  M1_original_selected_positive_rows=0, new_model_requests=0,
                  output_digest=digest([r['expected_current'] for r in cases]))
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(replay(args.packet), ensure_ascii=False, sort_keys=True))
