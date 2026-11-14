"""Actual diagnostic-guided refinement, with a same-information free teacher.

The completed eight-source acquisition is retained. Only those eight supply
update supervision. The next original-order TRAIN pair is fixed before calls;
previous post-freeze answers do not enter either teacher's input.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import fit, observe, execute_source_program
from legal_skill_guard.skill_evolution.repair_diagnosis import diagnose_repairs
from legal_skill_guard.skill_evolution.source_observations import signatures
from legal_skill_guard.skill_evolution.scoped_grammar import constructors
from legal_skill_guard.skill_evolution.span_compiler import METHODS, CALLS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories, attach_scored_theories
from legal_skill_guard.inference.codex_cli_client import (
    render_structured_codex_prompt, strict_output_schema_issues, CODEX_TURN_INPUT_CHARACTER_LIMIT)
from experiments.legal_skill_evolution_joint_acquisition_train import COMMON, SCHEMA as QUESTION_SCHEMA
from experiments.legal_skill_evolution_open_acquisition_train import (
    C_SPEC, FREE_SPEC, evaluate_source, source_material as original_source_material)


ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_source_functions_20261114'
PARENT = ROOT / 'artifacts/legal_skill_evolution_diagnosed_update_scalar_20261114'
SOURCE_SEED = ROOT / 'artifacts/legal_skill_evolution_source_function_integration_20261114/actual_source_library.json'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PUBLIC = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING = PUBLIC.with_name('grading.json')
ARMS = ('ConstraintAcquire', 'FreeUpdate')
read = lambda p: json.loads(Path(p).read_text())

SCHEMA = deepcopy(QUESTION_SCHEMA)
SCHEMA['properties']['source_functions'] = {'type': 'array', 'items': {'type': 'string'}}
SCHEMA['required'].append('source_functions')

SOURCE_CONTRACT = """The previously missing deterministic/concept-source update
call path is now executable for BOTH arms. The shared initial source_program is
an actual paid teacher program, not a host legal extractor. Its actual output is
provided as the common incoming source_output. source_functions adds/replaces
complete pure functions in that declared source_program. Its apply receives
inputs={source_text,source_spans:[{id,text}],source_output:<common actual seed
output>}, premises={}, and returns exactly {statements:[{term:<typed current
constructor list>,support_ids:[actual current unit IDs]}],complete:bool,
unresolved:[string]}. The returned acquired source output actually reaches
planning, neural observations and downstream composition. [] preserves the
shared program. All helpers must be supplied as complete pure functions. The
same source-function capability is available to FreeUpdate. It can also keep
its strongest complete Python composition or use neural concepts if useful.

Use source functions, narrow neural reads, or their combination to address the
actual TRAIN error, rather than unconditionally send the same semantic problem
to the weak executor. Do not classify a native hypothesis or return native answer
labels from source code. Do not infer absence from a parser's failure to match;
unknown/unread/unresolved is not a legal negative. A declared finite scalar sort
accepts only its supplied values; a new literal is text unless its acquired sort
is explicitly declared through the candidate vocabulary. Source-specific actors,
conditions and scope must remain tied to the current source.

The supplied source reviews are PARTIAL TRAIN supervision of actual observed
claims. They do not label unreviewed facts false or certify full source meaning.
In particular, no-retention wording must not produce a retention permission;
all-material disposal alone must not be classified as an EXPLICIT no-retention
statement when the operation explicitly excludes this inference. Both arms see
the same source/code/labels/history/diagnostic/reviews and shared acquired seed.
A completed downstream native answer does not certify omitted conditions or an
invented recipient class. Native interpretation may be learned separately while
preserving the source event and actor meanings.

