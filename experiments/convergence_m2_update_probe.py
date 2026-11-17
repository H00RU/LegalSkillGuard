"""Matched M2 update validation on a fixed TRAIN mother and controlled source edit.

All selectors use the same teacher proposal pool and frozen executor outputs.
The two edited views diagnose shared factual explanations. Original native
TRAIN outcomes are graded separately and never provided to the executor.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from experiments.convergence_source_audit import study_teacher_configuration
from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.paired_interfaces.diversity_supervision import controlled_citizenship_relation
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.shared_semantics import choose_groups
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/legal_skill_convergence_20261117'
HANDOFF = BASE / 'handoff'
POINTER = HANDOFF / 'm2_update_probe_current.json'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
TEACHER_SCHEMA = record_schema({
    'candidate_a': {'type': 'string'},
    'candidate_b': {'type': 'string'},
})
TEACHER_SYSTEM = (
    'Propose two distinct short, reusable reader instruction additions for the supplied '
    'frozen legal benchmark skill. Keep the original interface and legal rules. '
    'Use the same instructions for the full yes/no task and the local same-state question. '
    'One addition should emphasize binding each cited state to the named party. '
    'The other should emphasize computing the same-state relation from the two bound values '
    'and preserving genuine lack of information. Return only two instruction strings, '
    'each at most 90 words. Do not use examples, source identities, party names, U.S. state '
    'names, answers to individual cases, new assumptions, or executable code.'
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_status(out, state):
    payload = {'artifact_root': str(out.relative_to(ROOT)), **state}
    temp = POINTER.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, indent=2) + '\n')
    temp.replace(POINTER)


def frozen_paths():
    return (
        'experiments/convergence_m2_update_probe.py',
        'experiments/convergence_source_audit.py',
        'configs/legal_skill_convergence_teacher_v1.json',
        'legal_skill_guard/paired_interfaces/diversity_supervision.py',
        'legal_skill_guard/paired_interfaces/diversity.py',
        'legal_skill_guard/paired_interfaces/diversity_relational.py',
        'legal_skill_guard/paired_interfaces/shared_semantics.py',
        'legal_skill_guard/paired_interfaces/shared_semantics_validation.py',
        'legal_skill_guard/paired_interfaces/formal_actors.py',
        'legal_skill_guard/paired_interfaces/control_programs.py',
        'legal_skill_guard/paired_interfaces/control_learning.py',
        'legal_skill_guard/paired_interfaces/control_worker.py',
        'legal_skill_guard/paired_interfaces/control_answers.py',
        'legal_skill_guard/paired_interfaces/control_tools.py',
        'legal_skill_guard/paired_interfaces/formal_tools.py',
        'legal_skill_guard/skill_evolution/native.py',
        'legal_skill_guard/skill_evolution/clients.py',
        'legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/inference/codex_cli_client.py',
        'legal_skill_guard/rr/client.py',
    )


def prepare():
    # This is the frozen existing primary polarity-failure mother. The older
    # reuse trial fixes the identity before this M2 experiment is prepared.
    earlier = BASE / 'diversity_reader_probe_01' / 'add5766667c7aec93f6d55098133bb0432a26f16b02f8648b29840af9401843c'
    observed = read(earlier / 'terminal.json')
    if observed['status'] != 'completed':
        raise ValueError('M2 requires the settled TRAIN error')
    wrong = next(row for row in observed['completed'] if row['learned_main_path_executed'])
    if wrong['native_correct'] or wrong['all_local_relations_source_faithful']:
        raise ValueError('The selected source no longer matches the recorded problem')
    root = ROOT / read(HANDOFF / 'normalized_inputs_current.json')['artifact_root']
    audit_dir = ROOT / read(HANDOFF / 'source_audit_current.json')['artifact_root']
    pilot = {row['source'] for row in read(audit_dir / 'pilot20.json')}
    train = {row['key']: row for row in read(root / 'train/public.json')
             if row['key'] in pilot and row['dataset'] == 'LegalBench_Diversity'}
    source = train[wrong['source']]
    group = controlled_citizenship_relation(source)
    cases = [{
        'id': case.source_id, 'root_id': case.root_id, 'law_scope': case.law_scope,
        'source_text_sha256': digest(case.public),
    } for case in group['cases']]
    # Send a source-supported failure class and public task rules. Both
    # selectors will receive exactly the same returned candidate strings.
    teacher_input = {
        'public_task_rules': source['views'][0]['public']['rules'],
        'observed_train_failure': 'The reader cited two matching citizenship-state statements but asserted '
                                  'the entities had different citizenship states.',
        'scope_constraint': 'If an edited TRAIN view withholds one party state, no unseen state may be '
                            'invented. Its unseen state is the same across views of that mother.',
        'native_format': 'Yes or No',
        'local_projection_format': 'true for the same state, false for different states, null for incomplete evidence',
    }
    profile, teacher_config = study_teacher_configuration()
    binding = {
        'study_id': 'convergence_m2_controlled_citizenship_update_01',
        'normalized_inputs_root': str(root.relative_to(ROOT)),
        'train_source': source['key'], 'train_public_sha256': digest(source),
        'original_failure_receipt_sha256': sha(earlier / 'terminal.json'),
        'controlled_cases': cases, 'teacher_input_sha256': digest(teacher_input),
        'teacher_profile': profile, 'teacher_config': teacher_config,
        'executor': read(HANDOFF / 'executor_readiness.json')['executor_config'],
        'source_sha256': {name: sha(ROOT / name) for name in frozen_paths()},
        'proposals': 2, 'native_source_denominator': 1, 'controlled_sources_in_native_denominator': 0,
    }
    out = BASE / 'm2_update_probe' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'teacher_input.json', teacher_input)
    immutable_json(out / 'public_TRAIN_source.json', source)
    save_status(out, {'status': 'prepared', 'teacher_requests': 1, 'executor_cells': 9})
    print(json.dumps({'prepared': str(out.relative_to(ROOT)), 'teacher_requests': 1,
                      'executor_cells': 9, 'controlled_missingness': True}), flush=True)


def projection_source(root, case, parties):
    plaintiff, defendant = parties
    return {
        'key': root['key'], 'dataset': root['dataset'], 'project_split': 'train',
        'controlled_derivative_id': case.source_id,
        'views': [{'id': 'same_state', 'public': {
            'source_text': case.public['source_text'],
            'question': f'Do {plaintiff} and {defendant} have the same state of citizenship? '
                        'Use null if the text does not establish their relationship.',
        }, 'answer_schema': {'type': ['boolean', 'null']}}],
    }


def program_with_directive(directive):
    program = direct_program()
    if directive:
        program['predicates'][0]['prompt'] += '\nAdditional reader guidance: ' + directive.strip()
    return program


def settled_execution(actor, program, source):
    result = actor.execute(program, source, 'skill_actor')
    actor.verify_program_result(source, program, 'skill_actor', result)
    calls = [trace['physical_call_id'] for trace in result['execution']['traces']
             if 'physical_call_id' in trace]
    if len(calls) != 1:
        raise ValueError('Each measured program cell must have exactly one verified frozen reader response')
    return result, calls[0]


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'reused_terminal': True, 'new_calls': 0}))
        return
    binding = read(out / 'binding.json')
    for name, expected in binding['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Bound implementation changed: ' + name)
    source = read(out / 'public_TRAIN_source.json')
    teacher_input = read(out / 'teacher_input.json')
    if digest(source) != binding['train_public_sha256'] or digest(teacher_input) != binding['teacher_input_sha256']:
        raise ValueError('TRAIN evidence binding changed')
    group = controlled_citizenship_relation(source)
    if [digest(case.public) for case in group['cases']] != [
            case['source_text_sha256'] for case in binding['controlled_cases']]:
        raise ValueError('Controlled source byte binding changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Settle the existing live research request first')
    ledger = EvolutionLedger(
        LEDGER, run_id='convergence-m2-update-' + digest(binding)[:16],
        sources={'train': [source['key']], 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    actor = ProgramActor(executor, out, max_calls=1)
    teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])
    state = {'status': 'running', 'pid': os.getpid(), 'stage': 'teacher_proposals'}
    try:
        save_status(out, state)
        proposal = teacher.propose(
            ledger.run_id + ':teacher-shared-pool',
            source_ids=[source['key']], system_prompt=TEACHER_SYSTEM,
            user_prompt=json.dumps(teacher_input, ensure_ascii=False), output_schema=TEACHER_SCHEMA)
        if proposal['model'] != binding['teacher_config']['model']:
            raise ValueError('Teacher response differs from the fixed model')
        directives = proposal['value']
        if (len(set(directives.values())) != 2
                or any(not text.strip() or len(text.split()) > 90 for text in directives.values())):
            raise ValueError('Teacher output did not supply the two distinct prespecified patch candidates')
        programs = {'baseline': program_with_directive('')}
        programs.update({name: program_with_directive(text) for name, text in directives.items()})
        immutable_json(out / 'program_pool.json', programs)
        state.update(stage='executor')
        save_status(out, state)
        grading = ROOT / read(HANDOFF / 'diversity_train_current.json')['artifact_root']
        target = read(grading / 'grading.json')[source['key']]['native']
        cases = group['cases']
        measured = {}
        for name, program in programs.items():
            native, native_call = settled_execution(actor, program, source)
            grade = grade_view(source['dataset'], source['views'][0], target, native['native']['native']['answer'])
            outputs = []
            physical = []
            for case in cases:
                derivative = projection_source(source, case, group['compared_parties'])
                result, call = settled_execution(actor, program, derivative)
                outputs.append(result['native']['same_state']['answer'])
                physical.append(call)
            measured[name] = {
                'native_utility': grade['grade'], 'native_physical_call_id': native_call,
                'program_sha256': digest(program), 'controlled_outputs': outputs,
                'controlled_physical_call_ids': physical,
            }
            immutable_json(out / 'measurements' / (name + '.json'), measured[name])
        baseline = measured['baseline']
        receipts = {}
        for name, trial in measured.items():
            def verify_projection(patch, identity, case, output):
                index = next(i for i, member in enumerate(cases) if member.source_id == case.source_id)
                return (patch == trial['program_sha256'] and identity == trial['controlled_physical_call_ids'][index]
                        and output == trial['controlled_outputs'][index])

            def verify_native(patch, pair):
                return (patch == trial['program_sha256'] and pair['source'] == source['key']
                        and pair['baseline_utility'] == baseline['native_utility']
                        and pair['patch_utility'] == trial['native_utility'])

            receipts[name] = validate_patch(
                group['theory'], trial['program_sha256'],
                [{'cases': cases, 'outputs': trial['controlled_outputs'],
                  'physical_call_ids': trial['controlled_physical_call_ids']}],
                [{'source': source['key'], 'baseline_utility': baseline['native_utility'],
                  'patch_utility': trial['native_utility']}],
                visible_train={source['key']}, verify_projection=verify_projection, verify_native_pair=verify_native)
        scores = {name: row['native_utility'] for name, row in measured.items()}
        candidates = sorted(programs, key=lambda name: (-scores[name], name != 'baseline', name))
        selected_relation = next((name for name in candidates
                                  if receipts[name]['status'] == 'eligible_train_update'), 'baseline')
        report = {
            'status': 'completed', 'native_scores': scores, 'controlled_missingness': True,
            'same_measured_candidate_pool_for_all_selectors': True,
            'ordinary_native_selection': candidates[0], 'shared_semantics_selection': selected_relation,
            'refutation_cover_from_actual_signatures': choose_groups(
                group['theory'], [cases], [{n: row['controlled_outputs'] for n, row in measured.items()}]),
            'validation': receipts, 'native_effect_evidence_mothers': 1,
        }
        immutable_json(out / 'terminal.json', report)
        save_status(out, {'status': 'completed', 'native_scores': scores,
                          'ordinary_native_selection': candidates[0], 'shared_semantics_selection': selected_relation})
        print(json.dumps({'native_scores': scores, 'ordinary': candidates[0],
                          'shared': selected_relation,
                          'statuses': dict(Counter(row['status'] for row in receipts.values()))}), flush=True)
    except Exception as error:
        save_status(out, {'status': 'interrupted_or_failed', 'stage': state['stage'],
                          'error_type': type(error).__name__})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else run)()
