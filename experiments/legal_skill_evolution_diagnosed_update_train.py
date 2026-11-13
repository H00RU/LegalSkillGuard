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
from legal_skill_guard.skill_evolution.open_acquisition import fit, observe
from legal_skill_guard.skill_evolution.repair_diagnosis import diagnose_repairs
from legal_skill_guard.skill_evolution.source_observations import signatures
from legal_skill_guard.skill_evolution.span_compiler import METHODS, CALLS
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories, attach_scored_theories
from legal_skill_guard.inference.codex_cli_client import (
    render_structured_codex_prompt, strict_output_schema_issues, CODEX_TURN_INPUT_CHARACTER_LIMIT)
from experiments.legal_skill_evolution_joint_acquisition_train import COMMON, SCHEMA
from experiments.legal_skill_evolution_open_acquisition_train import (
    C_SPEC, FREE_SPEC, evaluate_source, source_material)


ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_diagnosed_update_scalar_20261114'
PAID_UPDATE = ROOT / 'artifacts/legal_skill_evolution_diagnosed_update_compact_20261114'
PARENT = ROOT / 'artifacts/legal_skill_evolution_joint_acquisition_evidence_set_20261114'
PROFILES = ROOT / 'artifacts/legal_skill_evolution_joint_acquisition_compiled_20261114/direct_profile_recovery/profiles'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PUBLIC = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING = PUBLIC.with_name('grading.json')
ARMS = ('ConstraintAcquire', 'FreeUpdate')
read = lambda p: json.loads(Path(p).read_text())

REFINEMENT = '''This is the next REAL update, not a request to restate a design.
The supplied complete current-rule residual diagnosis establishes which native
mistakes no selection of CURRENT acquired rules can repair. It does NOT prove
source ambiguity, missing observations, source truth, or insufficient unrestricted
composition. Do not claim representation collisions: there are none certified.
Use the diagnosis to select an actual change to executable source concepts,
candidate composition/output language, or consumer interpretation. Both arms see
the exact same diagnostic, current raw sources, lawful supervision, both real
histories, and shared current C library; the free arm can use all of this freely.

For every proposed semantic change explain the actual failure and why the change
can generalize. Fix the concept/combination, not a source-specific label. A broad
choice bundling recipient roles, confidentiality form, trigger and material scope
may omit legal combinations or force a false stronger class. Acquire independent
distinctions or structured relations when the source needs them. Classification
demonstrations must themselves support the declared choice, not just contain the
right nouns. Keep source-specific conditions, ownership, and exceptions. Selection
of a source unit is not proof that every aspect of a composite choice is present.
Do not infer a new permission from an information definition, copying permission,
or a disposal instruction. Do not equate agreement termination, service endpoint
and nonformation events; native task interpretation belongs in the consumer and
must be justified separately without falsifying their source constructors.

Previous baseline programs and observations are real assets and are available to
both arms, including their failed source readings. Reuse or replace components
for actual semantic reasons. Changed meaning/window requires new real reads;
unchanged exact questions reuse existing readings, even if their answer was wrong.
Do not repair those answers in host code or supply desired classifications as facts.
There is no zero-native-error or zero-fallback requirement. Do not manufacture a
weaker suggested G for the NoFit control. In rationale identify the selected repair
layer, actual executable change and remaining unknowns. No future-pair material,
labels or prior-pair outcomes are supplied for this update.'''


