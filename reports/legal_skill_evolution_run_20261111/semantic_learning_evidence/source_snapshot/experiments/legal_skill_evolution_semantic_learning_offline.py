"""Exercise new acquisition constraints on preserved, already reviewed TRAIN.

No model client or native grading file is used. No old experiment is resumed.
This validates the new implementation, not a fresh method-success estimate.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.semantic_learning import (
    check_binding, compile_bundle, producing_calls, review_binding, run_bundle)


RUN = 'legal_skill_evolution_semantic_learning_offline_20261113'


def read(path):
    return json.loads(path.read_text())


def ledger_snapshot(root):
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        rows = db.execute('select * from calls order by id').fetchall()
        return {'rows': len(rows), 'sha256': hashlib.sha256(json.dumps(
            rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
            'counts': db.execute('select role,status,count(*) from calls group by role,status').fetchall()}


def revision_inventory(root):
    """Count actual revision events, not independent proposals as new sources."""
    folder = root / 'artifacts/legal_skill_evolution_20261111/formal_v5/Full'
    entries = []
    for batch in range(1, 9):
        teacher = read(folder / f'teacher_B{batch}.json')
        old = read(folder / f'B{batch - 1}.json')['skills']
        new = read(folder / f'B{batch}.json')['skills']
        for block, proposal in enumerate(teacher['value']['blocks']):
            for revision in proposal['revisions']:
                if revision['operation'] != 'revise':
                    continue
                sid = revision['skill']['id']
                changed = sid in old and sid in new and digest(old[sid]) != digest(new[sid])
                entries.append({'batch': batch, 'block': block, 'skill_id': sid,
                                'rationale': proposal['rationale'],
                                'installed_version_changed': changed,
                                'old': old.get(sid), 'installed_new': new.get(sid),
                                'teacher_receipt': f'artifacts/legal_skill_evolution_20261111/formal_v5/Full/teacher_B{batch}.json'})
    fragment = []
    base = root / 'artifacts/legal_skill_evolution_fragment_program_update_20261112'
    for arm in ('Full', 'Lift+GenericJoint'):
        value = read(base / arm / 'program_update.json')
        fragment.append({'arm': arm, 'accepted': value['accepted'],
                         'revised_skills': [r['skill_id'] for r in value['revisions']],
                         'trigger': value['table']['trigger'],
                         'learned_pattern_count_original': value['pattern_count'],
                         'is_independent_repeated_revision_event': False})
    return {'fixed_Full_revision_proposals': entries,
            'fixed_Full_installed_changes': sum(e['installed_version_changed'] for e in entries),
            'fragment_updates': fragment,
            'fragment_trigger_event_count': 1,
            'guarded_update_induction_or_transfer_proved': False}


def main(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'completed.json').exists():
        print('Already completed; inspect the preserved receipt, do not rerun.')
        return
    before = ledger_snapshot(root)
    if any(status not in ('completed', 'failed') for _, status, _ in before['counts']):
        raise ValueError('Resolve existing in-flight requests before an offline checkpoint')
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    old = root / 'artifacts/legal_skill_evolution_relational_acquisition_v2_20261113'
    recent = root / 'artifacts/legal_skill_evolution_source_program_acquisition_20261113'
    spec = read(old / 'ScopedAcquisition/frozen_candidate.json')['spec']
    review = read(old / 'targeted_source_semantic_review.json')
    copied, checks, observations = {}, [], []
    for prefix, field in (('4d4e55', 'restricted_recipient_scope'), ('5cad3f', 'action')):
        path = next((old / 'ScopedAcquisition/results').glob('ContractNLI_' + prefix + '*.json'))
        row = read(path)
        source = public[row['source']]
        record = row['records'][1]
        entry = next(e for e in review['entries'] if e['source_prefix'] == prefix and e.get('source_proof_supported') is False)
        observation = review_binding(source, spec, kind=record['kind'], field=field,
            value=record['values'][field], support_ids=record['support_ids'], polarity='rejected',
            reason=entry['issue'], review_origin='artifacts/legal_skill_evolution_relational_acquisition_v2_20261113/targeted_source_semantic_review.json')
        check = check_binding(observation, source, spec, row['records'])
        assert check['status'] == 'violated'
        current = read(recent / 'LearnedSourceCompiler' / path.name)
        current_spec = read(recent / 'frozen_specs.json')['ScopedAcquisition']
        now = check_binding(observation, source, current_spec, current['records'])
        checks.append({'source': row['source'], 'task': 'nda-7',
                       'cached_native_correct': next(v['score']['correct'] for v in row['views'] if v['view'] == 'nda-7'),
                       'old': check, 'later_program': now,
                       'new_independent_acquisition_or_core_success': False})
        observations.append(observation)
        copied[row['source']] = source
    immutable_json(folder / 'source_observations.json', {'observations': observations, 'checks': checks})
    free = read(recent / 'IndependentWholeProgram/teacher.json')['value']
    bundle = {'spec': read(recent / 'frozen_specs.json')[free['compiler_choice']],
              'source_program': free['source_program']}
    materials = {e['source']: public[e['source']]['views'][0]['public']['source_text']
                 for e in bundle['spec']['source_examples']}
    compile_bundle(bundle, materials)
    cached = read(next((recent / 'IndependentWholeProgram').glob('ContractNLI_d50*.json')))
    source = public[cached['source']]
    traced = run_bundle(bundle, source, trace=True)
    assert traced['source_trace']['result'] == cached['raw_program_output']
    assert traced['records'] == cached['records']
    producers = [producing_calls(traced['source_trace'], r) for r in traced['records']
                 if r['kind'] == 'confidential_information_authorization']
    assert producers and all(p['functions'] for p in producers)
    copied[source['key']] = source
    immutable_json(folder / 'actual_source_trace.json', traced)
    immutable_json(folder / 'trace_receipt.json', {
        'source': source['key'], 'old_raw_output_and_records_identical': True,
        'producing_calls': producers, 'localization_is_semantic_fault_proof': False,
        'same_previously_failed_program_not_retrained': True,
        'source_program_sha256': hashlib.sha256(bundle['source_program'].encode()).hexdigest()})
    immutable_json(folder / 'TRAIN_public_inputs.json', {'sources': list(copied.values())})
    immutable_json(folder / 'replayed_bundle.json', bundle)
    immutable_json(folder / 'real_revision_inventory.json', revision_inventory(root))
    after = ledger_snapshot(root)
    assert before == after
    paths = [Path(__file__).relative_to(root).as_posix(),
             'legal_skill_guard/skill_evolution/semantic_learning.py',
             'legal_skill_guard/skill_evolution/span_compiler.py',
             'legal_skill_guard/skill_evolution/span_compiler_worker.py',
             'tests/test_skill_evolution_semantic_learning.py']
    immutable_json(folder / 'completed.json', {
        'captured_utc': datetime.now(timezone.utc).isoformat(),
        'new_physical_requests': {'executor': 0, 'teacher': 0},
        'ledger_before_and_after': before,
        'source_snapshot': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        'previously_native_correct_but_source_rejected_paths_detected': len(checks),
        'traced_actual_program_raw_output_identical': True,
        'new_native_labels_loaded': False, 'DEV_TEST_used': False,
        'production_induction_implemented': False,
        'new_semantics_acquired_or_update_transferred': False, 'goal_complete': False})
    print(json.dumps(read(folder / 'completed.json'), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main(Path(__file__).resolve().parents[1])
