"""Source-only targeted review of the independent ordinary cache's own literals."""
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from experiments.rr_v2_legal_independent_cache import SCHEMA, ROOT, BASE, REPORT, STAGE as FIRST, read, check_code, check_fixtures, execute_code
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import RULE, PRIORITY
from legal_skill_guard.rr.method_client import MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger

RUN = 'legal_independent_cache_review_v1_20261110'
STAGE = BASE / RUN
PATCH_SCHEMA = {'type': 'object', 'properties': {
    'rule_updates': {'type': 'array', 'items': RULE},
    'new_rules': {'type': 'array', 'items': RULE},
    'priorities': {'type': 'array', 'items': PRIORITY}},
    'required': ['rule_updates', 'new_rules', 'priorities'], 'additionalProperties': False}


def extract_literals(code):
    tree = check_code(code); out = {}
    for node in tree.body[0].body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('predicates', 'rules', 'priorities', 'unresolved'):
                if name in out: raise ValueError('Repeated literal declaration')
                out[name] = ast.literal_eval(node.value)
    if set(out) != {'predicates', 'rules', 'priorities', 'unresolved'}:
        raise ValueError('The actual first cache must have four explicit literal declarations')
    return tree, out


def apply_review(code, patch):
    tree, program = extract_literals(code)
    updated = deepcopy(program)
    ids = [r['id'] for r in program['rules']]
    replacements = {r['id']: r for r in patch['rule_updates']}
    added_ids = [r['id'] for r in patch['new_rules']]
    if len(replacements) != len(patch['rule_updates']) or not set(replacements) <= set(ids):
        raise ValueError('An update must identify one existing rule')
    if len(set(added_ids)) != len(added_ids) or set(added_ids) & set(ids):
        raise ValueError('New rule identities must be new and unique')
    updated['rules'] = [deepcopy(replacements.get(r['id'], r)) for r in program['rules']] + deepcopy(patch['new_rules'])
    updated['priorities'] = deepcopy(patch['priorities'])
    rewritten = deepcopy(tree)
    for node in rewritten.body[0].body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('rules', 'priorities'):
                node.value = ast.parse(repr(updated[name]), mode='eval').body
    code2 = ast.unparse(ast.fix_missing_locations(rewritten)) + '\n'
    _, actual = extract_literals(code2)
    assert actual == updated and actual['predicates'] == program['predicates'] and actual['unresolved'] == program['unresolved']
    def skeleton(t):
        t = deepcopy(t)
        for n in t.body[0].body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('rules', 'priorities'):
                n.value = ast.Constant('<declared source review>')
        return ast.dump(t, include_attributes=False)
    assert skeleton(tree) == skeleton(ast.parse(code2))
    return code2, {'only_teacher_supplied_rule_and_priority_literals_changed': True,
                   'predicate_signatures_unresolved_and_execution_function_unchanged': True,
                   'updated_ids': list(replacements), 'added_ids': added_ids,
                   'no_manual_rule_or_answer_changes': True}


