"""Frozen original-TRAIN execution comparison after matched controller learning.

No legal kernel is edited here. Native annotations are opened by the scoring
phase only, after immutable executions have been saved. This is a three-mother
mechanism pilot, not a new blind test or evidence that both contributions hold.
"""
import argparse
import fcntl
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_case_observation_learning as learn
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import (
    apply_adapter, check_bindings, execute_alternatives, validate_adapter)
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages


ROOT = learn.ROOT
RUN = 'legal_skill_evolution_case_observation_trial_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = (*learn.ARMS, 'DirectRead')
KERNEL_NAMES = ('family_employment_A', 'agricultural_employer_threshold',
    'qualifying_child_residence_gate')
WITNESS = record_schema({'field': {'type': 'string', 'enum': ['facts', 'question']},
    'quote': {'type': 'string'}})
DIRECT_SYSTEM = '''Instantiate the supplied UNCHANGED correct legal program from
the current case. Extract factual inputs only, never answer legal applicability.
Keep employer/employee, relative-owner/relative and payer/payee directions exact.
Normalize explicit dates to ISO; preserve each event, year and amount. Read all
relevant current facts, keeping shared event context with each entity. Do not
invent missing facts or use statute text as a case witness. Resolved finite case
extraction differs from an unread/unknown fact. If the case permits several input
assignments, return all coherent alternatives rather than guess one. Omit
unknown ports with null in this wire record; the host removes null before kernel
execution. Use nonempty verbatim current facts/question witnesses. An unresolved
list records relevant uncertainty not already represented by the alternatives.
The host runs every alternative and never selects a favorable answer. You have
the same correct program, raw source, literal context and actual error history
as the learned-controller comparison. Do not reproduce a native answer label.
'''


def read(p):
    return json.loads(p.read_text())


def event_schema(name):
    nullable_string = {'type': ['string', 'null']}
    if name == 'payment_events':
        return record_schema({'payer': {'type': 'string'}, 'payee': {'type': 'string'},
            'stated_labor': nullable_string, 'amount': {'type': 'number', 'minimum': 0},
            'period_start': {'type': 'string'}, 'period_end': {'type': 'string'},
            'wages_given': {'type': ['boolean', 'null']}})
    if name == 'residence_events':
        return record_schema({'persons': {'type': 'array', 'items': {'type': 'string'}},
            'start_date': {'type': 'string'}, 'end_date': {'type': 'string'}})
    raise ValueError('No concrete event schema for ' + name)


def direct_schema(kernel):
    ports = {}
    for name, spec in json.loads(kernel['input_fields_json']).items():
        port = deepcopy(spec)
        port['type'] = [spec['type'], 'null']
        if spec['type'] == 'array':
            port['items'] = event_schema(name)
        ports[name] = port
    return record_schema({'bindings': {'type': 'array', 'items': record_schema({
        'inputs': record_schema(ports), 'witnesses': {'type': 'array', 'items': WITNESS}})},
        'unresolved': {'type': 'array', 'items': {'type': 'string'}}})


def checked_contracts():
    contracts = {}
    for arm in learn.ARMS:
        value = read(learn.OUT / arm / 'teacher.json')['value']
        rows = value['contracts']
        assert len(rows) == len(KERNEL_NAMES) and {r['kernel_name'] for r in rows} == set(KERNEL_NAMES)
        contracts[arm] = {r['kernel_name']: r for r in rows}
        for row in rows:
            validate_adapter(row['binding_program'], excluded_source_ids=read(learn.OUT / 'protocol.json')['sources'])
            schema = json.loads(row['observation_schema_json'])
            jsonschema.Draft202012Validator.check_schema(schema)
    return contracts


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    old = read(learn.OUT / 'protocol.json')
    contracts = checked_contracts()
    bank = {k['name']: k for k in read(learn.OUT / 'kernel_bank.json')}
    public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    cases = [{'source': public[sid], 'kernel': bank[name]}
        for sid, name in zip(old['sources'], KERNEL_NAMES)]
    offline = []
    for arm in learn.ARMS:
        for item in cases:
            source, kernel = item['source'], item['kernel']
            view = source['views'][0]
            contract = contracts[arm][kernel['name']]
            try:
                grounded = apply_adapter(contract, kernel, view['public'], None,
                    literal_context=literal_bindings(view))
                result = execute_alternatives(kernel, grounded)
                offline.append({'arm': arm, 'source': source['key'], 'grounded': grounded,
                    'result': result, 'no_model_request': True})
            except Exception as exc:
                # No failure is transformed into a default factual input.
                offline.append({'arm': arm, 'source': source['key'],
                    'adapter_error': type(exc).__name__ + ': ' + str(exc), 'no_model_request': True})
    before = learn.base.rows()
    assert not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    immutable_json(OUT / 'frozen_contracts.json', contracts)
    immutable_json(OUT / 'fixed_cases.json', cases)
    immutable_json(OUT / 'offline_adapter_preflight.json', offline)
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py',
        ROOT / 'legal_skill_guard/skill_evolution/clients.py',
        ROOT / 'legal_skill_guard/skill_evolution/ledger.py',
        ROOT / 'legal_skill_guard/skill_evolution/literal_facts.py',
        ROOT / 'legal_skill_guard/skill_evolution/runtime.py']
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': old['sources'], 'arms': list(ARMS), 'executor_profile': old['executor_profile'],
        'learned_contract_sha256': digest(contracts), 'fixed_cases_sha256': digest(cases),
        'learning_mothers': old['learning_sources'],
        'future_original_TRAIN_mothers': old['frozen_original_TRAIN_transfer_sources'],
        'historical_TRAIN_exposure_disclosed': True,
        'shared_source_only_kernel_acquisition_and_repair_charged_to_all': True,
        'native_scoring_after_immutable_execution': True,
        'no_fallback_or_legal_program_repair': True,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    for f in files:
        dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    immutable_json(OUT / 'protocol.json', p)
    return p


