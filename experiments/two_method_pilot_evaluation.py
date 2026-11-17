"""Freeze main D0 choices and score all original paid pilot outputs.

Zero new model calls. Do not load structural reference proposals. Predictions
exist before grading; only original D0 grades select M1. M2/replay decisions
must already be sealed without evaluation predictions or grades.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_literal_graph_corpus import decode
from legal_skill_guard.paired_interfaces import airline_interfaces
from legal_skill_guard.paired_interfaces.control_tools import module_assets
from legal_skill_guard.paired_interfaces.empirical_channel import graph_record
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan
from legal_skill_guard.paired_interfaces.pilot_metrics import select_fixed_plans, summarize
from legal_skill_guard.paired_interfaces.rich_graph_pairs import consumer_signature, reference_graph
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


def read_evidence(result, graph, identities, units, public):
    """Use actual read quotes only; evidence targets never enter this function."""
    if 'sentence_spans' not in public:
        return []
    by_id = {identities[node['id']]: node for node in graph['nodes']}
    by_unit = {unit['id']: unit for unit in units}
    spans = []
    for identity in result.get('used_nodes', []):
        node = by_id.get(identity)
        if node is None:
            continue
        unit = by_unit[node['unit_id']]
        if unit['field'] != 'source_text':
            continue
        positions = [match.start() for match in re.finditer(re.escape(node['quote']), unit['text'])]
        if len(positions) == 1:
            start = unit['start'] + positions[0]
            spans.append((start, start + len(node['quote'])))
    return sorted({index for index, (a, b) in enumerate(public['sentence_spans'])
                   if any(start < b and end > a for start, end in spans)})


def grade_predictions(predictions, train, grading):
    rows = []
    for prediction in predictions:
        source = train[prediction['source']]
        views = {view['id']: view for view in source['views']}
        for task, result in prediction['native'].items():
            native = (grade_view(source['dataset'], views[task], grading[source['key']][task],
                                 result['answer'], prediction['native_evidence'].get(task, []))
                      if result['handled'] else {'grade': 0., 'unresolved_or_failed': True})
            if native['grade'] is None:
                raise ValueError('The original native grader did not produce a score')
            rows.append({key: prediction[key] for key in ('source', 'dataset', 'role', 'plan',
                'plan_version', 'physical_call_id', 'opaque_view')} | {
                'view': task, 'handled': result['handled'], 'answer': result['answer'],
                'grade': native['grade'], 'native_metrics': native,
                'fallback_executed': False})
    return rows


def run(selection_path):
    selection_path = selection_path.resolve()
    if not selection_path.is_relative_to(BASE.resolve()):
        raise ValueError('Use a sealed selection artifact in the current project')
    decision = read(selection_path)
    m2_protocol = read(selection_path.parent / 'protocol.json')
    if decision['protocol_sha256'] != sha(selection_path.parent / 'protocol.json'):
        raise ValueError('The M2 choice lost its frozen protocol binding')
    if (decision['structure_evaluation_reference_graphs_opened'] is not False
            or decision['native_grading_or_evaluation_predictions_opened'] is not False):
        raise ValueError('M2 choices must predate their evaluation truth and predictions')
    for name, expected in m2_protocol['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('A frozen M2/consumer implementation changed: ' + name)
    lock_path, reader_path = BASE / 'pilot_lock.json', BASE / 'pilot_reads_v3/protocol.json'
    lock, reader = read(lock_path), read(reader_path)
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    grade_path = public_path.with_name('grading.json')
    source_lock = read(BASE / 'prepared/source_lock.json')
    if (sha(lock_path) != reader['pilot_lock_sha256'] or sha(lock_path) != m2_protocol['pilot_lock_sha256']
            or sha(public_path) != m2_protocol['TRAIN_public_sha256']
            or sha(grade_path) != source_lock['prepared_sha256']['train']['grading']):
        raise ValueError('A fixed source/grade/reader binding changed')
    train = {source['key']: source for source in read(public_path)}
    own_paths = [str(Path(__file__).relative_to(ROOT)),
                 'legal_skill_guard/paired_interfaces/pilot_metrics.py',
                 'legal_skill_guard/skill_evolution/native.py',
                 'legal_skill_guard/skill_evolution/grade_worker.py',
                 'legal_skill_guard/rr/scoring.py']
    bindings = {**m2_protocol['source_sha256'], **{name: sha(ROOT / name) for name in own_paths}}
    protocol = {'experiment': 'fixed_pilot_native_evaluation_v1', 'source_sha256': bindings,
        'pilot_lock_sha256': sha(lock_path), 'reader_protocol_sha256': sha(reader_path),
        'TRAIN_public_sha256': sha(public_path), 'TRAIN_native_grading_sha256': sha(grade_path),
        'M2_selection_path': str(selection_path.relative_to(ROOT)), 'M2_selection_sha256': sha(selection_path),
        'candidate_selection': 'original D0 mother-macro;stable originally locked candidate order',
        'same_paid_responses_are_not_new_independent_trials': True,
        'source_unit': 'original mother;all native views averaged within mother',
        'native_primary_metrics': {'OpenExempt': 'official EC/EV F1', 'other_datasets': 'native exact match'},
        'all_fixed_sources_and_unsupported_outputs_in_denominator': True,
        'new_model_requests': 0, 'new_independent_trials': 0,
        'structure_reference_graphs_opened': False, 'fresh_DEV_or_TEST_grading_opened': False}
    out = BASE / 'pilot_evaluation_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for name in own_paths:
        target = out / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('An evaluation source snapshot changed')
        if not target.exists():
            target.write_bytes(raw)
    plans = {(dataset, plan['name']): plan for dataset, candidates in lock['plans'].items() for plan in candidates}
    airline = {plan['version']: plan for plan in map(schema_visible_plan,
        airline_interfaces.compile_plans(lock['plans']['RuleArena_Airline']))}
    predictions, cache, expected_ids = [], {}, set()
    for row in lock['rows']:
        source = train[row['key']]
        if digest(source) != row['public_sha256']:
            raise ValueError('An original pilot source changed')
        task, mapping = inputs(source)
        for view in task['views']:
            native_tasks = sorted(name for name, opaque in mapping.items() if opaque == view['view_id'])
            native_public = {v['id']: v['public'] for v in source['views'] if v['id'] in native_tasks}
            context = source['dataset'] + ':' + digest(native_tasks)
            for candidate, version in zip(lock['plans'][source['dataset']], reader['read_versions'][source['dataset']]):
                identity = digest([row['key'], view['view_id'], version])
                expected_ids.add(identity)
                path = BASE / 'pilot_reads_v3/reads' / identity / 'decoded.json'
                actual = read(path)
                if (actual['source'], actual['role'], actual['plan'], actual['plan_version'], actual['opaque_source_view']) != (
                        row['key'], row['role'], candidate['name'], version, view['view_id']):
                    raise ValueError('A paid read differs from its fixed source/view/role/version')
                item = {'source': row['key'], 'view': view['view_id'], 'version': version,
                    'read_path': str(path.relative_to(ROOT)), 'dataset': source['dataset'], 'plan': candidate['name']}
                plan = airline[version] if source['dataset'] == 'RuleArena_Airline' else plans[source['dataset'], candidate['name']]
                decoded = decode(actual, item, view['source_units'], plan)
                native, evidence = {}, {}
                if decoded['graph'] is None:
                    native = {name: {'handled': False, 'answer': None,
                        'reason': 'Production decoder abstention', 'errors': decoded['errors']} for name in native_tasks}
                else:
                    (world, _, _), identities = reference_graph(decoded['graph'],
                        {unit['id']: unit for unit in view['source_units']}, context)
                    key = digest([graph_record(world), source['dataset'], native_public])
                    if key not in cache:
                        cache[key] = consumer_signature(world, source['dataset'], native_public)
                    native = cache[key]['native']
                    if source['dataset'] == 'ContractNLI':
                        evidence = {name: read_evidence(result, decoded['graph'], identities,
                            view['source_units'], native_public[name]) for name, result in native.items()}
                prediction = {'source': row['key'], 'dataset': source['dataset'], 'role': row['role'],
                    'opaque_view': view['view_id'], 'plan': candidate['name'], 'plan_version': version,
                    'physical_call_id': decoded['physical_call_id'], 'native': native, 'native_evidence': evidence,
                    'read_artifact_sha256': sha(path), 'decode_receipt': decoded,
                    'fallback_executed': False, 'new_model_requests': 0}
                immutable_json(out / 'predictions' / (identity + '.json'), prediction)
                predictions.append(prediction)
    actual_ids = {path.parent.name for path in (BASE / 'pilot_reads_v3/reads').glob('*/decoded.json')}
    if actual_ids != expected_ids:
        raise ValueError('The physical pilot output inventory differs from its complete fixed cohort')
    # This read occurs after all156 native predictions exist. Only the D0
    # branch enters candidate selection; later scores are constructed after seal.
    grading = read(grade_path)
    development = grade_predictions([p for p in predictions if p['role'] == 'development'], train, grading)
    immutable_json(out / 'development_native_scores.json', development)
    orders = {dataset: [plan['name'] for plan in candidates] for dataset, candidates in lock['plans'].items()}
    view_ids = {row['key']: [view['id'] for view in train[row['key']]['views']] for row in lock['rows']}
    m1 = select_fixed_plans(development, lock['rows'], orders, view_ids)
    immutable_json(out / 'frozen_libraries/shared_F_assets.json', {dataset: module_assets(dataset) for dataset in orders})
    immutable_json(out / 'frozen_libraries/fixed_candidate_interfaces.json', {
        dataset: {plan['name']: (airline[version] if dataset == 'RuleArena_Airline' else plan)
                  for plan, version in zip(candidates, reader['read_versions'][dataset])}
        for dataset, candidates in lock['plans'].items()})
    seal = {'M1_dataset_choices': m1, 'M2_selection_sha256': sha(selection_path),
        'development_native_scores_sha256': sha(out / 'development_native_scores.json'),
        'calibration_or_structure_evaluation_grades_used_for_main_selection': False,
        'all_predictions_exist_before_grading': True,
        'structure_reference_graphs_opened': False, 'new_model_requests': 0}
    immutable_json(out / 'selection_freeze.json', seal)
    exposure = {'selection_freeze_sha256': sha(out / 'selection_freeze.json'),
        'TRAIN_native_grading_sha256': sha(grade_path), 'all_pilot_mothers': sorted(view_ids),
        'structure_evaluation_mothers': sorted(row['key'] for row in lock['rows'] if row['role'] == 'structure_evaluation'),
        'native_grades_used_only_for_frozen_pilot_evaluation': True,
        'structure_reference_graphs_opened': False, 'fresh_DEV_or_TEST_grading_opened': False}
    immutable_json(out / 'pilot_grading_exposure.json', exposure)
    scores = grade_predictions(predictions, train, grading)
    immutable_json(out / 'all_candidate_native_scores.json', scores)
    aggregates = []
    for dataset, plan, role in sorted({(row['dataset'], row['plan'], row['role']) for row in scores}):
        selected = [r for r in scores if (r['dataset'], r['plan'], r['role']) == (dataset, plan, role)]
        expected = {(r['key'], task) for r in lock['rows'] if r['dataset'] == dataset and r['role'] == role
                    for task in view_ids[r['key']]}
        aggregates.append({'dataset': dataset, 'plan': plan, 'role': role, **summarize(selected, expected)})
    selected_rows = [row for row in scores if row['plan'] == m1[row['dataset']]['plan']]
    m1_report = []
    for dataset, role in sorted({(row['dataset'], row['role']) for row in selected_rows}):
        rows = [row for row in selected_rows if (row['dataset'], row['role']) == (dataset, role)]
        expected = {(r['key'], task) for r in lock['rows'] if r['dataset'] == dataset and r['role'] == role
                    for task in view_ids[r['key']]}
        m1_report.append({'dataset': dataset, 'role': role, 'plan': m1[dataset]['plan'], **summarize(rows, expected)})
    transfer = []
    for target in decision['decisions']:
        choices = {mode: target['M2'][mode]['plan'] for mode in ('unrestricted', 'detectable_residual')}
        choices['complete_paired_trace_replay'] = target['complete_paired_trace_replay']['plan']
        choices['M1_selected'] = m1[target['dataset']]['plan']
        by_plan = {}
        for plan in orders[target['dataset']]:
            rows = [row for row in scores if row['source'] == target['source'] and row['opaque_view'] == target['view']
                    and row['plan'] == plan]
            if sorted(row['view'] for row in rows) != target['native_tasks']:
                raise ValueError('A transfer decision lost one of its fixed native tasks')
            if {row['plan_version'] for row in rows} != {target['candidate_read_bindings'][plan]['raw_read_version']}:
                raise ValueError('Transfer evaluation differs from the actually calibrated reader version')
            by_plan[plan] = {'native_mother_view_mean': sum(row['grade'] for row in rows) / len(rows),
                            'full_signature_failure': float(not all(row['handled'] and row['grade'] == 1 for row in rows))}
        transfer.append({key: target[key] for key in ('source', 'dataset', 'view', 'native_tasks')} | {
            'frozen_choices': choices, 'observed_fixed_candidate_outcomes': by_plan,
            'single_case_outcome_is_not_confidence_interval_coverage': True,
            'relationship_structure_novelty_not_yet_audited': True})
    for name, expected in bindings.items():
        if sha(ROOT / name) != expected:
            raise ValueError('An evaluation source changed: ' + name)
    report = {'artifact_root': str(out.relative_to(ROOT)), 'read_outputs': len(predictions),
        'native_task_plan_rows': len(scores), 'mothers': len(view_ids),
        'native_tasks_handled': sum(row['handled'] for row in scores),
        'native_task_plan_rows_with_positive_grade': sum(row['grade'] > 0 for row in scores),
        'candidate_native_metrics': aggregates, 'M1_selected_native_metrics': m1_report,
        'M2_transfer_target_views': transfer,
        'M2_risk_informed_selection_views': {
            mode: sum(target['M2'][mode]['risk_informed_ranking'] for target in decision['decisions'])
            for mode in ('unrestricted', 'detectable_residual')},
        'no_method_advantage_or_structural_transfer_claim': True,
        'SCOPE_completion_checked_elsewhere': True, 'full_formal_training_or_TEST_complete': False,
        'new_model_requests': 0, 'new_independent_trials': 0}
    immutable_json(out / 'report.json', report)
    print(json.dumps({key: report[key] for key in ('artifact_root', 'read_outputs', 'native_task_plan_rows',
        'mothers', 'native_tasks_handled', 'native_task_plan_rows_with_positive_grade',
        'new_model_requests', 'new_independent_trials')}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m2-selection', type=Path, required=True)
    run(parser.parse_args().m2_selection)


if __name__ == '__main__':
    main()
