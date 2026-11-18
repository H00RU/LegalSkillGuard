"""Fit the native-supervised program control on the fixed 20-source TRAIN pilot."""

import argparse
from collections import Counter
import json
import math
import sqlite3

import jsonschema

from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, POINTER as B0, ROOT, read, sha, write_status
from experiments.convergence_source_audit import study_teacher_configuration
from legal_skill_guard.paired_interfaces.control_learning import program_from_proposal, proposal_schema
from legal_skill_guard.paired_interfaces.convergence_training import measure_program_prefix
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'native_teacher_pilot_current.json'
SYSTEM = (
    'Return only the requested structured JSON. Do not run commands, browse, open files, or call tools. '
    'Propose one compact reusable external legal skill program for the supplied public task family, using the measured '
    'aggregate TRAIN feedback. The runtime has at most one neural predicate call per supplied bundle. '
    'Retain every native task and use only its public facts and rules. The compose function signature is '
    'compose(inputs, predict, extractors) and it returns a mapping from each native task ID to its answer. '
    'A predicate with schema_mode native uses the supplied native bundle schema, including evidence. '
    'A fixed predicate must state a valid JSON schema and can return local facts for deterministic composition. '
    'Inputs contain public, native_answer_schema, native_wire_schema, dataset, and optional legal_tools. '
    'Use one predicate and a compose function of at most 35 lines. Prefer no separate extractors unless the '
    'program needs them. Use only deterministic builtins and declared pure callbacks. Preserve uncertainty and source scope. '
    'Never hard-code source identities, case answers, undisclosed facts, or legal rules that contradict the supplied '
    'public corpus. When available a shared legal tool may consume literal inputs using its public contract. '
    'The caller will independently validate the complete program and all original native tasks.'
)
INSTRUCTIONS = {
    'ContractNLI': 'The bundle includes all seventeen hypotheses and a shared exact document with explicit zero-based evidence spans.',
    'OpenExempt': 'EC and EV are separate bundles. Respect the current family’s supplied public assumptions and exact asset identities.',
    'MAUD': 'The bundle contains three native merger-agreement questions. Preserve the operative clause scope and attached qualifications.',
    'RuleArena_Airline': ('Return the exact integer cost including the ticket. Keep measurements attached to their own items. '
                         'The public domestic standard-weight fee tool may be available in the observed source scope.'),
    'LegalBench_Diversity': 'Preserve named parties, their citizenship and same-pair claim attribution in the supplied public task.',
}


