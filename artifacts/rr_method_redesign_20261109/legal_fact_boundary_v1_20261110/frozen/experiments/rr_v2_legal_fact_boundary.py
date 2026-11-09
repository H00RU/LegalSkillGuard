"""Bounded fact-search diagnostic using existing TRAIN and SymBa's real validator.

This is an adaptation diagnostic, not a reproduction of SymBa or a new method.
No rules, target labels or foreign benchmark examples are supplied to the reader.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import sys
import types

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_fact_boundary_v1_20261110'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109' / RUN
OLD = ROOT / 'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109/seal.json'
REFERENCE = Path('/tmp/lsg_symba_reference_20261110')
UPSTREAM = 'https://github.com/lbox-kr/symba/tree/df0e291152093e1d8a56a545b9310bd502f8dcd0'


def read(p):
    return json.loads(p.read_text())


def load_validator():
    # Package shells bypass only __init__ imports of the unused LLM/framework
    # wrapper; actual parser/unifier/validator source files remain unmodified.
    for name, directory in [('pysolver', REFERENCE/'pysolver')]:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(directory)]
        sys.modules[name] = pkg
    path = REFERENCE/'hiereason/symba/validate_statements.py'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == 'c59cfaab6f1291bbb536b2424492fa2853969ddf9936c21716554185fe47b859'
    spec = importlib.util.spec_from_file_location('symba_reference_validator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from pysolver.utils import parse_line
    return module.validate_statement_list, parse_line


def parse_search(text, facts):
    lines = [line.strip().replace('`', '') for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return {'status': 'rejected_empty', 'selections': []}
    if all('No applicable fact' in line or 'not directly given' in line for line in lines):
        return {'status': 'no_direct_fact', 'selections': []}
    selections = [line for line in lines if 'No applicable fact' not in line and 'not directly given' not in line]
    return {'status': 'selected', 'selections': selections,
            'all_verbatim': all(line in facts for line in selections),
            'verbatim_is_NOT_semantic_validation': True}


def offline():
    validator, parse = load_validator()
    goal = parse('qualifying_child(alice,bob,2019).').head
    # A deliberately invalid NL-to-fact connection, not a real LLM response.
    wrong = {'statement': 'qualifying_child(alice,bob,2019).',
             'description': 'Bob bears a relationship to Alice pursuant to section 152(c)(2) for the years 2015 to 2020.', 'is_fact': True}
    accepted, errors = validator([deepcopy(wrong)], goal, None)
    assert len(accepted) == 1 and errors == ['Success']
    wrong_head = deepcopy(wrong); wrong_head['statement'] = 'qualifying_child(bob,alice,2019).'
    rejected, reject_errors = validator([wrong_head], goal, None)
    assert not rejected and 'statement head should start' in reject_errors[0]
    assert parse_search('No applicable fact', 'anything')['status'] == 'no_direct_fact'
    assert parse_search('No applicable fact (not directly given)', 'anything')['status'] == 'no_direct_fact'
    assert parse_search('Alice has a son, Bob.', 'Alice has a son, Bob.')['all_verbatim']
    assert not parse_search('Bob qualifies.', 'Alice has a son, Bob.')['all_verbatim']
    return {'software_assertions': 6, 'upstream': UPSTREAM, 'clingo_version': '5.6.2',
            'actual_official_validator_executed': True,
            'synthetic_unsupported_translation_accepted': bool(accepted),
            'different_role_head_rejected': not rejected,
            'validator_is_not_NL_fidelity_certificate': True,
            'synthetic_counterexample_is_NOT_model_failure': True,
            'package_initializers_bypassed_only': True, 'new_model_calls': 0}


def prepare():
    old = read(OLD)
    packet = {r['key']: r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    cases = {str(i): packet[old['sources']['train'][i-1]] for i in (13, 81)}
    examples = []
    for ordinal, goal, answer in [(8, 'itemized_deduction(bob,2017)', 'Bob is allowed an itemized deduction of $4324.'),
                                 (8, 'qualifying_child(alice,bob,2017)', 'No applicable fact'),
                                 (18, 'qualifying_child(alice,bob,2015)', 'No applicable fact')]:
        f = packet[old['sources']['train'][ordinal-1]]['public']['facts']
        assert answer == 'No applicable fact' or answer in f
        examples.append({'existing_TRAIN_ordinal': ordinal, 'facts': f, 'goal': goal, 'answer': answer})
    system = ('Perform only fact search, as the first stage of symbolic backward chaining. '
              'Select verbatim case sentences that directly give the supplied positive goal. '
              'Return each selected sentence on its own line, without bullets or explanation. '
              'If the goal is not directly given, return exactly No applicable fact. '
              'Do not infer a legal qualification from a family relationship, residence, marriage or a statutory subcondition. '
              'Fact search and rule search are separate: an inferred goal must be left for rule search. '
              'The relation qualifying_child(claimant,subject,year) means the subject is explicitly given '
              'as the claimant\'s qualifying child/dependent under section152(c)(1) for that year. '
              'A relationship under section152(c)(2) alone does not give this composite relation. '
              'Use the existing TRAIN examples, including the negative examples, to distinguish a direct premise from a possible inference.')
    messages = {}
    for n, case in cases.items():
        y = '2019' if n == '13' else '2015'
        material = {'examples': examples, 'facts': case['public']['facts'], 'goal': f'qualifying_child(alice,bob,{y})'}
        messages[n] = [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)}]
    protocol = ROOT/'reports/method_redesign_20261109/legal_fact_boundary_protocol.md'
    files = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_fact_boundary.py', 'legal_skill_guard/rr/method_client.py',
        'legal_skill_guard/rr/method_ledger.py', 'legal_skill_guard/rr/client.py')}
    evidence = offline()
    seal = {'run_id': RUN, 'config': old['config'], 'sources': old['sources'],
            'binding': {'code_hash': digest(files), 'config_hash': digest(old['config'])},
            'files': files, 'cases': cases, 'messages': messages,
            'protocol_sha256': hashlib.sha256(protocol.read_bytes()).hexdigest(),
            'response_schema': None, 'thinking': False, 'query_labels_read': False,
            'official_source_manifest': read(REFERENCE/'source_manifest.json'),
            'offline_evidence': evidence, 'goal_complete': False,
            'decision': 'If13 has no direct fact and81 retains its direct premise, do not construct a special gate or claim an actual failure.'}
    immutable_json(STAGE/'offline.json', evidence)
    immutable_json(STAGE/'seal.json', seal)
    return seal


def generate(s, ordinal):
    path = STAGE/f'fact_search_{ordinal}.json'
    if path.exists():
        print(json.dumps({'existing_result': str(path)})); return
    l = MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
                     binding=s['binding'], sources=s['sources'], authorization_hash=s['protocol_sha256'],
                     question='Do ordinary negative-example fact search and the original SymBa validator already handle the proposed TRAIN13-versus81 evidence boundary? No new mechanism, no task grading, no new data.')
    e = MethodExecutor(l, STAGE, s['config']['executor']); e.readiness()
    w = e.generate(RUN+':facts'+ordinal, source=s['cases'][ordinal]['key'], purpose='method_primitive_observation',
                   messages=s['messages'][ordinal], thinking=False, schema=None)
    result = {'physical_response': w, 'search_parse': parse_search(w['content'], s['cases'][ordinal]['public']['facts']),
              'native_prediction_or_grade': None, 'ordinary_prompt_not_new_method': True}
    immutable_json(path, result)
    print(json.dumps({'ordinal': ordinal, 'content': w['content'], 'search_parse': result['search_parse'],
                      'usage': w['usage'], 'elapsed_seconds': w['elapsed_seconds'], 'finish_reason': w['finish_reason']}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['offline', 'prepare', '13', '81'])
    action = p.parse_args().action
    if action == 'offline': print(json.dumps(offline(), ensure_ascii=False, indent=2))
    else:
        seal = prepare()
        if action == 'prepare': print(json.dumps({'prepared': True, 'new_calls': 0, 'offline': seal['offline_evidence']}))
        else: generate(seal, action)
