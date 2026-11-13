"""One source-supported output-language repair using existing TRAIN readings.

The two wrong inquiry-target assertions are actual acquisition paths, not new
tasks. This does not reexecute the scored future pair or claim independent C/U
gain. All acquired reader meanings and paid readings remain unchanged.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.maud_source_feedback import evaluate_view, view_checker
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import fit
from legal_skill_guard.skill_evolution.scoped_grammar import CONSTRUCTOR, constructors
from legal_skill_guard.skill_evolution.source_composition import validate_renderers, validate_template_constructors
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack
from legal_skill_guard.skill_evolution.theory_supervision import attach_scored_theories, diagnose_inputs
from legal_skill_guard.inference.codex_cli_client import (
    strict_output_schema_issues, render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT)
from experiments.legal_skill_evolution_MAUD_rule_acquisition import ROOT, FOLDER, PUBLIC, GRADING, LEDGER, read, name_for

RUN = 'legal_skill_evolution_MAUD_role_repair_20261114'
OUT = ROOT / 'artifacts' / RUN
BASE = ROOT / 'artifacts/legal_skill_evolution_MAUD_revision_20261114/library.json'
PREDICATE = 'emit_knowledge_inquiry_unspecified'
SCHEMA = record_schema({'rationale': {'type': 'string'},
    'new_constructors': {'type': 'array', 'items': CONSTRUCTOR},
    'replacement_renderer_json': {'type': 'string'},
    'decision_functions': {'type': 'array', 'items': {'type': 'string'}}})


def rows():
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        return db.execute('select * from calls order by id').fetchall()


def contains(value, term):
    return value == term or isinstance(value, list) and any(contains(v, term) for v in value)


def material():
    p = read(FOLDER / 'protocol.json')
    keys = p['acquisition_sources']
    public = {s['key']: s for s in read(PUBLIC) if s['key'] in keys}
    grading = {k: v for k, v in read(GRADING).items() if k in keys}
    return p, public, grading


def check(library, source, view, annotation, reviews):
    native = view_checker(library['spec'], source, view, annotation)
    def callback(output):
        feedback = native(output)
        violated = [r['id'] for r in reviews if any(contains(row['term'], r['forbidden_subterm'])
                    for row in output['statements'])]
        feedback.update({'source_review_passed': not violated,
                         'explicit_source_review_violations': violated,
                         'partial_review_not_full_semantic_certificate': True})
        if violated:
            feedback.update({'accepted': False, 'reason': 'explicit_partial_source_counterevidence'})
        return feedback
    return callback


def profiles(library, reviews):
    p, public, grading = material(); actual = []; observations = []
    for key in p['acquisition_sources']:
        source = public[key]
        for view in source['views']:
            record = read(FOLDER / 'acquisition/ConstraintAcquire' / name_for(key, view))
            selected = [r for r in reviews if r['source'] == key and r['view'] == view['id']]
            callback = check(library, source, view, grading[key][view['id']], selected)
            profile = admissible_direct_compositions(library, record['observation'], callback, timeout_seconds=90)
            assert profile['status'] == 'complete'
            actual.append(profile); observations.append(record['observation'])
    return observations, actual


def offline():
    assert read(FOLDER / 'TERMINAL_PRESERVATION.json')['fixed_study_complete']
    before = rows(); assert not any(r[6] == 'reserved' for r in before)
    p, public, grading = material(); library = read(BASE); reviews = []
    for key, source in public.items():
        if source['parent_id'] not in ('contract_13', 'contract_41'):
            continue
        view = next(v for v in source['views'] if v['id'] == 'Knowledge Definition-Answer')
        quote = view['public']['source_text']
        name = name_for(key, view)
        record = read(FOLDER / 'acquisition/ConstraintAcquire' / name)
        answer = next(a for a in record['observation']['visible_inputs']['answers']
                      if 'knowledge_structure' in a['id'])
        assert answer['choice'] == 'designated_holders_after_reasonable_inquiry_unspecified_targets'
        reviews.append({'id': source['parent_id'] + ':unsupported_inquiry_target', 'source': key,
            'view': view['id'], 'evidence_quote': quote,
            'forbidden_subterm': ['reasonable_inquiry_of', ['designated_company_knowledge_holders'], ['matter_in_question']],
            'judgment': 'The actual definition conditions the holders knowledge on inquiry, but supplies no inquiry target. Inquiry OF the named holders is unsupported. Do not deny the inquiry duty or classify unspecified targets as no duty.',
            'partial_only': True, 'unreviewed_fields_are_not_false': True})
    assert len(reviews) == 2
    observations, admissions = profiles(library, reviews)
    learned, result = fit(library, [attach_scored_theories(o, a) for o, a in zip(observations, admissions)],
                          prior_rule_ids=library['selected_rule_ids'], timeout_seconds=90)
    diagnosis = diagnose_inputs(observations, admissions, 'not_run')
    assert diagnosis['decision'] == 'local_theory_or_constraint_failure'
    assert len(diagnosis['local_failures']) == 2 and result['native_loss'] == 2
    assert rows() == before
    immutable_json(OUT / 'partial_source_reviews.json', reviews)
    immutable_json(OUT / 'before/profile_summary.json', {
        'diagnosis': diagnosis, 'source_admissible_native_loss': result['native_loss'],
        'native_correct_without_source_check': 12, 'native_views': 12,
        'actual_paid_readings_unchanged': True, 'no_representation_collision_asserted': True,
        'new_model_requests': 0, 'all_ledger_rows_unchanged': len(before)})
    immutable_json(OUT / 'before/fit.json', result)
    for o, a in zip(observations, admissions):
        immutable_json(OUT / 'before/profiles' / (o['context']['id'] + '.json'), a)
    print('Offline: two native-correct paths violate explicit source roles; current output mapping has irreducible2 native errors under those source checks.', flush=True)


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    before = rows(); assert not any(r[6] == 'reserved' for r in before)
    old, public, grading = material()
    assert read(OUT / 'before/profile_summary.json')['source_admissible_native_loss'] == 2
    files = [Path(__file__), *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
             *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    data = [BASE, FOLDER / 'protocol.json', FOLDER / 'TERMINAL_PRESERVATION.json',
            PUBLIC, GRADING, OUT / 'partial_source_reviews.json', OUT / 'before/profile_summary.json']
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'acquisition_sources': old['acquisition_sources'], 'reuse_sources': [],
        'teacher_profile': old['teacher_profile'], 'executor_profile': old['executor_profile'],
        'purpose': 'Repair the acquired output-language mapping, not native-label tuning or a new C/U score study',
        'new_executor_requests': 0, 'future_pair_not_used': True,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    for path in files:
        target = OUT / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(path.read_bytes())
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    immutable_json(OUT / 'protocol.json', p)
    return p


def setup():
    p = prepare()
    for name, expected in {**p['source_sha256'], **p['data_sha256']}.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen source/input changed: ' + name)
    ledger = EvolutionLedger(LEDGER, run_id=RUN,
        sources={'train': p['acquisition_sources'], 'dev': [], 'test': []}, binding=digest(p))
    return p, ledger


def request():
    p, ledger = setup(); _, public, grading = material(); library = read(BASE)
    task = {'actual_acquired_library': library,
        'current_partial_reviews': read(OUT / 'partial_source_reviews.json'),
        'actual_diagnosis': read(OUT / 'before/profile_summary.json'),
        'original_acquisition_materials': [public[k] for k in p['acquisition_sources']],
        'lawful_acquisition_annotations': grading,
        'actual_knowledge_readings': [read(FOLDER / 'acquisition/ConstraintAcquire' / name_for(k, v))['observation']['visible_inputs']['answers']
            for k in p['acquisition_sources'] for v in public[k]['views'] if v['id'] == 'Knowledge Definition-Answer'],
        'target_renderer': next(r for r in library['renderers'] if r['predicate'] == PREDICATE),
        'no_future_material_labels_or_new_examples': True}
    system = '''You are the existing legal skill teacher. Repair one concrete source-role error in the supplied actual acquired program. Do not use tools. The two native-correct acquired paths render inquiry OF the designated knowledge holders, while the actual learned choice explicitly says inquiry targets are unspecified. The source says knowledge AFTER reasonable inquiry, without naming the targets. The strict current-output diagnostic finds two local output/constraint failures; it is not a representation collision and the actual readings need no retry.
Return a minimal executable output-language repair: new_constructors with explicit meanings and nominal types; replacement_renderer_json for ONLY emit_knowledge_inquiry_unspecified; and complete pure decision_functions needed to recognize the new condition using the existing current typed roots. Preserve the existing constructors meanings, G, reader/planner definitions, source program, actor, matter, other renderers and native scorer. The replacement renderer must preserve every field except term[2], the inquiry condition. Add a faithful Condition that states an operative reasonable-inquiry condition without inventing its target. It may have no arguments or the existing Matter; no new participant or native-answer label field. Missing target must not erase the supported inquiry duty. Distinguish native classification from full source semantics. New constructor names/meanings are learned assets, not current-source facts by themselves.
The exact existing consumer and legal materials are provided. Do not create a default answer or bypass typed roots, overwrite old meanings, label unknown as false, infer any omitted clause, generate new examples, add source/company-ID branches or claim C/U success. Functions must be complete pure Python functions, no imports/nested functions/lambda/file/network/reflection. Return [] for unnecessary functions/constructors. Keep rationale concise and specific to this actual semantic repair. This does not establish an independent method advantage or a reusable U event.
''' + INSTRUCTION
    args = {'source_ids': p['acquisition_sources'], 'system_prompt': system,
            'user_prompt': json.dumps(pack(task), ensure_ascii=False, separators=(',', ':')),
            'output_schema': SCHEMA}
    issues = strict_output_schema_issues(SCHEMA)
    size = len(render_structured_codex_prompt(system, args['user_prompt']))
    immutable_json(OUT / 'teacher_input.json', task)
    immutable_json(OUT / 'request_preflight.json', {'strict_schema_issues': issues,
        'input_characters': size, 'request_sha256': digest(args), 'new_model_requests': 0})
    assert not issues and size < CODEX_TURN_INPUT_CHARACTER_LIMIT
    return p, ledger, args


def acquire():
    if (OUT / 'teacher.json').exists():
        print('Paid repair already saved; no repeat.'); return
    p, ledger, args = request()
    result = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':teacher:source_role_repair', **args)
    immutable_json(OUT / 'teacher.json', result)
    print('Actual teacher repair saved.', flush=True)


def compile_repair():
    setup(); library = read(BASE); proposal = read(OUT / 'teacher.json')['value']
    new = deepcopy(library); new['spec']['constructors'].extend(proposal['new_constructors'])
    schema = constructors(new['spec'])
    replacement = json.loads(proposal['replacement_renderer_json'])
    old = next(r for r in library['renderers'] if r['predicate'] == PREDICATE)
    expected = deepcopy(old); expected['term'][2] = replacement['term'][2]
    assert replacement == expected, 'Only the unsupported inquiry condition may change'
    condition = replacement['term'][2]
    assert condition[0] not in {c['name'] for c in library['spec']['constructors']}
    ctor = next(c for c in proposal['new_constructors'] if c['name'] == condition[0])
    assert ctor['sort'] == 'Condition' and ctor['arguments'] in ([], ['Matter'])
    new['renderers'] = [replacement if r['predicate'] == PREDICATE else deepcopy(r) for r in library['renderers']]
    new['spec']['decision_program'] = function_update(library['spec']['decision_program'], proposal['decision_functions'])
    validate_renderers(new['language'], new['renderers']); validate_template_constructors(new['renderers'], new['spec'])
    immutable_json(OUT / 'candidate_library.json', new)
    immutable_json(OUT / 'actual_repair_event.json', {
        'physical_teacher_call': RUN + ':teacher:source_role_repair',
        'before_library_sha256': digest(library), 'after_library_sha256': digest(new),
        'changed_components': [k for k, a, b in [('renderers', library['renderers'], new['renderers']),
            ('constructors', library['spec']['constructors'], new['spec']['constructors']),
            ('decision_program', library['spec']['decision_program'], new['spec']['decision_program'])] if a != b],
        'actual_source_reviews': read(OUT / 'partial_source_reviews.json'),
        'reader_operations_and_G_unchanged': True, 'current_source_object_parameter_transfer': False,
        'not_counted_as_U_learning_or_independent_C_gain': True})
    print('Acquired new condition and renderer compiled without changing reader/G.', flush=True)


def validate():
    setup(); library = read(OUT / 'candidate_library.json'); reviews = read(OUT / 'partial_source_reviews.json')
    observations, admissions = profiles(library, reviews)
    diagnosis = diagnose_inputs(observations, admissions, 'not_run')
    assert not diagnosis['local_failures']
    fitted, result = fit(library, [attach_scored_theories(o, a) for o, a in zip(observations, admissions)],
                         prior_rule_ids=library['selected_rule_ids'], timeout_seconds=90)
    assert result['status'] == 'sat' and result['native_loss'] == 0 and result['selection_edits'] == 0
    p, public, grading = material(); results = []
    for key in p['acquisition_sources']:
        for view in public[key]['views']:
            name = name_for(key, view); record = read(FOLDER / 'acquisition/ConstraintAcquire' / name)
            actual = evaluate_view(fitted, record['observation'], public[key], view, grading[key][view['id']])
            source_checks = check(fitted, public[key], view, grading[key][view['id']],
                [r for r in reviews if r['source'] == key and r['view'] == view['id']])(actual['execution']['source_output'])
            assert source_checks['accepted']
            immutable_json(OUT / 'after/execution' / name, {'source': key, 'view': view['id'],
                'source_checks': source_checks, **actual})
            results.append({'source': key, 'view': view['id'], 'native_correct': True,
                            'partial_source_review_passed': True})
    immutable_json(OUT / 'after/fit.json', result)
    immutable_json(OUT / 'after/diagnosis.json', diagnosis)
    immutable_json(OUT / 'learned.json', fitted)
    immutable_json(OUT / 'result.json', {'rows': results, 'native_correct': 12, 'total': 12,
        'before_source_admissible_native_loss': 2, 'after_source_admissible_native_loss': 0,
        'partial_source_reviews': 2, 'old_actual_readings_reused': True, 'new_executor_requests': 0,
        'new_source_concept_reading_or_representation_collision': False,
        'entire_source_semantics_certified': False, 'independent_C_or_U_gain_established': False,
        'future_pair_not_reexecuted': True, 'goal_complete': False})
    print('Actual teacher output:12/12 native with two explicit source-role checks restored; old readings reused, no future pair run.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['offline', 'preflight', 'acquire', 'compile', 'validate'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'offline': offline, 'preflight': request, 'acquire': acquire, 'compile': compile_repair, 'validate': validate}[phase]()
