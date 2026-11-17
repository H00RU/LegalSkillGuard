"""Compare native and relation-aware update selection on two actual TRAIN failures."""

import argparse
import csv
import hashlib
import json
import re
import sqlite3

from experiments.convergence_airline_joint_relation import BAG, LOCAL_RULES
from experiments.convergence_m2_update_probe import (
    TEACHER_SCHEMA, frozen_paths, program_with_directive, settled_execution,
)
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, POINTER, ROOT, read, sha, write_status
from experiments.convergence_source_audit import study_teacher_configuration
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

PROBE = HANDOFF / 'airline_update_probe_current.json'
SYSTEM = (
    'Return two different short reader-instruction additions for the public RuleArena Airline total-cost task. '
    'Keep all original rules, the same source information, and the answer format. Use the aggregate measured '
    'errors to target the failure. Guide the reader to respect same-bag dimension and weight binding, '
    'the operative fees and applicable checked-bag rules. Each addition is at most 90 words. '
    'Do not provide code, case answers, example totals, customer names, or speculative fee rules.'
)
TEACHER_INPUT = {
    'benchmark': 'RuleArena Airline domestic Main Plus, same published fee rules',
    'actual_train_feedback': 'In two independent TRAIN source pairs, a legal swap of different weights '
                             'between two checked bags changed the reference total but the reader output '
                             'did not change. Both original native totals were also incorrect.',
    'independent_rule_review': 'Check-in base fees and ticket price are preserved in both edits. '
                               'The charge for simultaneous overweight and oversize is the larger '
                               'applicable charge for that same bag. The marginal lists alone lose this binding.',
}


def fees_unchanged_by_weight_swap(public):
    text = public['facts']
    ticket = re.findall(r"flight ticket is \$(\d+)\.", text)
    checked = len(BAG.findall(text)) - 1
    if len(ticket) != 1 or checked < 1:
        raise ValueError('The locked source lacks an explicit ticket or checked-bag inventory')
    base_fees = []
    for bag in range(1, min(4, checked) + 1):
        path = LOCAL_RULES / 'fee_tables' / f'bag_{bag}' / '0.csv'
        with path.open(encoding='utf-8-sig', newline='') as stream:
            row = next(row for row in csv.DictReader(stream) if row[''] == 'U.S.')
        base_fees.append(int(row['Main Plus']))
    return int(ticket[0]) + sum(base_fees[min(i, 3)] for i in range(checked))


def prepare():
    diagnostic = ROOT / read(HANDOFF / 'airline_joint_reader_current.json')['artifact_root']
    compiled = ROOT / read(HANDOFF / 'airline_joint_relation_current.json')['artifact_root']
    baseline = ROOT / read(POINTER)['artifact_root']
    baseline_binding = read(baseline / 'binding.json')
    paired = read(diagnostic / 'terminal.json')['comparison_rows']
    if len(paired) != 2 or not all(row['violated_relation'] for row in paired):
        raise ValueError('Two already measured nonlinear failures motivate this update')
    b0 = {source['key']: source for source in read(baseline / 'public_TRAIN_pilot.json')}
    edited = {cell['source']['key']: cell['source'] for cell in read(diagnostic / 'cells.json')}
    edits = {row['source']: row for row in read(compiled / 'quantitative_source_edits.json')}
    grading_path = baseline_binding['grading_paths']['RuleArena_Airline']
    if sha(ROOT / grading_path) != baseline_binding['grading_file_sha256'][grading_path]:
        raise ValueError('Original native TRAIN grading changed')
    grades = read(ROOT / grading_path)
    sources = []
    for row in paired:
        key = row['source']
        old, new = b0[key], edited[key]
        public_pair = [old['views'][0]['public'], new['views'][0]['public']]
        if public_pair != edits[key]['source_pair']:
            raise ValueError('The audited source edit changed')
        unchanged = [fees_unchanged_by_weight_swap(public) for public in public_pair]
        surcharge = edits[key]['nonlinear_native_rule_surcharge_pair']
        if (unchanged[0] != unchanged[1] or surcharge[1] - surcharge[0] != row['required_fee_delta']
                or unchanged[0] + surcharge[0] != grades[key]['native']['answer']):
            raise ValueError('Local fee decomposition does not reconstruct the original native reference')
        sources.append({'original': old, 'edited': new, 'unchanged_fees': unchanged[0],
                        'allowed_surcharges': surcharge, 'observed_old_delta': row['observed_delta']})
    profile, teacher = study_teacher_configuration()
    paths = set(frozen_paths()) | {
        'experiments/convergence_airline_update_probe.py', 'experiments/convergence_airline_joint_relation.py',
        'legal_skill_guard/paired_interfaces/control_programs.py',
    }
    binding = {
        'study_id': 'convergence_airline_measured_nonlinear_update_01', 'train_pairs_sha256': digest(sources),
        'native_grading_path': grading_path, 'native_grading_sha256': sha(ROOT / grading_path),
        'compiled_rule_files': read(compiled / 'binding.json')['official_local_rule_files'],
        'previous_real_pair_sha256': sha(diagnostic / 'terminal.json'), 'teacher_input_sha256': digest(TEACHER_INPUT),
        'teacher_system_sha256': digest(SYSTEM), 'source_sha256': {name: sha(ROOT / name) for name in sorted(paths)},
        'executor': baseline_binding['executor'], 'teacher_profile': profile, 'teacher_config': teacher,
        'exact_baseline_wire_roots': [str(path.relative_to(ROOT)) for path in (baseline, diagnostic)],
        'one_complete_local_rule_interpretation': True, 'live_candidates': 2, 'original_native_mothers': 2,
    }
    out = BASE / 'airline_update_probe' / digest(binding)
    if (out / 'terminal.json').is_file():
        print(json.dumps({'status': 'completed', 'new_requests': 0}), flush=True)
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'train_pairs.json', sources)
    write_status(out, {'status': 'prepared', 'teacher_cells': 1, 'new_executor_cells': 8,
                       'exact_baseline_replays': 4}, PROBE)
    print(json.dumps({'status': 'prepared', 'binding': digest(binding), 'new_executor_cells': 8}), flush=True)