def prepare():
    old = read(FIRST / 'seal.json'); raw = read(FIRST / 'source.json')
    diagnosis = read(REPORT / 'legal_independent_cache_first_failure.json')
    assert diagnosis['literal_program_extracted_without_execution'] and not diagnosis['validation_bypassed']
    assert raw['value']['code'] and extract_literals(raw['value']['code'])[1] == diagnosis['raw_program']
    messages = {
        'system': ('Review an independently generated policy cache against its source texts. No original candidate rules, cases, queries or benchmark labels are supplied. '
            'Return a targeted source repair, not a new full function: rule_updates replaces complete existing rules by id; new_rules appends genuinely missing source effects; priorities replaces the priority list. '
            'All guard_quote, quote and priority quote fields must be NONEMPTY EXACT VERBATIM substrings of one supplied source. Preserve capitalization, punctuation and whitespace; short exact substrings are preferable to joined or paraphrased paragraphs. '
            'Do not silently substitute an empty condition quote. Quotes are provenance, not evidence that the rules are faithful. '
            'Check the executable effect of152(b)(1), not just its applicability marker: a taxpayer who is a dependent has no dependents of their own for the matching year, so corresponding dependent and deduction derivations cannot stay active. '
            'Use the common signed, source-priority supported solver. Known explicit exceptions can defeat same-scope derivations; do not infer negatives from absent facts, globally close the people universe, reverse participants or mix years. '
            'Preserve the correct local151(d)(1)/(2)/(5) scope, and63(c)(5) applicability only. Unsupported full-policy dependencies remain unresolved. '
            'Do not emit source-unjustified changes or per-case answers. Every executable rule and edge must follow the supplied law.'),
        'user': json.dumps({'policies': old['policies'], 'independent_cache_literal_program': diagnosis['raw_program'],
                            'interface_failures': diagnosis['quote_issues'],
                            'source_effect_diagnostic': diagnosis['source_effect_diagnostic']}, ensure_ascii=False)}
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_cache_review.py', 'experiments/rr_v2_legal_independent_cache.py',
        'legal_skill_guard/rr/legal_predicate_skills.py', 'legal_skill_guard/rr/method_client.py',
        'legal_skill_guard/rr/method_ledger.py', 'legal_skill_guard/rr/client.py')}
    protocol = REPORT / 'legal_independent_cache_review_protocol.md'
    assert strict_output_schema_issues(PATCH_SCHEMA) == []
    seal = {'run_id': RUN, 'files': files, 'binding': {'code_hash': digest(files), 'config_hash': digest(old['config'])},
            'config': old['config'], 'sources': old['sources'], 'source_ids': old['source_ids'],
            'policies': old['policies'], 'schema': PATCH_SCHEMA, 'teacher_messages': messages,
            'protocol_sha256': hashlib.sha256(protocol.read_bytes()).hexdigest(),
            'original_cache_response_sha256': hashlib.sha256((FIRST/'source.json').read_bytes()).hexdigest(),
            'source_checks_not_bypassed': True, 'new_source_or_native_label': False, 'goal_complete': False}
    immutable_json(STAGE / 'seal.json', seal); return seal


def generate(seal):
    if (STAGE/'review.json').exists(): print('Existing source review; no redispatch'); return
    ledger = MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        binding=seal['binding'], sources=seal['sources'], authorization_hash=seal['protocol_sha256'],
        question='Source-only ordinary targeted repair of the independent cache: exact source quote interface and missing152(b)(1) effects. Preserve original request, code, failure, shared API, checks and cumulative costs; no native labels.')
    client = MethodTeacher(ledger, STAGE, seal['config']['teacher'])
    wire = client.summarize(RUN+':review', source_ids=seal['source_ids'], system_prompt=seal['teacher_messages']['system'],
                           user_prompt=seal['teacher_messages']['user'], output_schema=PATCH_SCHEMA)
    immutable_json(STAGE/'review.json', {'physical_response': wire, 'value': wire['value']})
    print(json.dumps({'review_captured': True, 'elapsed_seconds': wire['elapsed_seconds']}))


def close(seal):
    original = read(FIRST/'source.json')['value']['code']; patch = read(STAGE/'review.json')['value']
    code, application = apply_review(original, patch)
    immutable_json(STAGE/'review_application.json', application)
    path = STAGE/'reviewed_cache.py'
    if path.exists(): assert path.read_text() == code
    else: path.write_text(code)
    sources = [p['rules'] for p in seal['policies']]
    checks = check_fixtures(code, sources)
    cases = read(BASE/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json')['cases']; native = []
    for case in cases:
        try:
            out = execute_code(code, case['facts'], case['query'], sources)
            native.append({'ordinal': case['ordinal'], 'query': case['query'], 'output': out, 'executed': True})
        except Exception as exc:
            native.append({'ordinal': case['ordinal'], 'executed': False, 'error_type': type(exc).__name__, 'error': str(exc)})
    immutable_json(STAGE/'execution_closed_before_grading.json', {
        'closed_utc': datetime.now(timezone.utc).isoformat(),
        'review_response_sha256': hashlib.sha256((STAGE/'review.json').read_bytes()).hexdigest(),
        'reviewed_code_sha256': hashlib.sha256(code.encode()).hexdigest(),
        'software_source_checks': checks, 'native_results': native,
        'same_observed_four_TRAIN_sources_not_blind': True, 'new_labels_opened': False, 'goal_complete': False})
    print(json.dumps({'source_checks_passed': checks['all_passed'], 'native_answers': [
        {'ordinal': r['ordinal'], 'answer': r.get('output',{}).get('answer'), 'executed': r['executed']} for r in native]}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['prepare', 'generate', 'close']); action = p.parse_args().action
    seal = prepare()
    if action == 'prepare': print('Source review prepared; no dispatch')
    elif action == 'generate': generate(seal)
    else: close(seal)
