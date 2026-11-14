"""Learn and freeze factual observation contracts from real grounding errors.

Original TRAIN only. The current event/persistence frontier is fixed before
learning; future case facts stay outside both matched teacher inputs. Native
semantics alignment is shared with DirectRead and is not a method contribution.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_grounding_frontier as base
from experiments import legal_skill_evolution_grounding_frontier_read as direct
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.binding_refinement import compile_observation_plan, consume_factual_observation
from legal_skill_guard.skill_evolution.case_observation_contract import check_bindings, execute_alternatives, validate_adapter
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import record_schema, grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS, execute_json


ROOT = base.ROOT
RUN = 'legal_skill_evolution_temporal_contract_learning_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = ('ProgramGuided', 'FreeHistory')
REFINEMENT = record_schema({'id': {'type': 'string'}, 'prompt': {'type': 'string'},
    'schema_json': {'type': 'string'}, 'projection_program': {'type': 'string'},
    'declared_cost': {'type': 'number', 'exclusiveMinimum': 0}})
CONTRACT = record_schema({'kernel_name': {'type': 'string'}, 'requires_neural_read': {'type': 'boolean'},
    'observation_context_fields': {'type': 'array', 'items': {'type': 'string', 'enum': ['facts', 'question', 'source_text']}},
    'observation_prompt': {'type': 'string'}, 'observation_schema_json': {'type': 'string'},
    'binding_program': {'type': 'string'}, 'refinements': {'type': 'array', 'items': REFINEMENT}})
SCHEMA = record_schema({'rationale': {'type': 'string'}, 'contracts': {'type': 'array', 'items': CONTRACT}})
COMMON = '''Learn a reusable factual observation interface around the SAME FOUR
legal kernels. Do not use tools. Do not edit their programs, statutory meanings,
native answers or the provided common task-semantic alignment. Weights stay frozen.
Both arms see the same original TRAIN development cases, actual paid reads and
feedback, legal programs and source text. Future two case facts and annotations
are WITHHELD. Do not branch on source IDs, names, concrete years or desired labels.
This isolates factual grounding/execution, not acquiring new statutes.

The actual read says a marriage that "has been ... since" began AND ended on the
same day. That end date has no case witness. Learn how to observe a source fact
in its own event/state form and lower it to the requested input ports, rather
than forcing the weak model to invent a complete legacy interval. Also preserve
directed qualifying-child facts; a person's own child and being somebody's child
are different arguments. Do not overfit the named cases or parse native answers.

For each kernel return a contract. Its initial factual observation can use a
source-native event view (onset, ongoing-state, explicit closed interval, dated
decree, directed statutory given, etc), direct fields, or another correct view.
observation_schema_json is a complete strict JSON Schema. Unknown/unread is not
False, zero, an empty resolved record or a fabricated date. Resolved extraction
of a finite case differs from extraction failure. Explicit statutory givens and
the shared native itemized-deduction interpretation are allowed. Case status
persistence must be supported by actual text/native case semantics; never assert
arbitrary future permanence. No extra zero-error/world-exhaustiveness condition.

observation_context_fields selects the public fields sent for the factual read;
both arms may use facts/question only or full source as useful. Source and kernel
definitions are always available to both teachers. Prompt/schema must request
facts and witnesses, never final legal eligibility or an answer. Each binding
must cite a nonempty verbatim CURRENT facts/question substring.

binding_program is a complete pure module apply(inputs,premises). inputs has
kernel, public_case:{facts,question}, literal_context and observation (null on
the first deterministic pass). Return exactly {bindings:[{inputs:{port:value},
witnesses:[{field:'facts'|'question',quote:verbatim}]}],unresolved:[reason]}.
Unknown ports are omitted. Declared nullable arrays and missing ports retain
their kernel meaning; do not blindly fill []/False. Multiple bindings are coherent
alternative views, not fabricated benchmark instances. unresolved lists relevant
uncertainty not represented by those alternatives. Never drop a possible view to
make the program agree. Do not implement statutory tests inside the adapter.
Pure text/regex and date normalization may avoid a neural call when sufficient.

The host executes every alternative with the unchanged program. If its outputs
agree and there is no unrepresented relevant uncertainty, it can finish without
resolving irrelevant facts. If outputs differ, refinements supplies optional
factual observations. Each projection_program apply(binding_inputs,premises)
returns exactly {observation:<factual value>} corresponding to that read, with
no native answer. Each refinement schema_json MUST define the factual response
as {observation:<same value type>,witnesses:[{field,quote}]}. Its prompt asks only
that factual observation, never the target statute result. The common planner
chooses an exact minimum worst-case DECLARED-cost sequence distinguishing legal
program outcomes; declared cost is a planning unit, NOT an actual fee. Uncovered
kernel branches and unmodeled read values remain unresolved. This component is
available to BOTH arms, and neither it nor quote/type checks certify factual
coverage/truth. You may return no refinements if not useful. Do not create an
artificial ambiguity or request extra reads just to exercise the planner.

No imports, nested functions, recursion, lambdas, IO or exception-as-answer.
Calendar primitives and allowed Python operations are shared. Keep code compact.
'''


def read(p):
    return json.loads(p.read_text())


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    old = read(base.OUT / 'protocol.json')
    bank = read(base.OUT / 'unbound_native_aligned_kernel_bank.json')
    baseline = read(direct.OUT / 'scored_results.json')
    cases = read(direct.OUT / 'fixed_development_cases.json')
    task = {'unchanged_common_kernels': bank, 'development_cases': cases,
        'actual_paid_reads_and_native_TRAIN_feedback': baseline,
        'common_native_semantics_correction': read(base.OUT / 'native_semantics_audit/interface_change.json'),
        'future_case_facts_and_annotations_withheld': True,
        'adapter_interface_code': (ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py').read_text(),
        'refinement_interface_code': (ROOT / 'legal_skill_guard/skill_evolution/binding_refinement.py').read_text()}
    before = base.old.rows(); assert not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'kernel_bank.json', bank)
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    files = [Path(__file__), Path(direct.__file__),
        ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'legal_skill_guard/skill_evolution/binding_refinement.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler.py',
        ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py',
        ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py',
        ROOT / 'legal_skill_guard/skill_evolution/clients.py',
        ROOT / 'legal_skill_guard/skill_evolution/ledger.py',
        ROOT / 'tests/test_skill_evolution_binding_refinement.py']
    for f in files:
        dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': old['sources'], 'learning_sources': old['development_mothers'],
        'frozen_original_TRAIN_transfer_sources': old['frozen_transfer_mothers'],
        'source_and_kernel_definitions_all_four_exposed': True,
        'historical_TRAIN_exposure_disclosed': True,
        'teacher_profile': old['teacher_profile'], 'executor_profile': old['executor_profile'],
        'task_sha256': digest(task), 'kernel_bank_sha256': digest(bank),
        'shared_native_semantics_alignment_not_a_method_gain': True,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    immutable_json(OUT / 'protocol.json', p)
    return p


def acquire(p, ledger):
    for arm in ARMS:
        path = OUT / arm / 'teacher.json'
        if path.exists():
            continue
        system = COMMON + ('\nUse the actual grounding error to learn source-native observations and evidence-bound lowering; use program outcome equivalence for missing/ambiguous inputs.\n' if arm == 'ProgramGuided' else
            '\nIndependently learn the strongest compact strategy from the same full history. You may freely use event/state abstractions, direct or relational views, pure parsing, program-aware queries, ambiguity, cached correct repairs and the shared refinement planner.\n')
        system += '\nAllowed calls: ' + ','.join(sorted(CALLS)) + '\nAllowed attributes: ' + ','.join(sorted(METHODS))
        user = json.dumps(read(OUT / 'teacher_task.json'), ensure_ascii=False, separators=(',', ':'))
        assert not base.old.prior.strict_output_schema_issues(SCHEMA)
        assert len(base.old.prior.render_structured_codex_prompt(system, user)) <= base.old.prior.CODEX_TURN_INPUT_CHARACTER_LIMIT
        result = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':' + arm + ':contracts',
            source_ids=p['sources'], system_prompt=system, user_prompt=user, output_schema=SCHEMA)
        immutable_json(path, result)
        print(json.dumps({'arm': arm, 'contracts_saved': True}), flush=True)


def apply(contract, kernel, public, observation):
    validate_adapter(contract['binding_program'])
    value = execute_json(contract['binding_program'], {'kernel': kernel,
        'public_case': {'facts': public['facts'], 'question': public['question']},
        'literal_context': literal_bindings({'public': public}), 'observation': observation}, {}, allow_helpers=True)
    fields = json.loads(kernel['input_fields_json'])
    for spec in fields.values():
        spec['type'] = direct.nominal_type(spec['type'])
    return check_bindings(value, fields, public)


def factual_read(client, call_id, src, kernel, prompt, schema, context_fields):
    jsonschema.Draft202012Validator.check_schema(schema)
    wire, _ = decoder_schema(schema)
    public = src['views'][0]['public']
    response = client.generate(call_id, source=src['key'], purpose='skill_actor', thinking=False,
        messages=render_messages(prompt, {'current_case': {k: public[k] for k in context_fields},
            'unchanged_legal_program': kernel}, schema), schema=wire)
    assert response['finish_reason'] == 'stop'
    value = json.loads(response['content']); jsonschema.validate(value, schema)
    return value, {'call_id': call_id, 'usage': response['usage'],
        'elapsed_seconds': response['elapsed_seconds'], 'cache_hit': response['cache_hit']}


def execute(p, ledger):
    contracts = {}
    for arm in ARMS:
        rows = read(OUT / arm / 'teacher.json')['value']['contracts']
        assert len(rows) == 4 and {r['kernel_name'] for r in rows} == {t[2] for t in base.TARGETS}
        contracts[arm] = {r['kernel_name']: r for r in rows}
        for r in rows:
            validate_adapter(r['binding_program'], excluded_source_ids=p['sources'])
            jsonschema.Draft202012Validator.check_schema(json.loads(r['observation_schema_json']))
            assert r['observation_context_fields'] and set(r['observation_context_fields']) <= {'facts', 'question', 'source_text'}
            for ref in r['refinements']:
                validate_adapter(ref['projection_program'])
                jsonschema.Draft202012Validator.check_schema(json.loads(ref['schema_json']))
    immutable_json(OUT / 'frozen_contracts.json', contracts)
    # Future facts are first loaded for current execution after both contracts
    # have been saved and checked. They were never part of either teacher task.
    public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    bank = {k['name']: k for k in read(OUT / 'kernel_bank.json')}
    client = FrozenExecutor(ledger, OUT, p['executor_profile'])
    client.exact_replay_roots = [direct.OUT]
    for sid, target in zip(p['sources'], base.TARGETS):
        src, kernel = public[sid], bank[target[2]]
        pub = src['views'][0]['public']
        for arm in (*ARMS, 'DirectRead'):
            path = OUT / 'results' / arm / (digest(sid) + '.json')
            if path.exists():
                continue
            result = {'source': sid, 'arm': arm, 'kernel': kernel['name'], 'fallback': False, 'reads': []}
            try:
                if arm == 'DirectRead':
                    schema = direct.schema_for(kernel)
                    # Preserve the exact previous wire for unchanged kernels;
                    # changed itemization semantics has a new actual request.
                    response = client.generate(RUN + ':DirectRead:' + sid, source=sid, purpose='skill_actor',
                        messages=render_messages(direct.SYSTEM, {'current_case': pub,
                            'unchanged_legal_program': kernel}, schema), thinking=False, schema=decoder_schema(schema)[0])
                    assert response['finish_reason'] == 'stop'
                    value = json.loads(response['content']); jsonschema.validate(value, schema)
                    from legal_skill_guard.skill_evolution.case_observation_contract import checked_witnesses, kernel_execution
                    checked_witnesses(value['witnesses'], pub)
                    result['observation'] = value
                    result['reads'].append({'call_id': RUN + ':DirectRead:' + sid,
                        'cache_hit': response['cache_hit'], 'reused_physical_call_id': response.get('reused_physical_call_id'),
                        'usage': response['usage'], 'elapsed_seconds': response['elapsed_seconds']})
                    result['execution'] = kernel_execution(kernel, {k: v for k, v in value['inputs'].items() if v is not None})
                else:
                    contract = contracts[arm][kernel['name']]
                    grounded = apply(contract, kernel, pub, None)
                    outcome = execute_alternatives(kernel, grounded)
                    result['before_neural_read'] = {'grounded': grounded, 'execution': outcome}
                    if not outcome['handled'] and contract['requires_neural_read']:
                        value, receipt = factual_read(client, RUN + ':' + arm + ':' + sid, src, kernel,
                            contract['observation_prompt'], json.loads(contract['observation_schema_json']),
                            contract['observation_context_fields'])
                        result['observation'] = value; result['reads'].append(receipt)
                        grounded = apply(contract, kernel, pub, value)
                        outcome = execute_alternatives(kernel, grounded)
                    result['grounded'] = grounded
                    if not outcome['handled'] and grounded['bindings'] and not grounded['unresolved'] and contract['refinements']:
                        observations = [{k: r[k] for k in ('id', 'declared_cost', 'projection_program')}
                            for r in contract['refinements']]
                        plan = compile_observation_plan(kernel, grounded['bindings'], observations)
                        result['refinement_plan'] = plan; node = plan['tree']
                        while node['kind'] == 'observe':
                            ref = next(r for r in contract['refinements'] if r['id'] == node['observation_id'])
                            value, receipt = factual_read(client, RUN + ':' + arm + ':refine:' + sid + ':' + ref['id'],
                                src, kernel, ref['prompt'], json.loads(ref['schema_json']), contract['observation_context_fields'])
                            result['reads'].append(receipt)
                            node = consume_factual_observation(node, ref['id'], value['observation'], value['witnesses'], pub)
                        result['refinement_terminal'] = node
                        outcome = {'handled': node['kind'] == 'answer', 'answer': node.get('answer')}
                    result['execution'] = outcome
            except Exception as exc:
                result['error'] = type(exc).__name__ + ': ' + str(exc)
                result['execution'] = {'handled': False, 'answer': None}
            immutable_json(path, result)
            print(json.dumps({'arm': arm, 'source': sid, 'handled': result['execution']['handled'],
                'error': result.get('error')}), flush=True)


def score(p):
    public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    annotations = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    rows = []
    for sid in p['sources']:
        for arm in (*ARMS, 'DirectRead'):
            row = read(OUT / 'results' / arm / (digest(sid) + '.json'))
            src = public[sid]; view = src['views'][0]
            row['native_score'] = grade_view(src['dataset'], view, annotations[sid][view['id']], row['execution']['answer'])
            rows.append(row)
    summary = {arm: {part: {'correct': sum(r['native_score']['correct'] for r in rows if r['arm'] == arm and r['source'] in ids),
        'mothers': len(ids)} for part, ids in [('learning', p['learning_sources']),
            ('frozen_original_TRAIN', p['frozen_original_TRAIN_transfer_sources'])]} for arm in (*ARMS, 'DirectRead')}
    immutable_json(OUT / 'scored_results.json', {'summary': summary, 'rows': rows, 'goal_complete': False})
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'acquire', 'execute', 'score'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        assert digest(read(OUT / 'teacher_task.json')) == p['task_sha256']
        assert digest(read(OUT / 'kernel_bank.json')) == p['kernel_bank_sha256']
        for name, h in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == h
        if phase == 'preflight':
            return
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
            sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
        if phase == 'acquire':
            acquire(p, ledger)
        elif phase == 'execute':
            execute(p, ledger)
        else:
            score(p)


if __name__ == '__main__':
    main()
