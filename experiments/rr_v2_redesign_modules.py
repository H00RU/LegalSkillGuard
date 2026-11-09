"""Fixed-rule capacity controls for the redesign; no efficacy claim."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor, MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.semantic_contracts import validate_module

ROOT = Path(__file__).resolve().parents[1]
RUN = 'redesign_rule_modules_v1_20261109'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109' / RUN
OLD = ROOT / 'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
SCHEMA = {'type': 'object', 'properties': {
    'expression': {'type': 'string'},
    'rule_quotes': {'type': 'array', 'items': {'type': 'string'}},
    'scope_notes': {'type': 'string'},
    'unresolved_requirements': {'type': 'array', 'items': {'type': 'string'}},
}, 'required': ['expression', 'rule_quotes', 'scope_notes', 'unresolved_requirements'], 'additionalProperties': False}


def prepare():
    old = json.loads((OLD / 'seal.json').read_text())
    public = {s['key']: s for s in json.loads((ROOT / 'data/packets/rr_v2/public_train.json').read_text())['sources']}
    targets = [
        dict(ordinal=2, id='airline_size', signature=dict(length='integer', width='integer', height='integer'),
             meanings='length, width and height are the three outside dimensions of a bag in inches',
             target='the calculated size of a bag, before applying any size limit or baggage price'),
        dict(ordinal=18, id='sara_percentage', signature=dict(income='integer', threshold='integer', married_separate='boolean'),
             meanings='income is adjusted gross income in dollars; threshold is the applicable amount under section 68(b); married_separate states whether this taxpayer is a married individual filing a separate return',
             target='the applicable percentage under section 151(d)(3)(B), in integer percentage points, on the domain income > threshold; this is not the exemption amount or final tax'),
    ]
    system = ('Translate only the requested policy function into one pure integer/Boolean expression. '
              'Use input names from the supplied signature; no case facts or final answer are available. '
              'Allowed syntax: integer/Boolean literals, + - * //, comparisons, and/or/not, conditional expression '
              '(a if condition else b), min, max, and ceildiv(n,d) for exact integer ceiling division by a positive denominator. '
              'No imports, functions, assignment, attributes, floats, free names, or other calls. '
              'Quote the governing rule verbatim. List missing requirements rather than supplying assumptions. '
              'Return only the schema object. A quote is provenance, not a guarantee of faithfulness.')
    for target in targets:
        target['source'] = old['sources']['train'][target['ordinal'] - 1]
        target['rules'] = public[target['source']]['public']['rules']
        target['messages'] = [dict(role='system', content=system), dict(role='user', content=json.dumps({
            'rules': target['rules'], 'target_function': target['target'], 'input_signature': target['signature'],
            'input_meanings': target['meanings']}, ensure_ascii=False))]
    files = science_files(ROOT)
    files['configs/redesign_requirements_20261109.txt'] = hashlib.sha256((ROOT / 'configs/redesign_requirements_20261109.txt').read_bytes()).hexdigest()
    protocol = ROOT / 'reports/method_redesign_20261109/protocol.md'
    seal = dict(run_id=RUN, files=files, binding=dict(code_hash=digest(files), config_hash=digest(old['config'])),
                config=old['config'], sources=old['sources'], targets=targets,
                protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
                schema=SCHEMA, signature_is_supplied_control_not_learned=True,
                natural_language_semantics_not_proved_by_equivalence=True,
                TEST_authorized=False, paper_authorized=False)
    immutable_json(STAGE / 'seal.json', seal)
    return seal


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'executor', 'teacher']); args = parser.parse_args()
    seal = prepare()
    if args.action == 'prepare':
        print(json.dumps({'run_id': RUN, 'targets': [t['id'] for t in seal['targets']], 'new_calls': 0})); return
    ledger = MethodLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        binding=seal['binding'], sources=seal['sources'], authorization_hash=seal['protocol_sha256'],
        question='Can compact source-only parametric arithmetic modules remove the previous representation bottleneck? Fixed signatures and rule definitions are capacity controls, not learned-method efficacy.')
    executor = MethodExecutor(ledger, STAGE, seal['config']['executor'])
    teacher = MethodTeacher(ledger, STAGE, seal['config']['teacher'])
    for target in seal['targets']:
        path = STAGE / (args.action + '_' + target['id'] + '.json')
        if path.exists():
            print(json.dumps({'role': args.action, 'target': target['id'], 'existing_result': True})); continue
        call_id = RUN + ':' + args.action + ':' + target['id'] + ':0'
        if args.action == 'executor':
            executor.readiness()
            wire = executor.generate(call_id, source=target['source'], purpose='method_train_synthesis',
                                      messages=target['messages'], schema=SCHEMA, thinking=False)
            value = json.loads(wire['content'])
        else:
            wire = teacher.summarize(call_id, source_ids=[target['source']],
                system_prompt=target['messages'][0]['content'], user_prompt=target['messages'][1]['content'], output_schema=SCHEMA)
            value = wire['value']
        try:
            compiled = validate_module(value, target['signature'], target['rules'])
            validation = {'status': 'typed_executable_module', 'symbolic_expression': compiled.sexpr(),
                          'unresolved_requirements': value['unresolved_requirements']}
        except Exception as exc:
            validation = {'status': 'rejected', 'error_type': type(exc).__name__, 'error': str(exc)}
        immutable_json(path, dict(captured_utc=datetime.now(timezone.utc).isoformat(), target=target['id'],
            source=target['source'], role=args.action, module=value, physical_response=wire,
            validation=validation, source_semantic_review='pending_independent_review',
            counts_as_core_method_success=False, library_updated=False))
        print(json.dumps({'role': args.action, 'target': target['id'], 'validation': validation}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
