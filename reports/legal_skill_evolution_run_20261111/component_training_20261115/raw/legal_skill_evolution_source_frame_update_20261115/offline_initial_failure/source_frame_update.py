"""Learn a positive source frame from native-equivalent semantic failures.

Original TRAIN only. Actual concept reads remain frozen-executor requests; the
host neither fixes their labels nor supplies missing legal distinctions. The
ordinary teacher receives the same frame feedback and acquisition capabilities.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
from itertools import product
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_projection_runtime as previous
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.inference.codex_cli_client import (strict_output_schema_issues,
    render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher, FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.relational_rules import validate_language
from legal_skill_guard.skill_evolution.semantic_operations import validate_operations
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
from legal_skill_guard.skill_evolution.source_function_patch import apply_function_edits
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure

ROOT = previous.ROOT
RUN = 'legal_skill_evolution_source_frame_update_20261115'
OUT = ROOT / 'artifacts' / RUN
ARMS = ('ConstraintAcquire', 'FreeUpdate')
FUNCTIONS = {'type': 'array', 'items': record_schema({'name': {'type': 'string'}, 'code': {'type': 'string'}})}
SCHEMA = record_schema({
    'rationale': {'type': 'string'}, 'new_operations_json': {'type': 'string'},
    'reading_scopes_json': {'type': 'string'}, 'planner_functions': FUNCTIONS,
    'source_function_edits': FUNCTIONS, 'relational_rule_edits_json': {'type': 'string'},
    'retired_rule_ids': {'type': 'array', 'items': {'type': 'string'}},
    'constant_additions_json': {'type': 'string'}, 'composition_functions': FUNCTIONS,
    'recommended_rule_ids': {'type': 'array', 'items': {'type': 'string'}}})
SYSTEM = '''Learn a reusable legal source acquisition update from a REAL source
semantic failure, even when the native benchmark answer is already correct.
Both arms receive the same complete acquisition sources, annotations, prior
libraries, tools/architecture and budget. No tools. Return strict schema JSON.

Actual issue: a source-program frame copied operative context into a definition
and confused recipient-owned with affiliate-owned employees. A different valid
clause made the native answer correct, so answer-only feedback cannot locate it.
Acquire POSITIVE source meanings (operative focus/effect and recipient owner),
not merely supported/refuted verdicts, old-root deletion or a label postprocessor.
Definitions may supply context but do not themselves license a new disclosure.
Do not merge affiliate employees into the recipient's own employees.

You may add small finite-valued semantic operations, change the learned planner,
edit pure source-reader functions, and change your composition. A reader gets
source units and its learned semantic question; it never gets a native answer.
Use actual focal units and exact source witnesses. Unknown stays unknown. The
new operative distinction must enter actual subsequent composition. Retain valid
disposal/retention behavior and prior legal conditions. The consumer and scorer
are frozen for BOTH arms. Do not use benchmark labels to invent source norms.

new_operations_json is a JSON list of {name,question,choices:[{name,meaning}],
examples:[{source,quote,choice}]}, using the supplied operation validator. Do not
list unknown as a choice: the host supplies it. reading_scopes_json maps each
NEW operation to focus_last or window. focus_last means the final unit is the
operative focus; preceding units are context, not additional assertion sites.
Do not change meanings of existing operations or repeat their old reads.
planner_functions and source_function_edits contain exact {name,code} top-level
pure Python definitions; existing apply(inputs,premises) may be replaced. Other
functions remain byte-identical. The current source_output and semantic_answers
are available to the planner. A new source reading is scheduled only by this
learned planner, not by host legal rules. No source IDs, case/entity names,
exact source-specific sentences, native verdicts or reference facts in code.
Use generic grammatical cues and actual current variables. No imports, nested
functions, classes, IO or reflection. Prebound re and supported pure methods only.

ConstraintAcquire: learn at least one genuinely new source-frame operation;
relational_rule_edits_json is a JSON list of at most SIX complete new/replacement
rules in the existing typed relation format. Existing head predicates/renderers
can express own/controlled-employee norms; no new constructor is needed. Existing
query_focus, query_choice, reader_query, root_support and typed frame predicates
bind actual source units. Copy all required support/conditions from actual source
evidence, never constants made from a source ID. retired_rule_ids removes obsolete
rules. constant_additions_json maps sorts to new finite SEMANTIC vocabulary.
The host learns a subset of these edited rules under the explicit source hard
constraints, then native TRAIN loss, edit count and complexity. Existing remaining
selected rules stay fixed; there is no unbounded whole-library search. Supply your
own recommended_rule_ids for a same-observation NoFit comparison. composition_functions
must be empty. Do not merely emit permission when the old effect is residual.

FreeUpdate: independently produce the strongest ordinary-teacher acquisition
update. You have the SAME semantic operations, planner, source-program functions,
all source feedback and full history. You may use the same source-frame design;
do not weaken your own architecture. composition_functions patches your existing
free composition program. Return [] for relational_rule_edits_json/retired_rule_ids,
{} for constant_additions_json and [] for recommended_rule_ids. Optional new
operations have the identical actual frozen-executor interface and cost accounting.
All corrections are shared runtime capabilities, not exclusive to the method.

Native TRAIN supervision is legal but cannot reverse a reviewed source meaning.
Unreviewed source claims stay unreviewed; this is partial source supervision.
No new data, synthetic examples, DEV/TEST access or new model configuration.
'''


def read(path):
    return json.loads(path.read_text())


def bank():
    train = previous.update.train
    public = {s['key']: s for s in read(train.parent.PREPARED / 'public.json')
              if s['dataset'] == 'ContractNLI' and s['split'] == 'train'}
    return public, read(train.parent.PREPARED / 'grading.json')


def frame_review(sid, source_output):
    """Partial source assertions; never consumes a native answer or label."""
    if ':4d4e550a' not in sid:
        return {'reviewed': False, 'failures': [], 'checks': [], 'native_answer_used': False}
    records = []
    for row in source_output['statements']:
        term = row['term']
        if not (isinstance(term, list) and len(term) >= 3 and term[0] == 'permission'):
            continue
        action = term[2]
        if not (isinstance(action, list) and len(action) == 3 and action[0] == 'disclose'):
            continue
        todo, own, affiliated = [action[2]], False, False
        while todo:
            node = todo.pop()
            if not isinstance(node, list) or not node:
                continue
            if node[0] in ('employees_of', 'internal_personnel_of'):
                serialized = json.dumps(node[1:], sort_keys=True)
                if 'controlled_entities_of' in serialized or 'affiliates_of' in serialized:
                    affiliated = True
                else:
                    own = True
            todo.extend(node[1:])
        if own or affiliated:
            records.append({'support': row['support_ids'], 'own': own, 'affiliated': affiliated})
    checks = [
        ('Affiliate employee permission is positively acquired at operative unit13',
         any(r['affiliated'] and 13 in r['support'] for r in records)),
        ('Unit13 does not license own employees without the separate unit20',
         not any(r['own'] and 13 in r['support'] and 20 not in r['support'] for r in records)),
        ('Definition unit14 alone is not an employee permission source',
         not any(14 in r['support'] and not set(r['support']) & {13, 20} for r in records)),
        ('The independent own-employee permission at unit20 remains',
         any(r['own'] and 20 in r['support'] for r in records))]
    return {'reviewed': True, 'checks': [{'check': k, 'passed': v} for k, v in checks],
            'failures': [k for k, v in checks if not v], 'native_answer_used': False,
            'not_full_source_truth_certificate': True, 'matched_employee_permissions': records}


def prepare():
    public, grading = bank()
    parent = read(previous.update.train.OUT / 'protocol.json')
    original_task = read(previous.update.train.OUT / 'B8/teacher_task.json')
    order = [t['source_id'] for t in original_task['tasks']]
    acquisition = [next(s for s in order if ':' + p in s) for p in ('4d4e550a', 'd9360f2a')]
    reuse = [s for s in order if s not in acquisition][:2]
    assert len(set(acquisition + reuse)) == 4
    libraries = {a: read(previous.OUT / a / 'library.json') for a in ARMS}
    task = {'current_libraries': libraries, 'acquisition_sources': [],
            'explicit_source_frame_supervision': {
                '4d4e550a': {'operative_unit13_employee_owner': 'recipient_affiliate',
                    'definition_unit14_alone_does_not_assert_permission': True,
                    'operative_unit20_employee_owner': 'recipient'}},
            'frame_review_code': Path(__file__).read_text().split('def frame_review', 1)[1].split('\ndef prepare', 1)[0],
            'shared_partial_reviews': {k: original_task.get(k) for k in
                ('shared_reviewed_source_scope_checks', 'shared_branch_authorization_review')},
            'operation_validator': (ROOT / 'legal_skill_guard/skill_evolution/semantic_operations.py').read_text(),
            'observation_encoder': (ROOT / 'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
            'original_B8_exposure_not_a_blind_split': True,
            'reuse_sources_not_in_current_teacher_task': True}
    before = []
    for sid in acquisition:
        histories = {a: read(previous.OUT / a / 'results' / previous.update.train.previous.old.name_for(sid)) for a in ARMS}
        task['acquisition_sources'].append({'source': sid, 'public': public[sid],
            'native_TRAIN_supervision': grading[sid], 'actual_old_results': histories})
        for arm, value in histories.items():
            before.append({'source': sid, 'arm': arm, 'native_correct': value['correct'],
                           'frame_review': frame_review(sid, value['source_output'])})
    immutable_json(OUT / 'teacher_task.json', task)
    prompt_size = len(render_structured_codex_prompt(SYSTEM + '\nYour arm: ConstraintAcquire',
        json.dumps(task, ensure_ascii=False, separators=(',', ':'))))
    assert prompt_size <= CODEX_TURN_INPUT_CHARACTER_LIMIT
    assert not strict_output_schema_issues(SCHEMA)
    baseline = []
    for sid in acquisition:
        for arm in ARMS:
            old = read(previous.OUT / arm / 'results' / previous.update.train.previous.old.name_for(sid))
            result = assessed(libraries[arm], old['observation'], sid, public, grading, task)
            assert result['native_correct'] == old['correct']
            baseline.append(result)
    immutable_json(OUT / 'offline_before.json', {'rows': baseline, 'new_model_calls': 0,
        'prompt_characters': prompt_size, 'strict_schema_issues': [],
        'native_equivalence_does_not_resolve_frame_errors': True})
    files = [Path(__file__), OUT / 'teacher_task.json']
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [previous.OUT / a / 'library.json' for a in ARMS]
    p = {'run_id': RUN, 'same_goal': True, 'sources': order, 'acquisition_sources': acquisition,
         'fixed_reuse_sources': reuse, 'teacher_profile': parent['teacher_profile'],
         'executor_profile': parent['executor_profile'], 'source_frame_feedback_triggers_update_even_if_native_correct': True,
         'original_TRAIN_only': True, 'original_B8_exposure_not_a_blind_split': True,
         'reuse_selection': 'First two original B8 task-order sources excluding the two acquisition sources; before proposals.',
         'no_new_DEV_TEST_or_full_training': True, 'goal_complete': False,
         'ledger_before': lineage.ledger_snapshot(),
         'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    immutable_json(OUT / 'protocol.json', p)
    immutable_json(OUT / 'before.json', before)
    for f in files:
        target = OUT / 'source_snapshot' / f.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.read_bytes())
    print(json.dumps({'acquisition': acquisition, 'fixed_reuse': reuse,
                      'before': before, 'task_characters': len(json.dumps(task))}))


def protocol():
    p = read(OUT / 'protocol.json')
    for name, expected in p['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    return p


def acquire():
    p = protocol()
    assert not strict_output_schema_issues(SCHEMA)
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p), teacher_concurrency=2)
    task = read(OUT / 'teacher_task.json')
    def one(arm):
        path = OUT / arm / 'teacher.json'
        if path.exists():
            return
        value = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':' + arm + ':source_frame',
            source_ids=p['acquisition_sources'], system_prompt=SYSTEM + '\nYour arm: ' + arm,
            user_prompt=json.dumps(task, ensure_ascii=False, separators=(',', ':')), output_schema=SCHEMA)
        immutable_json(path, value)
        print(json.dumps({'teacher_saved': arm}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one, arm) for arm in ARMS]
        for job in jobs:
            job.result()


def compile_patch(arm, value):
    library = deepcopy(read(previous.OUT / arm / 'library.json'))
    public, _ = bank()
    operations = json.loads(value['new_operations_json'])
    assert isinstance(operations, list)
    assert not {o['name'] for o in operations} & {o['name'] for o in library['operations']}
    library['operations'].extend(operations)
    validate_operations(library['operations'], {s: [v['public']['source_text'] for v in row['views']]
                                              for s, row in public.items()})
    scopes = json.loads(value['reading_scopes_json'])
    assert set(scopes) == {o['name'] for o in operations}
    assert all(v in ('window', 'focus_last') for v in scopes.values())
    library['operation_scopes'].update(scopes)
    library['planner_program'], planner_receipt = apply_function_edits(library['planner_program'], value['planner_functions'])
    library['source_program'], source_receipt = apply_function_edits(library['source_program'], value['source_function_edits'])
    rules = json.loads(value['relational_rule_edits_json'])
    if arm == 'ConstraintAcquire':
        assert operations and not value['composition_functions'] and len(rules) <= 6
        additions = json.loads(value['constant_additions_json'])
        for sort, values in additions.items():
            assert sort not in ('unit', 'term', 'query', 'json_node', 'text'), 'No opaque/source memorization vocabulary'
            library['language']['constants'][sort] = list(dict.fromkeys(library['language']['constants'].get(sort, []) + values))
        old_rules = {r['id']: r for r in library['language']['rules']}
        assert set(value['retired_rule_ids']) <= set(old_rules)
        for name in value['retired_rule_ids']:
            old_rules.pop(name)
        for rule in rules:
            old_rules[rule['id']] = rule
        library['language']['rules'] = list(old_rules.values())
        validate_language(library['language'])
        library['selected_rule_ids'] = [r for r in library['selected_rule_ids'] if r in old_rules]
        assert set(value['recommended_rule_ids']) <= set(old_rules)
    else:
        assert not rules and not value['retired_rule_ids'] and not json.loads(value['constant_additions_json'])
        library['composition_program'], _ = apply_function_edits(library['composition_program'], value['composition_functions'])
    validate_procedure(library['planner_program'], allow_helpers=True)
    return library, {'planner': planner_receipt, 'source': source_receipt,
                     'added_operations': [o['name'] for o in operations], 'edited_rule_ids': [r['id'] for r in rules]}


def assessed(library, observation, sid, public, grading, task):
    core = previous.update.train.previous.old.previous.prior.prior
    actual = core.evaluate_source(library, observation, public[sid], None)
    check = with_disposal_review(core.checker(library, public[sid], grading[sid]), sid,
        task['shared_partial_reviews'].get('shared_reviewed_source_scope_checks') or [],
        library['spec']['decision_program'], authorization_review=task['shared_partial_reviews'].get('shared_branch_authorization_review'))
    feedback = check(actual['execution']['source_output'])
    frame = frame_review(sid, actual['execution']['source_output'])
    return {'source': sid, 'source_output': actual['execution']['source_output'], 'feedback': feedback,
            'frame_review': frame, 'hard_source_pass': feedback.get('source_review_passed', True) and not frame['failures'],
            'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in feedback['views']),
            'unresolved': sum(not v['core_executed'] for v in feedback['views'])}


def validate():
    p = protocol()
    public, grading = bank()
    task = read(OUT / 'teacher_task.json')
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
    client = FrozenExecutor(ledger, OUT, p['executor_profile'])
    results = []
    for arm in ARMS:
        folder = OUT / arm
        try:
            if (folder / 'result.json').exists():
                results.append(read(folder / 'result.json'))
                continue
            raw = read(folder / 'teacher.json')['value']
            library, receipt = compile_patch(arm, raw)
            immutable_json(folder / 'compiled_library.json', library)
            immutable_json(folder / 'compilation.json', receipt)
            observations = {}
            def get_observation(sid):
                target = folder / 'observations' / (digest(sid) + '.json')
                if target.exists():
                    return read(target)
                prior = read(previous.OUT / arm / 'results' / previous.update.train.previous.old.name_for(sid))['observation']
                upstream = read(previous.update.train.parent.OUT / 'source_pass/upstream' / previous.update.train.previous.old.name_for(sid))['source_output']
                def event(value):
                    immutable_json(folder / 'read_events' / (digest(value['call_id']) + '.json'), value)
                obs = observe(client, RUN + ':' + arm + ':' + sid, sid, library,
                    source_text=public[sid]['views'][0]['public']['source_text'], units=prior['visible_inputs']['units'],
                    source_output=upstream, previous_observation=prior, save_event=event)
                immutable_json(target, obs)
                return obs
            for sid in p['acquisition_sources']:
                observations[sid] = get_observation(sid)
            nofit = None
            if arm == 'ConstraintAcquire':
                edited = receipt['edited_rule_ids']
                fixed = set(library['selected_rule_ids']) - set(edited)
                candidates = []
                for bits in product((False, True), repeat=len(edited)):
                    ids = fixed | {name for name, enabled in zip(edited, bits) if enabled}
                    candidate = deepcopy(library)
                    candidate['selected_rule_ids'] = sorted(ids)
                    rows = [assessed(candidate, observations[sid], sid, public, grading, task) for sid in p['acquisition_sources']]
                    prior_ids = set(read(previous.OUT / arm / 'library.json')['selected_rule_ids'])
                    rank = (-sum(r['native_correct'] for r in rows), len(ids ^ prior_ids),
                            sum(r['cost'] for r in library['language']['rules'] if r['id'] in ids), sorted(ids))
                    entry = {'rule_ids': sorted(ids), 'rows': rows, 'hard_source_pass': all(r['hard_source_pass'] for r in rows), 'rank': rank}
                    immutable_json(folder / 'fitting' / (''.join(map(lambda b: str(int(b)), bits)) + '.json'), entry)
                    if entry['hard_source_pass']:
                        candidates.append((rank, candidate))
                immutable_json(folder / 'fit_receipt.json', {'evaluated': 2 ** len(edited), 'feasible': len(candidates),
                    'acquisition_sources_only': True, 'source_hard_then_native_then_edits_and_complexity': True})
                if not candidates:
                    raise ValueError('No source-faithful fitted composition; retain paid reads without supplying a missing frame')
                library = min(candidates, key=lambda x: x[0])[1]
                unfit = deepcopy(library)
                unfit['selected_rule_ids'] = raw['recommended_rule_ids']
                nofit = [assessed(unfit, observations[sid], sid, public, grading, task) for sid in p['acquisition_sources']]
            # Freeze the selected candidate before any reuse request or score.
            immutable_json(folder / 'selected_before_reuse.json', {'library': library, 'library_sha256': digest(library),
                'selected_without_reuse': True, 'not_a_blind_split': True})
            acquisition = [assessed(library, observations[sid], sid, public, grading, task) for sid in p['acquisition_sources']]
            reuse = [assessed(library, get_observation(sid), sid, public, grading, task) for sid in p['fixed_reuse_sources']]
            result = {'arm': arm, 'acquisition': acquisition, 'fixed_reuse': reuse, 'NoFit_acquisition': nofit,
                      'goal_complete': False, 'DEV_TEST_loaded': False}
            immutable_json(folder / 'result.json', result)
            results.append(result)
        except Exception as error:
            failure = {'arm': arm, 'error': type(error).__name__ + ': ' + str(error),
                       'goal_complete': False, 'paid_artifacts_preserved': True}
            immutable_json(folder / 'validation_failure.json', failure)
            results.append(failure)
    immutable_json(OUT / 'result.json', {'arms': results, 'goal_complete': False, 'no_full_training_or_DEV_TEST': True})
    print(json.dumps([{'arm': r['arm'], 'error': r.get('error'), 'acquisition': [(v['native_correct'], v['hard_source_pass']) for v in r.get('acquisition', [])],
                      'reuse': [(v['native_correct'], v['hard_source_pass']) for v in r.get('fixed_reuse', [])]} for r in results]), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'acquire', 'validate'))
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'prepare': prepare, 'acquire': acquire, 'validate': validate}[args.phase]()