class ReplayAuditedExecutor(FrozenExecutor):
    replay_required = False

    def generate(self, *args, **kwargs):
        if self.replay_required:
            wire = json.dumps(self.payload(messages=kwargs['messages'], thinking=kwargs['thinking'],
                                           schema=kwargs.get('schema')), ensure_ascii=False).encode()
            key = (kwargs['source'], kwargs['purpose'], hashlib.sha256(wire).hexdigest())
            if not any(row[2] == wire for row in self.replay_index(self.exact_replay_roots).get(key, ())):
                raise ValueError('Original or edited incumbent lost its settled, exact wire response')
        return super().generate(*args, **kwargs)


def run():
    out = ROOT / read(PROBE)['artifact_root']
    if (out / 'terminal.json').is_file():
        print(json.dumps({'status': 'completed', 'new_requests': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    sources = read(out / 'train_pairs.json')
    frozen = binding['source_sha256'] | binding['compiled_rule_files']
    if (digest(sources) != binding['train_pairs_sha256'] or digest(TEACHER_INPUT) != binding['teacher_input_sha256']
            or digest(SYSTEM) != binding['teacher_system_sha256']
            or sha(ROOT / binding['native_grading_path']) != binding['native_grading_sha256']
            or any(sha(ROOT / name) != expected for name, expected in frozen.items())):
        raise ValueError('The matched Airline study binding changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Settle the existing physical request before this update')
    keys = [row['original']['key'] for row in sources]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-airline-update-' + digest(binding)[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    executor = ReplayAuditedExecutor(ledger, out, binding['executor'])
    executor.exact_replay_roots = tuple(ROOT / path for path in binding['exact_baseline_wire_roots'])
    executor.readiness()
    actor = ProgramActor(executor, out, max_calls=1)
    grades = read(ROOT / binding['native_grading_path'])
    teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])

    def measure(name, program, *, replay_required=False):
        executor.replay_required = replay_required
        rows = []
        for case in sources:
            native, original_id = settled_execution(actor, program, case['original'])
            edited, edited_id = settled_execution(actor, program, case['edited'])
            original, variant = native['native']['native']['answer'], edited['native']['native']['answer']
            key = case['original']['key']
            score = grade_view('RuleArena_Airline', case['original']['views'][0],
                               grades[key]['native'], original)['grade']
            concrete = type(original) is int and type(variant) is int
            observed = [original - case['unchanged_fees'], variant - case['unchanged_fees']] if concrete else None
            allowed = case['allowed_surcharges']
            rows.append({
                'source': key, 'native_utility': score, 'original_physical_id': original_id,
                'edited_physical_id': edited_id, 'actual_projected_surcharges': observed,
                'allowed_surcharge_signatures': [allowed], 'audited_relation_passed': observed == allowed,
                'fee_delta_only_passed': concrete and variant - original == allowed[1] - allowed[0],
            })
        value = {'program_sha256': digest(program), 'native_utility': sum(row['native_utility'] for row in rows) / len(rows),
                 'per_source_actual_measurements': rows}
        immutable_json(out / 'measurements' / (name + '.json'), value)
        return value

    write_status(out, {'status': 'running', 'stage': 'exact_incumbent_replay'}, PROBE)
    try:
        base = measure('baseline', program_with_directive(''), replay_required=True)
        if any(row['audited_relation_passed'] or row['fee_delta_only_passed'] for row in base['per_source_actual_measurements']):
            raise ValueError('Exact replay did not retain the observed nonlinear failure')
        write_status(out, {'status': 'running', 'stage': 'teacher'}, PROBE)
        proposal = teacher.propose(ledger.run_id + ':teacher-shared-pool', source_ids=keys,
            system_prompt=SYSTEM, user_prompt=json.dumps(TEACHER_INPUT, ensure_ascii=False), output_schema=TEACHER_SCHEMA)
        directives = proposal['value']
        if (proposal['model'] != binding['teacher_config']['model'] or len(set(directives.values())) != 2
                or any(not text.strip() or len(text.split()) > 90 for text in directives.values())):
            raise ValueError('Expected two distinct fixed-model instruction additions')
        write_status(out, {'status': 'running', 'stage': 'matched_candidate_reads'}, PROBE)
        pool = {'baseline': base}
        for name, directive in directives.items():
            pool[name] = measure(name, program_with_directive(directive))
        order = sorted(pool, key=lambda name: (-pool[name]['native_utility'], name != 'baseline', name))
        choices = {'native_only': order[0]}
        for selector, check in [('delta_only_control', 'fee_delta_only_passed'), ('audited_relation', 'audited_relation_passed')]:
            choices[selector] = next((name for name in order if pool[name]['native_utility'] > base['native_utility']
                                      and all(row[check] for row in pool[name]['per_source_actual_measurements'])),
                                     'baseline')
        terminal = {'status': 'completed', 'comparison_choices': choices,
                    'native_scores': {name: row['native_utility'] for name, row in pool.items()},
                    'same_candidate_pool_and_reads': True, 'same_original_TRAIN_challenge': keys,
                    'single_local_interpretation': True, 'measurements': pool}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal, PROBE)
        print(json.dumps({'native_scores': terminal['native_scores'], 'selections': choices}), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'error_type': type(error).__name__}, PROBE)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
