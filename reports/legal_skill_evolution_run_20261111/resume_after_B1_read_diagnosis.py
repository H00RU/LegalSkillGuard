"""Preserve settled B1, carry literal failed reads forward, and resume other work."""
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.study import Study, load_json, PILOT_ARMS
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.native import public_task

ROOT = Path(__file__).resolve().parents[2]
study = Study(ROOT, load_json(ROOT / 'configs/legal_skill_evolution_pilot_v7_20261111.json'))
study.initialize()
prior = ROOT / 'artifacts/legal_skill_evolution_20261111/pilot_v6'
empty = Library()
with sqlite3.connect('file:' + str(study.ledger.path) + '?mode=ro', uri=True) as db:
    before = list(db.execute('select role,status,count(*) from calls group by role,status'))
    assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    imports = []
    for key in study.order[:5]:
        source = study.records[key]
        for view in source['views']:
            identity = digest({'source': key, 'view': view, 'library_hash': empty.hash, 'retrieved': None})
            saved = load_json(prior / 'view_results' / (identity + '.json'))
            assert saved['execution']['answer'] is not None
            immutable_json(study.folder / 'view_results' / (identity + '.json'), saved)
            baseline = digest({'source': key, 'task': public_task(source, view),
                               'frozen_executor': study.executor.config})
            immutable_json(study.folder / 'native_direct_baselines' / (baseline + '.json'),
                           {'identity': baseline, 'execution': saved['execution']})
            imports.append({'source': key, 'view': view['id'], 'original_view_hash': digest(saved)})
    for arm in PILOT_ARMS:
        initial = load_json(prior / arm / 'initial_B1.json')
        assert initial['binding']['library_hash'] == empty.hash
        immutable_json(study.folder / arm / 'initial_B1.json', initial)

    # This is diagnostic feedback from already-billed outputs, not a new replay.
    reads = []
    for path in sorted((prior / 'calls').glob('*/request.json')):
        request = load_json(path)
        row = db.execute('select status,result from calls where id=?', (request['id'],)).fetchone()
        assert row and row[0] == 'completed'
        result = json.loads(row[1])
        assert result['finish_reason'] == 'stop'
        task = json.loads(request['payload']['messages'][1]['content'])['task']
        fields = json.loads(result['content'])
        spans = task['source_spans']
        for value in fields.values():
            value['support'] = [spans[i] for i in value['support_ids']]
        reads.append({'physical_call_id': request['id'], 'source': request['source'],
            'view': task['view_id'], 'fields_requested': task['fields'],
            'returned_fields': fields, 'question': task['read_question'],
            'locator': task['source_locator'], 'raw_result_path': str(path.with_name('result.json'))})
    library = Library.load(prior / 'Full/B1.json')
    for edit in library.provisional_edits:
        declared = {name for revision in edit.get('revisions') or []
                    for name, port in revision['new']['inputs'].items() if port['mode'] == 'read'}
        edit['read_diagnostics'] = [read for read in reads if set(read['fields_requested']) <= declared]
    library.save(study.library_path('Full', 1))
    receipt = load_json(prior / 'Full/update_B1.json')
    assert receipt['new_library_hash'] == library.hash == empty.hash
    assert receipt['logical_candidate_parent_executions'] == 60
    immutable_json(study.folder / 'Full/update_B1.json', receipt)
    after = list(db.execute('select role,status,count(*) from calls group by role,status'))
    assert before == after
immutable_json(study.folder / 'B1_settled_state_import.json', {
    'prior_profile': 'configs/legal_skill_evolution_pilot_v6_20261111.json',
    'original_initial_views': imports, 'settled_full_B1_receipt': receipt,
    'failed_read_diagnostics_preserved': len(reads), 'literal_model_values_unchanged': True,
    'new_model_calls': 0, 'physical_counts_before_after': before,
    'next_work': 'Other fixed arms B1, then fixed new TRAIN sources B2; do not replay unchanged Full B1',
    'core_success': 0, 'accepted_skills': 0})
print(json.dumps({'original_initial_views_imported': len(imports), 'failed_reads_preserved': len(reads),
                  'Full_B1_skipped_as_settled': True, 'new_model_calls': 0}), flush=True)
