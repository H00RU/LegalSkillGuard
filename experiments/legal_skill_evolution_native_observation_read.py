"""Two fixed real factual reads against the common author statute backend."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_native_execution_reuse as common
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import checked_witnesses, kernel_execution
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import render_messages, decoder_schema


ROOT = common.ROOT
RUN = 'legal_skill_evolution_native_observation_read_20261114'
OUT = ROOT / 'artifacts' / RUN
ONTOLOGY = '''Shared factual encoding from the author statute program:
service_(event), agent_(service,worker), patient_(service,employer).
payment_(event), agent_(payment,payer), patient_(payment,payee),
purpose_(payment,service_event), amount_(payment,amount).
purpose_(service,"domestic service"|"agricultural labor") is a stated service kind.
marriage_(event) has an agent_ fact for EACH spouse.
death_(event) has agent_(event,deceased), start_(event,actual_death_date).
enrollment_(event) has agent_(event,student), patient_(event,institution).
attending_classes_(event) has agent_(event,student), location_(event,institution).
educational_institution_(event) has agent_(event,institution).
income_(event) has agent_(event,recipient), amount_(event,amount).
start_/end_ describe the dates/period of that SAME event, not arbitrary dates
belonging to a different event. A stated annual income can be represented over
its stated calendar year with canonical year bounds; this does not invent the
date of an instantaneous payment. Never allocate a cross-year payment or give
it a payment date copied from a service period without support.
Explicit section151 allowance givens use s151_b_applies(taxpayer,spouse,year)
or s151_c_applies(taxpayer,dependent,year), with polarity retained separately.
Raw predicate names and argument positions are shared to all controls; this
ontology is a common component, not a learned method contribution.
'''
SYSTEM = '''Extract only the factual record of the current finite case into
the shared native event vocabulary. Do not decide the statutory claim or add
the target as a fact. Preserve entity/role direction and distinct event IDs;
use the query's opaque event ID when it names the event described in this case.
Other event IDs can be consistent local strings. Use current facts/question
verbatim witnesses. The restored native query constraints say WHAT is asked,
never whether it is true. A question is not evidence for its own premise.
Only explicit intermediate statutory givens may become given facts.

Canonicalize explicit dates. Omit an unstated event endpoint rather than invent
one; the immutable author program applies its own finite-source convention.
complete means all relevant supplied finite text was read successfully, not
that the real world is exhaustively known. unread preserves extraction failure
and cannot produce a guessed negative answer. Return only factual JSON.
'''


def read(path):
    return json.loads(path.read_text())


def schema_for(kernel):
    return record_schema({'inputs': json.loads(kernel['input_schema_json']),
        'witnesses': {'type': 'array', 'minItems': 1, 'items': record_schema({
            'field': {'type': 'string', 'enum': ['facts', 'question']}, 'quote': {'type': 'string', 'minLength': 1}})}})


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    parent = read(common.OUT / 'protocol.json')
    views = read(common.OUT / 'corrected_TRAIN_views.json')[:2]
    bank = read(common.OUT / 'kernel_bank.json')[:2]
    cases = [{'source': source, 'kernel': kernel} for source, kernel in zip(views, bank)]
    schemas = [schema_for(kernel) for kernel in bank]
    for schema in schemas:
        jsonschema.Draft202012Validator.check_schema(schema)
    before = common.old.rows()
    assert not any(row[6] == 'reserved' for row in before)
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/sara_statute_kernel.py',
        ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'tests/test_skill_evolution_sara_statute_kernel.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': [source['key'] for source in views],
        'new_sources': 0, 'fixed_development_cases': 2,
        'common_statutes_and_query_restoration_not_a_method_contribution': True,
        'planned_new_executor_requests': 2, 'teacher_requests': 0,
        'new_native_labels_not_supplied_to_reader': True,
        'executor_profile': parent['executor_profile'],
        'case_packet_sha256': digest(cases), 'schemas_sha256': digest(schemas),
        'system': SYSTEM, 'shared_ontology': ONTOLOGY,
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}
    immutable_json(OUT / 'protocol.json', protocol)
    immutable_json(OUT / 'cases.json', cases)
    immutable_json(OUT / 'schemas.json', schemas)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {row[0]: digest(row) for row in before})
    for path in files:
        target = OUT / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    return protocol


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preflight', 'read'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol = prepare()
        for name, expected in protocol['source_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
        cases, schemas = read(OUT / 'cases.json'), read(OUT / 'schemas.json')
        assert digest(cases) == protocol['case_packet_sha256'] and digest(schemas) == protocol['schemas_sha256']
        if args.phase == 'preflight':
            return
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
            run_id=RUN, sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
        client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
        for case, schema in zip(cases, schemas):
            source, kernel = case['source'], case['kernel']
            path = OUT / 'results' / (digest(source['key']) + '.json')
            if path.exists():
                continue
            task = {'current_case': source['views'][0]['public'],
                    'native_query': kernel['native_query'], 'fact_arities': kernel['fact_arities'],
                    'shared_factual_encoding': ONTOLOGY}
            response = client.generate(RUN + ':DirectRead:' + source['key'], source=source['key'],
                purpose='skill_actor', thinking=False,
                messages=render_messages(SYSTEM, task, schema), schema=decoder_schema(schema)[0])
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
