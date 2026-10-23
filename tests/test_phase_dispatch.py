"""Scheduling contracts only: no model, teacher, legal target or TEST access."""
import ast
from collections import Counter
import hashlib
import copy
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from legal_skill_guard.learning.phase_dispatch import PhaseDispatch


def dispatch(native=4, teacher=2, serving=4, on_failure=lambda: None):
    return PhaseDispatch({
        'execution_contract': 'direct_statutory_claims', 'execution_contract_version': 14,
        'phase_dispatch': {'policy': 'ordered_independent_phases_v1',
                           'native_workers': native, 'teacher_workers': teacher,
                           'required_max_num_seqs': serving}},
        environment={'actual_argv': ['vllm', '--max-num-seqs', str(serving)]},
        on_failure=on_failure)


def test_absent_policy_preserves_serial_order():
    d = PhaseDispatch({})
    seen = []
    assert d.native(lambda x: seen.append(x) or x * 2, range(8)) == list(range(0, 16, 2))
    assert seen == list(range(8))
    assert d.teacher(lambda x: x, []) == []
    function = lambda x: x
    assert d.locked_requests(function, lambda x: x) is function
    assert d.limited_teacher(function) is function


def test_completion_order_does_not_change_result_or_merge_order():
    d = dispatch()
    release_first = threading.Event()
    completed = []
    def work(i):
        if i == 0:
            assert release_first.wait(2)
        elif i == 3:
            release_first.set()
        completed.append(i)
        return ('row', i)
    assert d.native(work, range(12)) == [('row', i) for i in range(12)]
    assert completed[0] != 0


def test_identical_complete_wires_have_one_physical_origin():
    d = dispatch()
    cache, calls = {}, Counter()
    both_keys = threading.Barrier(2)
    def original_actor(key):
        if key not in cache:
            calls[key] += 1
            both_keys.wait(timeout=2)
            cache[key] = 'physical-' + str(key)
        return cache[key]
    actor = d.locked_requests(original_actor, lambda key: key)
    keys = [0, 1, 0, 1, 1, 0, 0, 1]
    assert d.native(actor, keys) == ['physical-' + str(k) for k in keys]
    assert calls == {0: 1, 1: 1}
    assert actor.__wrapped__ is original_actor


def test_failure_cancels_unstarted_work_and_drains_actual_inflight():
    four_started = threading.Barrier(4)
    failed = threading.Event()
    started, completed, callbacks = set(), set(), []
    lock = threading.Lock()
    def stop():
        callbacks.append(True)
        failed.set()
    d = dispatch(on_failure=stop)
    def work(i):
        with lock:
            started.add(i)
        four_started.wait(timeout=2)
        if i == 1:
            raise ValueError('original transport failure')
        assert failed.wait(2)
        with lock:
            completed.add(i)
        return i
    with pytest.raises(ValueError, match='original transport failure'):
        d.native(work, range(30))
    assert started == {0, 1, 2, 3}
    assert completed == {0, 2, 3}
    assert len(callbacks) == 1


def test_native_case_workers_do_not_exceed_remote_teacher_limit():
    d = dispatch()
    pair = threading.Barrier(2)
    lock = threading.Lock()
    active, peak = 0, 0
    def original_teacher(i):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        pair.wait(timeout=2)
        with lock:
            active -= 1
        return i
    teacher = d.limited_teacher(original_teacher)
    assert d.native(teacher, range(12)) == list(range(12))
    assert peak == 2 and active == 0


@pytest.mark.parametrize('field,value', [('native_workers', True), ('native_workers', 0),
    ('native_workers', 8), ('teacher_workers', 0), ('teacher_workers', 3),
    ('required_max_num_seqs', 2)])
def test_bad_or_undeclared_worker_counts_fail_not_fallback(field, value):
    cfg = {'execution_contract': 'direct_statutory_claims', 'execution_contract_version': 14,
           'phase_dispatch': {'policy': 'ordered_independent_phases_v1',
                              'native_workers': 4, 'teacher_workers': 2,
                              'required_max_num_seqs': 4}}
    cfg['phase_dispatch'][field] = value
    with pytest.raises(ValueError):
        PhaseDispatch(cfg, environment={'actual_argv': ['vllm', '--max-num-seqs', '4']})


