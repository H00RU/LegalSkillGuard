"""Run native-supervised and SCOPE-style programs via compact teacher contracts."""

import argparse
import json
import math
import sqlite3

import jsonschema

from experiments.convergence_native_teacher_pilot import INSTRUCTIONS, POINTER as NESTED
from experiments.convergence_parse_pilot import cohort_contract
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_compact_proposal import (
    CONTRACT, SCHEMA, compact_native_passthrough, compile_proposal,
)
from legal_skill_guard.paired_interfaces.convergence_training import measure_program_prefix
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

POLICIES = {
    'ordinary': ('Optimize one reusable legal skill from the common native TRAIN feedback. '
                 'Choose the strongest supported reading strategy and preserve the native answer and policy.'),
    'scope': ('Decompose the task into a source-grounded weak-reader predicate and deterministic composition. '
              'In the rationale identify an error mode and a regression the decomposition must preserve. '
              'Use native mode if the complete direct reader offers the best evidence and output contract.'),
}


def pointer(style):
    return HANDOFF / ('compact_teacher_' + style + '_current.json')


def teacher_system(style, dataset):
    guidance = (' For ContractNLI use native schema mode, which is the runtime path that preserves exact evidence IDs.'
                if dataset == 'ContractNLI' else '')
    return CONTRACT + ' ' + POLICIES[style] + guidance


def prepare(style, *, recover_from=None):
    parent = ROOT / read(NESTED)['artifact_root']
    original = read(parent / 'binding.json')
    sources, baseline = read(parent / 'train_sources.json'), read(parent / 'incumbent_scores.json')
    payloads = read(parent / 'teacher_payloads.json')
    if (digest(sources) != original['pilot_source_sha256'] or digest(baseline) != original['native_incumbent_sha256']
            or digest(payloads) != original['teacher_inputs_sha256'] or any(s['project_split'] != 'train' for s in sources)):
        raise ValueError('Use exactly the settled same-information native development cohort')
    protocol = ROOT / 'reports/legal_skill_convergence_20261117/protocol.json'
    paths = set(original['source_sha256']) | {str(protocol.relative_to(ROOT)),
        'experiments/convergence_compact_teacher_pilot.py', 'experiments/convergence_parse_pilot.py',
        'legal_skill_guard/paired_interfaces/convergence_compact_proposal.py',
        'legal_skill_guard/paired_interfaces/scope_learning.py'}
    binding = {'study_id': 'convergence_compact_program_fixed20', 'style': style,
               'parent_root': str(parent.relative_to(ROOT)), 'parent_binding_sha256': digest(original),
               'source_sha256': {name: sha(ROOT / name) for name in sorted(paths)},
               'teacher_systems': {dataset: teacher_system(style, dataset) for dataset in INSTRUCTIONS},
               'teacher_schema_sha256': digest(SCHEMA), 'executor': original['executor'],
               'teacher_profile': original['teacher_profile'], 'teacher_config': original['teacher_config'],
               'matched_public_conditions': cohort_contract(original, sources, protocol),
               'same_source_feedback': original['teacher_inputs_sha256'], 'full_paper_reproduction': False}
    if recover_from is not None:
        previous_root = ROOT / recover_from
        previous = read(previous_root / 'binding.json')
        if (previous_root.parent != BASE / 'compact_teacher_pilot'
                or previous_root.name != digest(previous) or previous.get('recovery') is not None
                or {k: v for k, v in previous.items() if k != 'source_sha256'}
                != {k: v for k, v in binding.items() if k != 'source_sha256'}
                or (previous_root / 'terminal.json').exists()
                or read(previous_root / 'source_snapshot_receipt.json')['files'] != previous['source_sha256']):
            raise ValueError('Recovery requires the archived, interrupted exact same comparison')
        prefix = 'convergence-compact-' + style + '-' + previous_root.name[:16] + ':teacher:'
        with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
            teachers = {dataset: prefix + dataset for dataset in INSTRUCTIONS if db.execute(
                "select 1 from calls where id=? and role='teacher' and status='completed'",
                (prefix + dataset,)).fetchone()}
        records = {file.stem: sha(file) for file in sorted((previous_root / 'measured_libraries').glob('*.json'))}
        if not records.keys() <= teachers.keys() or set(teachers) - records.keys() != {'OpenExempt'}:
            raise ValueError('Only the settled OpenExempt passthrough is awaiting transport repair')
        binding['recovery'] = {'root': recover_from, 'parent_binding_sha256': digest(previous),
                               'measured_libraries': records, 'completed_teacher_calls': teachers}
    out = BASE / 'compact_teacher_pilot' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    write_status(out, {'status': 'prepared', 'style': style, 'fixed_TRAIN_mothers': 20,
                       'retained_libraries': sorted(binding.get('recovery', {}).get('measured_libraries', {}))},
                 pointer(style))
    print(json.dumps(read(pointer(style))), flush=True)


