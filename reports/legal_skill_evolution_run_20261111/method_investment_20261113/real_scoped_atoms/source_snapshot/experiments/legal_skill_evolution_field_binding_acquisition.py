"""Finite TRAIN correction of observed role/condition/action-binding errors.

Same Goal, data, models and ledger. No validation-source replay or full study.
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
FIELD_PARENT = ROOT / 'artifacts/legal_skill_evolution_field_binding_20261114'
RUN = 'legal_skill_evolution_field_binding_function_reuse_20261114'
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
replace/add functions in the ALREADY SUPPLIED
actual_current_libraries_both_available.FreeUpdate.composition_program.
This changes output serialization only: the unchanged helper bodies of your
actual previous Free program need not be reprinted. You may replace all
functions/add arbitrary pure helpers; every complete program expressible before
remains expressible. No fresh C proposal or reading has been added to this task.
The previous600-second failure had no recoverable output and is preserved.

The host assembles your actual complete program with the same function_update.
All source_functions, planner_functions, new_constructors and decision_functions
still update shared_actual_initial_library exactly as before. Redeclare any
constructor required by your assembled program that is absent from the shared
initial spec; the actual previous Free spec and all meanings are supplied.
apply(inputs,premises) receives inputs={source_text,source_spans,source_output,
semantic_answers}, premises={}; return exactly {statements:[{term:<typed current
term>,support_ids:[current IDs]}],complete:bool,unresolved:[str]}.
Return renderers_json='[]', suggested_rule_ids=[]. This is not a restriction to
small patches or particular neural operations. Use the strongest approach.
'''


def rows():
    return prior.rows()


def guard_nonoperative_consumer(program):
    """A record explicitly classified nonoperative cannot prove a legal answer."""
    tree = ast.parse(program); changed = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If): continue
        source = ast.unparse(node.test)
        for constructor, size, absent in (
            ('source_disclosure_binding', 12, 'not_an_operative_disclosure_norm'),
            ('source_disposal_binding', 10, 'not_a_disposal_action')):
            if source == "term[0] == '" + constructor + "' and len(term) >= " + str(size):
                node.test = ast.BoolOp(op=ast.And(), values=[node.test,
                    ast.parse("term[1] != '" + absent + "'", mode='eval').body])
                changed.append(constructor)
    assert sorted(changed) == ['source_disclosure_binding', 'source_disposal_binding']
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + '\n'


def offline():
    boundary = read(FIELD_PARENT / 'PROBE_BOUNDARY_PRESERVATION.json')
    assert boundary['client_terminal']
    before = rows(); assert not any(r[6] == 'reserved' for r in before)
    assert len(before) == boundary['ledger_rows']
    assert all(digest(r) == boundary['ledger_row_sha256'][r[0]] for r in before)
    for path in FIELD_PARENT.rglob('*.json'):
        rel = path.relative_to(FIELD_PARENT)
        if rel.parts[0] in {'initial','history','shared','upstream'} or str(rel) in {
            'base.json','grammar.json','partial_source_checks.json','teacher_task.json','offline_check.json'}:
            immutable_json(OUT / rel, read(path))
    for name in ('teacher.json','canonical_proposal.json','compilation_receipt.json',
                 'offline_candidate_check.json','offline_counterfactual_interface.json'):
        immutable_json(OUT / 'ConstraintAcquire' / name, read(FIELD_PARENT / 'ConstraintAcquire' / name))
    original = read(FIELD_PARENT / 'ConstraintAcquire/compiled.json'); lib = deepcopy(original)
    lib['spec']['decision_program'] = guard_nonoperative_consumer(original['spec']['decision_program'])
    assert {k:v for k,v in original.items() if k!='spec'} == {k:v for k,v in lib.items() if k!='spec'}
    assert {k:v for k,v in original['spec'].items() if k!='decision_program'} == {
        k:v for k,v in lib['spec'].items() if k!='decision_program'}
    immutable_json(OUT / 'ConstraintAcquire/compiled.json', lib)
    public = {s['key']:s for s in read(prior.PUBLIC)}; grading = read(prior.GRADING); checks=[]
    for path in sorted((FIELD_PARENT / 'acquisition/ConstraintAcquire').glob('*.json')):
        row = read(path); key = row['source']; o = row['observation']
        direct = deepcopy(lib); direct['selected_rule_ids'] = lib['suggested_rule_ids']
        actual = prior.evaluate_source(direct, o, public[key], grading[key])
        assert actual['execution']['source_output'] == row['NoFit']['execution']['source_output']
        output = actual['execution']['source_output']
        for view in actual['feedback']['views']:
            for i in view['execution']['value']['used_nodes']:
                term = output['statements'][i]['term']
                assert not (term[0]=='source_disclosure_binding' and term[1]=='not_an_operative_disclosure_norm')
                assert not (term[0]=='source_disposal_binding' and term[1]=='not_a_disposal_action')
        direct_bodies = all(lib['language']['signatures'][a['predicate']]['kind']=='observed'
            for rule in lib['language']['rules'] for a in rule['body'])
        enumerator = prior.admissible_theories if o['context']['unknown_groups'] else \
            prior.admissible_direct_compositions if direct_bodies else prior.admissible_program_compositions
        profile = enumerator(lib, o, prior.checker(lib,public[key],grading[key]), timeout_seconds=90)
        assert profile['status']=='complete'
        immutable_json(OUT/'ConstraintAcquire/profiles'/path.name, profile)
        immutable_json(OUT/'acquisition/ConstraintAcquire'/path.name,
            {'source':key,'observation':o,'NoFit':actual,'profile':profile})
        checks.append({'source':key,'actual_source_output_unchanged':True,
            'no_nonoperative_record_used_as_legal_evidence':True,
            'native_feedback_before':row['NoFit']['feedback'],'native_feedback_after':actual['feedback']})
    proof = read(FIELD_PARENT / 'unbound_Free_function_reuse_offline_proof.json')
    assert proof['all_original_complete_function_ASTs_exact'] and len(proof['checks'])==12
    immutable_json(OUT/'offline_resume_proof.json', {'both_original_teacher_requests_retained':True,
        'C_paid_proposal_reused_no_new_teacher':True,'C_probe_observations_reused_no_new_executor':True,
        'only_C_consumer_nonoperative_evidence_guards_changed':True,'guard_checks':checks,
        'Free_output_serialization_basis':proof,'complete_teacher_task_unchanged':
            digest(read(OUT/'teacher_task.json'))==digest(read(FIELD_PARENT/'teacher_task.json')),
        'fresh_C_data_not_added_to_Free_request':True,'old_ledger_rows_unchanged':len(before),'new_model_requests':0})
    assert rows()==before
    print('C paid proposal/probes retained; nonoperative consumer proof guard checked; Free codec12 outputs exact;0 new calls.',flush=True)


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
        FIELD_PARENT / 'PROBE_BOUNDARY_PRESERVATION.json', OUT / 'offline_resume_proof.json',
        OUT / 'ConstraintAcquire/compiled.json',
        PARENT / 'TERMINAL_PRESERVATION.json', OUT / 'shared/initial_library.json',
        OUT / 'base.json', OUT / 'grammar.json', OUT / 'partial_source_checks.json',
        *sorted((OUT / 'history').glob('*/*.json')), *sorted((OUT / 'initial').glob('*.json'))]
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'parent_run': FIELD_PARENT.name, 'C_paid_teacher_reused': True,
        'Free600s_failure_preserved': True, 'Free_serialization_base_is_previous_Free_program': True,
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
        proposal = deepcopy(raw)
        if arm == 'FreeUpdate':
            jsonschema.validate(raw, prior.FREE_SCHEMA)
            proposal.pop('composition_functions')
            base = read(OUT/'teacher_task.json')['actual_current_libraries_both_available']['FreeUpdate']['composition_program']
            proposal['composition'] = prior.function_update(base,prior.functions(raw['composition_functions']))
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
