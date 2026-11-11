"""Compare proposed production update inputs with actual B3 teacher requests.

Run from the isolated implementation worktree. Teacher dispatch is intercepted;
the only native input reads are already authorized TRAIN records and caches.
"""
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.study import Study

ROOT = Path(__file__).resolve().parents[2]


class Captured(RuntimeError):pass


def main():
    profile = json.loads((ROOT / 'configs/legal_skill_evolution_formal_v2_20261111.json').read_text())
    original = ROOT / profile['artifacts']
    actual_requests = {}
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        identities = [r[0] for r in db.execute("select id from calls where role='teacher' and id like ?", (profile['run_id'] + ':%',))]
    for identity in identities:
        path = original / 'calls' / digest(identity) / 'request.json'
        if not path.exists():continue
        request = json.loads(path.read_text());context = json.loads(request['user_prompt'])
        if context['batch'] == 3:actual_requests[context['arm']] = path
    manifest = json.loads((ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json').read_text())
    rows = []
    with tempfile.TemporaryDirectory() as folder:
        study = object.__new__(Study)
        study.folder, study.profile, study.stage = Path(folder), profile, 'formal'
        study.batches = [[r['source_key'] for r in b['sources']] for b in manifest['source_sequence']]
        study.order = sum(study.batches, [])
        train = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train'
        study.records = {r['key']: r for r in json.loads((train / 'public.json').read_text())}
        study.grading = json.loads((train / 'grading.json').read_text())
        def forbidden_parent(*args, **kwargs):raise AssertionError('No new history execution is allowed in this parity check')
        study.parent = forbidden_parent
        class Teacher:
            ledger = SimpleNamespace(run_id=profile['run_id'])
            def propose(self, call_id, **kwargs):
                arm = json.loads(kwargs['user_prompt'])['arm']
                actual = actual_requests[arm]
                saved = json.loads(actual.read_text())
                for field in ('source_ids', 'system_prompt'):
                    assert json.dumps(saved[field], ensure_ascii=False) == json.dumps(kwargs[field], ensure_ascii=False), field
                assert digest(saved['output_schema']) == digest(kwargs['output_schema']), 'schema types or constraints changed'
                assert digest(json.loads(saved['user_prompt'])) == digest(json.loads(kwargs['user_prompt'])), 'model input content changed'
                assert set(kwargs['source_ids']) <= set(study.records)
                context = json.loads(kwargs['user_prompt'])
                rows.append({'arm': context['arm'], 'batch': 3, 'original_request': str(actual.relative_to(ROOT)),
                    'original_request_sha256': hashlib.sha256(actual.read_bytes()).hexdigest(),
                    'model_input_content_equal': True,
                    'original_fresh_user_bytes_equal_to_cached_replay': saved['user_prompt'] == kwargs['user_prompt'],
                    'persisted_schema_property_order_equal': json.dumps(saved['output_schema'], ensure_ascii=False) == json.dumps(kwargs['output_schema'], ensure_ascii=False),
                    'proposed_payload_sha256': hashlib.sha256(json.dumps(kwargs, ensure_ascii=False).encode()).hexdigest(),
                    'cohort': kwargs['source_ids'],
                    'failed_raw_programs_visible': sum(bool(x.get('raw_block')) for x in context['retained_edits'])})
                raise Captured()
        study.teacher = Teacher()
        for arm in ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev'):
            for name in ('B2.json', 'initial_B3.json', 'update_context_B3.json'):
                target = study.folder / arm / name;target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original / arm / name, target)
            with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('Network forbidden')):
                try:study.update(arm, 3)
                except Captured:pass
                else:raise AssertionError('Teacher dispatch was not intercepted')
    result = {'actual_existing_TRAIN_teacher_input_contents_equal': len(rows), 'rows': rows,
        'current_Study_code_sha256': hashlib.sha256(Path(inspect.getfile(Study)).read_bytes()).hexdigest(),
        'new_model_calls': 0, 'new_history_executions': 0, 'TEST_opened': False,
        'cached_replay_order_note': 'Persisted contexts sort JSON keys. Compare old-versus-new replay payload bytes separately; original fresh-versus-reloaded context is required to preserve every JSON value. Exact response caches still require literal wire equality.',
        'scope': 'Model input content parity and real failed-draft visibility; not new method-effect evidence.'}
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'reports/legal_skill_evolution_run_20261111/actual_teacher_prefetch_payload_parity.json'
    destination.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':main()
