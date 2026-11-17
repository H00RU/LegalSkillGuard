"""Read-only study/ledger audit and immutable result delivery; no dispatch."""
import argparse
import json
from pathlib import Path

from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_delivery import (
    EvidenceReader, completeness, contrasts, cost_summary, csv_text, load_diagnostics,
    load_main, physical_references, read_ledger, training_accounting)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
PUBLIC = {'train': ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
          'dev': BASE / 'prepared/dev/public.json', 'test': BASE / 'prepared/sealed_test/public.json'}


def immutable_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = text.encode()
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('A delivered artifact changed: ' + str(path))
    if not path.exists(): path.write_bytes(raw)


def run(study_root=None, *, draws=10000):
    if type(draws) is not int or draws < 100:
        raise ValueError('Prespecify at least100 mother resamples')
    if study_root is None:
        study_root = ROOT / read(BASE / 'handoff/current_checkpoint.json')['formal_main_study_preparation']['artifact_root']
    study_root = Path(study_root).resolve()
    reader = EvidenceReader(study_root)
    protocol = reader.read('protocol.json')
    cohorts = {}
    for split, path in PUBLIC.items():
        if sha(path) != protocol['source_partition_bytes'][split]['public']:
            raise ValueError('Use the original public source manifest,never an old exposed TEST substitute')
        cohorts[split] = read(path)
    for name, expected in protocol['source_sha256'].items():
        if sha(study_root / 'source_snapshot' / name) != expected:
            raise ValueError('A frozen scientific source snapshot changed')
    state = completeness(study_root, cohorts, protocol['postfreeze_diagnostic_design'])
    records = read_ledger(LEDGER)
    prefix = 'two_method_formal_v1_20261117_' + study_root.name[:16] + '_'
    study_calls = [r for r in records if r['id'].startswith(prefix)]
    goal_calls = [r for r in records if r['id'].startswith('two_method_')]
    rejected = [r for r in records if r['id'].startswith('two_method_train128_references_v1_20261117:')]
    baseline = read(BASE / 'handoff/baseline.json')
    costs = {'continuous_ledger_snapshot_sha256': digest(records),
        'continuous_role_status_counts': {role + ':' + status: sum(r['role'] == role and r['status'] == status for r in records)
            for role, status in sorted({(r['role'], r['status']) for r in records})},
        'continuous_physical_requests': len(records),
        'new_goal_run_id_prefix': 'two_method_',
        'new_goal_prefix_count_reconciles_original_baseline': len(records) == sum(r[2] for r in baseline['ledger_counts']) + len(goal_calls),
        'new_goal_physical_costs': cost_summary(goal_calls, executor_context=protocol['executor']['context_tokens']),
        'this_formal_study_physical_costs': cost_summary(study_calls, executor_context=protocol['executor']['context_tokens']),
        'rejected96_phase_actual_calls': len(rejected), 'scope_does_not_authorize_or_retry_any_call': True,
        'continuous_ledger_and_cached_physical_costs_never_reset': True}
    tables, result = {}, None
    if state['all_required_files_present']:
        if any(r['status'] == 'reserved' for r in study_calls):
            raise ValueError('A formal study request is still live;delivery must wait for its actual settlement')
        main = load_main(reader, cohorts, draws=draws)
        binding = main['training']['study_binding']
        if binding.get('protocol_sha256') != sha(study_root / 'protocol.json'):
            raise ValueError('The result belongs to another original study protocol')
        diagnostic = load_diagnostics(reader, cohorts, protocol['postfreeze_diagnostic_design'], main, draws=draws)
        training_details = training_accounting(reader, main, records, context_tokens=protocol['executor']['context_tokens'])
        ledger_by_id = {r['id']: r for r in records}
        for evidence in main['training']['actual_control_completion_evidence'].values():
            identities = evidence['actual_fixed_optimizer_teacher_calls']
            if len(set(identities)) != 20:
                raise ValueError('Every control needs all20 actual fixed optimizer stages')
            for identity in identities:
                row = ledger_by_id[identity]
                if row['role'] != 'teacher' or row['status'] != 'completed' or not identity.startswith(prefix):
                    raise ValueError('A claimed optimizer stage has no actual completed original-study teacher request')
        refs = physical_references(diagnostic)
        refs.update(training_details['physical_ids'])
        for path in sorted(reader.inputs):
            if '/predictions/' in path:
                refs.update(physical_references(reader.read(path)))
        for identity in refs:
            if identity not in ledger_by_id or ledger_by_id[identity]['status'] not in ('completed', 'failed'):
                raise ValueError('A reused physical response is absent or unsettled in the continuous ledger')
        costs['evaluated_physical_response_ids'] = sorted(refs)
        costs['reused_previous_run_physical_response_ids'] = sorted(i for i in refs if not i.startswith(prefix))
        costs['old_physical_costs_are_not_rebilled_or_independent_trials'] = True
        comparisons = contrasts(main['metrics'], draws=draws) + diagnostic['comparisons']
        tables = {'native_tasks.csv': main['native_rows'] + diagnostic['native_rows'],
            'dataset_metrics.csv': main['metrics'] + diagnostic['metrics'],
            'paired_contrasts.csv': comparisons,
            'execution_modes.csv': main['execution_modes'],
            'transfer_predictions.csv': diagnostic['transfer_prediction_diagnostics'],
            'TRAIN_local_graph_disagreement.csv': training_details['graph_pairs'],
            'comparison_information_budgets.csv': training_details['comparison_budgets'],
            'DEV_learning_curve.csv': [r for r in main['metrics'] if r['partition'] == 'dev']}
        tables['mother_scores.csv'] = [{k: metric[k] for k in ('partition', 'arm', 'batch', 'dataset')} |
            {'source': source, 'native_mother_score': value}
            for metric in main['metrics'] + diagnostic['metrics'] for source, value in metric['per_mother'].items()]
        result = {'main_and_fixed_diagnostic_evidence_verified': True,
            'source_counts': {k: len(v) for k, v in cohorts.items()},
            'curve_cells': 28, 'test_cells': 7, 'metrics': main['metrics'] + diagnostic['metrics'],
            'paired_contrasts': comparisons,
            'raw_metrics': 'official EC/EV F1 for OE;native exact match within each other dataset',
            'no_cross_dataset_or_metric_unit_headline_average': True,
            'source_bootstrap_not_five_training_runs_or_guaranteed_rule_family_coverage': True,
            'M1_operator_endpoints_equal_and_not_independent_trials': True,
            'MOAR_uses_current_TRAIN_feedback_after_full_prediction_seal': True,
            'natural_source_novelty_and_two_method_advantage_require_separate_scientific_evidence': True,
            'complete_goal_claimed': False}
    source_paths = [Path(__file__), ROOT / 'legal_skill_guard/paired_delivery.py',
                    ROOT / 'legal_skill_guard/paired_delivery_plots.py',
                    ROOT / 'experiments/requirements_paired_plotting.txt']
    report_protocol = {'experiment': 'offline_formal_evidence_delivery_v1',
        'study_root': str(study_root.relative_to(ROOT)), 'study_protocol_sha256': sha(study_root / 'protocol.json'),
        'reporting_source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        'input_files_sha256': reader.inputs, 'ledger_snapshot_sha256': digest(records),
        'missing_files': state['missing_files'], 'bootstrap_draws': draws, 'bootstrap_seed': 45,
        'no_new_model_calls_or_native_grading': True, 'complete_goal_claimed': False}
    out = BASE / 'formal_delivery_v1' / digest(report_protocol)
    if (out / 'manifest.json').exists():
        previous = read(out / 'manifest.json')
        if read(out / 'protocol.json') != report_protocol:
            raise ValueError('A saved delivery belongs to changed inputs')
        for name, expected in previous['output_files_sha256'].items():
            if sha(out / name) != expected:
                raise ValueError('A delivered output changed: ' + name)
        return out, previous
    immutable_json(out / 'protocol.json', report_protocol)
    immutable_json(out / 'readiness.json', state)
    immutable_json(out / 'costs.json', costs)
    for p in source_paths:
        immutable_text(out / 'source_snapshot' / p.relative_to(ROOT), p.read_text())
    if goal_calls:
        immutable_text(out / 'new_goal_physical_requests.csv', csv_text(costs['new_goal_physical_costs']['per_physical_request']))
    if result is not None:
        immutable_json(out / 'evaluation_report.json', result)
        for name, rows in tables.items(): immutable_text(out / name, csv_text(rows))
        from legal_skill_guard.paired_delivery_plots import plot_curves
        plots = plot_curves(tables['DEV_learning_curve.csv'], out / 'figures')
        immutable_json(out / 'plot_manifest.json', plots)
    else:
        immutable_text(out / 'INCOMPLETE.md', 'Formal evaluation is incomplete.\n\n'
            + f"{len(state['missing_files'])} required artifacts are missing. No result table or learning curve was fabricated.\n"
            + 'See readiness.json for the exact missing files and costs.json for the continuous physical accounting.\n')
    output_files = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                    if p.is_file() and p.name != 'manifest.json'}
    summary = {'artifact_root': str(out.relative_to(ROOT)), 'missing_required_files': len(state['missing_files']),
        'full_evaluation_report_written': result is not None, 'goal_physical_requests': len(goal_calls),
        'formal_physical_requests': len(study_calls), 'rejected96_phase_calls': len(rejected),
        'new_model_calls': 0, 'complete_goal_claimed': False, 'output_files_sha256': output_files}
    immutable_json(out / 'manifest.json', summary)
    return out, summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-root', type=Path)
    parser.add_argument('--bootstrap-draws', type=int, default=10000)
    args = parser.parse_args()
    _, summary = run(args.study_root, draws=args.bootstrap_draws)
    print(json.dumps({k: v for k, v in summary.items() if k != 'output_files_sha256'}, ensure_ascii=False))
