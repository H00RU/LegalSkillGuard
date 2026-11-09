"""Existing fixed TRAIN pool numeric-binding frontend opportunity check."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.asset_values import ASSET_VALUE_SCHEMA, decode_asset_values
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor, MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj

ROOT = Path(__file__).resolve().parents[1]
RUN = 'numeric_binding_frontend_v1_20261109'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109' / RUN
PROTOCOL = ROOT / 'reports/method_redesign_20261109/numeric_binding_protocol.md'
REVIEW_SCHEMA = obj({'cases': {'type': 'array', 'items': obj({
    'case_id': {'type': 'string'}, 'independent_bindings': ASSET_VALUE_SCHEMA,
    'relation_and_completeness_review': {'type': 'string'},
    'unresolved': {'type': 'array', 'items': {'type': 'string'}}})}})


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    base = read(ROOT / 'artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109/seal.json')
    public = {s['key']: s for s in read(ROOT / 'data/packets/rr_v2/public_train.json')['sources']}
    cases = []
    for row in base['source_pool']:
        if row['dataset'] != 'OpenExempt' or row['fold'] != 'induction':
            continue
        view = public[row['source']]['public']['views']['EC']
        assert view.count('\n\nFacts:\n') == 1
        facts = view.split('\n\nFacts:\n', 1)[1].split('\n\nOutput contract:', 1)[0]
        cases.append({**row, 'case_id': 'TRAIN' + str(row['ordinal']), 'facts': facts,
                      'public_EC_input_sha256': hashlib.sha256(view.encode()).hexdigest()})
    assert [c['ordinal'] for c in cases] == [1, 6]
    paths = ['experiments/rr_v2_numeric_binding_pilot.py', 'legal_skill_guard/rr/asset_values.py',
        'legal_skill_guard/rr/semantic_frames.py', 'legal_skill_guard/rr/payment_scope.py',
        'legal_skill_guard/rr/source_discrimination.py', 'legal_skill_guard/rr/method_client.py',
        'legal_skill_guard/rr/client.py', 'legal_skill_guard/rr/method_ledger.py', 'legal_skill_guard/rr/ledger.py',
        'legal_skill_guard/rr/checkpoint.py', 'legal_skill_guard/rr/coverage.py',
        'legal_skill_guard/inference/codex_cli_client.py', 'tests/test_rr_asset_values.py', str(PROTOCOL.relative_to(ROOT))]
    files = {p: sha(ROOT / p) for p in paths}
    seal = {'run_id': RUN, 'cases': cases, 'config': base['config'], 'sources': base['sources'],
            'files': files, 'binding': {'code_hash': digest(files), 'config_hash': digest(base['config'])},
            'protocol_sha256': sha(PROTOCOL), 'original_pool_seal_sha256': sha(ROOT / 'artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109/seal.json'),
            'native_labels_read': False, 'TEST_authorized': False, 'goal_complete': False}
    immutable_json(STAGE / 'seal.json', seal)
    return seal


def clients(seal):
    for p, h in seal['files'].items():
        assert sha(ROOT / p) == h, p
    ledger = MethodLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        binding=seal['binding'], sources=seal['sources'], authorization_hash=seal['protocol_sha256'],
        question='Do the existing two OpenExempt induction mothers contain a real asset-value reading failure after a compact shared frontend, or does direct extraction/ordinary local binding already solve the opportunity? No new source or native answer.')
    return MethodExecutor(ledger, STAGE, seal['config']['executor']), MethodTeacher(ledger, STAGE, seal['config']['teacher'])


def extract(seal, ordinal):
    case = next(c for c in seal['cases'] if c['ordinal'] == ordinal)
    path = STAGE / ('executor_' + case['case_id'] + '.json')
    if path.exists():
        print(json.dumps({'existing': str(path)})); return
    e, _ = clients(seal); e.readiness()
    messages = [{'role': 'system', 'content': 'Extract every explicitly priced asset and its stated gross value. Return an exact short asset noun phrase as asset_span, the complete dollar literal as amount_span, and an exact supporting clause or sentence as evidence_span. Preserve each asset/value association. Do not copy another asset price, calculate ownership shares, apply exemption law, or infer an unstated value. No final EC/EV answer. Return only the schema object.'},
                {'role': 'user', 'content': json.dumps({'facts': case['facts']}, ensure_ascii=False)}]
    wire = e.generate(RUN + ':direct:' + case['case_id'], source=case['source'], purpose='method_train_synthesis',
        messages=messages, schema=ASSET_VALUE_SCHEMA, thinking=False)
    try:
        validation = {'status': 'decoded', 'decoded': decode_asset_values(json.loads(wire['content']), case['facts'])}
    except Exception as exc:
        validation = {'status': 'rejected', 'error_type': type(exc).__name__, 'error': str(exc)}
    immutable_json(path, {'case_id': case['case_id'], 'physical_response': wire,
        'validation': validation, 'captured_utc': datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'case_id': case['case_id'], 'validation': validation}, ensure_ascii=False), flush=True)


def review(seal):
    path = STAGE / 'teacher.json'
    if path.exists():
        print(json.dumps({'existing': str(path)})); return
    outputs = {str(p.relative_to(STAGE)): sha(p) for c in seal['cases']
               for p in [STAGE / ('executor_' + c['case_id'] + '.json')]}
    immutable_json(STAGE / 'execution_closed_before_teacher.json', {'executor_files': outputs,
        'seal_sha256': sha(STAGE / 'seal.json')})
    _, t = clients(seal)
    wire = t.summarize(RUN + ':independent_review', source_ids=[c['source'] for c in seal['cases']],
        system_prompt='Independently list all explicitly priced assets and their stated gross values in each supplied TRAIN Facts passage. Return exact short source asset spans, complete dollar spans, and exact supporting clauses/sentences. Review relation scope and completeness. Do not compute ownership shares, exemptions or final EC/EV labels. No executor response is supplied; flag any actual ambiguity.',
        user_prompt=json.dumps({'cases': [{'case_id': c['case_id'], 'facts': c['facts']} for c in seal['cases']]}, ensure_ascii=False),
        output_schema=REVIEW_SCHEMA)
    validation = []
    for row in wire['value']['cases']:
        case = next(c for c in seal['cases'] if c['case_id'] == row['case_id'])
        try:
            validation.append({'case_id': row['case_id'], 'status': 'decoded',
                               'decoded': decode_asset_values(row['independent_bindings'], case['facts'])})
        except Exception as exc:
            validation.append({'case_id': row['case_id'], 'status': 'rejected', 'error': str(exc)})
    immutable_json(path, {'physical_response': wire, 'validation': validation,
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'teacher_did_not_receive_executor': True})
    print(json.dumps(wire['value'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'extract', 'review'])
    parser.add_argument('--ordinal', type=int)
    args = parser.parse_args(); seal = prepare()
    if args.action == 'extract':
        if args.ordinal not in (1, 6):
            parser.error('Use an existing induction mother ordinal1 or6')
        extract(seal, args.ordinal)
    elif args.action == 'review':
        review(seal)
    else:
        print(json.dumps({'prepared': True, 'cases': [c['case_id'] for c in seal['cases']], 'new_calls': 0}))