def prepare():
    b0 = ROOT / read(B0)['artifact_root']
    cni = ROOT / read(HANDOFF / 'cni_indexed_evidence_current.json')['artifact_root']
    fees = ROOT / read(HANDOFF / 'airline_public_fee_reader_current.json')['artifact_root']
    baseline_binding = read(b0 / 'binding.json')
    sources = read(b0 / 'public_TRAIN_pilot.json')
    if (digest(sources) != baseline_binding['sources_digest']
            or Counter(row['dataset'] for row in sources) != dict.fromkeys(INSTRUCTIONS, 4)):
        raise ValueError('The complete predetermined 20-mother study is required')
    for stage in (b0, cni, fees):
        if read(stage / 'terminal.json')['status'] != 'completed':
            raise ValueError('Wait for the measured common baseline and real constituent updates')
    fee_correct = {row['source']: row['native_utility']
                   for row in read(fees / 'terminal.json')['evidence']['match_bag_max']}
    native_base, tasks = {}, {}
    for source in sources:
        origin = cni if source['dataset'] == 'ContractNLI' else b0
        record = read(origin / 'source_results' / (digest(source['key']) + '.json'))
        values = {key: value['grade'] for key, value in record['grades'].items()}
        if source['key'] in fee_correct:
            values = {'native': fee_correct[source['key']]}
        if values.keys() != {view['id'] for view in source['views']}:
            raise ValueError('Common baseline lost a native TRAIN task')
        native_base[source['key']] = values
        tasks.setdefault(source['dataset'], Counter()).update(values.values())
    payloads = {}
    for dataset, counts in tasks.items():
        payloads[dataset] = {'public_task_family': dataset, 'public_source_contract': INSTRUCTIONS[dataset],
            'measured_native_TRAIN_mothers': 4, 'total_native_tasks': sum(counts.values()),
            'aggregate_exact_success_count': counts[1.0],
            'aggregate_mean_native_utility': math.fsum(score * count for score, count in counts.items()) / sum(counts.values()),
            'source_or_label_examples_included': False}
    profile, teacher = study_teacher_configuration()
    files = set(baseline_binding['source_sha256']) | {
        'experiments/convergence_native_teacher_pilot.py', 'experiments/convergence_source_audit.py',
        'legal_skill_guard/inference/codex_cli_client.py',
        'legal_skill_guard/paired_interfaces/convergence_training.py',
        'legal_skill_guard/paired_interfaces/convergence_actors.py',
        'legal_skill_guard/paired_interfaces/airline_public_fees.py',
        'legal_skill_guard/paired_interfaces/native_adapters.py',
        'configs/legal_skill_convergence_teacher_v1.json',
    }
    binding = {'study_id': 'convergence_native_supervised_fixed20_pilot_v1',
               'source_sha256': {name: sha(ROOT / name) for name in sorted(files)},
               'pilot_source_sha256': digest(sources), 'teacher_inputs_sha256': digest(payloads),
               'native_incumbent_sha256': digest(native_base),
               'common_terminal_receipts': {str(stage.relative_to(ROOT)): sha(stage / 'terminal.json')
                                            for stage in (b0, cni, fees)},
               'grading_paths': baseline_binding['grading_paths'],
               'grading_file_sha256': baseline_binding['grading_file_sha256'],
               'teacher_profile': profile, 'teacher_config': teacher, 'executor': baseline_binding['executor'],
               'teacher_proposal_system_sha256': digest(SYSTEM), 'fixed_sources_per_family': 4,
               'no_preloading_of_pilot_skills_in_formal_training': True}
    out = BASE / 'native_teacher_pilot' / digest(binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}))
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'train_sources.json', sources)
    immutable_json(out / 'teacher_payloads.json', payloads)
    immutable_json(out / 'incumbent_scores.json', native_base)
    write_status(out, {'status': 'prepared', 'teacher_cells': 5, 'native_executor_cells_if_no_replay': 24}, POINTER)
    print(json.dumps({'status': 'prepared', 'binding': digest(binding)}), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}))
        return
    binding = read(out / 'binding.json')
    sources = read(out / 'train_sources.json')
    payloads = read(out / 'teacher_payloads.json')
    baseline = read(out / 'incumbent_scores.json')
    if (digest(sources) != binding['pilot_source_sha256'] or digest(payloads) != binding['teacher_inputs_sha256']
            or digest(baseline) != binding['native_incumbent_sha256'] or digest(SYSTEM) != binding['teacher_proposal_system_sha256']
            or any(sha(ROOT / path) != value for path, value in (
                    binding['source_sha256'] | binding['grading_file_sha256']).items())):
        raise ValueError('The preselected pilot conditions changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('Another study request is in flight')
    all_keys = [source['key'] for source in sources]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-native-teacher-pilot-' + digest(binding)[:16],
                             sources={'train': all_keys, 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.exact_replay_roots = tuple(ROOT / path for path in binding['common_terminal_receipts'])
    executor.readiness()
    teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])
    actor = ProgramActor(executor, out, max_calls=1)
    results = {}
    try:
        for dataset in sorted(payloads):
            scoped = [source for source in sources if source['dataset'] == dataset]
            keys = [source['key'] for source in scoped]
            if dataset == 'RuleArena_Airline':
                scoped = [{**source, 'enable_public_airline_fee_tool': True} for source in scoped]
            write_status(out, {'status': 'running', 'current_library': dataset, 'completed_libraries': len(results)}, POINTER)
            response = teacher.propose(ledger.run_id + ':teacher:' + dataset, source_ids=keys,
                                    system_prompt=SYSTEM, user_prompt=json.dumps(payloads[dataset], sort_keys=True),
                                    output_schema=proposal_schema())
            if response['model'] != binding['teacher_config']['model']:
                raise ValueError('Teacher identity changed')
            before = math.fsum(math.fsum(baseline[key].values()) / len(baseline[key]) for key in keys) / len(keys)
            try:
                candidate = program_from_proposal(response['value'], all_keys)
            except (ValueError, TypeError, KeyError, SyntaxError, jsonschema.SchemaError, jsonschema.ValidationError) as error:
                result = {'status': 'invalid_teacher_program', 'error_type': type(error).__name__, 'incumbent_native': before,
                          'measured_candidate': False}
            else:
                grading = {}

                def grade(key):
                    if not grading:
                        grading.update(read(ROOT / binding['grading_paths'][dataset]))
                    return grading[key]

                trace = measure_program_prefix(actor, candidate, scoped,
                                               grade_provider=grade, visible_prefix=all_keys)
                after = math.fsum(row['native_utility'] for row in trace['source_rows']) / len(keys)
                result = {'status': 'completed', 'measured_candidate': True, 'incumbent_native': before,
                          'candidate_native': after, 'selected': 'candidate' if after > before else 'incumbent',
                          'candidate': candidate, 'program_measurement': trace}
            immutable_json(out / 'measured_libraries' / (dataset + '.json'), result)
            results[dataset] = result
        terminal = {'status': 'completed', 'native_teacher_control_only': True,
                    'fixed_train_mothers': len(sources), 'libraries': {
                    dataset: {key: value for key, value in result.items() if key not in ('candidate', 'program_measurement')}
                    for dataset, result in results.items()}}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal, POINTER)
        print(json.dumps(terminal), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'completed_libraries': len(results),
                           'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
