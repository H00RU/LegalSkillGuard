"""The observation-learning branch of the authorized fixed five-library TRAIN run.

One reusable component library/planner/converter is updated cumulatively over
the original eight mixed batches. This replaces the former four per-kernel
prototype scripts; it does not change data, models, legal kernels or the ledger.
Only the SARA branch currently has an integrated immutable native backend.
Other five-dataset routes remain explicit integration work in the parent run.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import legal_skill_evolution_five_train as parent
from experiments import legal_skill_evolution_observation_reuse as history
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter, execute_alternatives, validate_adapter
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import record_schema, grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS, execute_json
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues, render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT


ROOT = parent.ROOT
RUN = 'legal_skill_evolution_observation_library_train_v1_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = ('ProgramGuided', 'FreeHistory')
read = parent.read
COMPONENT = record_schema({'id': {'type': 'string'}, 'meaning': {'type': 'string'},
    'prompt': {'type': 'string'}, 'schema_json': {'type': 'string'},
    'parent_component_ids': {'type': 'array', 'items': {'type': 'string'}},
    'error_feedback_ids': {'type': 'array', 'items': {'type': 'string'}}})
SCHEMA = record_schema({'rationale': {'type': 'string'},
    'components': {'type': 'array', 'items': COMPONENT},
    'planner_program': {'type': 'string'}, 'binding_program': {'type': 'string'}})
SYSTEM = '''Learn a reusable OBSERVATION AND CONVERSION LIBRARY for unchanged legal
programs, not model weights or a new legal solver. This is the authorized full
original TRAIN continuation, in the original eight mixed batches. Both arms get
identical law, lawful TRAIN feedback, common old programs and real raw failures.
Future case facts/questions/answers are not in this batch's update task; public
legal interfaces and source laws are shared. Historical TRAIN exposure is
disclosed. Never use TEST/DEV or tools. Do not assert the target legal query as
a fact. Do not memorize source IDs, names, amounts, dates or native answers.

Return ONE cumulative library, not one unrelated schema/prompt per case or
kernel. components are reusable source-native observations with exact schemas,
meanings, prompts and real parent/error provenance. A new source-only primitive
has empty error IDs; do not relabel it as error learning. The planner's pure
apply(inputs,premises) receives kernel and public_case and returns exactly
{component_ids:[declared IDs]}. Select factual distinctions actually needed by
the law, rather than dumping a verbose native Prolog graph on the weak model.
The host asks for the selected components jointly in a single full-case read.
Component schema_json is a complete inline JSON schema: no $ref/definitions.
Keep event observations compact. Observation prompts may use the actual kernel
and current question, but the claim cannot serve as evidence of a case event.

binding_program is one complete pure apply(inputs,premises) module. It receives
kernel, public_case:{facts,question}, literal_context, observation:{componentID:
actual JSON value} (or null before reading), and returns exactly
{bindings:[{inputs:{facts:[{predicate,arguments}],negative_givens:[{predicate,
arguments}],extraction_status:'complete'|'unread'},witnesses:[{field:'facts'|
'question',quote:verbatim}]}],unresolved:[reason]}. It may have helpers. Its only
function is factual lowering into the supplied author-native primitives; the
author statutes remain immutable. Both arms have the same code capacity.

Learn/update observation distinctions AND lowering from actual errors, preserve
useful components, and use shared factual primitives across distinct clauses.
Report true parents and which error changed what. An old component reference is
not proof of use: the host records actual selected fields, converter calls and
native facts. Native answer feedback is lawful TRAIN learning feedback, never
a generated factual feature. New source-only primitives are explicitly distinct
from transferred error repairs. Do not import an old case's constants.

Full finite extraction, source absence, and neural unread/ambiguity are distinct.
Unread is not false, zero or an empty completed list. Do not add a requirement to
prove every real-world negative: native statutes already define their own finite
failure. An explicitly stated marriage onset is a valid native event without an
invented end or an extra persistence gate. No query-derived death/date facts.
Positive event records require nonempty verbatim FACTS witnesses; question
witnesses can identify query roles/parameters but cannot establish case events.
Preserve coherent alternatives and all genuine unresolved reasons. Complete
schema/output is not a semantic certificate. Only source-stated legal givens
allowed by the given input interface can be asserted, in the original direction.

Do not silently preserve known mistakes: the shared review shows PG's supposed
4/4 included false Bob deaths inferred from a question. The strong free control
reaches4/4 after the common native onset-interface correction. That apparent
margin is NOT an established method advantage. Neither a generic IE+solver nor
blocking-led rereading is by itself new (ACL2021/NLLP2023/SymBa). Current training
must expose what is actually learned, updated and reused before any claim.

Python is pure, top-level helper functions, one apply entry; no imports, nested
functions, lambdas, IO, recursion or native-answer branching. All declared
component schemas must agree with their actual converter and native types.
Return a compact, runnable cumulative library.''' 


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    original = parent.prepare()
    assert not strict_output_schema_issues(SCHEMA)
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'legal_skill_guard/skill_evolution/sara_statute_kernel.py',
        ROOT / 'legal_skill_guard/skill_evolution/clients.py', ROOT / 'legal_skill_guard/skill_evolution/ledger.py']
    protocol = {'run_id': RUN, 'parent_five_dataset_run': parent.RUN, 'same_goal': True,
        'sources': original['train_sources'], 'batches': original['batches'],
        'executor_profile': original['executor_profile'], 'teacher_profile': original['teacher_profile'],
        'thinking': False, 'TEST_opened': False, 'new_source_or_seed': False,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'data_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [parent.OUT / 'protocol.json', parent.OUT / 'SARA_native_kernel_bank.json',
             parent.OUT / 'SARA_corrected_TRAIN_views.json', history.OUT / 'unbound_native_interface_review/result.json']},
        'currently_integrated_native_dataset': 'SARA_v2_Binary', 'not_all_five_training_finished': True,
        'all_old_raw_failures_and_costs_inherited': True, 'goal_complete': False}
    protocol['zero_dispatch_preflight_predecessor'] = 'legal_skill_evolution_observation_library_train_20261114'
    immutable_json(OUT / 'protocol.json', protocol)
    for p in files:
        target = OUT / 'source_snapshot' / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
    return protocol


def setup():
    protocol = prepare()
    for name, sha in {**protocol['source_sha256'], **protocol['data_sha256']}.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    public = {s['key']: s for s in read(parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {s['source']: s['kernel'] for s in read(parent.OUT / 'SARA_native_kernel_bank.json')}
    return protocol, ledger, public, kernels


def make_task(protocol, batch, public, kernels):
    path = OUT / f'B{batch}/teacher_task.json'
    if path.exists():
        return read(path)
    if batch > 1:
        assert (OUT / f'B{batch-1}/scored_results.json').exists(), 'Settle the previous batch before updating'
        assert (OUT / f'B{batch}/initial_scored_results.json').exists(), 'Observe the previous library on this batch before updating'
    keys = [k for k in protocol['batches'][batch-1] if k in public]
    grading = read(parent.PREPARED / 'grading.json')
    cards = []
    for sid, kernel in kernels.items():
        card = deepcopy(kernel)
        card['native_query'] = [{'predicate': c['predicate'], 'arguments': [
            x if isinstance(x, dict) else {'query_parameter_type': type(x).__name__}
            for x in c['arguments']]} for c in kernel['native_query']]
        cards.append(card)
    laws = {digest(s['views'][0]['public']['source_text']): s['views'][0]['public']['source_text'] for s in public.values()}
    prior = {a: read(OUT / f'B{batch-1}' / a / 'library.json') for a in ARMS} if batch > 1 else {}
    feedback = deepcopy(read(history.OUT / 'teacher_task.json')['error_feedback_by_id'])
    feedback.update({'query_is_not_a_positive_case_event': 'Actual cd2 PG observation invents Bob death2015 using only the target question as witness; keep the raw failure and learn factual-role separation.',
        'native_onset_gate_is_extra': 'Native author code accepts marriage onset with no invented end; both prior converters added an unsupported persistence gate. Common code correction makes Free4/4.'})
    feedback.update({f'native_batch{batch}_{i}': {'source': sid, 'public_source': public[sid],
        'native_TRAIN_supervision': grading[sid]} for i, sid in enumerate(keys)}
    )
    history_rows = []
    for b in range(1, batch):
        history_rows.extend(read(OUT / f'B{b}/scored_results.json')['rows'])
    task = {'batch': batch, 'batch_TRAIN_sources': keys, 'unchanged_legal_interfaces': cards,
        'source_laws': laws, 'current_libraries_both_available': prior,
        'previous_four_kernel_prototypes_shared': read(history.OUT / 'frozen_contracts.json'),
        'actual_common_corrected_prototypes': read(history.OUT / 'unbound_native_interface_review/corrected_contracts.json'),
        'actual_common_semantic_review': read(history.OUT / 'unbound_native_interface_review/result.json'),
        'original_actual_raw_native_errors': read(history.OUT / 'teacher_task.json')['actual_complete_raw_native_responses_including_failures'],
        'error_feedback_by_id': feedback, 'past_training_rows': history_rows,
        'current_pre_update_results': read(OUT / f'B{batch}/initial_scored_results.json') if batch > 1 else
            {'reason': 'No global library at B0; per-kernel prototypes remain explicitly shared history.'},
        'native_event_encoding': history.native_direct.prior.ONTOLOGY,
        'future_case_facts_questions_labels_withheld_from_this_update': True}
    assert unpack_programs(pack_programs(task)) == task
    immutable_json(path, task)
    return task


def acquire(protocol, ledger, public, kernels, batch):
    task = make_task(protocol, batch, public, kernels)
    user = json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':'))
    for arm in ARMS:
        path = OUT / f'B{batch}' / arm / 'teacher.json'
        if path.exists():
            continue
        difference = ('Learn joint program-conditioned factual distinctions and conversion updates from the real binding/execution errors, preserve coherent alternatives and explicitly share primitive components across clauses.'
            if arm == 'ProgramGuided' else
            'Independently generate the strongest ordinary teacher library with the SAME full information and code/representation/planning capacity. Program-aware extraction, error repair, shared views, pure parsing and all same modules are allowed. Do not deliberately weaken the control.')
        system = SYSTEM + '\n' + difference + '\n' + PROGRAM_INSTRUCTION
        system += '\nAllowed calls: ' + ','.join(sorted(CALLS)) + '\nAllowed attributes: ' + ','.join(sorted(METHODS))
        size = len(render_structured_codex_prompt(system, user))
        assert size <= CODEX_TURN_INPUT_CHARACTER_LIMIT
        immutable_json(path.with_name('preflight.json'), {'task_sha256': digest(task),
            'request_characters': size, 'schema_issues': strict_output_schema_issues(SCHEMA)})
        result = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(
            RUN + ':B' + str(batch) + ':' + arm + ':update', source_ids=keys_seen(protocol, batch),
            system_prompt=system, user_prompt=user, output_schema=SCHEMA)
        immutable_json(path, result)
        print(json.dumps({'batch': batch, 'arm': arm, 'cumulative_observation_library_saved': True}), flush=True)


def keys_seen(protocol, batch):
    # Historic shared prototypes have already seen original TRAIN; preserve
    # their lawful exposure in the source ledger rather than hiding it.
    return [s for s in protocol['sources'] if s.startswith('SARA_v2_Binary:')]


def freeze(protocol, batch):
    for arm in ARMS:
        folder = OUT / f'B{batch}' / arm
        if (folder / 'library.json').exists():
            continue
        library = read(folder / 'teacher.json')['value']
        jsonschema.validate(library, SCHEMA)
        components = {c['id']: c for c in library['components']}
        assert len(components) == len(library['components']) and components
        validate_adapter(library['planner_program'], excluded_source_ids=protocol['sources'])
        validate_adapter(library['binding_program'], excluded_source_ids=protocol['sources'])
        for cid, component in components.items():
            assert cid.isidentifier()
            schema = json.loads(component['schema_json'])
            jsonschema.Draft202012Validator.check_schema(schema)
            def check_inline(value):
                if isinstance(value, dict):
                    assert '$ref' not in value and '$defs' not in value and 'definitions' not in value
                    for child in value.values():
                        check_inline(child)
                elif isinstance(value, list):
                    for child in value:
                        check_inline(child)
            check_inline(schema)
        immutable_json(folder / 'library.json', library)


def execute(protocol, ledger, public, kernels, batch, *, initial=False):
    if not initial:
        freeze(protocol, batch)
    elif batch == 1:
        raise ValueError('B0 has no global observation library; do not invent a first-attempt result')
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    for sid in [k for k in protocol['batches'][batch-1] if k in public]:
        pub, kernel = public[sid]['views'][0]['public'], kernels[sid]
        for arm in ARMS:
            folder = OUT / f'B{batch}' / arm
            stage = 'initial_results' if initial else 'results'
            path = folder / stage / (digest(sid) + '.json')
            if path.exists():
                continue
            library = read((OUT / f'B{batch-1}' / arm if initial else folder) / 'library.json')
            row = {'source': sid, 'arm': arm, 'batch': batch, 'library_sha256': digest(library),
                'stage': 'pre_update_TRAIN' if initial else 'post_update_TRAIN', 'fallback': False, 'reads': []}
            try:
                plan = execute_json(library['planner_program'], {'kernel': kernel, 'public_case': pub}, {}, allow_helpers=True)
                assert set(plan) == {'component_ids'}
                ids = plan['component_ids']
                assert isinstance(ids, list) and len(ids) == len(set(ids))
                components = {c['id']: c for c in library['components']}
                assert set(ids) <= set(components)
                row['actual_component_ids'] = ids
                observation = {}
                if ids:
                    schema = record_schema({cid: json.loads(components[cid]['schema_json']) for cid in ids})
                    prompt = '\n\n'.join(components[cid]['prompt'] for cid in ids)
                    messages = render_messages(prompt, {'current_case': pub, 'unchanged_legal_program': kernel,
                        'component_meanings': {cid: components[cid]['meaning'] for cid in ids}}, schema)
                    count = client.tokenize(messages, thinking=False)['count']
                    assert count + protocol['executor_profile']['max_tokens'] <= protocol['executor_profile']['context_tokens'], 'Complete input exceeds frozen context; no truncation'
                    row['input_tokens'] = count
                    response = client.generate(RUN + ':B' + str(batch) + ':' + stage + ':' + arm + ':' + sid,
                        source=sid, purpose='skill_actor', thinking=False,
                        messages=messages,
                        schema=decoder_schema(schema)[0])
                    row['reads'].append({'finish_reason': response['finish_reason'], 'usage': response['usage'],
                        'elapsed_seconds': response['elapsed_seconds'], 'cache_hit': response.get('cache_hit', False)})
                    assert response['finish_reason'] == 'stop'
                    observation = json.loads(response['content'])
                    jsonschema.validate(observation, schema)
                contract = {'binding_program': library['binding_program']}
                row['observation'] = observation
                row['grounded'] = apply_adapter(contract, kernel, pub, observation,
                    literal_context=literal_bindings({'public': pub}))
                row['execution'] = execute_alternatives(kernel, row['grounded'])
            except Exception as error:
                with ledger.transaction() as db:
                    assert not db.execute("select 1 from calls where status='reserved'").fetchone(), 'Reconcile pending physical call'
                row.update(error=type(error).__name__ + ': ' + str(error),
                    execution={'handled': False, 'answer': None})
            immutable_json(path, row)
            print(json.dumps({'batch': batch, 'arm': arm, 'source': sid,
                'handled': row['execution']['handled'], 'error': row.get('error')}), flush=True)


def score(protocol, public, batch, *, initial=False):
    grading = read(parent.PREPARED / 'grading.json')
    rows = []
    for sid in [k for k in protocol['batches'][batch-1] if k in public]:
        for arm in ARMS:
            row = read(OUT / f'B{batch}' / arm / ('initial_results' if initial else 'results') / (digest(sid) + '.json'))
            src, view = public[sid], public[sid]['views'][0]
            rows.append({**row, 'native_score': grade_view(src['dataset'], view,
                grading[sid][view['id']], row['execution']['answer'])})
    immutable_json(OUT / f'B{batch}' / ('initial_scored_results.json' if initial else 'scored_results.json'), {'rows': rows, 'goal_complete': False,
        'pre_update': initial, 'historical_TRAIN_exposure_disclosed_not_a_blind_test': True,
        'semantic_truth_not_certified_by_native_accuracy': True})
    print(json.dumps({'batch': batch, 'correct': {a: sum(r['native_score']['correct'] for r in rows if r['arm'] == a) for a in ARMS}}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'acquire', 'freeze', 'execute', 'score', 'initial'])
    parser.add_argument('--batch', type=int, choices=range(1, 9), default=1)
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol, ledger, public, kernels = setup()
        if args.phase == 'prepare':
            return
        if args.phase == 'acquire':
            acquire(protocol, ledger, public, kernels, args.batch)
        elif args.phase == 'freeze':
            freeze(protocol, args.batch)
        elif args.phase == 'execute':
            execute(protocol, ledger, public, kernels, args.batch)
        elif args.phase == 'initial':
            execute(protocol, ledger, public, kernels, args.batch, initial=True)
            score(protocol, public, args.batch, initial=True)
        else:
            score(protocol, public, args.batch)


if __name__ == '__main__':
    main()
