"""Audit the compact SCOPE control's pure composition using settled TRAIN reads."""

import json

from experiments.convergence_compact_teacher_pilot import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from experiments.convergence_shared_dev_checkpoint import ReadOnlyLedger
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_compact_proposal import (
    compact_native_passthrough, compile_proposal,
)
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_tools import legal_tools
from legal_skill_guard.paired_interfaces.scope_replay import attribute
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


def run():
    original = ROOT / read(pointer('scope'))['artifact_root']
    binding, terminal = read(original / 'binding.json'), read(original / 'terminal.json')
    common = ROOT / binding['parent_root']
    parent = read(common / 'binding.json')
    sources = read(common / 'train_sources.json')
    if (terminal['status'] != 'completed' or len(sources) != 20 or any(s['project_split'] != 'train' for s in sources)
            or digest(parent) != binding['parent_binding_sha256']
            or digest(sources) != parent['pilot_source_sha256']):
        raise ValueError('Use the settled SCOPE comparison on the locked TRAIN pilot')
    public = {source['key']: source for source in sources}
    executor = FrozenExecutor(ReadOnlyLedger(), original, binding['executor'])
    audit = ProgramActor(executor, original, max_calls=1)
    source_paths = ('experiments/convergence_scope_attribution.py', 'experiments/convergence_shared_dev_checkpoint.py',
                    'legal_skill_guard/paired_interfaces/scope_replay.py')
    study = {'SCOPE_terminal_sha256': sha(original / 'terminal.json'),
             'SCOPE_binding_sha256': digest(binding),
             'observation_paths': {dataset: sha(original / 'measured_libraries' / (dataset + '.json'))
                                   for dataset in terminal['libraries']},
             'source_sha256': {path: sha(ROOT / path) for path in source_paths},
             'source_selection': 'first candidate error in fixed original source order per dataset',
             'counterfactual_intervention': 'one finite label leaf in an actual recorded predicate response',
             'max_replays_per_execution': 128}
    out = BASE / 'compact_scope_attribution' / digest(study)
    immutable_json(out / 'binding.json', study)
    results = {}
    for dataset, summary in sorted(terminal['libraries'].items()):
        measurement = read(original / 'measured_libraries' / (dataset + '.json'))
        if measurement['summary'] != summary or summary['status'] != 'completed':
            raise ValueError('Each dataset must have its actual compact proposal and measurements')
        proof = measurement['measurement']
        scoped = [source['key'] for source in sources if source['dataset'] == dataset]
        if [row['source'] for row in proof['source_rows']] != scoped:
            raise ValueError('Attribution must follow the exact fixed measured order')
        row = next((row for row in proof['source_rows'] if row['native_utility'] < 1), None)
        if row is None:
            results[dataset] = {'status': 'no_error_in_measured_candidate'}
            continue
        source = public[row['source']]
        program = compile_proposal(measurement['proposal'], list(public))
        if dataset == 'OpenExempt':
            program = compact_native_passthrough(program)
        if dataset == 'RuleArena_Airline':
            source = {**source, 'enable_public_airline_fee_tool': True}
        if digest(source) != row['public_sha256'] or digest(program) != proof['program_sha256']:
            raise ValueError('Attribution may replay only the actual measured program and input')
        grade_path = parent['grading_paths'][dataset]
        if sha(ROOT / grade_path) != parent['grading_file_sha256'][grade_path]:
            raise ValueError('The original native TRAIN grading changed')
        annotations = read(ROOT / grade_path)[source['key']]
        summaries = []
        for cell in common_cells(source):
            bundle = source_bundle(cell)
            tools, assets = legal_tools(cell, bundle)
            runtime = ControlProgramRuntime(executor, original, max_calls=1, shared_assets=assets, legal_tools=tools)
            path = runtime.execution_path(program, cell, bundle, purpose='skill_actor')
            execution = read(path)
            native = audit._native(cell, execution)
            audit.verify_program_result(cell, program, 'skill_actor', {'execution': execution, 'native': native})
            if any(trace['physical_call_id'] not in row['physical_call_ids'] for trace in execution['traces']
                   if 'finish_reason' in trace):
                raise ValueError('An attribution input is missing from the original measured cohort')
            replay = attribute(read(path.with_name('input.json')), execution, legal_tools=tools,
                               max_label_edits=1, max_replays=study['max_replays_per_execution'])
            target = out / dataset / (digest(cell) + '.json')
            immutable_json(target, replay)
            repaired = set()
            for replay_case in replay['interventions']:
                if not replay_case['supported']:
                    continue
                for task in cell['views']:
                    key = task['id']
                    if key in replay_case['answer'] and row['native_task_utilities'][key] < 1:
                        grade = grade_view(dataset, task, annotations[key], replay_case['answer'][key])
                        if grade['grade'] > row['native_task_utilities'][key]:
                            repaired.add(key)
            summaries.append({'views': [view['id'] for view in cell['views']],
                              'physical_composition_reproduced': replay['baseline_reproduced'],
                              'counterfactual_interventions': len(replay['interventions']),
                              'original_tasks_with_higher_counterfactual_grade': len(repaired),
                              'replay_result_sha256': digest(replay)})
        results[dataset] = {'status': 'completed', 'cells': summaries, 'source': source['key']}
    receipt = {'artifact_root': str(out.relative_to(ROOT)), 'datasets': results, 'generation_requests': 0,
               'counterfactual_native_improvement_is_observed_model_gain': False,
               'verified_source_edit_stage_complete': False}
    immutable_json(out / 'terminal.json', receipt)
    immutable_json(HANDOFF / 'compact_SCOPE_composition_attribution_20261118.json', receipt)
    print(json.dumps({k: {name: value for name, value in row.items() if name != 'source'}
                      for k, row in results.items()}, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
