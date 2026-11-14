"""Retry the two actual failures after explicit native-arity schema repair.

Original requests stay charged and preserved. The actual model/schema change
has a real-response offline regression; this is not an unchanged repeat.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_native_observation_read as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import checked_witnesses, kernel_execution
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.sara_statute_kernel import input_schema


ROOT = prior.ROOT
RUN = 'legal_skill_evolution_native_typed_read_20261114'
OUT = ROOT / 'artifacts' / RUN


def read(path):
    return json.loads(path.read_text())


def schema_for(kernel):
    result = prior.schema_for(kernel)
    result['properties']['inputs'] = input_schema(kernel)
    return result


def request(source, kernel):
    return {'current_case': source['views'][0]['public'],
            'native_query': kernel['native_query'], 'fact_arities': kernel['fact_arities'],
            'shared_factual_encoding': prior.ONTOLOGY}


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    parent = read(prior.OUT / 'protocol.json')
    cases = read(prior.OUT / 'cases.json')
    schemas = [schema_for(case['kernel']) for case in cases]
    for case, schema in zip(cases, schemas):
        jsonschema.Draft202012Validator.check_schema(schema)
        actual = read(prior.OUT / 'results' / (digest(case['source']['key']) + '.json'))['observation']
        assert list(jsonschema.Draft202012Validator(schema).iter_errors(actual))
    before = prior.common.old.rows()
    assert not any(row[6] == 'reserved' for row in before)
    paths = [Path(__file__), Path(prior.__file__),
        ROOT / 'legal_skill_guard/skill_evolution/sara_statute_kernel.py',
        ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'tests/test_skill_evolution_sara_statute_kernel.py']
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': parent['sources'], 'executor_profile': parent['executor_profile'],
        'original_loose_wire_run': prior.RUN, 'planned_physical_requests': 2,
        'actual_change': 'native arity and parameter types moved from host-only validation into decoder schema',
        'offline_real_response_regressions_passed': 2, 'related_tests_passed': 27,
        'original_rule_program_query_and_case_unchanged': True,
        'cases_sha256': digest(cases), 'schemas_sha256': digest(schemas),
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    immutable_json(OUT / 'protocol.json', p)
    immutable_json(OUT / 'cases.json', cases)
    immutable_json(OUT / 'schemas.json', schemas)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {row[0]: digest(row) for row in before})
    for path in paths:
        dest = OUT / 'source_snapshot' / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    return p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preflight', 'read'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        for name, expected in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
        cases, schemas = read(OUT / 'cases.json'), read(OUT / 'schemas.json')
        assert digest(cases) == p['cases_sha256'] and digest(schemas) == p['schemas_sha256']
        if args.phase == 'preflight':
            return
        assert (OUT / 'offline_serving_grammar_check.json').exists()
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
            run_id=RUN, sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
        client = FrozenExecutor(ledger, OUT, p['executor_profile'])
        for case, schema in zip(cases, schemas):
            source, kernel = case['source'], case['kernel']
            path = OUT / 'results' / (digest(source['key']) + '.json')
            if path.exists():
                continue
            response = client.generate(RUN + ':DirectRead:' + source['key'], source=source['key'],
                purpose='skill_actor', thinking=False, messages=render_messages(prior.SYSTEM, request(source, kernel), schema),
                schema=decoder_schema(schema)[0])
            row = {'source': source['key'], 'fallback': False, 'usage': response['usage'],
                'elapsed_seconds': response['elapsed_seconds'], 'finish_reason': response['finish_reason']}
            try:
                assert response['finish_reason'] == 'stop'
                value = json.loads(response['content'])
                row['observation'] = value
                jsonschema.validate(value, schema)
                checked_witnesses(value['witnesses'], source['views'][0]['public'])
                row['execution'] = kernel_execution(kernel, value['inputs'])
            except Exception as error:
                row.update(error=type(error).__name__ + ': ' + str(error), execution={'handled': False, 'answer': None})
            immutable_json(path, row)
            print(json.dumps({'source': source['key'], 'handled': row['execution']['handled'],
                'answer': row['execution']['answer'], 'error': row.get('error')}), flush=True)


if __name__ == '__main__':
    main()
