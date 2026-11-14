"""Two fixed original-TRAIN development reads of source-only legal kernels.

First establish actual grounding failures. This launches no controller learning,
does not inspect the two frozen-transfer case facts, and does not change a rule.
"""
import argparse
import fcntl
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_grounding_frontier as source
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import checked_witnesses, kernel_execution
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema, grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure


ROOT = source.ROOT
RUN = 'legal_skill_evolution_grounding_frontier_read_20261114'
OUT = ROOT / 'artifacts' / RUN
TYPES = {'array', 'object', 'boolean', 'integer', 'number', 'string', 'null'}
SYSTEM = '''Read the supplied current case into the factual input ports of the
unchanged legal program. Do not decide the target statutory conclusion. Preserve
who bears a relation TO whom, who files/itemizes, and the actual dates. Explicit
legal givens are usable as givens; never import a listed relation from the statute
into case facts. Each event/record must belong to the current case and carry a
nonempty verbatim facts/question witness. Resolved finite extraction with no
record is [], while unknown/unread is null. Do not invent missing endings or
elections, and do not turn a target claim into proof of its premise. Preserve
unknown itemization when only eligibility is stated. Return only the requested
factual JSON, not a native answer. The code and descriptions specify each port.
'''


def read(path):
    return json.loads(path.read_text())


def nominal_type(value):
    types = value.split('|') if isinstance(value, str) else value
    if not types or not set(types) <= TYPES:
        raise ValueError('Unknown declared JSON type: ' + str(value))
    return types[0] if len(types) == 1 else types


def port_schema(spec):
    result = {'type': nominal_type(spec['type']), 'description': spec['description']}
    types = result['type'] if isinstance(result['type'], list) else [result['type']]
    if 'array' in types:
        # Exact flat record notation is already explicitly supplied by this
        # actual teacher response. This codec changes no field meaning/type.
        match = re.search(r'\{([^{}]+)\}', spec['description'])
        if not match:
            raise ValueError('Array record shape must be explicit before generation')
        fields = {}
        for item in match.group(1).split(','):
            name, kind = item.strip().split(':')
            fields[name] = {'type': nominal_type(kind)}
        result['items'] = record_schema(fields)
    # Null on the wire denotes an omitted/unread input, never a false value.
    result['type'] = list(dict.fromkeys([*types, 'null']))
    return result


def schema_for(kernel):
    fields = json.loads(kernel['input_fields_json'])
    return record_schema({'inputs': record_schema({k: port_schema(v) for k, v in fields.items()}),
        'witnesses': {'type': 'array', 'items': record_schema({
            'field': {'type': 'string', 'enum': ['facts', 'question']}, 'quote': {'type': 'string'}})},
        'unresolved': {'type': 'array', 'items': {'type': 'string'}}})


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    old = read(source.OUT / 'protocol.json')
    kernels = read(source.OUT / 'teacher.json')['value']['kernels']
    assert len(kernels) == 4 and {k['name'] for k in kernels} == {t[2] for t in source.TARGETS}
    bank = {k['name']: k for k in kernels}
    public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    cases = [{'source': public[sid], 'kernel': bank[target[2]]}
        for sid, target in zip(old['development_mothers'], source.TARGETS[:2])]
    checks = []
    for case in cases:
        kernel = case['kernel']
        validate_procedure(kernel['program'], allow_helpers=True)
        schema = schema_for(kernel)
        jsonschema.Draft202012Validator.check_schema(schema)
        checks.append({'kernel': kernel['name'], 'schema': schema,
            'declared_nullable_union_codec': {'array|null': ['array', 'null']},
            'field_names_and_record_types_preserved': True, 'no_new_model_request': True})
    before = source.old.rows(); assert not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'fixed_development_cases.json', cases)
    immutable_json(OUT / 'offline_schema_check.json', checks)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py',
        ROOT / 'legal_skill_guard/skill_evolution/clients.py',
        ROOT / 'legal_skill_guard/skill_evolution/ledger.py',
        ROOT / 'legal_skill_guard/skill_evolution/runtime.py']
    for f in files:
        dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': old['development_mothers'], 'transfer_case_facts_not_loaded_here': True,
        'executor_profile': old['executor_profile'], 'development_cases_sha256': digest(cases),
        'schemas_sha256': digest(checks), 'source_sha256': {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'planned_new_executor_calls': 2, 'rule_edits_or_native_answer_fallback': False,
        'score_only_after_saved_physical_outputs': True}
    immutable_json(OUT / 'protocol.json', p)
    return p


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'read', 'score'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        for path, h in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == h
        cases = read(OUT / 'fixed_development_cases.json')
        checks = read(OUT / 'offline_schema_check.json')
        assert digest(cases) == p['development_cases_sha256'] and digest(checks) == p['schemas_sha256']
        if phase == 'preflight':
            return
        if phase == 'score':
            annotations = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
            rows = []
            for case in cases:
                src = case['source']; view = src['views'][0]
                row = read(OUT / 'results' / (digest(src['key']) + '.json'))
                row['native_score'] = grade_view(src['dataset'], view, annotations[src['key']][view['id']], row['execution']['answer'])
                rows.append(row)
            immutable_json(OUT / 'scored_results.json', rows)
            print(json.dumps([{'source': r['source'], 'execution': r['execution'], 'score': r['native_score']} for r in rows]), flush=True)
            return
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
            sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
        client = FrozenExecutor(ledger, OUT, p['executor_profile'])
        for case, check in zip(cases, checks):
            src, kernel = case['source'], case['kernel']
            path = OUT / 'results' / (digest(src['key']) + '.json')
            if path.exists():
                continue
            schema = check['schema']
            wire, constraints = decoder_schema(schema)
            task = {'current_case': src['views'][0]['public'], 'unchanged_legal_program': kernel}
            call_id = RUN + ':DirectRead:' + src['key']
            response = client.generate(call_id, source=src['key'], purpose='skill_actor',
                messages=render_messages(SYSTEM, task, schema), thinking=False, schema=wire)
            result = {'source': src['key'], 'kernel': kernel['name'], 'call_id': call_id,
                'physical_response_saved': True, 'fallback': False,
                'usage': response['usage'], 'elapsed_seconds': response['elapsed_seconds']}
            try:
                assert response['finish_reason'] == 'stop'
                value = json.loads(response['content']); jsonschema.validate(value, schema)
                checked_witnesses(value['witnesses'], src['views'][0]['public'])
                factual_inputs = {k: v for k, v in value['inputs'].items() if v is not None}
                executed = kernel_execution(kernel, factual_inputs)
                # Named unresolved ports may be irrelevant to a decisive kernel
                # witness. Preserve the raw unknowns; do not infer them false.
                result.update({'observation': value, 'inputs_omitting_unread_null': factual_inputs,
                    'execution': executed, 'deferred_host_checks': constraints})
            except Exception as exc:
                result.update({'error': type(exc).__name__ + ': ' + str(exc),
                    'execution': {'handled': False, 'answer': None}})
            immutable_json(path, result)
            print(json.dumps({'source': src['key'], 'execution': result['execution'], 'error': result.get('error')}), flush=True)


if __name__ == '__main__':
    main()
