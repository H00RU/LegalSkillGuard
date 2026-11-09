"""Preserve the two actual requests, recoveries and native TRAIN executions.

This audit reads existing outputs only. It cannot dispatch either model.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'reports/method_redesign_20261109'
BASE = ROOT / 'artifacts/rr_method_redesign_20261109'
V1 = BASE / 'legal_primitive_chain_v1_20261110'
V2 = BASE / 'legal_primitive_chain_v2_20261110'
BEFORE = Path('/media/sangfor/vdb/legal-skill-backups/legal_scope_plain_20261110/ledger.after.sqlite3')
BACKUP = Path('/media/sangfor/vdb/legal-skill-backups/legal_primitive_chain_20261110')


def read(path):
    return json.loads(path.read_text())


def snapshot(path):
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
        return {t: db.execute('select * from ' + t + ' order by 1').fetchall()
                for t in ('calls', 'meta', 'oracle_views')}


def main():
    old = snapshot(BEFORE)
    assert digest(old) == 'e84a7f9a2bddb6cd0bf75541ded889f57667d6d9feff179ed2a7937d0a98e2b1'
    dbpath = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    current = snapshot(dbpath)
    grades = read(V2 / 'TRAIN_grades.json')['rows']
    executions = read(V2 / 'execution_closed_before_grading.json')
    added_calls = {'legal_primitive_chain_v1_20261110:source',
                   'legal_primitive_chain_v2_20261110:facts8'}
    added_meta = {'method_runtime_policy:legal_primitive_chain_v1_20261110',
                  'method_runtime_policy:legal_primitive_chain_v2_20261110'}
    added_views = {(g['source'], g['view_hash']) for g in grades}
    historical = deepcopy(current)
    historical['calls'] = [r for r in historical['calls'] if r[0] not in added_calls]
    historical['meta'] = [r for r in historical['meta'] if r[0] not in added_meta]
    historical['oracle_views'] = [r for r in historical['oracle_views'] if (r[0], r[1]) not in added_views]
    assert historical == old
    assert len(current['calls']) - len(old['calls']) == 2
    assert len(current['oracle_views']) - len(old['oracle_views']) == 2
    source1 = read(V1 / 'source.json')
    source2 = read(V2 / 'source.json')
    assert source1['physical_response'] == source2['physical_response']
    assert source1['value']['c6_program'] == source2['value']['c6_program']
    assert source2['source_response_reused_without_dispatch'] is True
    recovery = read(V2 / 'source_recovery.json')
    assert recovery['new_teacher_dispatches'] == 0
    assert all(r['original_condition_reachable_with_program'] and
               r['implication_normalization_equivalent_for_all_inputs_and_results']
               for r in recovery['checks'])
    copies = {}
    for stage in (V1, V2):
        seal = read(stage / 'seal.json')
        for relative, expected in seal['files'].items():
            preserved = stage / 'frozen_source' / relative
            if not preserved.exists():
                actual = ROOT / relative
                assert hashlib.sha256(actual.read_bytes()).hexdigest() == expected, relative
                preserved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(actual, preserved)
            assert hashlib.sha256(preserved.read_bytes()).hexdigest() == expected, relative
            copies[str(preserved.relative_to(ROOT))] = expected
    execution_seal = read(V2 / 'execution_seal.json')
    for name, expected in (
        ('source.json', execution_seal['source_response_sha256']),
        ('facts.json', execution_seal['fact_response_sha256']),
    ):
        assert hashlib.sha256((V2 / name).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((REPORT / 'execute_legal_primitive_chain.py').read_bytes()).hexdigest() == execution_seal['script_sha256']
    c6 = executions['c6_native']
    assert c6['proof']['answer'] == c6['ordinary_correct_join_control'] == 'Entailment'
    assert c6['actual_fact_semantic_check']['all_actual_model_rows_supported']
    assert c6['whole_applicability_was_not_a_fact_input']
    assert executions['actual_composition_into_old_basic_deduction_module']['assessment_of_zero']['answer'] == 'Entailment'
    assert executions['f68_native']['assessment']['answer'] == 'Entailment'
    assert executions['library_restoration_reproduces_actual_predictions']
    assert all(g['correct'] and g['prediction_frozen_before_grade'] for g in grades)
    assert not c6['fallback_used'] and not executions['f68_native']['fallback_used']
    with sqlite3.connect('file:' + str(dbpath) + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        statuses = [dict(role=r[0], status=r[1], n=r[2]) for r in
                    db.execute('select role,status,count(*) from calls group by role,status')]
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    assert counts == {'executor': 1377, 'teacher': 60} and pending == 0
    stat = Path('/proc/958223/stat').read_text()
    ticks = int(stat[stat.rindex(')') + 2:].split()[19])
    assert ticks == 486445918
    clients = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if b'-m' in argv and any(a.startswith(b'experiments.rr_v2_legal_') for a in argv):
            clients.append(int(proc.name))
    assert not clients
    facts = read(V2 / 'facts.json')['physical_response']
    teacher = source1['physical_response']
    assert facts['thinking_requested'] is False and facts['finish_reason'] == 'stop'
    out = {
        'captured_utc': datetime.now(timezone.utc).isoformat(),
        'counts_total': counts, 'statuses': statuses, 'pending': pending,
        'new_charged_attempts': {'executor': 1, 'teacher': 1},
        'new_physical_dispatches': {'executor': 1, 'teacher': 1},
        'new_TRAIN_oracle_views': 2, 'oracle_views_total': len(current['oracle_views']),
        'all_pre_turn_rows_equal_backup': True,
        'all_pre_turn_rows_preserved_sha256': digest(historical),
        'current_full_ledger_logical_sha256': digest(current),
        'new_call_ids': sorted(added_calls),
        'native_results': grades,
        'ordinary_correct_policy_cache_equal': True,
        'actual_cross_module_use': 'TRAIN8 primitive proof binds the source-matched c6A input of the old basic63 module; its amount is provably zero with other inputs unknown.',
        'composition_is_not_an_extra_native_example': True,
        'f68_scope': 'local exception activation, not whole section68 applicability',
        'raw_teacher_response_unchanged_and_not_redispatched': True,
        'source_program_postcondition_adapter_has_equivalence_and_reachability_evidence': True,
        'original_v1_rejections_retained': source1['validation'],
        'execution_order_error_preserved': 'The first local fixture lacked required unresolved=[]; the teacher request was started before the failed test was handled. The prompt did not contain the fixture. Fix and source-response reuse required no teacher retry.',
        'bound_source_copies': copies,
        'recovery_protocol_sha256': hashlib.sha256((REPORT / 'legal_primitive_chain_recovery_protocol.md').read_bytes()).hexdigest(),
        'executor': {'thinking_requested': False, 'finish_reason': facts['finish_reason'],
                     'input_tokens': facts['usage']['prompt_tokens'],
                     'output_tokens': facts['usage']['completion_tokens'],
                     'elapsed_seconds': facts['elapsed_seconds']},
        'teacher': {'input_tokens': teacher['invocation']['usage']['input_tokens'],
                    'output_tokens': teacher['invocation']['usage']['output_tokens'],
                    'reasoning_tokens_subset_of_output': teacher['invocation']['usage']['reasoning_output_tokens'],
                    'elapsed_seconds': teacher['elapsed_seconds'], 'temperature_explicitly_set': False},
        'known_incremental_executor_API_cash_usd': 0,
        'GPU_cost_usd': None, 'teacher_actual_invoice_usd': None, 'total_project_cash_cost_usd': None,
        'current_research_clients': clients,
        'original_model_service': {'pid': 958223, 'start_ticks': ticks, 'unchanged': True},
        'new_sources_or_seeds': 0, 'new_full_build_started': False,
        'main_training_started': False, 'TEST_started': False, 'paper_started': False,
        'two_contributions_established': False, 'goal_complete': False,
    }
    immutable_json(REPORT / 'legal_primitive_chain_results.json', out)
    BACKUP.mkdir(parents=True, exist_ok=True)
    after = BACKUP / 'ledger.after.sqlite3'
    if not after.exists():
        with sqlite3.connect('file:' + str(dbpath) + '?mode=ro', uri=True) as src:
            with sqlite3.connect(after) as dst:
                src.backup(dst)
    assert snapshot(after) == current
    print(json.dumps({k: out[k] for k in ('counts_total', 'pending', 'new_physical_dispatches',
          'new_TRAIN_oracle_views', 'all_pre_turn_rows_equal_backup', 'two_contributions_established')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
