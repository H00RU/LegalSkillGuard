"""Independent ordinary-code rule acquisition conditional on the shared API.

The source compiler sees no existing rule bodies, cases, queries or answers.
Both ordinary Python and the common supported-model solver are available.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import resource

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import PROGRAM, run, validate
from legal_skill_guard.rr.method_client import MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rr_method_redesign_20261109'
RUN = 'legal_independent_cache_v1_20261110'
STAGE = BASE / RUN
REPORT = ROOT / 'reports/method_redesign_20261109'
INPUTS = {'case_subject_year', 'qualifying_child', 'qualifying_relative', 'dependent',
          'deduction_under_section_151_allowable', 'taxable_year_begins_in_151_d_5_period'}
SCHEMA = {'type': 'object', 'properties': {'code': {'type': 'string'},
          'unresolved': {'type': 'array', 'items': {'type': 'string'}}},
          'required': ['code', 'unresolved'], 'additionalProperties': False}
import builtins
BUILTINS = {n: getattr(builtins, n) for n in ('set', 'frozenset', 'list', 'dict', 'tuple', 'str', 'int',
            'bool', 'len', 'sorted', 'enumerate', 'zip', 'any', 'all', 'min', 'max', 'sum', 'isinstance')}
METHODS = {'get', 'items', 'keys', 'values', 'add', 'discard', 'append', 'extend', 'update',
           'setdefault', 'copy', 'union', 'intersection', 'difference', 'replace', 'startswith', 'endswith',
           'pop', 'remove', 'clear', 'count', 'index', 'issubset', 'issuperset', 'isdisjoint',
           'intersection_update', 'difference_update', 'symmetric_difference', 'symmetric_difference_update',
           'lower', 'upper', 'strip', 'split', 'rsplit', 'join', 'isdigit', 'sort', 'reverse', 'fromkeys'}


def read(path):
    return json.loads(path.read_text())


def check_code(code):
    tree = ast.parse(code)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('Exactly one ordinary function law_cache is required')
    fn = tree.body[0]
    if fn.name != 'law_cache' or [a.arg for a in fn.args.args] != ['facts', 'query']:
        raise ValueError('Expected law_cache(facts, query)')
    if fn.decorator_list or fn.returns or fn.args.defaults or fn.args.kw_defaults or fn.args.vararg or fn.args.kwarg:
        raise ValueError('No evaluated decorators, annotations or defaults')
    if fn.args.posonlyargs or fn.args.kwonlyargs or any(a.annotation for a in fn.args.args):
        raise ValueError('Only the two ordinary positional arguments are supported')
    blocked = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.AsyncFunctionDef, ast.Lambda, ast.Global,
               ast.Nonlocal, ast.With, ast.AsyncWith, ast.Try, ast.Raise, ast.Delete, ast.Await, ast.Yield, ast.YieldFrom)
    for node in ast.walk(tree):
        if isinstance(node, blocked) or (isinstance(node, ast.FunctionDef) and node is not fn):
            raise ValueError('Unsupported code statement: ' + type(node).__name__)
        if isinstance(node, ast.Name) and node.id.startswith('__'):
            raise ValueError('Private environment access is unsupported')
        if isinstance(node, ast.Attribute) and node.attr not in METHODS:
            raise ValueError('Unsupported collection method: ' + node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in {*BUILTINS, 'solve'}:
            raise ValueError('Unsupported function call: ' + node.func.id)
        if isinstance(node, ast.Call) and not isinstance(node.func, (ast.Name, ast.Attribute)):
            raise ValueError('Dynamic call target is unsupported')
    return tree


def _worker(connection, code, facts, query, sources):
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        def solve(program, given_facts, given_query):
            validate(program, sources)
            return run(program, {'facts': given_facts, 'query': given_query, 'unresolved': []})
        namespace = {'__builtins__': BUILTINS, 'solve': solve}
        exec(compile(check_code(code), '<independent-source-cache>', 'exec'), namespace)
        value = namespace['law_cache'](facts, query)
        connection.send_bytes(json.dumps({'value': value}, ensure_ascii=False).encode())
    except BaseException as exc:
        connection.send_bytes(json.dumps({'error_type': type(exc).__name__, 'error': str(exc)}).encode())
    finally:
        connection.close()


def execute_code(code, facts, query, sources):
    check_code(code)
    parent, child = multiprocessing.get_context('fork').Pipe(duplex=False)
    process = multiprocessing.get_context('fork').Process(target=_worker, args=(child, code, facts, query, sources))
    process.start(); child.close()
    try:
        if not parent.poll(8):
            raise ValueError('Independent cache exceeded bounded execution time')
        result = json.loads(parent.recv_bytes())
    finally:
        if process.is_alive(): process.terminate()
        process.join(); parent.close()
    if 'error' in result:
        raise ValueError(result['error_type'] + ': ' + result['error'])
    value = result['value']
    if not isinstance(value, dict) or value.get('answer') not in ('Entailment', 'Contradiction', None):
        raise ValueError('The cache must return a dict with an explicit answer field')
    if 'answer' not in value:
        raise ValueError('Missing answer field is not an unknown prediction')
    return value


def fixture_cases():
    def f(p, args, positive=True):
        return {'atom': {'predicate': p, 'arguments': args, 'positive': positive}, 'quote': 'software fixture'}
    def q(p, args):
        return {'predicate': p, 'arguments': args, 'positive': True}
    neutral = [f('case_subject_year', [p, '2015']) for p in ('P', 'Q', 'R')]
    child = f('qualifying_child', ['P', 'Q', '2015'])
    return [
        ('absence_is_not_false', neutral, q('section_151_c_applies', ['P', 'Q', '2015']), None),
        ('child_source_path', neutral + [child], q('section_151_c_applies', ['P', 'Q', '2015']), 'Entailment'),
        ('role_reversal_not_inferred', neutral + [child], q('section_151_c_applies', ['Q', 'P', '2015']), None),
        ('relative_source_path', neutral + [f('qualifying_relative', ['P', 'Q', '2015'])],
         q('section_151_c_applies', ['P', 'Q', '2015']), 'Entailment'),
        ('dependent_taxpayer_exception', neutral + [f('dependent', ['P', 'Q', '2015']),
         f('qualifying_child', ['Q', 'R', '2015'])], q('section_151_c_applies', ['Q', 'R', '2015']), [None, 'Contradiction']),
        ('same_key_zero_overrides_general', neutral + [f('deduction_under_section_151_allowable', ['P', 'Q', '2015'])],
         q('exemption_amount', ['Q', '2015', '$2000']), 'Contradiction'),
        ('year_mismatch_not_joined', neutral + [child], q('section_151_c_applies', ['P', 'Q', '2016']), None),
        ('one_negative_is_not_universal', neutral + [f('deduction_under_section_151_allowable', ['P', 'Q', '2015'], False)],
         q('section_63_c_5_applies', [None, 'Q', '2015']), None),
    ]


def check_fixtures(code, sources):
    rows = []
    for name, facts, query, expected in fixture_cases():
        try:
            result = execute_code(code, facts, query, sources)
            permitted = expected if isinstance(expected, list) else [expected]
            rows.append({'name': name, 'allowed_answers': permitted, 'actual': result['answer'],
                         'passed': result['answer'] in permitted, 'execution': result})
        except Exception as exc:
            rows.append({'name': name, 'passed': False, 'error_type': type(exc).__name__, 'error': str(exc)})
    return {'rows': rows, 'all_passed': all(r['passed'] for r in rows),
            'not_native_cases_or_new_training_examples': True}


def prepare():
    old = read(BASE / 'legal_relations_exceptions_native_v1_20261109/seal.json')
    library = read(BASE / 'legal_library_runtime_v1_20261109/frozen_library.json')['program']
    public = {r['key']: r for r in read(ROOT / 'data/packets/rr_v2/public_train.json')['sources']}
    source63 = public[old['sources']['train'][86]]['public']['rules']
    start = source63.index('    (5)')
    end = source63.index('    (6)', start)
    policies = old['policies'] + [{'section': '63(c)(5)', 'rules': source63[start:end]}]
    inputs = [p for p in library['predicates'] if p['name'] in INPUTS]
    outputs = [{k: p[k] for k in ('name', 'roles', 'functional')} for p in library['predicates'] if p['name'] not in INPUTS]
    system = (
        'Compile an ordinary reusable Python policy cache from the source texts. No cases, native queries, answers, existing rule bodies or priority edges are supplied. '
        'Return one undecorated function law_cache(facts, query), and a list of unresolved source dependencies. '
        'The fixed learned interface is shared with the comparison method; this experiment does not test discovering that interface. '
        'facts is a list of {atom:{predicate:str,arguments:list[str],positive:bool},quote:str}; query has predicate,arguments and positive, with null arguments existentially projected. '
        'Return a dict containing answer exactly Entailment, Contradiction, or null, plus your diagnostic/proof fields. '
        'Use the source to derive joins, effects and exceptions; no case-specific people, years or per-query answers. Source-stated policy constants are allowed. '
        'Missing evidence is unknown, not an explicit negative. A projected participant is not limited to enumerated case people, so one negative witness cannot refute an unbounded existential. '
        'Known source exceptions may suppress defaults only for matching participants/years. Do not conflate a dependent subject with the taxpayer who can claim that person. '
        'The exemption output here is the local d1/d2/d5 module; list unsupported151(b),151(d)(3),152(c)/(d) details rather than inventing them. '
        'All ordinary collection/Boolean/integer Python code is allowed. No imports, classes, lambdas, nested functions, decorators, annotations, exceptions, files, network or dynamic calls. '
        'Allowed builtins are set,frozenset,list,dict,tuple,str,int,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance. '
        'An optional common helper solve(program,facts,query) validates and runs the shared supported-model solver; its PROGRAM schema is supplied so you need not reimplement joins, conflict isolation or priority execution. '
        'You may choose ordinary code, that helper, or both. When using it, construct your own rules and priorities from the supplied source, with actual source quotes and the supplied predicate declarations. '
        'No code fences. The code field must contain only the one ordinary function.')
    declarations = [{**p, 'meaning': ('Applicability of section63(c)(5) for these participant/year roles.'
                     if p['name'] == 'section_63_c_5_applies' else
                     'The local exemption amount within151(d)(1),(2),(5); other dependencies remain explicit.'
                     if p['name'] == 'exemption_amount' else p['meaning'])} for p in library['predicates']]
    material = {'policies': policies, 'shared_input_API': inputs, 'requested_output_API': outputs,
                'optional_common_solver': {'name': 'solve(program,facts,query)', 'program_schema': PROGRAM,
                                           'predicate_declarations': declarations}}
    protocol = REPORT / 'legal_independent_cache_protocol.md'
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_independent_cache.py', 'legal_skill_guard/rr/legal_predicate_skills.py',
        'legal_skill_guard/rr/method_client.py', 'legal_skill_guard/rr/method_ledger.py', 'legal_skill_guard/rr/client.py')}
    assert strict_output_schema_issues(SCHEMA) == []
    seal = {'run_id': RUN, 'files': files, 'binding': {'code_hash': digest(files), 'config_hash': digest(old['config'])},
            'config': old['config'], 'sources': old['sources'], 'policies': policies, 'schema': SCHEMA,
            'source_ids': [old['sources']['train'][i-1] for i in (81, 86, 87)],
            'teacher_messages': {'system': system, 'user': json.dumps(material, ensure_ascii=False)},
            'protocol_sha256': hashlib.sha256(protocol.read_bytes()).hexdigest(),
            'shared_API_given_not_independently_rediscovered': True,
            'source_rule_bodies_or_cases_or_labels_in_prompt': False,
            'source63_excerpt_is_extra_available_information': True, 'goal_complete': False}
    immutable_json(STAGE / 'seal.json', seal)
    return seal


def ledger(seal):
    return MethodLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        binding=seal['binding'], sources=seal['sources'], authorization_hash=seal['protocol_sha256'],
        question='Independent ordinary-code rule acquisition from source with the shared learned API and optional common solver; no existing rule bodies. Conditional rule-acquisition control, not API-learning or a new method contribution.')


def generate(seal):
    path = STAGE / 'source.json'
    if path.exists():
        print('Existing source response; no redispatch')
        return
    client = MethodTeacher(ledger(seal), STAGE, seal['config']['teacher'])
    wire = client.summarize(RUN + ':source', source_ids=seal['source_ids'],
                           system_prompt=seal['teacher_messages']['system'],
                           user_prompt=seal['teacher_messages']['user'], output_schema=SCHEMA)
    immutable_json(path, {'physical_response': wire, 'value': wire['value']})
    print(json.dumps({'source_captured': True, 'elapsed_seconds': wire['elapsed_seconds']}))


def close(seal):
    raw = read(STAGE / 'source.json'); code = raw['value']['code']
    sources = [p['rules'] for p in seal['policies']]
    checks = check_fixtures(code, sources)
    cases = read(BASE / 'legal_grounded_replay_v1_20261109/shared_grounded_cases.json')['cases']
    native = []
    for case in cases:
        try:
            out = execute_code(code, case['facts'], case['query'], sources)
            native.append({'ordinal': case['ordinal'], 'query': case['query'], 'output': out, 'executed': True})
        except Exception as exc:
            native.append({'ordinal': case['ordinal'], 'executed': False, 'error_type': type(exc).__name__, 'error': str(exc)})
    immutable_json(STAGE / 'execution_closed_before_grading.json', {
        'closed_utc': datetime.now(timezone.utc).isoformat(), 'source_response_sha256': hashlib.sha256((STAGE/'source.json').read_bytes()).hexdigest(),
        'software_source_checks': checks, 'native_results': native,
        'same_original_four_cases_already_observed_not_a_new_blind_evaluation': True,
        'new_labels_opened': False, 'goal_complete': False})
    print(json.dumps({'source_checks_passed': checks['all_passed'],
          'native_answers': [{'ordinal': r['ordinal'], 'answer': r.get('output', {}).get('answer'), 'executed': r['executed']} for r in native]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'generate', 'close'])
    action = parser.parse_args().action; seal = prepare()
    if action == 'prepare': print('Source-only ordinary-code control prepared; no dispatch')
    elif action == 'generate': generate(seal)
    else: close(seal)