def test_four_sequence_profile_rejects_original_one_sequence_service():
    cfg = {'execution_contract': 'direct_statutory_claims', 'execution_contract_version': 14,
           'phase_dispatch': {'policy': 'ordered_independent_phases_v1',
                              'native_workers': 4, 'teacher_workers': 2,
                              'required_max_num_seqs': 4}}
    with pytest.raises(ValueError, match='disagree'):
        PhaseDispatch(cfg, environment={'actual_argv': ['vllm', '--max-num-seqs', '1']})
    # Explicit one-sequence overlap is distinct from a batching speedup claim.
    assert dispatch(serving=1).required_max_num_seqs == 1


def test_wire_identity_contains_complete_schema_and_generation():
    builder = lambda row: ([{'role': 'user', 'content': row}], {'type': 'object'}, [])
    one = PhaseDispatch.payload_key({'seed': 45}, builder)
    two = PhaseDispatch.payload_key({'seed': 145}, builder)
    assert one('a') == one('a') and one('a') != one('b') and one('a') != two('a')


@pytest.mark.parametrize('module,klass', [('experiments.openexempt_online', 'Online'),
    ('experiments.openexempt_ace_online', 'ACEOnline'),
    ('experiments.openexempt_trace2skill', 'Trace2Skill')])
def test_real_atomic_progress_writes_are_serialized(module, klass, tmp_path):
    import importlib
    cls = getattr(importlib.import_module(module), klass)
    owner = object.__new__(cls)
    owner._dispatch, owner.out, owner.run_id = dispatch(), tmp_path, 'synthetic-progress'
    owner.current_batch, owner.teacher_attempts = 1, 0
    owner.native, owner.teachers, owner.reuse_events, owner.bank = [], [], [], []
    owner.playbook = ''
    assert owner._dispatch.native(lambda i: owner.progress('synthetic', current_document_id=i) or i,
                                  range(32)) == list(range(32))
    saved = json.loads((tmp_path / 'progress.json').read_text())
    assert saved['run_id'] == 'synthetic-progress' and saved['current_document_id'] in range(32)


def test_existing_teacher_ledger_reservation_is_atomic_across_threads(tmp_path):
    from legal_skill_guard.inference.codex_cli_client import CodexCLIClient, CodexInvocationError
    client = object.__new__(CodexCLIClient)
    client.invocation_budget_path = tmp_path / 'synthetic-budget.json'
    client.max_invocations, client.model = 16, 'synthetic-not-invoked'
    reservations = dispatch().native(lambda i: client._reserve_invocation(
        purpose=f'toy_{i}', request_sha256=str(i), attempt=0), range(16))
    assert sorted(r['sequence'] for r in reservations) == list(range(1, 17))
    assert len(json.loads(client.invocation_budget_path.read_text())['reservations']) == 16
    with pytest.raises(CodexInvocationError, match='exhausted'):
        client._reserve_invocation(purpose='outside-budget', request_sha256='x', attempt=0)


def test_legacy_serial_controls_can_reuse_original_progress_without_dispatch(tmp_path):
    from experiments.openexempt_online import Online
    owner = SimpleNamespace(out=tmp_path, run_id='serial-control', current_batch=1,
        native=[], teachers=[], teacher_attempts=0, reuse_events=[], bank=[])
    Online.progress(owner, 'synthetic')
    value = json.loads((tmp_path / 'progress.json').read_text())
    assert value['run_id'] == 'serial-control' and 'execution_dispatch' not in value


