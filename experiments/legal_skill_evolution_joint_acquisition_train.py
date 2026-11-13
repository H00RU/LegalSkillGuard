"""Current finite original-TRAIN acquisition stream with common initial state.

The previous six-source study is preserved. Two following original-order TRAIN
mothers supply acquisition feedback; the next two are frozen before acquisition
and used once afterwards. This is not a new full training/DEV/TEST study.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import compile_update, fit, observe, update_candidates
from legal_skill_guard.skill_evolution.scoped_grammar import constructors
from legal_skill_guard.skill_evolution.semantic_execution import decode_answers as decode_quoted
from legal_skill_guard.skill_evolution.semantic_operations import validate_operations
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.source_observations import signatures
from legal_skill_guard.skill_evolution.source_composition import validate_template_constructors
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure, occurrences, METHODS, CALLS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack
from legal_skill_guard.skill_evolution.theory_supervision import (
    admissible_theories, attach_scored_theories, diagnose_inputs)
from legal_skill_guard.inference.codex_cli_client import (
    render_structured_codex_prompt, strict_output_schema_issues, CODEX_TURN_INPUT_CHARACTER_LIMIT)
from experiments.legal_skill_evolution_open_acquisition_train import (
    C_SPEC, FREE_SPEC, SCHEMA as OLD_SCHEMA, functions, evaluate_source, source_material)

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_joint_acquisition_compiled_20261114'
ACQUISITION_RUN = ROOT / 'artifacts/legal_skill_evolution_joint_acquisition_train_20261114'
PARENT = ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PUBLIC = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING = PUBLIC.with_name('grading.json')
ARMS = ('ConstraintAcquire', 'FreeUpdate')
read = lambda path: json.loads(Path(path).read_text())
SCHEMA = deepcopy(OLD_SCHEMA)
del SCHEMA['properties']['scope']; SCHEMA['required'].remove('scope')
SCHEMA['properties']['reading_contracts'] = {'type': 'array', 'items': record_schema({
    'operation': {'type': 'string'}, 'scope': {'type': 'string', 'enum': ['window', 'focus_last']},
    'complete_source_absence_choices': {'type': 'array', 'items': {'type': 'string'}}})}
SCHEMA['required'].append('reading_contracts')

COMMON = r'''Learn a reusable legal source-rule acquisition update from the original TRAIN history supplied. Both arms start from the exact same actual acquired library, see identical sources, lawful native labels, observed source readings, current program outputs, errors and history, and may freely change predicates, planners, helpers, composition and consumer code. All inherited acquisition costs are shared and retained. Weights stay frozen. No synthetic examples or source/company-ID branches. Do not generate native labels or native-answer probes as source concepts. A native score or citation is not a certificate of source truth. A different contract's rule must not become global law.

Learn reusable source operations with meanings, choices and verbatim original TRAIN demonstrations. The frozen Qwen3-8B executor has thinking OFF. For each query it returns {choice,evidence_unit_ids:[actual current IDs]}. The host retrieves the full selected units verbatim and marks that origin. It does not fix the model's classification or certify its semantics. Canonical actual answers retain id,operation,choice,evidence:[{unit_id,quote,unit_occurrences,quote_origin}],source_semantics_verified:false. An old valid quote-reading can be reused only for the exact same operation meaning, ordered current source window and scope. Unknown is terminal for an unchanged question. Changed meanings need actual new readings.

planner_functions add/replace complete pure functions in the shared actual planner. apply(inputs,premises) returns only {queries:[{id,operation,unit_ids}]}. inputs={phase:'plan',source_text,source_spans:[{id,text}],source_output:<actual common upstream>,semantic_answers:<actual answers so far>}. The host repeats planning until no new queries occur. No query ID churn or alteration of an issued query's meaning/window. Broad source discovery and subsequent precise questions are allowed. Use current roles, modality, cross-clause scope and exceptions, not lexical whitelists of old contracts. The planner must not return final answers.

reading_contracts declares EVERY acquired operation once. scope=window classifies its whole supplied window; scope=focus_last classifies the LAST unit using the others as context. complete_source_absence_choices lists only choices whose stated meaning explicitly judges absence after examining the COMPLETE current source. These choices require window scope and all current units. Missing, unread and unknown never imply a negative. Other definite choices require current supporting unit IDs. Do not mix context clauses into an effect attributed to the focus. Original examples remain contiguous verbatim quotes, not rewritten words or concatenated passages.

The common source compiler remains an upstream asset. The downstream composition forms source-specific typed statements and support_ids from actual observations/current text. The same typed consumer answers native hypotheses; the original scorer is unchanged. New constructors have explicit {name,meaning,sort,arguments}; decision_functions add/replace complete pure consumer functions. Empty arrays are valid. Preserve meanings of existing constructors, current actors, copies and source event distinctions. Missing semantics remains unresolved. Source-only constraints are partial; unreviewed meanings and unknown are not false. Residual training errors are minimized and reported, never a zero-error installation requirement.

All acquired operations and rules must be useful beyond the supplied contracts. Each function string is a complete pure function/module; no imports, nested functions, lambda, network or files. Helpers and constants of the public programming language are available equally. Include enough raw-value/source provenance for exact arithmetic and source-specific parameter binding. Do not copy a contract-specific value into a reusable rule unconditionally. The actual U core is supplied as an available common research component, but its dictionary currently contains no acquired phi/G edit; do not invent evidence that U ran or that a representation collision occurred. Provide an actual independent acquisition/repair proposal and explain the learned semantic change.'''


def rows():
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        return db.execute('select * from calls order by id').fetchall()


def prepare():
    folder = ROOT / 'artifacts' / RUN
    if (folder / 'protocol.json').exists():
        return folder, read(folder / 'protocol.json')
    before = rows()
    if any(r[6] == 'reserved' for r in before):
        raise ValueError('Reconcile current requests before a safe continuation')
    boundary = read(ACQUISITION_RUN / 'TERMINAL_PRESERVATION.json')
    if not boundary['run_boundary_terminal']:
        raise ValueError('Preserve the previous actual run before scientific changes')
    old = read(ACQUISITION_RUN / 'protocol.json')
    files = [Path(__file__).resolve(), ROOT / 'experiments/legal_skill_evolution_open_acquisition_train.py',
             *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
             *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    data = [PUBLIC, GRADING, ACQUISITION_RUN / 'protocol.json', ACQUISITION_RUN / 'TERMINAL_PRESERVATION.json',
            ACQUISITION_RUN / 'base.json', ACQUISITION_RUN / 'grammar.json',
            ACQUISITION_RUN / 'ConstraintAcquire/teacher.json',
            ACQUISITION_RUN / 'ConstraintAcquire/teacher_input.json',
            ACQUISITION_RUN / 'ConstraintAcquire/canonical_proposal.json',
            ACQUISITION_RUN / 'ConstraintAcquire/renderer_recovery.json',
            ACQUISITION_RUN / 'shared/initial_library.json',
            *(ACQUISITION_RUN / 'initial' / (k.replace(':', '_') + '.json') for k in old['new_acquisition_sources']),
            *(PARENT / 'acquisition/ConstraintAcquire' / (k.replace(':', '_') + '.json') for k in old['historical_acquisition_sources'])]
    p = {**old, 'run_id': RUN, 'continuation_of': old['run_id'],
        'safe_boundary': boundary,
        'reused_paid_C_proposal': 'Exact original result; deterministic renderer punctuation recovery retained separately, no teacher reacquisition.',
        'failed_Free_request_kept_charged': old['run_id'] + ':FreeUpdate:teacher',
        'changed_Free_request': 'Remove redundant actual_reading_execution transport logs only. Original sources, supervision, canonical actual readings, source output, feedback and shared library remain identical; verify legal-task hash before dispatch.',
        'necessary_public_fixes': ['Validate inherited TRAIN examples against exact seed quotes already supplied to both arms.',
            'Recover only the unique scalar-token-preserving renderer JSON value under existing constructor types.',
            'Reject new legal literal occurrences justified only by an equal value elsewhere in old code.'],
        'source_snapshot': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    immutable_json(folder / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    for name in ('base.json', 'grammar.json', 'shared/initial_library.json',
                 'ConstraintAcquire/teacher.json', 'ConstraintAcquire/canonical_proposal.json',
                 'ConstraintAcquire/renderer_recovery.json'):
        immutable_json(folder / name, read(ACQUISITION_RUN / name))
    for key in p['new_acquisition_sources']:
        name = key.replace(':', '_') + '.json'
        immutable_json(folder / 'initial' / name, read(ACQUISITION_RUN / 'initial' / name))
        immutable_json(folder / 'upstream' / name, read(ACQUISITION_RUN / 'upstream' / name))
    for f in files:
        dst = folder / 'source_snapshot' / f.relative_to(ROOT); dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    immutable_json(folder / 'protocol.json', p)
    return folder, p


def setup():
    folder, p = prepare()
    for name, expected in {**p['source_snapshot'], **p['data_sha256']}.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen scientific input changed: ' + name)
    ledger = EvolutionLedger(LEDGER, run_id=RUN,
        sources={'train': p['acquisition_sources'] + p['reuse_sources'], 'dev': [], 'test': []}, binding=digest(p))
    return folder, p, ledger, {s['key']: s for s in read(PUBLIC)}


def initial():
    folder, p, ledger, public = setup(); library = read(folder / 'shared/initial_library.json')
    client = FrozenExecutor(ledger, folder, p['executor_profile'])
    for key in p['new_acquisition_sources']:
        dst = folder / 'initial' / (key.replace(':', '_') + '.json')
        if dst.exists(): continue
        pub, units, upstream = source_material(folder, public, key)
        try:
            o = observe(client, RUN + ':initial:' + key, key, library, source_text=pub['source_text'], units=units,
                source_output=upstream, save_event=lambda e: immutable_json(folder / 'initial/events' / (digest(e['call_id']) + '.json'), e))
        except (ValueError, jsonschema.ValidationError) as error:
            immutable_json(dst, {'source': key, 'status': 'observation_rejected', 'error': str(error),
                'all_native_views_retained_in_denominator': len(public[key]['views']), 'no_implicit_negative': True})
            print(json.dumps({'stage': 'initial', 'source': key, 'error': str(error)}), flush=True)
            continue
        actual = evaluate_source(library, o, public[key], read(GRADING)[key])
        immutable_json(dst, {'source': key, 'observation': o, **actual})
        print(json.dumps({'stage': 'initial', 'source': key, 'queries': o['execution']['planned_queries'],
            'native': [(v['view'], v['core_executed'], (v.get('score') or {}).get('correct')) for v in actual['feedback']['views']]}), flush=True)


def teacher_request(arm):
    folder, p, ledger, public = setup(); library = read(folder / 'shared/initial_library.json')
    tasks = []; grading = read(GRADING)
    for key in p['acquisition_sources']:
        old = (PARENT / 'acquisition/ConstraintAcquire' if key in p['historical_acquisition_sources'] else folder / 'initial') / (key.replace(':', '_') + '.json')
        actual = read(old)
        item = {'source': public[key], 'native_TRAIN_supervision': grading[key]}
        if 'observation' in actual:
            o = actual['observation']
            evaluation = evaluate_source(library, o, public[key], grading[key])
            item.update({'actual_previous_reading': o['visible_inputs'], 'actual_reading_execution': o['execution'],
                         'actual_source_output': evaluation['execution']['source_output'], 'actual_feedback': evaluation['feedback']})
        else:
            item['actual_previous_failure'] = actual
        tasks.append(item)
    task = {'tasks': tasks, 'shared_actual_initial_library': library,
        'common_source_asset': read(folder / 'base.json'),
        'common_observed_signatures': {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'}},
        'fact_encoder_source': (ROOT / 'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'derived_fact_encoding': 'Facts are exactly reconstructible from the complete supplied actual visible inputs; no added legal facts.',
        'previous_exact_representation_collisions': 0, 'same_original_material_and_supervision': True,
        'reuse_source_or_label_supplied': False}
    # Keep every legal input. Raw transport logs duplicate the validated actual
    # answers and add machine paths/timing, not source semantics. Both original
    # arms received those logs; the paid failed Free request remains charged.
    removed = []
    for item in task['tasks']:
        if 'actual_reading_execution' in item:
            value = item.pop('actual_reading_execution')
            removed.append({'source': item['source']['key'], 'transport_log_sha256': digest(value)})
    previous_task = read(ACQUISITION_RUN / 'ConstraintAcquire/teacher_input.json')
    for item in previous_task['tasks']:
        item.pop('actual_reading_execution', None)
    if digest(previous_task) != digest(task):
        raise ValueError('Changed Free request must retain exactly the same legal task')
    immutable_json(folder / arm / 'legal_information_equivalence.json', {
        'old_full_task_sha256': read(ACQUISITION_RUN / 'ConstraintAcquire/teacher_preflight.json')['task_sha256'],
        'legal_task_sha256_before': digest(previous_task), 'legal_task_sha256_after': digest(task),
        'removed_redundant_transport_logs': removed, 'all_legal_fields_equal': True,
        'new_model_requests_during_projection': 0})
    system = COMMON + '\n' + (C_SPEC if arm == 'ConstraintAcquire' else FREE_SPEC) + '\n' + INSTRUCTION
    system += '\nAllowed pure attributes: ' + ','.join(sorted(METHODS)) + '\nAllowed calls: ' + ','.join(sorted(CALLS))
    user = json.dumps(pack(task), ensure_ascii=False)
    args = {'source_ids': p['acquisition_sources'], 'system_prompt': system, 'user_prompt': user, 'output_schema': SCHEMA}
    issues = strict_output_schema_issues(SCHEMA); size = len(render_structured_codex_prompt(system, user))
    immutable_json(folder / arm / 'teacher_input.json', task)
    immutable_json(folder / arm / 'teacher_preflight.json', {'input_characters': size,
        'transport_limit': CODEX_TURN_INPUT_CHARACTER_LIMIT, 'schema_issues': issues,
        'task_sha256': digest(task), 'request_sha256': digest(args), 'new_model_requests': 0})
    if issues or size > CODEX_TURN_INPUT_CHARACTER_LIMIT:
        raise ValueError('Repair actual teacher transport offline; do not truncate')
    return folder, p, ledger, public, args


def acquire(arm):
    folder, p, ledger, public = setup()
    dst = folder / arm / 'teacher.json'
    if dst.exists(): return
    folder, p, ledger, public, args = teacher_request(arm)
    result = FrozenTeacher(ledger, folder, p['teacher_profile']).propose(
        RUN + ':' + arm + ':teacher', **args)
    immutable_json(dst, result)


def compile_arm(arm):
    folder, p, ledger, public = setup(); dst = folder / arm / 'compiled.json'
    if dst.exists(): return
    raw = read(folder / arm / 'teacher.json')['value']
    canonical = folder / arm / 'canonical_proposal.json'
    if not canonical.exists():
        immutable_json(canonical, raw)
        immutable_json(folder / arm / 'proposal_identity_receipt.json', {
            'raw_proposal_sha256': digest(raw), 'canonical_proposal_sha256': digest(raw), 'changes': []})
    proposal = read(canonical); jsonschema.validate(proposal, SCHEMA)
    if proposal != raw:
        receipt = read(folder / arm / 'renderer_recovery.json')
        if digest(raw) != receipt['original_teacher_value_sha256'] or digest(proposal) != receipt['canonical_proposal_sha256']:
            raise ValueError('The explicit unique-format recovery lost its actual teacher provenance')
    previous = read(folder / 'shared/initial_library.json')
    texts = {k: public[k]['views'][0]['public']['source_text'] for k in p['acquisition_sources']}
    inherited = {}
    for operation in proposal['operations']:
        for example in operation['examples']:
            if example['source'] in texts: continue
            matches = [s for s in previous['spec']['seeds'] if s['source'] == example['source']
                       and occurrences(s['quote'], example['quote'])]
            if not matches:
                raise ValueError('A demonstration needs current acquisition text or an actually supplied inherited TRAIN seed')
            inherited.setdefault(example['source'], []).append(matches[0]['quote'])
    # Each outside-cohort quote was separately contained in one supplied seed;
    # joining validation strings cannot authorize a cross-seed new quotation.
    texts.update({source: '\n\n'.join(dict.fromkeys(quotes)) for source, quotes in inherited.items()})
    immutable_json(folder / arm / 'inherited_example_validation.json', {
        'source_to_actual_supplied_seed_quotes': inherited, 'new_source_text_or_labels_supplied': False,
        'new_physical_requests': 0})
    validate_operations(proposal['operations'], texts)
    contracts = {r['operation']: r for r in proposal['reading_contracts']}
    if len(contracts) != len(proposal['reading_contracts']) or set(contracts) != {o['name'] for o in proposal['operations']}:
        raise ValueError('Declare every actual operation contract exactly once')
    for op in proposal['operations']:
        absence = contracts[op['name']]['complete_source_absence_choices']
        if len(set(absence)) != len(absence) or not set(absence) <= {c['name'] for c in op['choices']}:
            raise ValueError('Absence policies must name actual acquired choices')
        if absence and contracts[op['name']]['scope'] != 'window':
            raise ValueError('Complete-source absence requires window scope')
    planner = functions(proposal['planner_functions']); decisions = functions(proposal['decision_functions'])
    identities = {v for k in p['acquisition_sources'] for v in (k, public[k]['parent_id'])}
    for code in planner + decisions + ([proposal['composition']] if arm == 'FreeUpdate' else []):
        if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in identities for n in ast.walk(ast.parse(code))):
            raise ValueError('A source identity is not an applicability guard')
    semantic = {'constructors': proposal['new_constructors'], 'decision_functions': decisions}
    if arm == 'ConstraintAcquire':
        language = json.loads(proposal['composition'])
        language['signatures'] = {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'}, **language['signatures']}
        if any(language['constants'].get(s) for s in ('unit', 'term', 'query', 'json_node')):
            raise ValueError('Current opaque identities cannot be vocabulary')
        library = compile_update(previous, {**proposal, 'scope': 'window', 'planner_functions': planner,
            'language': language, 'renderers': json.loads(proposal['renderers_json'])}, texts, semantic_update=semantic)
        if not set(proposal['suggested_rule_ids']) <= {r['id'] for r in language['rules']}:
            raise ValueError('NoFit selected an unproposed rule')
        library['suggested_rule_ids'] = proposal['suggested_rule_ids']
        validate_template_constructors(library['renderers'], library['spec'])
    else:
        validate_procedure(proposal['composition'], allow_helpers=True); spec = deepcopy(previous['spec'])
        spec['constructors'].extend(deepcopy(proposal['new_constructors']))
        spec['decision_program'] = function_update(spec['decision_program'], decisions); constructors(spec)
        library = {'operations': proposal['operations'], 'planner_program': function_update(previous['planner_program'], planner),
            'scope': 'window', 'composition_program': proposal['composition'], 'spec': spec}
    library['operation_scopes'] = {n: r['scope'] for n, r in contracts.items()}
    library['complete_source_absence_choices'] = {n: r['complete_source_absence_choices'] for n, r in contracts.items()
                                               if r['complete_source_absence_choices']}
    immutable_json(dst, library)


def run_stage(reuse=False):
    folder, p, ledger, public = setup(); stage = 'reuse' if reuse else 'acquisition'
    if reuse and not (folder / 'library_freeze.json').exists(): raise ValueError('Freeze both arms first')
    grading = read(GRADING)
    for arm in ARMS:
        library = read(folder / arm / ('learned.json' if reuse else 'compiled.json'))
        client = FrozenExecutor(ledger, folder, p['executor_profile']); successful = []
        for key in p['reuse_sources'] if reuse else p['acquisition_sources']:
            dst = folder / stage / arm / (key.replace(':', '_') + '.json')
            if dst.exists():
                row = read(dst)
                if 'observation' in row: successful.append(row)
                continue
            pub, units, upstream = source_material(folder, public, key)
            prior = None
            if not reuse:
                oldpath = (PARENT / 'acquisition/ConstraintAcquire' if key in p['historical_acquisition_sources'] else folder / 'initial') / dst.name
                prior = read(oldpath).get('observation')
            try:
                o = observe(client, RUN + ':' + stage + ':' + arm + ':' + key, key, library,
                    source_text=pub['source_text'], units=units, source_output=upstream, previous_observation=prior,
                    save_event=lambda e: immutable_json(folder / stage / arm / 'events' / (digest(e['call_id']) + '.json'), e))
            except (ValueError, jsonschema.ValidationError) as error:
                immutable_json(dst, {'source': key, 'status': 'observation_rejected', 'error': str(error),
                    'all_native_views_retained_in_denominator': len(public[key]['views']), 'no_missing_or_false_facts_supplied': True})
                print(json.dumps({'stage': stage, 'arm': arm, 'source': key, 'status': 'observation_rejected', 'error': str(error)}), flush=True)
                continue
            # This is the actual candidate-construction entry. Empty learned
            # phi/G dictionary is recorded as empty, never called a U success.
            u = update_candidates(library, p['U_dictionary'], o,
                {k: public[k]['views'][0]['public']['source_text'] for k in p['acquisition_sources']})
            immutable_json(folder / stage / arm / 'update_candidates' / dst.name, u)
            row = {'source': key, 'observation': o}
            if arm == 'ConstraintAcquire' and not reuse:
                row['admission'] = admissible_theories(library, o, contract_checker(library['spec'], public[key], grading[key]), timeout_seconds=90)
                row['NoFit'] = evaluate_source({**library, 'selected_rule_ids': library['suggested_rule_ids']}, o, public[key], grading[key])
            else:
                row.update(evaluate_source(library, o, public[key], grading[key]))
            if arm == 'ConstraintAcquire' and reuse:
                row['NoFit'] = evaluate_source({**library, 'selected_rule_ids': library['suggested_rule_ids']}, o, public[key], grading[key])
            immutable_json(dst, row); successful.append(row)
            print(json.dumps({'stage': stage, 'arm': arm, 'source': key,
                'queries': o['execution']['planned_queries'], 'new_physical': o['execution']['new_physical_requests']}), flush=True)
        if not reuse:
            if arm == 'ConstraintAcquire':
                observations = [r['observation'] for r in successful]; admissions = [r['admission'] for r in successful]
                immutable_json(folder / arm / 'diagnosis.json', diagnose_inputs(observations, admissions, 'not_run'))
                if any(a['status'] != 'complete' for a in admissions): raise ValueError('Finite theory search incomplete; preserve actual status')
                learned, result = fit(library, [attach_scored_theories(o, a) for o, a in zip(observations, admissions)], timeout_seconds=90)
                immutable_json(folder / arm / 'fit.json', result)
                if result['status'] != 'sat': raise ValueError('No source-consistent composition; diagnose before another request')
                for row in successful:
                    key = row['source']
                    immutable_json(folder / arm / 'fitted_execution' / (key.replace(':', '_') + '.json'),
                                   evaluate_source(learned, row['observation'], public[key], grading[key]))
            else:
                learned = library
            immutable_json(folder / arm / 'learned.json', learned)
    if not reuse:
        immutable_json(folder / 'library_freeze.json', {'libraries': {a: digest(read(folder / a / 'learned.json')) for a in ARMS},
            'reuse_sources': p['reuse_sources'], 'reuse_labels_not_used_in_acquisition': True, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'initial', 'teacher-preflight', 'acquire', 'compile', 'train', 'reuse'])
    parser.add_argument('--arm', choices=ARMS); args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'prepare': prepare()
        elif args.phase == 'initial': initial()
        elif args.phase == 'teacher-preflight': teacher_request(args.arm)
        elif args.phase == 'acquire': acquire(args.arm)
        elif args.phase == 'compile': compile_arm(args.arm)
        else: run_stage(args.phase == 'reuse')