def run(style):
    out = ROOT / read(pointer(style))['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    parent = ROOT / binding['parent_root']
    original = read(parent / 'binding.json')
    sources, baseline = read(parent / 'train_sources.json'), read(parent / 'incumbent_scores.json')
    payloads = read(parent / 'teacher_payloads.json')
    if (binding['style'] != style or digest(original) != binding['parent_binding_sha256']
            or digest(sources) != original['pilot_source_sha256'] or digest(baseline) != original['native_incumbent_sha256']
            or digest(payloads) != binding['same_source_feedback'] or digest(SCHEMA) != binding['teacher_schema_sha256']
            or any(sha(ROOT / name) != value for name, value in (
                binding['source_sha256'] | original['grading_file_sha256']).items())):
        raise ValueError('The compact program proposal is limited to its original exact study conditions')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Settle all existing physical requests before starting a new comparison')
    keys = [source['key'] for source in sources]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-compact-' + style + '-' + digest(binding)[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = tuple(ROOT / path for path in original['common_terminal_receipts'])
    reader.readiness()
    teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])
    actor = ProgramActor(reader, out, max_calls=1)
    recovery = binding.get('recovery')
    if recovery:
        previous_root = ROOT / recovery['root']
        previous = read(previous_root / 'binding.json')
        if (digest(previous) != recovery['parent_binding_sha256']
                or any(sha(previous_root / 'measured_libraries' / (dataset + '.json')) != expected
                       for dataset, expected in recovery['measured_libraries'].items())):
            raise ValueError('Recovered observations must retain the exact prior bindings')
        previous_id = 'convergence-compact-' + style + '-' + previous_root.name[:16]
        previous_ledger = EvolutionLedger(LEDGER, run_id=previous_id,
                                          sources={'train': keys, 'dev': [], 'test': []}, binding=previous)
        previous_teacher = FrozenTeacher(previous_ledger, previous_root, previous['teacher_config'],
                                         authorized_profile=previous['teacher_profile'])
        reader.exact_replay_roots += (previous_root,)
    reports = {}
    current = None
    try:
        for dataset in sorted(INSTRUCTIONS):
            current = dataset
            record = out / 'measured_libraries' / (dataset + '.json')
            if record.exists():
                reports[dataset] = read(record)['summary']
                continue
            if recovery and dataset in recovery['measured_libraries']:
                old = previous_root / 'measured_libraries' / record.name
                reports[dataset] = read(old)['summary']
                continue
            write_status(out, {'status': 'running', 'style': style, 'current_library': dataset,
                               'completed_libraries': len(reports)}, pointer(style))
            scoped = [source for source in sources if source['dataset'] == dataset]
            source_ids = [source['key'] for source in scoped]
            identity = ledger.run_id + ':teacher:' + dataset
            teacher_actor = teacher
            if recovery and dataset in recovery['completed_teacher_calls']:
                identity = recovery['completed_teacher_calls'][dataset]
                with previous_ledger.transaction() as db:
                    status = db.execute("select status from calls where id=? and role='teacher'", (identity,)).fetchone()
                if status != ('completed',):
                    raise ValueError('Recovery cannot redispatch the preserved teacher proposal')
                teacher_actor = previous_teacher
            reply = teacher_actor.propose(identity, source_ids=source_ids, system_prompt=binding['teacher_systems'][dataset],
                                          user_prompt=json.dumps(payloads[dataset], sort_keys=True), output_schema=SCHEMA)
            if reply['model'] != binding['teacher_config']['model']:
                raise ValueError('Actual teacher differs from the frozen matched configuration')
            base = math.fsum(math.fsum(baseline[k].values()) / len(baseline[k]) for k in source_ids) / len(source_ids)
            proof = None
            try:
                if dataset == 'ContractNLI' and reply['value']['schema_mode'] != 'native':
                    raise ValueError('The current fixed program callback cannot preserve native CNI evidence')
                program = compile_proposal(reply['value'], keys)
            except (ValueError, KeyError, TypeError, SyntaxError, jsonschema.SchemaError,
                    jsonschema.ValidationError) as error:
                summary = {'status': 'invalid_teacher_program', 'error_type': type(error).__name__,
                           'incumbent_native': base, 'selected': 'incumbent'}
            else:
                if dataset == 'OpenExempt':
                    compiled = compact_native_passthrough(program)
                    if recovery and compiled == program:
                        raise ValueError('The interrupted proposal lacked the direct native passthrough')
                    immutable_json(out / 'reader_transport' / (dataset + '.json'), {
                        'original_program_sha256': digest(program), 'executed_program_sha256': digest(compiled),
                        'direct_native_passthrough_compacted': compiled != program,
                        'public_task_and_native_wire_retained': True,
                    })
                    program = compiled
                if dataset == 'RuleArena_Airline':
                    scoped = [{**source, 'enable_public_airline_fee_tool': True} for source in scoped]
                grades = {}

                def grade(key):
                    if not grades:
                        grades.update(read(ROOT / original['grading_paths'][dataset]))
                    return grades[key]

                proof = measure_program_prefix(actor, program, scoped, grade_provider=grade, visible_prefix=keys)
                measured = math.fsum(row['native_utility'] for row in proof['source_rows']) / len(source_ids)
                summary = {'status': 'completed', 'incumbent_native': base, 'candidate_native': measured,
                           'selected': 'candidate' if measured > base else 'incumbent'}
            immutable_json(record, {'summary': summary, 'teacher_physical_call': identity,
                                    'proposal': reply['value'], 'measurement': proof})
            reports[dataset] = summary
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'style': style, 'current_library': current,
                           'completed_libraries': len(reports), 'error_type': type(error).__name__}, pointer(style))
        raise
    terminal = {'status': 'completed', 'style': style, 'libraries': reports, 'fixed_train_mothers': len(keys),
                'strongest_external_family_selected': False, 'SCOPE_counterexample_stage_complete': False}
    if recovery:
        terminal['recovery'] = recovery
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, terminal, pointer(style))
    print(json.dumps(terminal), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    parser.add_argument('style', choices=tuple(POLICIES))
    parser.add_argument('--recover-from')
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare(args.style, recover_from=args.recover_from)
    else:
        if args.recover_from is not None:
            parser.error('--recover-from is a prepare argument')
        run(args.style)