def prepare():
    folder = ROOT / 'artifacts' / RUN
    if (folder / 'protocol.json').exists(): return folder, read(folder / 'protocol.json')
    terminal = read(PARENT / 'TERMINAL_PRESERVATION.json')
    if not terminal['run_boundary_terminal']: raise ValueError('Preserve the completed run first')
    if not read(PAID_UPDATE / 'TERMINAL_PRESERVATION.json')['run_boundary_terminal']:
        raise ValueError('Preserve the actual type-failure run before changing its execution binding')
    with sqlite3.connect(LEDGER) as db: rows = db.execute('select * from calls order by id').fetchall()
    if any(r[6] == 'reserved' for r in rows): raise ValueError('Reconcile live physical requests first')
    prior = read(PARENT / 'protocol.json'); public = read(PUBLIC)
    old = read(ROOT / 'artifacts/legal_skill_evolution_source_program_acquisition_20261113/protocol.json')
    closed = read(ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113/protocol.json')
    excluded = set(old['teacher_sources'] + old['fixed_TRAIN_reuse_sources'] + closed['reuse_sources']
                   + prior['acquisition_sources'] + prior['reuse_sources'])
    reuse = [s['key'] for s in public if s['dataset'] == 'ContractNLI' and s['key'] not in excluded][:2]
    if len(reuse) != 2: raise ValueError('Two original-order TRAIN sources required')
    files = [Path(__file__).resolve(), ROOT / 'experiments/legal_skill_evolution_joint_acquisition_train.py',
        ROOT / 'experiments/legal_skill_evolution_open_acquisition_train.py',
        *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    data = [PUBLIC, GRADING, PARENT / 'protocol.json', PARENT / 'TERMINAL_PRESERVATION.json',
        PAID_UPDATE / 'protocol.json', PAID_UPDATE / 'TERMINAL_PRESERVATION.json',
        PAID_UPDATE / 'actual_type_failure.json', PAID_UPDATE / 'finite_scalar_recovery.json',
        *(PAID_UPDATE / a / 'teacher.json' for a in ARMS),
        PAID_UPDATE / 'acquisition/ConstraintAcquire' / (prior['acquisition_sources'][0].replace(':', '_') + '.json'),
        PAID_UPDATE / 'recovered_observations/ConstraintAcquire' / (prior['acquisition_sources'][1].replace(':', '_') + '.json'),
        ROOT / 'artifacts/legal_skill_evolution_source_program_acquisition_20261113/protocol.json',
        ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113/protocol.json',
        PARENT / 'ConstraintAcquire/learned.json', PARENT / 'FreeUpdate/learned.json',
        *(PARENT / 'acquisition' / arm / (key.replace(':', '_') + '.json')
          for arm in ARMS for key in prior['acquisition_sources']),
        *(PROFILES / (key.replace(':', '_') + '.json') for key in prior['acquisition_sources']),
        *(PARENT / 'ConstraintAcquire/fitted_execution' / (key.replace(':', '_') + '.json')
          for key in prior['acquisition_sources']),
        *(PARENT / 'upstream' / (key.replace(':', '_') + '.json') for key in prior['acquisition_sources'])]
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'parent_run': PARENT.name,
        'acquisition_sources': prior['acquisition_sources'], 'reuse_sources': reuse,
        'selection': 'Next2 original-order TRAIN after excluding the previous source-program study, closed pairs and current8 histories; fixed before acquisition. Original full TRAIN exposure disclosed, not blind TEST.',
        'same_teacher_input_both_arms': True, 'shared_initial_library': 'actual preceding C learned library',
        'strong_control': 'Independent free update with identical raw source, supervision, both complete current histories, diagnostic, shared library and comparable teacher resources.',
        'inherited_cost': 'All previous source/compiler/reader/teacher costs remain; both share preceding assets.',
        'diagnosis_drives': 'Exhausted current candidates route to actual open reading/language/consumer refinement; no fictitious representation-conflict certificate.',
        'paid_update_reuse': 'Reuse both exact completed teacher responses, completed first source, and all20 paid executor responses. Finite nominal string sorts come only from acquired relational vocabularies; no unrestricted-text cast or fabricated semantics.',
        'U_dictionary': [], 'U_not_established': True,
        'executor_profile': prior['executor_profile'], 'teacher_profile': prior['teacher_profile'],
        'automatic_retries': 0, 'no_new_mechanical_call_cap': True,
        'no_full_training_DEV_TEST_paper': True,
        'source_snapshot': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    immutable_json(folder / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in rows})
    for file in ('base.json', 'grammar.json'):
        immutable_json(folder / file, read(PARENT / file))
    immutable_json(folder / 'shared/initial_library.json', read(PARENT / 'ConstraintAcquire/learned.json'))
    for arm in ARMS:
        for name in ('teacher.json', 'teacher_input.json', 'teacher_preflight.json'):
            immutable_json(folder / arm / name, read(PAID_UPDATE / arm / name))
    first = prior['acquisition_sources'][0].replace(':', '_') + '.json'
    proof = read(PAID_UPDATE / 'finite_scalar_recovery.json')['actual_source_checks'][0]
    if not proof['unchanged_first_source_output'] or not proof['unchanged_first_source_feedback']:
        raise ValueError('Reusing first-source scores requires exact output and feedback equivalence')
    immutable_json(folder / 'acquisition/ConstraintAcquire' / first,
                   read(PAID_UPDATE / 'acquisition/ConstraintAcquire' / first))
    second = prior['acquisition_sources'][1].replace(':', '_') + '.json'
    immutable_json(folder / 'prior_observations/ConstraintAcquire' / second,
                   read(PAID_UPDATE / 'recovered_observations/ConstraintAcquire' / second))
    for key in prior['acquisition_sources']:
        name=key.replace(':','_')+'.json'
        immutable_json(folder / 'upstream' / name, read(PARENT / 'upstream' / name))
    for f in files:
        dst = folder / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
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


def teacher_request(arm):
    folder, p, ledger, public = setup(); grading = read(GRADING)
    previous = read(folder / 'shared/initial_library.json'); records = []; tasks = []
    for key in p['acquisition_sources']:
        name = key.replace(':', '_') + '.json'
        histories = {a: read(PARENT / 'acquisition' / a / name) for a in ARMS}
        executed = read(PARENT / 'ConstraintAcquire/fitted_execution' / name)
        records.append({'observation': histories['ConstraintAcquire']['observation'],
                        'profile': read(PROFILES / name), 'feedback': executed['feedback']})
        tasks.append({'source': public[key], 'native_TRAIN_supervision': grading[key],
            'actual_histories': {a: {'visible_inputs': h['observation']['visible_inputs'],
                'execution': executed if a == 'ConstraintAcquire' else
                    {k: h[k] for k in ('execution', 'feedback')}} for a, h in histories.items()}})
    diagnosis = diagnose_repairs(previous, records)
    immutable_json(folder / 'diagnosis.json', diagnosis)
    libraries = {a: {k: v for k, v in read(PARENT / a / 'learned.json').items() if k != 'fit'} for a in ARMS}
    task = {'tasks': tasks, 'shared_actual_initial_library': {k: v for k, v in previous.items() if k != 'fit'},
        'common_source_asset': read(folder / 'base.json'),
        'actual_previous_libraries_both_available': libraries, 'diagnosis': diagnosis,
        'common_observed_signatures': {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'}},
        'fact_encoder_source': (ROOT / 'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'no_prior_reuse_outcomes_or_future_material': True,
        'derived_context_relations_reconstructible_from_supplied_visible_inputs': True}
    system = COMMON + '\n' + REFINEMENT + '\n' + (C_SPEC if arm == 'ConstraintAcquire' else FREE_SPEC)
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
        {k: public[k] for k in p['acquisition_sources']})
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
            histories = [] if reuse else [read(PARENT / 'acquisition' / a / name)['observation'] for a in ARMS]
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
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'preflight', 'acquire', 'compile', 'train', 'reuse'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'prepare': prepare()
        elif args.phase == 'preflight':
            for arm in ARMS: teacher_request(arm)
        elif args.phase == 'acquire':
            for arm in ARMS: acquire(arm)
        elif args.phase == 'compile':
            for arm in ARMS: compile_arm(arm)
        else: run_stage(args.phase == 'reuse')