# Pinned ASTs from the actual current v14 implementation, before dispatch edits.
# Whitespace and line movement may change; inference, scoring and gates may not.
PROTECTED = {
    'experiments/openexempt_online.py:Online.answer': '2b71d59251519b7fe784a02d2b33ede7688c6a0f949a064070496a0a28bd3f7d',
    'experiments/openexempt_online.py:Online.grade': '9fc5a0dc06d134b51a9c4397ba24edf6cfb24aa689f806fde1b33661abecf24d',
    'experiments/openexempt_online.py:actor_payload': '3d1a7601b64e18deb1c52231cd6688bd350c461b535cfffa4d2c06707dab0f19',
    'experiments/openexempt_online.py:direct_case_input': '7012b2a217dce408a88add4845894322363c86edeb984186ceea497e475df29b',
    'experiments/openexempt_online.py:acceptance': '07af66cc8a75b7a83b6f9594896597a2fe2816fe3e30bf459f125b2ac0304d73',
    'experiments/openexempt_online.py:task_admission': '6351a172b4f06c6f5f7f8d204e017bc9cdde9c6850bf1ad621eb1bd7cc00de13',
    'experiments/openexempt_online.py:legal_scope_admission': '2e977b21fc3505a662e96b1535247fe429e08277ef0c2e3a73b3720d29bca300',
    'experiments/openexempt_ace_online.py:ACEOnline.answer': '8729c0e5a3bacf3dcaad6f49311f4571ed8b80444e57ba4d464eb8ef83eaa075',
    'experiments/openexempt_ace_online.py:ACEOnline.train_solved': 'ee033bc921fcd0b5a3b3436af667ef1753b93099a17157bd58a1202bada76d0c',
    'legal_skill_guard/learning/experiment.py:Comparison.call': 'cb1a2e2725ac9fa79ab94a2932d06f565ff5d22479d0230d76ec7e067c1472af',
    'legal_skill_guard/learning/experiment.py:Comparison.check': 'c96f5d82c76d447c00c6ac506424b1a1ef864affa7bc8c5e93b0555a536f4ed2',
    'legal_skill_guard/learning/trace2skill_text.py:merge_groups': 'b73063cf4837f50e23982e96c122b1b8bea022226289e026c0a6f80eb4858bfb',
}


