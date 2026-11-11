"""Resume B1 from its real first attempts and representation-only teacher fix."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.study import Study, load_json, PILOT_ARMS
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.native import public_task
from legal_skill_guard.skill_evolution.teacher import compile_block

ROOT = Path(__file__).resolve().parents[2]
study = Study(ROOT, load_json(ROOT / 'configs/legal_skill_evolution_pilot_v5_20261111.json'))
study.initialize()
old = ROOT / 'artifacts/legal_skill_evolution_20261111/pilot_v4'
library = Library()
with sqlite3.connect('file:' + str(study.ledger.path) + '?mode=ro', uri=True) as db:
    before = dict(db.execute('select role,count(*) from calls group by role'))
    imports = []
    for key in study.order[:5]:
        source = study.records[key]
        for view in source['views']:
            identity = digest({'source': key, 'view': view, 'library_hash': library.hash, 'retrieved': None})
            prior = load_json(old / 'view_results' / (identity + '.json'))
            assert prior['execution']['answer'] is not None
            immutable_json(study.folder / 'view_results' / (identity + '.json'), prior)
            baseline = digest({'source': key, 'task': public_task(source, view),
                               'frozen_executor': study.executor.config})
            immutable_json(study.folder / 'native_direct_baselines' / (baseline + '.json'),
                           {'identity': baseline, 'execution': prior['execution']})
            imports.append({'source': key, 'view': view['id'], 'old_view_result_hash': digest(prior),
                            'old_execution_model_version': 'preserved real first attempt, not regenerated'})
    for arm in PILOT_ARMS:
        initial = load_json(old / arm / 'initial_B1.json')
        assert initial['binding']['library_hash'] == library.hash
        immutable_json(study.folder / arm / 'initial_B1.json', initial)
    response = deepcopy(load_json(old / 'Full/teacher_B1.json'))
    old_programs = [d['skill']['procedure'] for b in response['value']['blocks'] for d in b['revisions']]
    for block in response['value']['blocks']:
        for revision in block['revisions']:
            for record in revision['skill']['semantic_records']:
                record['ports'] = record.pop('premises')
        compile_block(block, library, study.records, 'Full')
    new_programs = [d['skill']['procedure'] for b in response['value']['blocks'] for d in b['revisions']]
    assert old_programs == new_programs
    response['representation_adaptation'] = {
        'only_change': 'semantic record member key premises renamed to ports; exact same named members',
        'procedures_inputs_reads_source_quotes_and_legal_values_unchanged': True,
        'read_input_field_already_equals_its_declared_name': True,
        'new_teacher_call': False, 'original_model_response_preserved': str(old / 'Full/teacher_B1.json')}
    immutable_json(study.folder / 'Full/teacher_B1.json', response)
    context = load_json(old / 'Full/update_context_B1.json')
    immutable_json(study.folder / 'Full/update_context_B1.json', context)
    after = dict(db.execute('select role,count(*) from calls group by role'))
    assert before == after
immutable_json(study.folder / 'B1_representation_recovery.json', {
    'imports': imports, 'teacher_adaptation': response['representation_adaptation'],
    'physical_counts_before_after': before, 'new_model_calls': 0,
    'empty_libraries_preserved': True, 'old_failed_candidate_receipts_preserved': True,
    'same_frozen_direct_fallback_for_all_masks': True})
print(json.dumps({'original_initial_views_preserved': len(imports), 'teacher_blocks_now_compile': len(response['value']['blocks']),
                  'new_model_calls': 0, 'physical_counts': before}), flush=True)