def request_observation(executor, arm, source, kernel, contract, history):
    view = source['views'][0]
    schema = direct_schema(kernel) if arm == 'DirectRead' else json.loads(contract['observation_schema_json'])
    jsonschema.Draft202012Validator.check_schema(schema)
    system = DIRECT_SYSTEM if arm == 'DirectRead' else contract['observation_prompt']
    system += '\nReturn only the specified factual JSON. Unknown is not false or zero. All witnesses must be verbatim current facts/question text.'
    task = {'current_case': view['public'], 'unchanged_correct_legal_kernel': kernel,
        'literal_context': literal_bindings(view)}
    if arm == 'DirectRead':
        task['same_actual_grounding_error_history'] = history
    messages = render_messages(system, task, schema)
    wire, host_checks = decoder_schema(schema)
    response = executor.generate(RUN + ':' + arm + ':' + source['key'], source=source['key'],
        purpose='skill_actor', messages=messages, thinking=False, schema=wire)
    if response['finish_reason'] != 'stop':
        raise ValueError('Nonterminal observation response: ' + str(response['finish_reason']))
    value = json.loads(response['content'])
    jsonschema.validate(value, schema)
    return value, {'call_id': RUN + ':' + arm + ':' + source['key'],
        'usage': response['usage'], 'elapsed_seconds': response['elapsed_seconds'],
        'host_schema_checks_preserved': host_checks, 'raw_response_preserved': True}


def execute(p):
    contracts = read(OUT / 'frozen_contracts.json')
    cases = read(OUT / 'fixed_cases.json')
    history = read(ROOT / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/verified_source_frame_error.json')
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
    executor = FrozenExecutor(ledger, OUT, p['executor_profile'])
    for item in cases:
        source, kernel = item['source'], item['kernel']
        view = source['views'][0]
        for arm in ARMS:
            path = OUT / arm / (digest(source['key']) + '.json')
            if path.exists():
                continue
            result = {'arm': arm, 'source': source['key'], 'kernel_name': kernel['name'],
                'fallback': False, 'new_executor_requests': 0}
            try:
                contract = contracts.get(arm, {}).get(kernel['name'])
                grounded = None
                if contract:
                    grounded = apply_adapter(contract, kernel, view['public'], None,
                        literal_context=literal_bindings(view))
                    result['before_neural_read'] = {'grounded': grounded,
                        'execution': execute_alternatives(kernel, grounded)}
                if arm == 'DirectRead' or (not result['before_neural_read']['execution']['handled']
                        and contract['requires_neural_read']):
                    # Increment before a possibly failing physical attempt.
                    result['new_executor_requests'] = 1
                    value, receipt = request_observation(executor, arm, source, kernel, contract, history)
                    result['raw_observation'] = value
                    result['observation_receipt'] = receipt
                    if arm == 'DirectRead':
                        for row in value['bindings']:
                            row['inputs'] = {k: v for k, v in row['inputs'].items() if v is not None}
                        grounded = check_bindings(value, json.loads(kernel['input_fields_json']), view['public'])
                    else:
                        grounded = apply_adapter(contract, kernel, view['public'], value,
                            literal_context=literal_bindings(view))
                result['grounded'] = grounded
                result['execution'] = execute_alternatives(kernel, grounded)
            except Exception as exc:
                result['error'] = type(exc).__name__ + ': ' + str(exc)
                result['execution'] = {'handled': False, 'answer': None}
            immutable_json(path, result)
            print(json.dumps({'arm': arm, 'source': source['key'],
                'handled': result['execution']['handled'], 'error': result.get('error')}), flush=True)


def score(p):
    # Never call the scorer from acquisition, adapter or executor prompts.
    annotations = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    cases = read(OUT / 'fixed_cases.json')
    all_rows = []
    for item in cases:
        source = item['source']
        view = source['views'][0]
        for arm in ARMS:
            row = read(OUT / arm / (digest(source['key']) + '.json'))
            row['native_score'] = grade_view(source['dataset'], view,
                annotations[source['key']][view['id']], row['execution']['answer'])
            all_rows.append(row)
    summary = {arm: {'correct': sum(r['native_score']['correct'] for r in all_rows if r['arm'] == arm),
        'mothers': len(cases), 'handled': sum(r['execution']['handled'] for r in all_rows if r['arm'] == arm),
        'executor_requests_attempted': sum(r['new_executor_requests'] for r in all_rows if r['arm'] == arm)} for arm in ARMS}
    immutable_json(OUT / 'scored_results.json', {'summary': summary, 'rows': all_rows,
        'not_independent_contribution_proof': True, 'goal_complete': False})
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'execute', 'score'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        for f, h in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h
        assert digest(read(OUT / 'frozen_contracts.json')) == p['learned_contract_sha256']
        assert digest(read(OUT / 'fixed_cases.json')) == p['fixed_cases_sha256']
        if phase == 'execute':
            execute(p)
        elif phase == 'score':
            score(p)


if __name__ == '__main__':
    main()
