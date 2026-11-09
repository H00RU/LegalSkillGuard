"""Close original TRAIN18 using existing source and binding evidence only.

No model client is imported. Source generation and the old diagnostic are
preserved; an original native prediction is closed before TRAIN grading.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tarfile

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.source_obligations import compile_module, verify, bind_and_assess
from legal_skill_guard.rr.semantic_contracts import evaluate

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/rr_method_redesign_20261109'
OLD = BASE / 'redesign_source_roles_v1_20261109'
STAGE = BASE / 'legal_percentage_reuse_v1_20261110'
DB = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'


def read(p):
    return json.loads(p.read_text())


def snapshot():
    with sqlite3.connect('file:' + str(DB) + '?mode=ro', uri=True) as db:
        return {t: db.execute('select * from ' + t + ' order by 1').fetchall()
                for t in ('calls', 'meta', 'oracle_views')}


def execute():
    target = read(OLD / 'seal.json')
    key = target['sources']['train'][17]
    row = next(r for r in read(ROOT / 'data/packets/rr_v2/public_train.json')['sources'] if r['key'] == key)
    public = row['public']
    existing = read(ROOT / 'reports/method_redesign_20261109/module_pilot_analysis.json')
    prior_row = next(r for r in existing['rows'] if r['source'] == key)
    prior = prior_row['public_TRAIN18_binding_for_diagnostic_only']
    facts = public['facts']
    income = re.fullmatch(r"([A-Z][a-z]+)'s income in (\d{4}) is \$([0-9,]+)\. (.*)", facts)
    assert income, 'This replay accepts only the actual explicit original fact form'
    person, year, amount, rest = income.groups()
    unmarried = person + ' is not married.'
    applicable = re.search(r'The applicable amount according to section 68\(b\) is \$([0-9,]+)\.', rest)
    assert unmarried in rest and applicable
    assert prior == {'income': int(amount.replace(',', '')), 'threshold': int(applicable[1].replace(',', '')),
                     'married_separate': False}
    query = re.fullmatch(r'Under section 151\(d\)\(3\)\(B\), the applicable percentage for ' + person +
                         r' for ' + year + r' is equal to (\d+)\.', public['query'])
    assert query, 'Local percentage query only; no exemption/tax output substitution'
    with tarfile.open(ROOT / 'data/cache/rr_v2/sara_v2.tar.gz') as archive:
        member = 'sara_v2/statutes/prolog/section151.pl'
        blob = archive.extractfile(member).read()
    reference = blob.decode()
    anchor = 's151_d_3_B(Ap,Taxp,Agi,Taxy,Aa) :-\n    gross_income(Taxp,Taxy,Agi),'
    assert anchor in reference
    raw = read(OLD / 'teacher_sara151_percentage.json')
    adapted = read(OLD / 'teacher_sara151_percentage.processed.json')
    assert adapted['original_sha256'] == hashlib.sha256((OLD / 'teacher_sara151_percentage.json').read_bytes()).hexdigest()
    module = compile_module(adapted['module'], public['rules'])
    checks = verify(module)
    assert checks['all_supplied_obligations_verified']
    bindings = {'adjusted_gross_income': prior['income'],
                'section68_applicable_amount': prior['threshold'],
                'married_filing_separately': prior['married_separate']}
    assert set(bindings) == set(module.signature)
    before = snapshot()
    seal = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'raw_teacher_sha256': hashlib.sha256((OLD / 'teacher_sara151_percentage.json').read_bytes()).hexdigest(),
            'processed_teacher_sha256': hashlib.sha256((OLD / 'teacher_sara151_percentage.processed.json').read_bytes()).hexdigest(),
            'existing_binding_evidence_sha256': hashlib.sha256((ROOT / 'reports/method_redesign_20261109/module_pilot_analysis.json').read_bytes()).hexdigest(),
            'source': key, 'public': public, 'source_role_module': adapted['module'],
            'bindings': bindings, 'requested_percentage': int(query[1]),
            'source_reference_member_only': member, 'source_reference_sha256': hashlib.sha256(blob).hexdigest(),
            'official_case_or_TEST_label_read': False,
            'benchmark_income_convention': 'The official source-only151(d)(3)(B) implementation supplies Agi from gross_income; this is a SARA input convention, not a general equivalence of income measures.',
            'unmarried_excludes_married_and_separate_without_closed_world_assumption': True,
            'explicit_external_amount_preserved_not_recomputed': True,
            'ledger_before_sha256': digest(before), 'model_calls_added': 0,
            'labels_opened': False, 'goal_complete': False}
    immutable_json(STAGE / 'execution_seal.json', seal)
    # Actually save and restore the source-generated module before application.
    immutable_json(STAGE / 'frozen_source_cache.json', {'module': adapted['module']})
    restored = compile_module(read(STAGE / 'frozen_source_cache.json')['module'], public['rules'])
    native = bind_and_assess(restored, bindings, int(query[1]))
    value = evaluate(restored.raw['expression'], restored.signature, bindings)
    assert native == bind_and_assess(module, bindings, int(query[1]))
    assert value == prior_row['teacher_actual_case_value']
    out = {'closed_utc': datetime.now(timezone.utc).isoformat(), 'source': key,
           'original_TRAIN_ordinal': 18, 'query': public['query'], 'bindings': bindings,
           'actual_percentage': value, 'native_assessment': native, 'source_checks': checks,
           'binding_provenance': [income[0][:income[0].index('. ') + 1], unmarried, applicable[0]],
           'shared_deterministic_binding_not_new_model_fact_extraction': True,
           'same_program_cache_control': native,
           'control_scope': 'Execution parity only; not an independent acquisition, learning or cost comparison.',
           'saved_library_restoration_reproduces_prediction': True,
           'fallback_used': False, 'new_model_calls': 0, 'labels_opened': False,
           'independent_method_contribution_established': False, 'goal_complete': False}
    immutable_json(STAGE / 'execution_closed_before_grading.json', out)
    assert snapshot() == before
    print(json.dumps({'prediction': native['answer'], 'actual_percentage': value, 'model_calls_added': 0}))


def grade():
    seal = read(STAGE / 'execution_seal.json')
    result = read(STAGE / 'execution_closed_before_grading.json')
    if (STAGE / 'TRAIN_grade.json').exists():
        print('Existing frozen TRAIN grade')
        return
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == seal['script_sha256']
    # Reuse the original fixed-source policy byte-for-byte; no new policy/meta.
    with sqlite3.connect('file:' + str(DB) + '?mode=ro', uri=True) as db:
        policy = json.loads(db.execute("select value from meta where key='method_runtime_policy:redesign_source_roles_v1_20261109'").fetchone()[0])
    ledger = MethodLedger(DB, run_id=policy['run_id'], binding=policy['execution_binding'],
                          sources=policy['sources'], authorization_hash=policy['authorization_hash'], question=policy['question'])
    view = {'kind': 'SARA_v2_Binary', 'edit': None}
    vh = digest(view)
    with ledger.transaction() as db:
        prior = db.execute('select 1 from oracle_views where source=? and view_hash=?', (seal['source'], vh)).fetchone()
    if not prior:
        ledger.reserve_oracle(seal['source'], vh)
    gold = read(ROOT / 'data/packets/rr_v2/grading_only/train.json')['sources'][seal['source']]['answer']
    out = {'source': seal['source'], 'original_TRAIN_ordinal': 18, 'view': view, 'view_hash': vh,
           'prediction': result['native_assessment']['answer'], 'gold': gold,
           'correct': result['native_assessment']['answer'] == gold,
           'prediction_frozen_before_grade': True, 'compatible_prior_view_reused': bool(prior),
           'new_model_calls': 0, 'TEST_started': False, 'goal_complete': False}
    immutable_json(STAGE / 'TRAIN_grade.json', out)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['execute', 'grade'])
    action = parser.parse_args().action
    execute() if action == 'execute' else grade()
