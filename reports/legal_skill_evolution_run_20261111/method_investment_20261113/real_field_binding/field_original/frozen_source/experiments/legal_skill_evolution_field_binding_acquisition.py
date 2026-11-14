"""Finite TRAIN correction of observed role/condition/action-binding errors.

Same Goal, data, models and ledger. No validation-source replay or full study.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import legal_skill_evolution_positive_binding_acquisition as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe, execute_source_program, fit
from legal_skill_guard.skill_evolution.semantic_operations import prepare_queries
from legal_skill_guard.skill_evolution.teacher_transport import PROGRAM_INSTRUCTION, INSTRUCTION, pack_programs, unpack_programs
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues, render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT

ROOT = prior.ROOT
PARENT = prior.OUT
RUN = 'legal_skill_evolution_field_binding_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = prior.ARMS
read = prior.read
name_for = prior.name_for
TARGET_PREFIXES = ('4607', '78ad', '6fce', 'e82b', '8fb3')

PURPOSE = r'''This is one targeted incremental acquisition on the SAME12 original
TRAIN mothers after the positive-binding study. Both arms receive exactly the
same12 source texts, native TRAIN supervision, current independently acquired C
and Free libraries, their ACTUAL outputs, common initial program, and
explicit source-field counterexamples. The previous4 reuse sources, their
readings, labels and postscore reviews are NOT supplied and must not guide this
update. No new source, test label, synthetic example, configuration or weight
update. Correctness is not relaxed, and improvement is not guaranteed.
Full actual reading histories are supplied for the five targeted field/absence
failures (4607/78ad/6fce/e82b/8fb3). For the other seven preservation materials,
full sources, actual outputs and native feedback are supplied, without dumping
their unrelated hundreds of broad/fine reader traces. Both arms get exactly
this same explicit selection; complete original histories remain preserved.

The actual positive path now runs. The bottleneck is its FIELD BINDING, not JSON
completion or missing executor inputs. Examples in the supplied actual review:
- permission condition omitted a source confidentiality safeguard;
- Recipient employees were converted into controlled-company employees;
- return AND destruction of distinct materials was converted into an authorized
  OR choice, even where no extra written authorization existed;
- Project-end destruction, Agreement-end return, backup and legal-record
  retention qualifications were collapsed by one composite profile.
A complete current-G profile has already been computed on actual paid reads.
When the explicitly wrong TRAIN fields are rejected, current shared minimum
native loss is21/48 (independent-per-source optimistic minimum15). This proves a
limitation of CURRENT readings/candidates, not global representation failure.
Do not just refit those same profiles, drop every difficult norm, or invent a
source field because it improves a native answer. Unknown remains unresolved.

Learn source-semantic distinctions and their reusable composition. Replace
inadequate whole-window profiles with appropriate independently bindable roles,
conditions, action connections, action-to-trigger associations and material/
retention scopes WHERE that decomposition is needed. Preserve what each actual
source says, including a request-only duty or different actions under different
triggers. Use genuine cross-clause context/definitions. Return and destroy can
have different material scopes. A backup exception is not a broad retention
permission for everything; all-material disposal is not an explicit source
sentence forbidding retention. Preserve legal interpretation separately in the
native consumer. No native-answer operation, source-ID branch or inferred
absence from unknown/unread. Unsupported recipient profiles must not become a
positive permission just because a broad scout found a paragraph.

You may retain valid existing abilities, replace unsuitable interfaces, add
source functions or use fine neural operations with a real adaptive planner.
No requirement to preserve obsolete profile names or invent aliases/wrappers.
The strong Free arm may directly reuse/translate any supplied C or Free asset,
use identical neural decomposition, or write a stronger pure program. Both
arms have the same raw text, source functions, planners, constructors, consumer
updates and native supervision. Do not deliberately weaken an initial proposed
G or the ordinary-program comparison to create an effect.

Keep programs compact. source_functions replace/add complete pure functions
in the shared_actual_initial_library.source_program, which runs BEFORE neural
reads. It receives inputs={source_text,source_spans:[{id,text}],source_output},
premises={}; return exactly {statements:[{term,support_ids}],complete,unresolved}.
The planner receives actual semantic_answers and can choose meaningful new
questions/windows; no unchanged unknown retry or opaque-ID churn. Each operation
needs reading_contracts={operation,scope,complete_source_absence_choices}.
Actual executor answers are {id,choice,evidence:[{unit_id,quote}]}, using only
supplied unit anchors, NOT id/unit/text aliases. Reading scope is explicit per
operation. Examples must be contiguous verbatim passages of provided TRAIN.
Use actual constructor meanings and declared sorts. Nominal choice domains
are installed from acquired operation choices in BOTH arms; arbitrary strings,
unknown and native labels are NOT members. Text fields may preserve verbatim
current-source qualifiers, but do not hide a native classifier in them.
Neither software checks nor a citation nor native correctness certify all
English source semantics. This update does not claim U transfer; U remains empty.
'''

FREE = r'''composition_functions is an array of complete pure functions that
replace/add functions in shared_actual_initial_library.composition_program.
The host uses the existing exact function_update to assemble the actual full
program. You may replace all functions or reuse unchanged helpers; there is no
capacity restriction to a shallow patch. apply(inputs,premises) receives
inputs={source_text,source_spans,source_output,semantic_answers}, premises={};
return exactly {statements:[{term:<typed current term>,support_ids:[current IDs]}],
complete:bool,unresolved:[str]}. Return renderers_json='[]', suggested_rule_ids=[].
All other actual source/planner/operation/type/consumer capabilities are shared.
'''


def rows():
    return prior.rows()


def offline():
    assert read(PARENT / 'TERMINAL_PRESERVATION.json')['fixed_study_complete']
    before = rows(); assert not any(r[6] == 'reserved' for r in before)
    pp = read(PARENT / 'protocol.json'); tasks = []; checks = []
    public = {s['key']: s for s in read(prior.PUBLIC)}; grading = read(prior.GRADING)
    for name in ('base.json', 'grammar.json', 'shared/initial_library.json', 'partial_source_checks.json'):
        immutable_json(OUT / name, read(PARENT / name))
    for key in pp['acquisition_sources']:
        initial = read(PARENT / 'initial' / name_for(key))
        immutable_json(OUT / 'initial' / name_for(key), initial)
        actual = {}
        for arm in ARMS:
            row = read(PARENT / 'acquisition' / arm / name_for(key))
            executed = read(PARENT / arm / 'fitted_execution' / name_for(key)) if arm == 'ConstraintAcquire' else row
            full = {'source': key, 'observation': row['observation'],
                    'execution': executed['execution'], 'feedback': executed['feedback']}
            immutable_json(OUT / 'history' / arm / name_for(key), full)
            compact = prior.compact_observation(full['observation'])
            assert prior.restore_observation(key, compact) == full['observation']
            # Source output and native feedback are complete. Redundant solver
            # timing/technical traces are not teacher supervision.
            actual[arm] = {'observation': compact,
                'source_output': full['execution']['source_output'], 'native_feedback': full['feedback']}
            if not key.split(':')[1].startswith(TARGET_PREFIXES):
                actual[arm].pop('observation')
            checks.append({'source': key, 'arm': arm, 'actual_observation_roundtrip_exact': True})
        compact = prior.compact_observation(initial['observation'])
        assert prior.restore_observation(key, compact) == initial['observation']
        tasks.append({'source': public[key], 'native_TRAIN_supervision': grading[key],
            'actual_shared_initial': {'source_output': initial['execution']['source_output'],
                                      'native_feedback': initial['feedback']}, 'actual_current': actual})
    libraries = {a: {k: v for k, v in read(PARENT / a / 'learned.json').items() if k != 'fit'} for a in ARMS}
    task = {'tasks': tasks, 'shared_actual_initial_library': read(OUT / 'shared/initial_library.json'),
        'actual_current_libraries_both_available': libraries,
        'explicit_acquisition_source_field_reviews': read(PARENT / 'live_analysis/actual_source_review.json'),
        'actual_current_G_field_diagnosis': read(PARENT / 'live_analysis/field_constraint_diagnosis.json'),
        'original_partial_source_reviews': read(prior.PROBE / 'postscore_source_review.json'),
        'common_observed_signatures': {**prior.signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'}},
        'fact_encoder_source': (ROOT / 'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'all_semantic_outputs_and_feedback_retained_technical_solver_timing_not_supervision': True,
        'full_reading_histories_target_source_prefixes': list(TARGET_PREFIXES),
        'no_previous4_reuse_material_or_labels': True}
    text = json.dumps(task, ensure_ascii=False)
    assert not any(k in text for k in pp['reuse_sources'])
    packed = pack_programs(task); assert unpack_programs(packed) == task
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'offline_check.json', {'actual_observations': checks,
        'initial_observation_roundtrips': 12, 'full_task_and_program_transport_roundtrip_exact': True,
        'teacher_task_sha256': digest(task),
        'all12_sources_outputs_feedback_kept_full_reading_histories_target5': True,
        'packed_characters': len(json.dumps(packed, ensure_ascii=False, separators=(',', ':'))),
        'new_model_requests': 0, 'all_old_ledger_rows_unchanged': len(before)})
    assert before == rows()
    print(json.dumps(read(OUT / 'offline_check.json') | {'actual_observations': len(checks)}), flush=True)


def prepare():
    if (OUT / 'protocol.json').exists(): return read(OUT / 'protocol.json')
    proof = read(OUT / 'offline_check.json'); pp = read(PARENT / 'protocol.json'); before = rows()
    assert not any(r[6] == 'reserved' for r in before)
    sources = [Path(__file__), Path(prior.__file__),
        ROOT / 'experiments/legal_skill_evolution_open_acquisition_train.py',
        ROOT / 'experiments/legal_skill_evolution_diagnosed_update_train.py',
        ROOT / 'experiments/legal_skill_evolution_joint_acquisition_train.py',
        *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
        *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    data = [prior.PUBLIC, prior.GRADING, OUT / 'teacher_task.json', OUT / 'offline_check.json',
        PARENT / 'TERMINAL_PRESERVATION.json', OUT / 'shared/initial_library.json',
        OUT / 'base.json', OUT / 'grammar.json', OUT / 'partial_source_checks.json',
        *sorted((OUT / 'history').glob('*/*.json')), *sorted((OUT / 'initial').glob('*.json'))]
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'parent_run': PARENT.name,
        'acquisition_sources': pp['acquisition_sources'], 'reuse_sources': [],
        'no_previous4_reuse_retry': True, 'no_new_source_or_DEV_TEST_or_full_training': True,
        'executor_profile': pp['executor_profile'], 'teacher_profile': pp['teacher_profile'],
        'U_dictionary': [], 'teacher_dispatch': 'serial', 'automatic_retries': 0,
        'offline_proof_sha256': digest(proof),
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    for f in sources:
        target = OUT / 'source_snapshot' / f.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    immutable_json(OUT / 'protocol.json', p)
    return p


def setup():
    p = prepare()
    for path, value in {**p['source_sha256'], **p['data_sha256']}.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == value, path
    ledger = EvolutionLedger(prior.LEDGER, run_id=RUN,
        sources={'train': p['acquisition_sources'], 'dev': [], 'test': []}, binding=digest(p))
    return p, ledger, {s['key']: s for s in read(prior.PUBLIC)}


def teacher_request(arm):
    p, ledger, _ = setup()
    system = prior.COMMON + '\n' + PURPOSE + '\n' + (prior.C_SPEC if arm == 'ConstraintAcquire' else FREE)
    system += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
    system += '\nAllowed pure attributes: ' + ','.join(sorted(prior.METHODS))
    system += '\nAllowed pure calls: ' + ','.join(sorted(prior.CALLS))
    user = json.dumps(pack_programs(read(OUT / 'teacher_task.json')), ensure_ascii=False, separators=(',', ':'))
    schema = prior.SCHEMA if arm == 'ConstraintAcquire' else prior.FREE_SCHEMA
    issues = strict_output_schema_issues(schema)
    size = len(render_structured_codex_prompt(system, user))
    immutable_json(OUT / arm / 'preflight.json', {'schema_issues': issues, 'input_characters': size,
        'complete_task_sha256': digest(read(OUT / 'teacher_task.json')), 'new_model_requests': 0})
    if issues or size > CODEX_TURN_INPUT_CHARACTER_LIMIT: raise ValueError('Repair complete offline transport before dispatch')
    return p, ledger, {'source_ids': p['acquisition_sources'], 'system_prompt': system,
        'user_prompt': user, 'output_schema': schema}


def acquire():
    for arm in ARMS:
        if (OUT / arm / 'teacher.json').exists(): continue
        p, ledger, args = teacher_request(arm)
        result = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':' + arm + ':teacher', **args)
        immutable_json(OUT / arm / 'teacher.json', result)
        print(json.dumps({'arm': arm, 'actual_teacher_proposal_saved': True}), flush=True)


def compile_all():
    p, _, public = setup()
    initial = read(OUT / 'shared/initial_library.json')
    for arm in ARMS:
        if (OUT / arm / 'compiled.json').exists(): continue
        raw = read(OUT / arm / 'teacher.json')['value']
        proposal = prior.canonical_free_proposal(initial, raw) if arm == 'FreeUpdate' else raw
        jsonschema.validate(proposal, prior.SCHEMA)
        lib, receipt = compile_proposal(initial, proposal, arm,
            {k: public[k] for k in p['acquisition_sources']}, source_functions=proposal['source_functions'])
        checks = []
        for key in p['acquisition_sources']:
            pub, units, upstream = prior.source_material(OUT, public, key)
            output, trace = execute_source_program(lib['source_program'], lib['spec'],
                source_text=pub['source_text'], units=units, source_output=upstream)
            plan = prepare_queries(lib['planner_program'], lib['operations'], pub['source_text'], units,
                answers=[], source_output=output)
            checks.append({'source': key, 'source_output_sha256': digest(output), 'initial_plan': plan,
                           'neural_semantics_not_yet_verified': True})
        immutable_json(OUT / arm / 'canonical_proposal.json', proposal)
        immutable_json(OUT / arm / 'compiled.json', lib)
        immutable_json(OUT / arm / 'compilation_receipt.json', receipt)
        immutable_json(OUT / arm / 'offline_candidate_check.json', {'checks': checks, 'new_model_requests': 0})
        print(json.dumps({'arm': arm, 'compiled_operations': len(lib['operations']), 'offline_actual_sources': len(checks)}), flush=True)


def run_stage(probe=False):
    p, ledger, public = setup(); grading = read(prior.GRADING)
    for arm in ARMS:
        if not probe and (OUT / arm / 'learned.json').exists(): continue
        lib = read(OUT / arm / 'compiled.json')
        keys = [p['acquisition_sources'][-4], p['acquisition_sources'][-1]] if probe else p['acquisition_sources']
        client = FrozenExecutor(ledger, OUT, p['executor_profile'])
        client.exact_replay_roots = (PARENT, prior.READING_PARENT)
        for key in keys:
            dst = OUT / 'acquisition' / arm / name_for(key)
            if dst.exists(): continue
            pub, units, upstream = prior.source_material(OUT, public, key)
            history = [read(OUT / 'history' / a / name_for(key))['observation'] for a in ARMS]
            history.append(read(OUT / 'initial' / name_for(key))['observation'])
            observation = observe(client, RUN + ':acquisition:' + arm + ':' + key, key, lib,
                source_text=pub['source_text'], units=units, source_output=upstream,
                previous_observations=history,
                save_event=lambda event: immutable_json(OUT / 'acquisition' / arm / 'events' /
                    (digest(event['call_id']) + '.json'), event))
            immutable_json(OUT / 'acquisition' / arm / 'observations' / name_for(key), observation)
            if arm == 'FreeUpdate':
                actual = prior.evaluate_source(lib, observation, public[key], grading[key])
            else:
                direct = deepcopy(lib); direct['selected_rule_ids'] = lib['suggested_rule_ids']
                actual = {'NoFit': prior.evaluate_source(direct, observation, public[key], grading[key])}
                direct_bodies = all(lib['language']['signatures'][a['predicate']]['kind'] == 'observed'
                    for rule in lib['language']['rules'] for a in rule['body'])
                enumerator = prior.admissible_theories if observation['context']['unknown_groups'] else \
                    prior.admissible_direct_compositions if direct_bodies else prior.admissible_program_compositions
                profile = enumerator(lib, observation, prior.checker(lib, public[key], grading[key]), timeout_seconds=90)
                immutable_json(OUT / arm / 'profiles' / name_for(key), profile)
                if profile['status'] != 'complete':
                    raise ValueError('Paid observation saved; repair deterministic profile before more generation')
                actual['profile'] = profile
            immutable_json(dst, {'source': key, 'observation': observation, **actual})
            print(json.dumps({'arm': arm, 'source': key,
                'planned_queries': observation['execution']['planned_queries'],
                'new_requests': observation['execution']['new_physical_requests']}), flush=True)
        if probe: continue
        records = [read(OUT / 'acquisition' / arm / name_for(k)) for k in p['acquisition_sources']]
        if arm == 'ConstraintAcquire':
            lib, result = fit(lib, [prior.attach_scored_theories(r['observation'], r['profile']) for r in records],
                              prior_rule_ids=lib['suggested_rule_ids'], timeout_seconds=90)
            immutable_json(OUT / arm / 'fit.json', result)
            if result['status'] != 'sat': raise ValueError('Inspect exact accumulated constraints; no blind re-request')
            for row in records:
                key = row['source']
                immutable_json(OUT / arm / 'fitted_execution' / name_for(key),
                    prior.evaluate_source(lib, row['observation'], public[key], grading[key]))
        immutable_json(OUT / arm / 'learned.json', lib)
    if not probe:
        immutable_json(OUT / 'library_freeze.json', {'libraries': {a: digest(read(OUT / a / 'learned.json')) for a in ARMS},
            'no_reuse4_replay': True, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['offline','preflight','acquire','compile','probe','train'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'offline': offline()
        elif args.phase == 'preflight':
            for arm in ARMS: teacher_request(arm)
        elif args.phase == 'acquire': acquire()
        elif args.phase == 'compile': compile_all()
        else: run_stage(probe=args.phase == 'probe')