The last frozen pair and its feedback are NOT supplied. Keep the declared next
pair untouched until freeze. The source seed has already been acquired and its
cost/exposure is inherited equally. Reusing its output does not establish C/U.
Source statements are fingerprinted by exact term and evidence set: unchanged
shared input, source-program new/changed, and composition are recorded separately.
These are provenance records, not a method-gain or semantic certificate. U remains
unestablished and its actual phi/G update dictionary is empty. Return a real
update and explain which reading/language/consumer defect it changes. Do not
weaken the suggested NoFit program or manufacture source-ID/company branches.
"""


class NoModel:
    def generate(self, *args, **kwargs):
        raise AssertionError('Offline shared-source verification cannot generate')


def initial_library():
    library = deepcopy(read(SOURCE_SEED))
    current = read(PARENT / 'ConstraintAcquire/learned.json')
    by_name = {c['name']: c for c in library['spec']['constructors']}
    for ctor in current['spec']['constructors']:
        if ctor['name'] in by_name and ctor != by_name[ctor['name']]:
            raise ValueError('Shared acquired constructor meanings disagree')
        if ctor['name'] not in by_name:
            library['spec']['constructors'].append(deepcopy(ctor)); by_name[ctor['name']] = ctor
    scalars = deepcopy(library['spec'].get('scalar_sorts', {}))
    for sort, values in current['spec'].get('scalar_sorts', {}).items():
        scalars[sort] = sorted(set(scalars.get(sort, []) + values))
    if scalars: library['spec']['scalar_sorts'] = scalars
    constructors(library['spec'])
    library['source_program_update'] = {'shared_acquired_seed': True,
        'program_sha256': digest(library['source_program']), 'changed_function_names': [],
        'not_independent_C_or_U_acquisition': True}
    return library


def offline_initial():
    folder = ROOT / 'artifacts' / RUN; library = initial_library()
    public = {s['key']: s for s in read(PUBLIC)}; grading = read(GRADING)
    keys = read(PARENT / 'protocol.json')['acquisition_sources']; checks = []
    for key in keys:
        old = read(PARENT / 'acquisition/FreeUpdate' / (key.replace(':', '_') + '.json'))
        v = old['observation']['visible_inputs']
        seed, seed_event = execute_source_program(library['source_program'], library['spec'],
            source_text=v['source_text'], units=v['units'], source_output=v['source_output'])
        observed = observe(NoModel(), 'offline-common-seed', key, library,
            source_text=v['source_text'], units=v['units'], source_output=seed)
        actual = evaluate_source(library, observed, public[key], grading[key])
        if seed != old['execution']['source_output'] or actual['execution']['source_output'] != seed:
            raise ValueError('Shared source asset changed its actual original output')
        if actual['feedback'] != old['feedback']:
            raise ValueError('Shared vocabulary union changed original Free feedback')
        if set(observed['execution']['acquired_source_program']['statement_origins'].values()) - {'unchanged_input'}:
            raise ValueError('An unchanged shared source seed must not claim new source roots')
        checks.append({'source': key, 'seed_output_sha256': digest(seed),
            'exact_original_Free_source_and_feedback_preserved': True,
            'unchanged_source_roots': len(observed['legacy_roots']),
            'source_program_trace': observed['execution']['acquired_source_program'],
            'new_model_requests': 0})
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'offline_initial_check.json').write_text(json.dumps({
        'shared_library_sha256': digest(library), 'checks': checks, 'new_model_requests': 0,
        'not_method_gain': True}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'offline_initial_sources': len(checks), 'new_model_requests': 0,
                      'shared_library_sha256': digest(library)}), flush=True)


def offline_wire():
    folder = ROOT / 'artifacts' / RUN; previous = initial_library()
    keys = read(PARENT / 'protocol.json')['acquisition_sources']
    public = {s['key']:s for s in read(PUBLIC)}
    sources = {key:public[key] for key in keys}
    supplied = {c['name']:c for c in previous['spec']['constructors']}
    from experiments.legal_skill_evolution_open_acquisition_train import functions
    paid = ROOT / 'artifacts/legal_skill_evolution_diagnosed_update_compact_20261114'
    source_functions = functions([read(paid / 'FreeUpdate/teacher.json')['value']['composition']])
    checks = []
    for arm in ARMS:
        raw = read(paid / arm / 'teacher.json')['value']; proposal = deepcopy(raw)
        # Offline transport fixture made ONLY from genuinely acquired functions
        # and already-shared constructor definitions, not a new teacher response.
        for ctor in proposal['new_constructors']:
            if ctor != supplied[ctor['name']]: raise ValueError('Cannot drop a nonidentical declaration')
        proposal['new_constructors'] = []
        proposal['source_functions'] = source_functions
        jsonschema.validate(proposal, SCHEMA)
        library, receipt = compile_proposal(previous, proposal, arm, sources,
            source_functions=proposal['source_functions'])
        outputs = []
        for key in keys:
            actual = read(PARENT / 'acquisition/FreeUpdate' / (key.replace(':','_')+'.json'))
            v = actual['observation']['visible_inputs']; seed = actual['execution']['source_output']
            output, trace = execute_source_program(library['source_program'], library['spec'],
                source_text=v['source_text'], units=v['units'], source_output=seed)
            if output != seed: raise ValueError('Actual paid-program wire fixture changed source semantics')
            if set(trace['statement_origins'].values()) - {'unchanged_input'}:
                raise ValueError('Shared unchanged outputs cannot be counted as new roots')
            outputs.append({'source':key,'source_output_sha256':digest(output),
                'unchanged_shared_root_count':len(output['statements']),'new_model_requests':0})
        checks.append({'arm':arm,'original_paid_proposal_sha256':digest(raw),
            'wire_fixture_sha256':digest(proposal),'fixture_is_not_a_new_teacher_response':True,
            'explicit_derivation':'Copy actual acquired Free functions; omit only identical constructors already in the common seed.',
            'source_program_update':library['source_program_update'],'receipt':receipt,'sources':outputs})
    folder.mkdir(parents=True,exist_ok=True)
    (folder / 'offline_wire_check.json').write_text(json.dumps({'checks':checks,
        'shared_library_sha256':digest(previous),'new_model_requests':0,
        'strict_schema_issues':strict_output_schema_issues(SCHEMA),'not_method_gain':True},
        ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'offline_wire_architectures':len(checks),'sources_each':len(keys),
        'new_model_requests':0}),flush=True)


def prepare():
    folder = ROOT / 'artifacts' / RUN
    if (folder / 'protocol.json').exists(): return folder, read(folder / 'protocol.json')
    if not read(PARENT / 'TERMINAL_PRESERVATION.json')['run_boundary_terminal']:
        raise ValueError('Preserve the completed preceding run first')
    with sqlite3.connect(LEDGER) as db: rows = db.execute('select * from calls order by id').fetchall()
    if any(r[6] == 'reserved' for r in rows): raise ValueError('Reconcile live physical requests first')
    initial = initial_library(); proof = read(folder / 'offline_initial_check.json')
    wire_proof = read(folder / 'offline_wire_check.json')
    if wire_proof['shared_library_sha256'] != digest(initial) or wire_proof['strict_schema_issues']:
        raise ValueError('Verify the current source-function teacher wire first')
    if proof['shared_library_sha256'] != digest(initial): raise ValueError('Verify the actual shared source asset first')
    prior = read(PARENT / 'protocol.json'); public = read(PUBLIC)
    old = read(ROOT / 'artifacts/legal_skill_evolution_source_program_acquisition_20261113/protocol.json')
    closed = read(ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113/protocol.json')
    older = read(ROOT / 'artifacts/legal_skill_evolution_joint_acquisition_evidence_set_20261114/protocol.json')
    excluded = set(old['teacher_sources'] + old['fixed_TRAIN_reuse_sources'] + closed['reuse_sources']
                   + older['acquisition_sources'] + older['reuse_sources'] + prior['reuse_sources'])
    excluded.update(seed['source'] for seed in initial['spec']['seeds'])
    reuse = [s['key'] for s in public if s['dataset'] == 'ContractNLI' and s['key'] not in excluded][:2]
    if len(reuse) != 2: raise ValueError('Two original-order TRAIN sources required')
    files = [Path(__file__).resolve(), ROOT / 'experiments/legal_skill_evolution_joint_acquisition_train.py',
        ROOT / 'experiments/legal_skill_evolution_open_acquisition_train.py',
        *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    data = [PUBLIC, GRADING, SOURCE_SEED, PARENT / 'protocol.json', PARENT / 'TERMINAL_PRESERVATION.json',
        PARENT / 'partial_retention_source_review.json', folder / 'offline_initial_check.json', folder / 'offline_wire_check.json',
        ROOT / 'artifacts/legal_skill_evolution_source_program_acquisition_20261113/protocol.json',
        ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113/protocol.json',
        ROOT / 'artifacts/legal_skill_evolution_joint_acquisition_evidence_set_20261114/protocol.json',
        *(PARENT / a / 'learned.json' for a in ARMS),
        *(PARENT / 'acquisition' / a / (key.replace(':', '_') + '.json')
          for a in ARMS for key in prior['acquisition_sources']),
        *(PARENT / 'ConstraintAcquire/fitted_execution' / (key.replace(':', '_') + '.json')
          for key in prior['acquisition_sources']),
        *(PARENT / 'upstream' / (key.replace(':', '_') + '.json') for key in prior['acquisition_sources'])]
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'parent_run': PARENT.name,
        'acquisition_sources': prior['acquisition_sources'], 'reuse_sources': reuse,
        'selection': 'Next2 original-order TRAIN excluding all prior fixed pairs/acquisition/seed examples, before generation. Historical full TRAIN exposure remains, not blind TEST.',
        'shared_initial_library_sha256': digest(initial),
        'shared_source_program_origin': 'Exact previously acquired Free source program; whole shared asset and all inherited acquisition/repair costs available equally to both arms.',
        'same_teacher_task_both_arms': True, 'U_dictionary': [], 'U_not_established': True,
        'executor_profile': prior['executor_profile'], 'teacher_profile': prior['teacher_profile'],
        'automatic_retries': 0, 'teacher_dispatch': 'serial', 'no_new_mechanical_call_cap': True,
        'no_full_training_DEV_TEST_paper': True,
        'source_snapshot': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    immutable_json(folder / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in rows})
    for name in ('base.json', 'grammar.json'):
        immutable_json(folder / name, read(PARENT / name))
    immutable_json(folder / 'shared/initial_library.json', initial)
    for key in p['acquisition_sources']:
        name = key.replace(':', '_') + '.json'
        immutable_json(folder / 'upstream' / name, read(PARENT / 'upstream' / name))
    for f in files:
        dst = folder / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    immutable_json(folder / 'protocol.json', p)
    return folder, p


def source_material(folder, public, key):
    pub, units, original = original_source_material(folder, public, key)
    path = folder / 'shared_source_outputs' / (key.replace(':', '_') + '.json')
    if not path.exists():
        seed = read(folder / 'shared/initial_library.json')
        output, event = execute_source_program(seed['source_program'], seed['spec'],
            source_text=pub['source_text'], units=units, source_output=original)
        immutable_json(path, {'source_output': output, 'execution': event,
            'common_to_both_arms': True, 'not_new_method_gain': True})
    return pub, units, read(path)['source_output']


def baseline():
    folder, p, _, public = setup(); initial = read(folder / 'shared/initial_library.json'); grading = read(GRADING)
    for key in p['acquisition_sources']:
        dst = folder / 'initial' / (key.replace(':', '_') + '.json')
        if dst.exists(): continue
        pub, units, shared = source_material(folder, public, key)
        observation = observe(NoModel(), RUN + ':initial:' + key, key, initial,
            source_text=pub['source_text'], units=units, source_output=shared)
        immutable_json(dst, {'source': key, 'observation': observation,
            **evaluate_source(initial, observation, public[key], grading[key])})


def setup():
    folder, p = prepare()
    for name, expected in {**p['source_snapshot'], **p['data_sha256']}.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen scientific input changed: ' + name)
    ledger = EvolutionLedger(LEDGER, run_id=RUN,
        sources={'train': p['acquisition_sources'] + p['reuse_sources'], 'dev': [], 'test': []}, binding=digest(p))
    return folder, p, ledger, {s['key']: s for s in read(PUBLIC)}


def teacher_request(arm):
    folder, p, ledger, public = setup(); grading = read(GRADING)
    previous = read(folder / 'shared/initial_library.json'); records = []; tasks = []
    previous_C = read(PARENT / 'ConstraintAcquire/learned.json')
    for key in p['acquisition_sources']:
        name = key.replace(':', '_') + '.json'
        histories = {a: read(PARENT / 'acquisition' / a / name) for a in ARMS}
        executed = read(PARENT / 'ConstraintAcquire/fitted_execution' / name)
        records.append({'observation': histories['ConstraintAcquire']['observation'],
                        'profile': histories['ConstraintAcquire']['profile'], 'feedback': executed['feedback']})
        initial = read(folder / 'initial' / name)
        tasks.append({'source': public[key], 'native_TRAIN_supervision': grading[key],
            'actual_common_initial_observation': initial['observation']['visible_inputs'],
            'actual_common_initial_execution': {k: initial[k] for k in ('execution', 'feedback')},
            'previous_C_observation': histories['ConstraintAcquire']['observation']['visible_inputs'],
            'previous_C_execution': executed,
            'previous_Free_execution': {k: histories['FreeUpdate'][k] for k in ('execution', 'feedback')}})
    diagnosis = diagnose_repairs(previous_C, records)
    diagnosis['relative_to'] = 'Preceding C library/observations BEFORE the new common source-program call path. Not a certificate about the new shared initial representation.'
    immutable_json(folder / 'diagnosis.json', diagnosis)
    task = {'tasks': tasks, 'shared_actual_initial_library': {k: v for k, v in previous.items() if k != 'fit'},
        'actual_previous_libraries_both_available': {a: {k: v for k, v in read(PARENT / a / 'learned.json').items() if k != 'fit'} for a in ARMS},
        'previous_C_diagnosis': diagnosis,
        'partial_TRAIN_source_reviews': read(PARENT / 'partial_retention_source_review.json'),
        'common_observed_signatures': {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'}},
        'fact_encoder_source': (ROOT / 'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'source_program_output_checks': 'Same typed terms/current support checks as all source programs; semantic reviews remain partial.',
        'no_previous_reuse_results_or_next_pair_material': True}
    body = json.dumps(task, ensure_ascii=False)
    if any(key in body for key in p['reuse_sources']): raise ValueError('Future TRAIN pair leaked into the teacher task')
    system = COMMON + '\n' + SOURCE_CONTRACT + '\n' + (C_SPEC if arm == 'ConstraintAcquire' else FREE_SPEC)
    system += '\n' + INSTRUCTION + '\nAllowed pure attributes: ' + ','.join(sorted(METHODS))
    system += '\nAllowed calls: ' + ','.join(sorted(CALLS))
    user = json.dumps(pack(task), ensure_ascii=False, separators=(',', ':'))
    args = {'source_ids': p['acquisition_sources'], 'system_prompt': system, 'user_prompt': user, 'output_schema': SCHEMA}
    issues = strict_output_schema_issues(SCHEMA); size = len(render_structured_codex_prompt(system, user))
    immutable_json(folder / arm / 'teacher_input.json', task)
    immutable_json(folder / arm / 'teacher_preflight.json', {'input_characters': size,
        'transport_limit': CODEX_TURN_INPUT_CHARACTER_LIMIT, 'schema_issues': issues,
        'task_sha256': digest(task), 'request_sha256': digest(args), 'new_model_requests': 0})
    if issues or size > CODEX_TURN_INPUT_CHARACTER_LIMIT:
        raise ValueError('Fix complete transport offline before dispatch, without truncation')
    return folder, p, ledger, args


def acquire(arm):
    folder, p = prepare(); dst = folder / arm / 'teacher.json'
    if dst.exists(): return
    folder, p, ledger, args = teacher_request(arm)
    result = FrozenTeacher(ledger, folder, p['teacher_profile']).propose(RUN + ':' + arm + ':teacher', **args)
    immutable_json(dst, result)


def compile_arm(arm):
    folder, p, _, public = setup(); dst = folder / arm / 'compiled.json'
    if dst.exists(): return
    proposal = read(folder / arm / 'teacher.json')['value']; jsonschema.validate(proposal, SCHEMA)
    library, receipt = compile_proposal(read(folder / 'shared/initial_library.json'), proposal, arm,
        {k: public[k] for k in p['acquisition_sources']}, source_functions=proposal['source_functions'])
    immutable_json(folder / arm / 'canonical_proposal.json', proposal)
    immutable_json(folder / arm / 'compilation_receipt.json', receipt)
    immutable_json(dst, library)


def run_stage(reuse=False):
    folder, p, ledger, public = setup(); stage = 'reuse' if reuse else 'acquisition'; grading = read(GRADING)
    if reuse and not (folder / 'library_freeze.json').exists(): raise ValueError('Freeze both learned libraries first')
    for arm in ARMS:
        if not reuse and (folder / arm / 'learned.json').exists(): continue
        library = read(folder / arm / ('learned.json' if reuse else 'compiled.json'))
        client = FrozenExecutor(ledger, folder, p['executor_profile']); observations = []; profiles = []
        for key in p['reuse_sources'] if reuse else p['acquisition_sources']:
            name = key.replace(':', '_') + '.json'; dst = folder / stage / arm / name
            if dst.exists():
                row = read(dst)
                if not reuse and 'profile' in row:
                    observations.append(row['observation']); profiles.append(row['profile'])
                continue
            pub, units, upstream = source_material(folder, public, key)
            histories = [] if reuse else [read(PARENT / 'acquisition' / a / name)['observation'] for a in ARMS] + [read(folder / 'initial' / name)['observation']]
            recovered = folder / 'prior_observations' / arm / name
            if not reuse and recovered.exists(): histories.append(read(recovered))
            try:
                o = observe(client, RUN + ':' + stage + ':' + arm + ':' + key, key, library,
                    source_text=pub['source_text'], units=units, source_output=upstream, previous_observations=histories,
                    save_event=lambda e: immutable_json(folder / stage / arm / 'events' / (digest(e['call_id']) + '.json'), e))
            except (ValueError, jsonschema.ValidationError) as error:
                immutable_json(dst, {'source': key, 'status': 'observation_rejected', 'error': str(error),
                    'all_native_views_retained_in_denominator': len(public[key]['views']), 'no_implicit_negative': True})
                print(json.dumps({'stage': stage, 'arm': arm, 'source': key, 'status': 'observation_rejected', 'error': str(error)}), flush=True)
                continue
            actual = evaluate_source(library, o, public[key], grading[key]) if reuse or arm == 'FreeUpdate' else None
            if actual is None:
                direct = deepcopy(library); direct['selected_rule_ids'] = library['suggested_rule_ids']
                actual = {'NoFit': evaluate_source(direct, o, public[key], grading[key])}
                direct_bodies = all(library['language']['signatures'][a['predicate']]['kind'] == 'observed'
                    for rule in library['language']['rules'] for a in rule['body'])
                enumerate_profile = admissible_direct_compositions if direct_bodies and not o['context']['unknown_groups'] else admissible_theories
                profile = enumerate_profile(library, o, contract_checker(library['spec'], public[key], grading[key]), timeout_seconds=90)
                if profile['status'] != 'complete':
                    immutable_json(folder / arm / 'incomplete_profiles' / name, profile)
                    raise ValueError('Incomplete profile; preserve actual reads and refine deterministic search offline')
                actual['profile'] = profile; profiles.append(profile); observations.append(o)
            elif reuse and arm == 'ConstraintAcquire':
                direct = deepcopy(library); direct['selected_rule_ids'] = library['suggested_rule_ids']
                actual['NoFit'] = evaluate_source(direct, o, public[key], grading[key])
            immutable_json(dst, {'source': key, 'observation': o, **actual})
            print(json.dumps({'stage': stage, 'arm': arm, 'source': key,
                'queries': o['execution']['planned_queries'], 'new_physical': o['execution']['new_physical_requests']}), flush=True)
        if not reuse:
            if arm == 'ConstraintAcquire':
                learned, result = fit(library, [attach_scored_theories(o, a) for o, a in zip(observations, profiles)], timeout_seconds=90)
                immutable_json(folder / arm / 'fit.json', result)
                if result['status'] != 'sat': raise ValueError('Inspect actual hard constraints before another model request')
                for observation in observations:
                    key = observation['context']['id']
                    immutable_json(folder / arm / 'fitted_execution' / (key.replace(':', '_') + '.json'),
                        evaluate_source(learned, observation, public[key], grading[key]))
            else: learned = library
            immutable_json(folder / arm / 'learned.json', learned)
    if not reuse:
        immutable_json(folder / 'library_freeze.json', {'libraries': {a: digest(read(folder / a / 'learned.json')) for a in ARMS},
            'reuse_sources': p['reuse_sources'], 'reuse_labels_not_used_in_update': True, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['offline', 'wirecheck', 'prepare', 'baseline', 'preflight', 'acquire', 'compile', 'train', 'reuse'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'offline': offline_initial()
        elif args.phase == 'wirecheck': offline_wire()
        elif args.phase == 'prepare': prepare()
        elif args.phase == 'baseline': baseline()
        elif args.phase == 'preflight':
            for arm in ARMS: teacher_request(arm)
        elif args.phase == 'acquire':
            for arm in ARMS: acquire(arm)
        elif args.phase == 'compile':
            for arm in ARMS: compile_arm(arm)
        else: run_stage(args.phase == 'reuse')
