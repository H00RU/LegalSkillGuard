"""Matched update/reuse of factual contracts on four fixed original TRAIN cases.

The common kernels must first pass source/operational review. Teachers see past
real errors and both earlier factual libraries, but no new case facts/questions
or labels. Primary outputs are saved before native grading. This does not
restart any closed pilot or a full training/evaluation matrix.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_native_execution_reuse as common
from experiments import legal_skill_evolution_native_typed_read as native_direct
from experiments import legal_skill_evolution_temporal_contract_learning as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import (
    apply_adapter, checked_witnesses, execute_alternatives, kernel_execution, validate_adapter,
)
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS
from legal_skill_guard.skill_evolution.sara_statute_kernel import input_schema


ROOT = common.ROOT
RUN = 'legal_skill_evolution_observation_reuse_schema1_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = ('ProgramGuided', 'FreeHistory')
OBSERVATION = {'anyOf': [
    record_schema({'kind': {'type': 'string', 'enum': ['reuse']},
        'component_id': {'type': 'string'}}),
    record_schema({'kind': {'type': 'string', 'enum': ['learned_update']},
        'parent_component_id': {'type': ['string', 'null']},
        'error_feedback_ids': {'type': 'array', 'items': {'type': 'string'}},
        'context_fields': {'type': 'array', 'items': {'type': 'string', 'enum': ['facts', 'question', 'source_text']}},
        'prompt': {'type': 'string'}, 'schema_json': {'type': 'string'}})]}
SCHEMA = record_schema({'rationale': {'type': 'string'}, 'contracts': {'type': 'array',
    'items': record_schema({'kernel_name': {'type': 'string'}, 'requires_neural_read': {'type': 'boolean'},
        'observation': OBSERVATION, 'binding_program': {'type': 'string'}})}})
SYSTEM = '''Update a reusable factual observation/binding library for the FOUR
new unchanged legal kernels. Do not use tools or edit legal programs/meanings.
The old paid father-direction, ongoing-state and unread-vs-source-absence errors,
both previous learned libraries, their actual programs and common semantic
corrections are shared. The first TWO new development facts/actual native reads
and TRAIN feedback are shared. The other TWO case facts, concrete question
entities and native labels are WITHHELD. All cases are historically exposed
original TRAIN, not a new blind test.

The common legal kernel now executes the author's immutable statute code on
typed primitive factual relations. It is a shared backend, not a learned legal
program or this method's contribution. The old generated custom kernels were
rejected before use for scope/native/interface defects. Do not replicate them.
The input fields facts, negative_givens and extraction_status have the supplied
exact schema and native argument roles. The adapter may lower a source-native
event view into these facts, but must not assert the target statutory query.
The actual kernel.native_query holds the original question's explicit query
parameters at execution time. Use those to identify the factual task, never to
assert the claim. Source-only teacher cards replace future concrete query
parameters with type markers. Old prepared questions omitted some native
constraints; the same source query constraints are now restored for EVERY arm.

Use the existing useful factual primitives and conversions instead of merely
adding a new kernel-name-specific prompt or copying benchmark answers. New
legal clauses may require a new factual primitive (e.g. enrollment at the SAME
service institution); that is distinct from reuse of payer/year, directed givens,
marriage/onset and calendar observations. Explain concrete reuse and additions
in rationale. Referencing an old component is not by itself proof of reuse.

Return one contract per new kernel under the supplied schema. The observation
is either an EXACT reuse of a provided frozen observation component by ID, or
a learned_update containing schema/prompt/context_fields, an optional real
parent_component_id and the actual error_feedback_ids it addresses. Reuse
copies the old prompt/schema bytes unchanged. A new source-only primitive with
no relevant error episode must say parent=null and error_feedback_ids=[]; do
not relabel it as error-driven reuse. A reference is not proof: the actual new
conversion must be run, and later code/trace checks will inspect what was used.
The learned binding apply(inputs,premises) module returns exactly
{bindings:[{inputs:{port:value},witnesses:[{field:'facts'|'question',quote:verbatim}]}],
 unresolved:[reason]}. The host passes kernel, public_case:{facts,question},
literal_context, and observation (null before any neural read). It executes ALL
coherent alternatives through the unchanged legal program. Never choose a
favorable interpretation or encode Entailment/Contradiction in the adapter.
Factual normalization/role projection is allowed; statutory tests stay in P.

Use original declared input names/types and current case/question witnesses.
Correct explicit intermediate positive/negative legal GIVENS in the case are
usable, but a query is not its own given. A given's arguments and polarity must
not be inverted. A statute passage alone cannot establish a case premise.
Distinguish records stated in this finite text, no matching statement after a
completed channel read, and unread/ambiguous extraction. Expose these states
explicitly in your factual schema/prompt wherever absence matters. Do not fill
missing dates, facts or flags from a native answer. Do not infer a permanent
future state from a past onset. Unknown is not zero/False/empty; finite native
failure under completed extraction is not neural uncertainty. Do not add extra
world-exhaustiveness/clinical or proof-of-every-negative requirements.

Records and completed-source absence require at least one nonempty verbatim
current facts/question witness in the JSON Schema and in the adapter. Unread
may have no witnesses and must remain unresolved. The schema, prompt, adapter
and fixed kernel must agree; no output of a default legal answer. Preserve
different coherent bindings and let the host compare their actual outputs.
Keep genuinely relevant opaque uncertainty; a merely optional missing endpoint
does not by itself invalidate an explicitly ongoing state.

Both arms may use the old learned source-native views, direct ports, shared
program analysis, cached correct repairs and pure string/regex parsing.
No source-ID/name/amount/year-specific case branching, imports,
nested defs, lambdas, IO, or exception-as-answer. Shared calendar primitives and
Python operations are unchanged. Return compact code, no tools.

The direct native-fact generation is a CLOSED diagnostic, not the strongest
baseline: it gave malformed event roles, then a repeated/truncated record list
even after exact arity/type schema repair. Do not repeat that wire as a default
strategy. The unrestricted FreeHistory arm represents ordinary strong factual
extraction plus a fixed solver and may use all the same reusable event views,
deterministic conversions, evidence, feedback and old programs. Current work
tests representation/conversion learning and reuse. No claim of a new solver,
information-extraction ontology, or residual-query novelty is made here.
'''


def read(path):
    return json.loads(path.read_text())


def bank():
    protocol = read(common.OUT / 'protocol.json')
    kernels = read(common.OUT / 'kernel_bank.json')
    assert digest(kernels) == protocol['kernel_bank_sha256']
    result = deepcopy(kernels)
    for kernel in result:
        kernel['input_schema_json'] = json.dumps(input_schema(kernel))
    return result


def prepare():
    assert not common.old.prior.strict_output_schema_issues(SCHEMA)
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    parent = read(common.OUT / 'protocol.json')
    kernels = bank()
    libraries = {}
    registry = {}
    old_sources = []
    for run in ('legal_skill_evolution_case_observation_20261114',
                'legal_skill_evolution_temporal_contract_learning_20261114'):
        path = ROOT / 'artifacts' / run
        old_sources.extend(read(path / 'protocol.json')['sources'])
        libraries[run] = {arm: read(path / arm / 'teacher.json')['value'] for arm in ARMS}
        for arm, library in libraries[run].items():
            for contract in library['contracts']:
                component_id = run + '/' + arm + '/' + contract['kernel_name']
                registry[component_id] = {'prompt': contract['observation_prompt'],
                    'schema_json': contract['observation_schema_json'],
                    'context_fields': contract.get('observation_context_fields', ['facts', 'question', 'source_text']),
                    'original_binding_program': contract['binding_program']}
    temporal = read(previous.OUT / 'scored_results.json')['rows']
    old_failure = [r for r in temporal if '8175fcb9' in r['source']]
    development = read(previous.direct.OUT / 'fixed_development_cases.json')
    teacher_cards = deepcopy(kernels)
    for card in teacher_cards:
        card['native_query'] = [{'predicate': call['predicate'], 'arguments': [
            arg if isinstance(arg, dict) else {'query_parameter_type': type(arg).__name__}
            for arg in call['arguments']]} for call in card['native_query']]
    development_cases = read(native_direct.OUT / 'cases.json')
    annotations = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    actual_development = []
    for case in development_cases:
        source = case['source']
        view = source['views'][0]
        result = read(native_direct.OUT / 'results' / (digest(source['key']) + '.json'))
        actual_development.append({'source': source, 'actual_read': result,
            'native_TRAIN_feedback': grade_view(source['dataset'], view, annotations[source['key']][view['id']], result['execution']['answer'])})
    feedback = {
        'past_father_direction': 'Past real employer/worker inversion; see shared original episode.',
        'past_ongoing_state': 'Past real has-been-married-since observation invented a same-day end.',
        'native_event_role_failure': 'On6939, the typed raw read uses agent_(Alice,Bob) with no service/payment event root; labels another event Bob as domestic service without source support, and puts amount-like strings into agent_. Execution can return a native answer without a faithful binding.',
        'native_arity_failure': 'The first1ff raw read gives marriage_/income_/joint_return_ three arguments and simultaneously positive/negative section151 allowances; the host rejects malformed native facts.',
        'native_repetition_failure': 'The typed1ff read emits repeated s151_b_applies records and reaches8192 output tokens; finish_reason=length, no complete executable IR. Do not confuse this with a kernel undecided on a valid factual input.'}
    actual_raw_failures = {}
    for folder in [native_direct.prior.OUT, native_direct.OUT]:
        actual_raw_failures[folder.name] = [read(path) for path in sorted((folder / 'calls').glob('*/result.json'))]
    task = {'new_unchanged_legal_kernels': teacher_cards,
        'new_source_only_materials': read(common.rejected.OUT / 'teacher_task.json')['source_only_targets'],
        'shared_official_statute_programs': {name: (common.OUT / 'statutes' / name).read_text()
            for name in parent['statute_source_sha256']},
        'shared_native_fact_encoding': native_direct.prior.ONTOLOGY,
        'actual_new_development_reads_and_TRAIN_feedback': actual_development,
        'shared_existing_learned_observation_libraries': libraries,
        'frozen_observation_component_registry': registry,
        'error_feedback_by_id': feedback,
        'actual_complete_raw_native_responses_including_failures': actual_raw_failures,
        'past_actual_father_direction_error': read(ROOT / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114/verified_source_frame_error.json'),
        'past_actual_temporal_reads': old_failure,
        'past_development_cases': development,
        'past_source_absence_read': read(ROOT / 'artifacts/legal_skill_evolution_missing_event_read_20261114/observation.json'),
        'shared_native_semantics_alignment': read(ROOT / 'artifacts/legal_skill_evolution_grounding_frontier_20261114/native_semantics_audit/interface_change.json'),
        'remaining_two_case_facts_questions_and_native_labels_withheld': True,
        'binding_interface': (ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py').read_text()}
    before = common.old.rows()
    assert not any(r[6] == 'reserved' for r in before)
    sources = list(dict.fromkeys([*parent['sources'], *old_sources]))
    paths = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
             ROOT / 'legal_skill_guard/skill_evolution/clients.py',
             ROOT / 'legal_skill_guard/skill_evolution/ledger.py',
             ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py',
             Path(previous.direct.__file__)]
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'supersedes_zero_dispatch_run': 'legal_skill_evolution_observation_reuse_20261114',
        'previous_experiment_binding_and_all_call_counts_preserved': True,
        'sources': sources, 'new_native_check_sources': parent['sources'],
        'history_sources': list(dict.fromkeys(old_sources)), 'new_sources': 0,
        'shared_old_libraries_available_to_both_teachers': True,
        'old_shared_acquisition_costs_not_free_or_independent_new_learning': True,
        'teacher_jobs': 2, 'primary_arms': list(ARMS),
        'closed_native_direct_diagnostic_not_repeated_on_future_cases': True,
        'primary_case_reads_per_arm': 'one unless deterministic learned adapter already handles',
        'no_repeated_seeds_or_closed_case_reruns': True,
        'development_sources': parent['sources'][:2],
        'teacher_input_withheld_original_TRAIN_sources': parent['sources'][2:],
        'remaining_two_case_facts_and_labels_withheld_from_teachers': True,
        'researcher_has_seen_public_facts': True, 'not_a_new_blind_test': True,
        'teacher_profile': parent['teacher_profile'], 'executor_profile': parent['executor_profile'],
        'task_sha256': digest(task), 'kernel_bank_sha256': digest(kernels),
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'kernel_bank.json', kernels)
    immutable_json(OUT / 'observation_component_registry.json', registry)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    for path in paths:
        dest = OUT / 'source_snapshot' / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    immutable_json(OUT / 'protocol.json', protocol)
    return protocol


def acquire(protocol, ledger):
    task = read(OUT / 'teacher_task.json')
    user = json.dumps(task, ensure_ascii=False, separators=(',', ':'))
    for arm in ARMS:
        output = OUT / arm / 'teacher.json'
        if output.exists():
            continue
        strategy = ('Use program-dependent factual distinctions and the actual past errors to learn source-native observations and evidence-bound lowering; preserve equivalent alternatives.'
                    if arm == 'ProgramGuided' else
                    'Independently learn the strongest compact strategy from all the same information; freely reuse event/state views, program-aware reading, deterministic parsing, correct repair caches and joint observations.')
        system = SYSTEM + '\n' + strategy
        system += '\nAllowed calls: ' + ','.join(sorted(CALLS)) + '\nAllowed attributes: ' + ','.join(sorted(METHODS))
        assert not common.old.prior.strict_output_schema_issues(SCHEMA)
        size = len(common.old.prior.render_structured_codex_prompt(system, user))
        assert size <= common.old.prior.CODEX_TURN_INPUT_CHARACTER_LIMIT
        immutable_json(OUT / arm / 'preflight.json', {'request_characters': size, 'schema_issues': [], 'task_sha256': digest(task)})
        result = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(RUN + ':' + arm + ':update',
            source_ids=protocol['sources'], system_prompt=system, user_prompt=user, output_schema=SCHEMA)
        immutable_json(output, result)
        print(json.dumps({'arm': arm, 'library_update_saved': True}), flush=True)


def freeze(protocol):
    result = {}
    kernels = read(OUT / 'kernel_bank.json')
    for arm in ARMS:
        contracts = read(OUT / arm / 'teacher.json')['value']['contracts']
        assert len(contracts) == len(kernels)
        assert {c['kernel_name'] for c in contracts} == {k['name'] for k in kernels}
        normalized = []
        registry = read(OUT / 'observation_component_registry.json')
        feedback = read(OUT / 'teacher_task.json')['error_feedback_by_id']
        for raw_contract in contracts:
            contract = deepcopy(raw_contract)
            observation = contract.pop('observation')
            if observation['kind'] == 'reuse':
                original = registry[observation['component_id']]
                contract['observation_prompt'] = original['prompt']
                contract['observation_schema_json'] = original['schema_json']
                contract['observation_context_fields'] = original['context_fields']
            else:
                assert observation['parent_component_id'] is None or observation['parent_component_id'] in registry
                assert set(observation['error_feedback_ids']) <= set(feedback)
                contract['observation_prompt'] = observation['prompt']
                contract['observation_schema_json'] = observation['schema_json']
                contract['observation_context_fields'] = observation['context_fields']
            contract['observation_provenance'] = observation
            validate_adapter(contract['binding_program'], excluded_source_ids=protocol['sources'])
            jsonschema.Draft202012Validator.check_schema(json.loads(contract['observation_schema_json']))
            assert contract['observation_context_fields'] and set(contract['observation_context_fields']) <= {'facts', 'question', 'source_text'}
            normalized.append(contract)
        result[arm] = {c['kernel_name']: c for c in normalized}
    immutable_json(OUT / 'frozen_contracts.json', result)
    return result


def execute(protocol, ledger):
    contracts = freeze(protocol)
    public = {s['key']: s for s in read(common.OUT / 'corrected_TRAIN_views.json')}
    kernels = {k['name']: k for k in read(OUT / 'kernel_bank.json')}
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    client.exact_replay_roots = [native_direct.OUT]
    for sid, target in zip(protocol['new_native_check_sources'], common.TARGETS):
        source = public[sid]
        pub = source['views'][0]['public']
        kernel = kernels[target[2]]
        for arm in ARMS:
            path = OUT / 'results' / arm / (digest(sid) + '.json')
            if path.exists():
                continue
            row = {'source': sid, 'arm': arm, 'kernel': kernel['name'], 'fallback': False, 'reads': []}
            try:
                if arm == 'DirectRead':
                    schema = native_direct.schema_for(kernel)
                    prompt = native_direct.prior.SYSTEM
                    context = pub
                else:
                    contract = contracts[arm][kernel['name']]
                    grounded = apply_adapter(contract, kernel, pub, None, literal_context=literal_bindings({'public': pub}))
                    row['before_neural_read'] = {'grounded': grounded, 'execution': execute_alternatives(kernel, grounded)}
                    if row['before_neural_read']['execution']['handled']:
                        row.update(grounded=grounded, execution=row['before_neural_read']['execution'])
                        immutable_json(path, row)
                        continue
                    if not contract['requires_neural_read']:
                        row.update(grounded=grounded, execution=row['before_neural_read']['execution'])
                        immutable_json(path, row)
                        continue
                    schema = json.loads(contract['observation_schema_json'])
                    prompt = contract['observation_prompt']
                    context = {key: pub[key] for key in contract['observation_context_fields']}
                jsonschema.Draft202012Validator.check_schema(schema)
                task = native_direct.request(source, kernel) if arm == 'DirectRead' else {'current_case': context, 'unchanged_legal_program': kernel}
                response = client.generate(RUN + ':' + arm + ':' + sid, source=sid, purpose='skill_actor', thinking=False,
                    messages=render_messages(prompt, task, schema), schema=decoder_schema(schema)[0])
                row['reads'].append({'usage': response['usage'], 'elapsed_seconds': response['elapsed_seconds'],
                    'finish_reason': response['finish_reason'], 'cache_hit': response.get('cache_hit', False),
                    'reused_physical_call_id': response.get('reused_physical_call_id')})
                assert response['finish_reason'] == 'stop'
                value = json.loads(response['content'])
                row['observation'] = value
                jsonschema.validate(value, schema)
                if arm == 'DirectRead':
                    checked_witnesses(value['witnesses'], pub)
                    factual_inputs = {key: val for key, val in value['inputs'].items() if val is not None}
                    row['execution'] = kernel_execution(kernel, factual_inputs)
                else:
                    grounded = apply_adapter(contract, kernel, pub, value, literal_context=literal_bindings({'public': pub}))
                    row.update(grounded=grounded, execution=execute_alternatives(kernel, grounded))
            except Exception as exc:
                row.update(error=type(exc).__name__ + ': ' + str(exc), execution={'handled': False, 'answer': None})
            immutable_json(path, row)
            print(json.dumps({'arm': arm, 'source': sid, 'handled': row['execution']['handled'], 'error': row.get('error')}), flush=True)


def score(protocol):
    annotations = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    public = {s['key']: s for s in read(common.OUT / 'corrected_TRAIN_views.json')}
    rows = []
    for sid in protocol['new_native_check_sources']:
        source = public[sid]
        for arm in ARMS:
            row = read(OUT / 'results' / arm / (digest(sid) + '.json'))
            view = source['views'][0]
            row['native_score'] = grade_view(source['dataset'], view, annotations[sid][view['id']], row['execution']['answer'])
            rows.append(row)
    immutable_json(OUT / 'scored_results.json', {'rows': rows, 'goal_complete': False,
        'no_full_training_DEV_TEST': True, 'primary_outputs_preserved_before_grading': True})
    print(json.dumps({arm: sum(r['native_score']['correct'] for r in rows if r['arm'] == arm) for arm in ARMS}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preflight', 'acquire', 'execute', 'score'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol = prepare()
        for name, expected in protocol['source_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
        assert digest(read(OUT / 'teacher_task.json')) == protocol['task_sha256']
        assert digest(read(OUT / 'kernel_bank.json')) == protocol['kernel_bank_sha256']
        if args.phase == 'preflight':
            return
        if args.phase == 'score':
            score(protocol)
            return
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
            sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
        if args.phase == 'acquire':
            acquire(protocol, ledger)
        else:
            execute(protocol, ledger)


if __name__ == '__main__':
    main()