@pytest.mark.parametrize('target,expected', PROTECTED.items())
def test_actor_grader_transport_and_admission_AST_unchanged(target, expected):
    root = Path(__file__).resolve().parents[1]
    file, dotted = target.split(':')
    body = ast.parse((root / file).read_text()).body
    node = None
    for name in dotted.split('.'):
        node = next(n for n in body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
        body = node.body
    assert hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest() == expected


@pytest.fixture
def memory_store(monkeypatch):
    from legal_skill_guard.experiment.storage import RunStore
    data, lock = {}, threading.Lock()
    def immutable(path, value):
        with lock:
            key = str(path)
            if key in data:
                assert data[key] == value
            data[key] = copy.deepcopy(value)
        return path
    def atomic(path, value):
        with lock:
            data[str(path)] = copy.deepcopy(value)
    monkeypatch.setattr(RunStore, 'immutable_json', staticmethod(immutable))
    monkeypatch.setattr(RunStore, 'atomic_json', staticmethod(atomic))
    return data


def toy_record(row, *, missing=0):
    return {'case_id': row['case_id'], 'family': row['family'],
            'parsed': {'answer': {}}, 'parse_error': None,
            'score': {'f1': 0.5, 'full_output_f1': 0.5, 'invalid_format': 0,
                      'full_output_claim_fp': 0, 'full_output_claim_fn': missing}}


def toy_metrics(records):
    return {f: {'f1': 0.5, 'full_output_f1': 0.5} for f in ('EC', 'EV')}


@pytest.mark.parametrize('workers', [1, 4])
def test_main_grades_only_after_all_rows_and_rotated_arms(workers, monkeypatch, tmp_path, memory_store):
    import experiments.openexempt_online as mod
    owner = object.__new__(mod.Online)
    owner._dispatch = PhaseDispatch({}) if workers == 1 else dispatch()
    owner.cfg = {'source_cases': 2, 'batch_source_cases': 2, 'frozen_after_first_batch_control': True}
    owner.rows = [{'case_id': i, 'family': f, 'batch': 1, 'source_key': str(i)}
                  for i in (181, 182) for f in ('EC', 'EV')]
    owner.out, owner.bank, owner.frozen_bank, owner.first_batch_frozen_bank = tmp_path, [], [], []
    for name in ('prequential_empty', 'prequential_skills', 'prequential_frozen',
                 'prequential_direct', 'prequential_first_batch_frozen', 'summaries'):
        setattr(owner, name, [])
    owner.native, seen, orders = [], [], {}
    def answer(row, bank, stage, arm):
        orders.setdefault((row['case_id'], row['family']), []).append(arm)
        seen.append((row['case_id'], row['family'], arm))
        return {**toy_record(row), 'arm': arm}
    owner.answer = answer
    def grade(records):
        assert len(seen) == len(owner.rows) * 5 and len(records) == len(seen)
    owner.grade, owner.progress = grade, lambda *a, **k: None
    owner.update = lambda *a: {'bank_sha256': mod.csha([]), 'parent_bank_sha256': mod.csha([])}
    monkeypatch.setattr(mod, 'metrics', toy_metrics)
    monkeypatch.setattr(mod, 'paired_effect', lambda *a: {'mean_f1_difference': 0})
    assert owner.execute() == 'completed_bounded_mechanism_study'
    saved = memory_store[str(tmp_path / 'batches/b1_prequential_records.json')]
    for arm, records in saved.items():
        assert [(r['case_id'], r['family']) for r in records] == [(r['case_id'], r['family']) for r in owner.rows]
    for row in owner.rows:
        arms = ('empty', 'frozen_initial', 'skills', 'empty_direct_numeric', 'frozen_after_B1')
        offset = (row['case_id'] + mod.FAMILIES[row['family']]) % len(arms)
        assert orders[row['case_id'], row['family']] == list(arms[offset:] + arms[:offset])


@pytest.mark.parametrize('workers', [1, 4])
def test_ACE_keeps_dependent_rounds_and_original_last_tag_order(workers, monkeypatch, tmp_path, memory_store):
    import experiments.openexempt_ace_online as mod
    owner = object.__new__(mod.ACEOnline)
    owner._dispatch = PhaseDispatch({}) if workers == 1 else dispatch()
    owner.current_batch, owner.playbook, owner.out = 1, 'parent', tmp_path
    owner.cfg = {'grading_directory': 'toy', 'ace_max_TRAIN_reflection_rounds': 3,
                 'execution_contract': 'direct_statutory_claims', 'execution_contract_version': 14,
                 'batch_source_cases': 16, 'source_cases': 128, 'library_token_hard_cap': 8192}
    rows = [{'case_id': i, 'family': 'EC'} for i in (181, 182, 183)]
    owner.answer = lambda row, stage, **kw: toy_record(row, missing=int(
        stage.endswith('initial') or (row['case_id'] == 182 and stage.endswith('round1'))))
    owner.grade, owner.check = lambda records: None, lambda: None
    owner.meter = SimpleNamespace(token_count=lambda **kw: 1)
    release_first, captured = threading.Event(), {}
    def teacher(name, system, body, schema):
        if name.endswith('curator'):
            return []
        case, number = int(name.split('_')[1]), int(name.split('_')[3][1:])
        if workers == 4 and case == 181:
            assert release_first.wait(2)
        if case == 183:
            release_first.set()
        return {'bullet_tags': [{'id': 'same', 'tag': f'{case}-{number}'}]}
    owner.teacher_call = owner._dispatch.limited_teacher(teacher)
    monkeypatch.setattr(mod, 'read', lambda p: {'targets': {'EC': {}}})
    monkeypatch.setattr(mod, 'reflector_request', lambda *a, **k: ('prompt', {}, []))
    monkeypatch.setattr(mod, 'validate_reflection', lambda *a: None)
    monkeypatch.setattr(mod, 'update_bullet_counts', lambda book, tags: book + '|' + tags[0]['tag'])
    def curate(parent, reflections, rows, **kw):
        captured['tags'], captured['reflections'] = kw['all_round_bullet_tags'], reflections
        return 'curator', {}, 'counted'
    monkeypatch.setattr(mod, 'curator_request', curate)
    monkeypatch.setattr(mod, 'commit_additions', lambda *a, **k: {'playbook': 'learned'})
    result = owner.update(rows, [toy_record(r) for r in rows], {(r['case_id'], 'EC'): {} for r in rows})
    assert [t['tag'] for t in captured['tags']] == ['181-1', '182-1', '182-2', '183-1']
    assert [len(t['rounds']) for t in result['actual_TRAIN_trajectories']] == [1, 2, 1]
    assert [t['source_case_id'] for t in result['actual_TRAIN_trajectories']] == [181, 182, 183]


@pytest.mark.parametrize('workers', [1, 4])
def test_Text_full256_barrier321_calls_and_ordered_merges(workers, monkeypatch, tmp_path, memory_store):
    import experiments.openexempt_trace2skill as mod
    owner = object.__new__(mod.Trace2Skill)
    owner._dispatch = PhaseDispatch({}) if workers == 1 else dispatch()
    owner.out, owner.current_batch, owner.bank = tmp_path / 'run', 0, []
    owner.cfg = {'grading_directory': 'toy', 'merge_batch_size': 5, 'max_merge_levels': 5,
                 'library_token_hard_cap': 8192, 'planned_teacher_responses_max': 321}
    owner.rows = [{'case_id': i, 'family': f, 'batch': (i - 181) // 16 + 1}
                  for i in range(181, 309) for f in ('EC', 'EV')]
    ordinal = {(r['case_id'], r['family']): i for i, r in enumerate(owner.rows)}
    # Preserve the author's existing tail placement, not sorted indices. The
    # small final tail is deliberately appended to earlier groups at each level.
    expected_groups = [[i] for i in range(256)]
    while len(expected_groups) > 1:
        expected_groups = [[i for part in group for i in part]
                           for group in mod.merge_groups(expected_groups, 5)]
    expected_traversal = expected_groups[0]
    assert sorted(expected_traversal) == list(range(256))
    sources, finals, grade_calls, names = [], [], [], []
    owner.teachers = []
    monkeypatch.setattr(mod, 'ROOT', tmp_path)
    def answer(row, bank, stage, arm):
        record = toy_record(row)
        if stage == 'source_first_forecasts':
            assert not names
            sources.append(ordinal[row['case_id'], row['family']])
            p = owner.out / 'native' / stage / f"{row['case_id']}_{row['family']}_{arm}.json"
            record['raw_call_path'] = str(p.relative_to(tmp_path))
            memory_store[str(p)] = {'response': {'content': '{}'}}
            memory_store[str(p.with_name(p.stem + '.input.json'))] = {'messages': [], 'schema': {}}
        else:
            assert len(names) == 321 and str(owner.out / 'publications/final.json') in memory_store
            finals.append(ordinal[row['case_id'], row['family']])
        return record
    owner.answer = answer
    def grade(records):
        assert len(records) == 256 and len(sources) == 256
        grade_calls.append(True)
    owner.grade = grade
    def read(path):
        if '/toy/' in str(path):
            assert len(sources) == 256 and len(grade_calls) >= 1
            return {'targets': {'EC': {}, 'EV': {}}}
        return memory_store[str(path)]
    monkeypatch.setattr(mod, 'read', read)
    def teacher(name, system, body, schema):
        assert len(sources) == 256 and str(owner.out / 'source_records.json') in memory_store
        names.append(name)
        owner.teachers.append(name)
        if name.startswith('map_'):
            _, case, family = name.split('_')
            return {'indices': [ordinal[int(case), family]]}
        if name.startswith('merge_'):
            return {'indices': [i for patch in body['all_patches_in_this_ordered_group'] for i in patch['indices']]}
        assert name == 'translate_final_patch'
        assert body['complete_hierarchically_merged_patch']['indices'] == expected_traversal
        return body['complete_hierarchically_merged_patch']
    owner.teacher_call = owner._dispatch.limited_teacher(teacher)
    monkeypatch.setattr(mod, 'apply_patch', lambda files, final: {'SKILL.md': 'compiled toy skill'})
    monkeypatch.setattr(mod, 'actor_bank', lambda files: [{'id': 'toy'}])
    monkeypatch.setattr(mod, 'metrics', toy_metrics)
    owner.meter = SimpleNamespace(token_count=lambda **kw: 1)
    result = owner.execute()
    assert result['status'] == 'completed_trace2skill_text_offline_adaptation'
    assert len(sources) == len(finals) == 256 and len(grade_calls) == 2
    assert len(names) == 321 and sum(n.startswith('map_') for n in names) == 256
    assert [sum(n.startswith(f'merge_L{level}_') for n in names) for level in range(1, 5)] == [51, 10, 2, 1]
    saved = memory_store[str(owner.out / 'final_TRAIN_records.json')]
    assert [(r['case_id'], r['family']) for r in saved] == [(r['case_id'], r['family']) for r in owner.rows]
