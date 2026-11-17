"""Offline delivery of sealed paired-interface evidence; never a model client.

Mother resampling describes this fixed cohort conditional on the fitted library.
It is not repeated-training uncertainty or a guarantee for unseen rule families.
No grading labels are accepted and no missing score is filled in.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import random
import sqlite3

from legal_skill_guard.paired_interfaces.formal_design import ARMS, CURVES
from legal_skill_guard.paired_interfaces.formal_evaluation import check_library, verify
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.skill_evolution.objects import digest


MAIN_COMPARISONS = (
    ('M1_only', 'ordinary_teacher_skills'),
    ('M1_only', 'budget_matched_SCOPE_adaptation'),
    ('M1_M2', 'M1_only'),
    ('M1_M2', 'M1_full_trace_replay'),
    ('M2_fixed_interfaces', 'M1_only'),
)


def resampling_interval(values, *, draws=10000, seed=45):
    if not values or type(draws) is not int or draws < 100:
        raise ValueError('A nonempty complete cohort and at least100 resamples are required')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('Every mother needs a finite measured value')
    rng = random.Random(seed)
    samples = sorted(math.fsum(rng.choices(values, k=len(values))) / len(values) for _ in range(draws))
    def quantile(p):
        index = (draws - 1) * p
        lower = math.floor(index)
        return samples[lower] + (index - lower) * (samples[math.ceil(index)] - samples[lower])
    return {'mean': math.fsum(values) / len(values), 'interval': [quantile(.025), quantile(.975)],
        'resampling_unit': 'original mother source', 'resamples': draws, 'seed': seed,
        'method': 'percentile mother bootstrap,linear quantiles;conditional on this frozen library and cohort',
        'independent_training_runs_inferred_from_resampling': False,
        'resampling_repeats_model_training': False, 'rule_family_or_template_generalization_coverage_claimed': False,
        'one_mother_has_no_sampling_information': len(values) == 1}


def dataset_statistics(rows, expected, *, draws=10000):
    report = summarize(rows, expected)
    if any(type(r['handled']) is not bool or not r['handled'] and r['grade'] != 0 for r in rows):
        raise ValueError('Unresolved native tasks retain their explicit zero in the full denominator')
    for row in rows:
        if row.get('native_metrics', {}).get('grade', row['grade']) != row['grade']:
            raise ValueError('Native task score differs from its saved native metric')
    return {**report, 'mother_resampling': resampling_interval(
        [report['per_mother'][s] for s in sorted(report['per_mother'])], draws=draws)}


def paired_difference(left, right, *, draws=10000):
    a, b = left['per_mother'], right['per_mother']
    if not a or set(a) != set(b):
        raise ValueError('A paired contrast requires the exact same original mother cohort')
    delta = [a[s] - b[s] for s in sorted(a)]
    return {'mothers': len(a), 'per_mother_differences': dict(zip(sorted(a), delta)),
        **resampling_interval(delta, draws=draws),
        'different_native_metrics_or_datasets_pooled': False, 'automatic_mechanism_attribution': False}


def csv_text(rows):
    if not rows:
        raise ValueError('An empty result table cannot stand in for missing evaluation')
    fields = list(dict.fromkeys(key for row in rows for key in row))
    output = io.StringIO(newline=''); writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (list, dict)) else value for key, value in row.items()})
    return output.getvalue()


def read_ledger(path):
    # A sqlite read transaction captures a single authoritative ledger snapshot;
    # it never constructs EvolutionLedger or creates/reserves/repairs requests.
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('BEGIN')
        return [dict(zip(('id', 'role', 'purpose', 'source', 'status', 'reserved_at', 'result'), row))
            for row in db.execute('select id,role,purpose,source,status,reserved_at,result from calls order by id')]


def cost_summary(records, *, executor_context=None):
    details = []
    for row in records:
        value = json.loads(row['result']) if row['result'] else {}
        usage = value.get('usage')
        metered = isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
            for k in ('prompt_tokens', 'completion_tokens'))
        tokens = usage['prompt_tokens'] + usage['completion_tokens'] if metered else None
        if row['role'] == 'executor' and tokens is not None and executor_context and tokens > executor_context:
            raise ValueError('Actual token usage exceeds its explicitly bound executor context')
        item = {key: row[key] for key in ('id', 'role', 'purpose', 'source', 'status', 'reserved_at')}
        item.update(input_plus_output_tokens=tokens,
            original_result_sha256=digest(value) if row['result'] else None,
            billing_basis=value.get('billing_basis'),
            actual_cash_invoice_available=value.get('actual_cash_invoice_available'))
        for field in ('incremental_api_cash_usd', 'gpu_cost_usd', 'elapsed_seconds'):
            number = value.get(field)
            if number is not None and (type(number) not in (int, float) or not math.isfinite(number) or number < 0):
                raise ValueError('A recorded cost or duration is not a finite nonnegative measurement')
            item[field] = number
        details.append(item)
    groups = []
    for role, purpose in sorted({(r['role'], r['purpose']) for r in details}):
        group = [r for r in details if (r['role'], r['purpose']) == (role, purpose)]
        known = [r['input_plus_output_tokens'] for r in group if r['input_plus_output_tokens'] is not None]
        unknown = [r['id'] for r in group if r['input_plus_output_tokens'] is None]
        result = {'role': role, 'purpose': purpose, 'physical_requests': len(group),
            'statuses': dict(Counter(r['status'] for r in group)),
            'known_input_plus_output_tokens': sum(known), 'unmetered_requests': unknown,
            'actual_input_plus_output_tokens': sum(known) if not unknown else None}
        result['settled_executor_token_interval'] = ([sum(known), sum(known) + len(unknown) * executor_context]
            if role == 'executor' and executor_context and not any(r['status'] == 'reserved' for r in group) else None)
        for field in ('incremental_api_cash_usd', 'gpu_cost_usd', 'elapsed_seconds'):
            numbers = [r[field] for r in group if r[field] is not None]
            result[field] = {'sum_known_measurements': math.fsum(numbers) if numbers else None,
                             'unmeasured_requests': len(group) - len(numbers),
                             'total': math.fsum(numbers) if len(numbers) == len(group) else None}
        groups.append(result)
    return {'physical_requests': len(details), 'groups': groups, 'per_physical_request': details,
        'unknown_usage_prices_and_durations_not_zero_filled': True,
        'request_elapsed_seconds_are_not_GPU_hours': True,
        'cash_invoice_or_hardware_cost_not_inferred_from_tokens': True}


class EvidenceReader:
    def __init__(self, root):
        self.root = Path(root)
        self.inputs = {}

    def read(self, relative):
        path = self.root / relative
        raw = path.read_bytes()
        self.inputs[str(relative)] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)


def required_files(cohorts, diagnostic_plan):
    files = ['protocol.json', 'training_B8_seal.json', 'main_matrix_terminal.json',
        'evaluation/selection_freeze.json', 'postfreeze_choice_seal.json', 'diagnostics/terminal.json']
    for batch in range(9):
        files.append(f'batch_seals/B{batch}.json')
        files.extend(f'libraries/B{batch}/{arm}.json' for arm in ARMS)
        files.extend(f'interface_training/B{batch}/' + name for name in (
            'shared_verified_raw_evidence.json', 'predictions_before_grading.json',
            'prediction_seal.json', 'native_TRAIN_scores.json'))
    for phase in ('ordinary', 'scope'):
        files.extend(f'controls/{phase}/budget/limits/B{batch}.json' for batch in range(1, 9))
    for split, batches in (('dev', CURVES), ('test', (8,))):
        for batch in batches:
            for arm in ARMS:
                directory = f'evaluation/{split}/B{batch}/{arm}'
                files.extend(directory + '/' + name for name in ('task.json', 'prediction_seal.json', 'scores.json'))
                files.extend(directory + '/predictions/' + digest(s['key']) + '.json' for s in cohorts[split])
    from legal_skill_guard.paired_interfaces.postfreeze_protocol import ABLATIONS
    for phase, labels, identities in (
        ('internal_structure', ARMS, diagnostic_plan['internal_structural_TRAIN_sources']),
        ('M1_ablation', ABLATIONS, diagnostic_plan['M1_ablation_fixed_TEST_sources'])):
        for label in labels:
            directory = f'diagnostics/{phase}/{label}'
            files.extend(directory + '/' + name for name in ('prediction_seal.json', 'scores.json'))
            files.extend(directory + '/predictions/' + digest(s) + '.json' for s in identities)
    files.extend('diagnostics/transfer/' + name for name in ('all_fixed_pool_predictions.json',
        'prediction_seal.json', 'all_fixed_candidate_native_scores.json', 'measured_MOAR_choices.json', 'report.json'))
    return files


def completeness(root, cohorts, diagnostic_plan):
    files = required_files(cohorts, diagnostic_plan)
    missing = [name for name in files if not (Path(root) / name).is_file()]
    return {'required_files': len(files), 'missing_files': missing,
        'all_required_files_present': not missing, 'file_presence_alone_proves_evaluation': False,
        'complete_goal_claimed': False}


def load_main(reader, cohorts, *, draws=10000):
    training = reader.read('training_B8_seal.json'); verify(training, 'training_seal_sha256')
    binding = training['study_binding']
    libraries = {(arm, batch): check_library(reader.read(f'libraries/B{batch}/{arm}.json'), arm, batch)
        for batch in range(9) for arm in ARMS}
    for batch in range(9):
        seal = reader.read(f'batch_seals/B{batch}.json'); verify(seal, 'batch_seal_sha256')
        if (seal['study_binding'] != binding or not seal['all_seven_libraries_frozen'] or seal['batch'] != batch
                or seal['libraries'] != {arm: libraries[arm, batch]['snapshot_sha256'] for arm in ARMS}
                or training['completed_original_prefix_seals'][str(batch)] != seal['batch_seal_sha256']):
            raise ValueError('A prefix seal differs from the original seven frozen libraries')
    if (training['libraries'] != {arm: libraries[arm, 8]['snapshot_sha256'] for arm in ARMS}
            or not training['all_seven_libraries_frozen'] or training['batch'] != 8):
        raise ValueError('The final training seal differs from its B8 libraries')
    freeze = reader.read('evaluation/selection_freeze.json'); verify(freeze, 'freeze_sha256')
    if (freeze['training_B8_seal'] != training or freeze['study_binding'] != binding
            or freeze['TEST_grading_opened_for_selection'] is not False
            or any(freeze[split.upper() + '_public_sha256'] != digest(cohorts[split]) for split in ('dev', 'test'))):
        raise ValueError('The final selection did not preserve original training/cohort/label boundaries')
    source_rows, metrics, modes, cells = [], [], [], {}
    for split, batches in (('dev', CURVES), ('test', (8,))):
        for batch in batches:
            for arm in ARMS:
                directory = f'evaluation/{split}/B{batch}/{arm}'
                report = reader.read(directory + '/scores.json'); verify(report, 'cell_sha256')
                task = reader.read(directory + '/task.json')
                seal = reader.read(directory + '/prediction_seal.json'); verify(seal, 'prediction_seal_sha256')
                if (any(report[k] != v for k, v in task.items()) or task['study_binding'] != binding
                        or (task['partition'], task['arm'], task['batch']) != (split, arm, batch)
                        or task['public_cohort_sha256'] != digest(cohorts[split])
                        or seal['task_sha256'] != digest(task)
                        or report['prediction_seal_sha256'] != seal['prediction_seal_sha256']
                        or not seal['all_predictions_saved_before_this_cell_grading']):
                    raise ValueError('A main cell lost its task/prediction/source binding')
                if set(report['datasets']) != {s['dataset'] for s in cohorts[split]}:
                    raise ValueError('A main cell changed its declared dataset denominator')
                selected = ({d: freeze['choices'][arm][d]['library_sha256'] for d in task['libraries']}
                    if split == 'test' else {s['dataset']: libraries[arm, batch]['snapshot_sha256'] for s in cohorts[split]})
                if task['libraries'] != selected or task['freeze_sha256'] != (freeze['freeze_sha256'] if split == 'test' else None):
                    raise ValueError('The cell did not execute its original per-dataset frozen checkpoint')
                predictions = {}
                for source in cohorts[split]:
                    prediction = reader.read(directory + '/predictions/' + digest(source['key']) + '.json')
                    if (prediction['source'] != source['key'] or prediction['public_source_sha256'] != digest(source)
                            or prediction['library_sha256'] != selected[source['dataset']]
                            or prediction['fallback_executed'] is not False):
                        raise ValueError('A scored prediction lost its original source/library')
                    predictions[source['key']] = prediction
                    result = prediction['result']
                    if set(result['native']) != {v['id'] for v in source['views']} or any(
                            type(v['handled']) is not bool for v in result['native'].values()):
                        raise ValueError('Every actual native output needs its original task and handling status')
                    checkpoint = freeze['choices'][arm][source['dataset']]['checkpoint_batch'] if split == 'test' else batch
                    modes.append({'partition': split, 'arm': arm, 'batch': batch, 'source': source['key'],
                        'dataset': source['dataset'], 'library_checkpoint_batch': checkpoint,
                        'execution_mode': result.get('execution_mode', 'interface_initialization' if checkpoint == 0 else 'interface_selection'),
                        'learned_program_main_path_executed': result.get('learned_main_path_executed'),
                        'fallback_executed': prediction['fallback_executed'],
                        'pre_generation_domain_refusals': sum(bool(d.get('pre_generation_domain_refusal')) for d in result.get('decisions', [])),
                        'risk_informed_interface_rankings': sum(bool(d.get('choice', {}).get('risk_informed_ranking')) for d in result.get('decisions', [])),
                        'risk_rankings_that_change_baseline': sum(bool(d.get('choice', {}).get('risk_informed_ranking'))
                            and bool(d.get('choice', {}).get('changed_baseline')) for d in result.get('decisions', [])),
                        'comparison_budget_refusals': len(result.get('pre_generation_comparison_refusals', []))})
                if seal['predictions_sha256'] != {s: digest(p) for s, p in predictions.items()}:
                    raise ValueError('The score seal differs from the saved predictions')
                by_source = {s['key']: s for s in cohorts[split]}
                for row in report['source_scores']:
                    if row['dataset'] != by_source[row['source']]['dataset']:
                        raise ValueError('A native task was relabelled as another dataset')
                    output = predictions[row['source']]['result']['native'][row['view']]
                    if row['handled'] != output['handled'] or row['answer'] != output.get('answer') or row['fallback_executed'] is not False:
                        raise ValueError('A native score differs from its actual saved output')
                for dataset in sorted({s['dataset'] for s in cohorts[split]}):
                    rows = [r for r in report['source_scores'] if r['dataset'] == dataset]
                    expected = {(s['key'], v['id']) for s in cohorts[split] if s['dataset'] == dataset for v in s['views']}
                    stat = dataset_statistics(rows, expected, draws=draws)
                    if report['datasets'][dataset] != {k: stat[k] for k in report['datasets'][dataset]}:
                        raise ValueError('A reported aggregate cannot be reproduced from every mother/native task')
                    metrics.append({'partition': split, 'arm': arm, 'batch': batch, 'dataset': dataset, **stat})
                source_rows.extend({'partition': split, 'arm': arm, 'batch': batch, **r} for r in report['source_scores'])
                cells[split, arm, batch] = report
    for arm in ARMS:
        for dataset, choice in freeze['choices'][arm].items():
            eligible = (0,) if arm == 'empty' else (1, 4, 8)
            best = max(eligible, key=lambda b: (cells['dev', arm, b]['datasets'][dataset]['mother_macro'], b))
            if (choice['checkpoint_batch'] != best or choice['library_sha256'] != libraries[arm, best]['snapshot_sha256']
                    or choice['DEV_mother_macro'] != cells['dev', arm, best]['datasets'][dataset]['mother_macro']):
                raise ValueError('Final DEV checkpoint selection is not the predeclared rule')
    if freeze['DEV_cells'] != {a + ':B' + str(b): cells['dev', a, b]['cell_sha256'] for a in ARMS for b in CURVES}:
        raise ValueError('The TEST freeze changed the full original DEV selection evidence')
    terminal = reader.read('main_matrix_terminal.json')
    if (terminal['study_binding'] != binding or terminal['training_seal_sha256'] != training['training_seal_sha256']
            or terminal['selection_freeze_sha256'] != freeze['freeze_sha256']
            or terminal['DEV_cells'] != [cells['dev', a, b]['cell_sha256'] for b in CURVES for a in ARMS]
            or terminal['TEST_cells'] != [cells['test', a, 8]['cell_sha256'] for a in ARMS]):
        raise ValueError('The terminal does not prove the complete original28+7 matrix')
    return {'native_rows': source_rows, 'metrics': metrics, 'execution_modes': modes,
            'training': training, 'freeze': freeze, 'libraries': libraries}


def contrasts(metrics, pairs=MAIN_COMPARISONS, *, draws=10000):
    lookup = {(r['partition'], r['batch'], r['dataset'], r['arm']): r for r in metrics}
    rows = []
    for split, batch, dataset in sorted({key[:3] for key in lookup}):
        for left, right in pairs:
            if (split, batch, dataset, left) not in lookup or (split, batch, dataset, right) not in lookup:
                raise ValueError('A predeclared contrast is missing one complete arm')
            rows.append({'partition': split, 'batch': batch, 'dataset': dataset,
                'left': left, 'right': right, **paired_difference(lookup[split, batch, dataset, left],
                                                               lookup[split, batch, dataset, right], draws=draws)})
    return rows


def load_diagnostics(reader, cohorts, plan, main, *, draws=10000):
    from legal_skill_guard.paired_interfaces.postfreeze_protocol import (
        ABLATIONS, TRANSFER_SYSTEMS, measured_MOAR_choices)
    choice = reader.read('postfreeze_choice_seal.json'); verify(choice, 'diagnostic_seal_sha256')
    if (choice['design'] != plan or choice['training_seal_sha256'] != main['training']['training_seal_sha256']
            or choice['main_B8_libraries'] != main['training']['libraries']
            or not choice['prepared_before_DEV_TEST_or_auxiliary_target_grading']):
        raise ValueError('Diagnostics lost their original pre-evaluation training/choice seal')
    public = {s['key']: s for values in cohorts.values() for s in values}
    native_rows, metrics, prediction_records = [], [], []
    for phase, labels, identities in (
        ('internal_structure', ARMS, plan['internal_structural_TRAIN_sources']),
        ('M1_ablation', ABLATIONS, plan['M1_ablation_fixed_TEST_sources'])):
        partition = 'test' if phase == 'M1_ablation' else 'train'
        for label in labels:
            directory = f'diagnostics/{phase}/{label}'
            report = reader.read(directory + '/scores.json')
            seal = reader.read(directory + '/prediction_seal.json'); verify(seal, 'diagnostic_prediction_seal_sha256')
            if (seal != report['prediction_seal'] or seal['diagnostic_seal_sha256'] != choice['diagnostic_seal_sha256']
                    or seal['source_cohort'] != identities or (seal['phase'], seal['label'], seal['partition']) != (phase, label, partition)
                    or not seal['all_predictions_saved_before_this_grading']):
                raise ValueError('A diagnostic cell changed its fixed source cohort or prediction seal')
            predictions = []
            for identity in identities:
                prediction = reader.read(directory + '/predictions/' + digest(identity) + '.json')
                library_sha = (choice['ablation_libraries'][label]['snapshot_sha256'] if phase == 'M1_ablation'
                               else main['training']['libraries'][label])
                if (prediction['source'] != identity or prediction['public_sha256'] != digest(public[identity])
                        or prediction['library_sha256'] != library_sha):
                    raise ValueError('A diagnostic prediction lost its source/library binding')
                predictions.append(prediction)
            if digest(predictions) != seal['predictions_sha256']:
                raise ValueError('Diagnostic scores differ from their saved predictions')
            outputs = {p['source']: p['result']['native'] for p in predictions}
            for row in report['source_scores']:
                if (row['dataset'] != public[row['source']]['dataset']
                        or row['handled'] != outputs[row['source']][row['view']]['handled']):
                    raise ValueError('A diagnostic native score lost its actual output')
            for dataset in sorted({public[s]['dataset'] for s in identities}):
                expected = {(s, v['id']) for s in identities if public[s]['dataset'] == dataset for v in public[s]['views']}
                rows = [r for r in report['source_scores'] if r['dataset'] == dataset]
                stat = dataset_statistics(rows, expected, draws=draws)
                if report['datasets'][dataset] != {k: stat[k] for k in report['datasets'][dataset]}:
                    raise ValueError('A diagnostic aggregate cannot be reproduced')
                metrics.append({'partition': phase, 'batch': 8, 'arm': label, 'dataset': dataset, **stat})
            native_rows.extend({'partition': phase, 'batch': 8, 'arm': label, **r} for r in report['source_scores'])
            prediction_records.extend(predictions)
    directory = 'diagnostics/transfer/'
    reads = reader.read(directory + 'all_fixed_pool_predictions.json')
    probe = reader.read(directory + 'prediction_seal.json'); verify(probe, 'probe_prediction_seal_sha256')
    decisions = choice['transfer_decisions']
    keys = sorted((r['source'], r['view'], r['plan'], task) for r in reads for task in r['read']['native'])
    if (probe['diagnostic_seal_sha256'] != choice['diagnostic_seal_sha256']
            or probe['predictions_sha256'] != digest(reads) or probe['native_slot_keys_sha256'] != digest(keys)
            or probe['native_candidate_slots'] != len(keys) or probe['diagnostic_decisions_sha256'] != digest(decisions)
            or not probe['all_fixed_pool_predictions_saved_before_native_grading']):
        raise ValueError('The MOAR candidate pool lost its complete pre-grading prediction seal')
    scores = reader.read(directory + 'all_fixed_candidate_native_scores.json')
    moar = measured_MOAR_choices(scores, decisions, probe)
    if reader.read(directory + 'measured_MOAR_choices.json') != moar:
        raise ValueError('MOAR did not select from the actual sealed fixed-pool scores')
    score_keys = [(r['source'], r['opaque_view'], r['plan'], r['view']) for r in scores]
    if sorted(score_keys) != keys or len(score_keys) != len(set(score_keys)):
        raise ValueError('The fixed-pool transfer denominator changed')
    outputs = {(r['source'], r['view'], r['plan'], task): value for r in reads for task, value in r['read']['native'].items()}
    for row in scores:
        key = row['source'], row['opaque_view'], row['plan'], row['view']
        if row['handled'] != outputs[key]['handled'] or row['dataset'] != public[row['source']]['dataset']:
            raise ValueError('A transfer score differs from its saved output')
    report = reader.read(directory + 'report.json')
    moar_lookup = {(r['source'], r['view']): r['plan'] for r in moar}
    for arm in TRANSFER_SYSTEMS:
        selected = {(d['source'], d['view']): (moar_lookup[d['source'], d['view']] if arm == TRANSFER_SYSTEMS[-1]
                    else d['frozen_choices'][arm]['plan']) for d in decisions}
        rows = [r for r in scores if r['plan'] == selected[r['source'], r['opaque_view']]]
        if report['selected_native_rows'][arm] != rows:
            raise ValueError('A diagnostic choice was revised from target outcomes')
        for dataset in sorted({public[s]['dataset'] for s in plan['transfer_TRAIN_sources']}):
            expected = {(s, v['id']) for s in plan['transfer_TRAIN_sources'] if public[s]['dataset'] == dataset for v in public[s]['views']}
            stat = dataset_statistics([r for r in rows if r['dataset'] == dataset], expected, draws=draws)
            if report['system_native_metrics'][arm][dataset] != {k: stat[k] for k in report['system_native_metrics'][arm][dataset]}:
                raise ValueError('A transfer score aggregate cannot be reproduced')
            metrics.append({'partition': 'transfer_TRAIN', 'batch': 8, 'arm': arm, 'dataset': dataset, **stat})
        native_rows.extend({'partition': 'transfer_TRAIN', 'batch': 8, 'arm': arm, **r} for r in rows)
    terminal = reader.read('diagnostics/terminal.json')
    if (terminal['diagnostic_seal_sha256'] != choice['diagnostic_seal_sha256']
            or terminal['transfer_mothers'] != 12 or terminal['internal_structure_systems'] != 7
            or terminal['M1_ablation_variants'] != 3 or terminal['M1_ablation_TEST_cells'] != 6):
        raise ValueError('Fixed contribution diagnostics are incomplete')
    comparisons = []
    for phase, pairs in (
        ('internal_structure', MAIN_COMPARISONS),
        ('M1_ablation', ((ABLATIONS[1], ABLATIONS[0]), (ABLATIONS[2], ABLATIONS[0]), (ABLATIONS[1], ABLATIONS[2]))),
        ('transfer_TRAIN', tuple(('M1_M2', other) for other in ('M1_only', 'M1_full_trace_replay',
                                                           'independent_field_noise', 'MOAR_style_measured_fixed_pool')))):
        comparisons.extend(contrasts([r for r in metrics if r['partition'] == phase], pairs, draws=draws))
    return {'native_rows': native_rows, 'metrics': metrics, 'comparisons': comparisons,
        'transfer_prediction_diagnostics': report['per_source_consumer_selection_and_prediction_diagnostics'],
        'prediction_records': prediction_records, 'probe_reads': reads}


def physical_references(value):
    ids = set()
    if isinstance(value, dict):
        if isinstance(value.get('physical_call_id'), str): ids.add(value['physical_call_id'])
        for item in value.values(): ids.update(physical_references(item))
    elif isinstance(value, list):
        for item in value: ids.update(physical_references(item))
    return ids


def local_graph_diagnostics(rows):
    """Report local-schema disagreement,not complete legal truth/native error."""
    result, identities = [], set()
    for row in rows:
        key = row['source'], row['view'], row['plan']
        if key in identities: raise ValueError('A local reference/observation pair was duplicated')
        identities.add(key)
        pair, alignment = row['pair'], row['alignment']
        abstained = bool(alignment.get('production_abstention') or alignment.get('known_production_abstention')
                         or alignment.get('observed_outcome', {}).get('production_abstention'))
        unknown = bool(alignment.get('analysis_alignment_unknown') or alignment.get('unknown_observation')) and not abstained
        reference = digest(pair['reference'])
        possibilities = [float(digest(world) != reference) for world in pair['observed']]
        if not possibilities: raise ValueError('Unknown/failed local reads must retain an observed placeholder')
        interval = [1., 1.] if abstained else [0., 1.] if unknown else [min(possibilities), max(possibilities)]
        result.append({'source': row['source'], 'dataset': row['dataset'], 'view': row['view'], 'plan': row['plan'],
            'role': pair['role'], 'channel_version': pair['plan_version'], 'physical_call_id': row['physical_call_id'],
            'production_abstention': abstained, 'analysis_alignment_unknown': unknown,
            'distinct_observation_alternatives': len(pair['observed']),
            'local_schema_disagreement_interval': interval,
            'conditional_on_scoped_source_review_not_complete_legal_gold': True,
            'native_failure_inferred_from_graph_mismatch': False})
    return result


def training_accounting(reader, main, records, *, context_tokens):
    from legal_skill_guard.paired_interfaces.control_accounting import usage_summary
    ledger = {r['id']: r for r in records}
    for batch in range(9):
        directory = f'interface_training/B{batch}/'
        raw = reader.read(directory + 'shared_verified_raw_evidence.json')
        predictions = reader.read(directory + 'predictions_before_grading.json')
        seal = reader.read(directory + 'prediction_seal.json'); verify(seal, 'training_prediction_seal_sha256')
        scores = reader.read(directory + 'native_TRAIN_scores.json')
        if (raw['study_binding'] != main['training']['study_binding'] or seal['batch'] != batch
                or seal['study_binding'] != main['training']['study_binding']
                or seal['predictions_sha256'] != digest(predictions) or seal['source_only_reference_native_labels_opened']):
            raise ValueError('Raw TRAIN observations lost their pre-grading batch/study binding')
        expected = {(p['source'], p['plan'], task) for p in predictions for task in p['native']}
        actual = [(r['source'], r['plan'], r['view']) for r in scores]
        if set(actual) != expected or len(actual) != len(set(actual)):
            raise ValueError('TRAIN native scores dropped a fixed failed/domain-refusal candidate')
        for row in raw['pairs']:
            physical = ledger[row['physical_call_id']]
            if physical['status'] != 'completed' or physical['role'] != 'executor' or physical['source'] != row['source']:
                raise ValueError('A fitted TRAIN pair has no actual completed source-matched physical read')
    b8 = raw
    choice = reader.read('postfreeze_choice_seal.json')
    if choice['paired_TRAIN_records_sha256'] != digest(b8['pairs']):
        raise ValueError('Diagnostic fits differ from original frozen B8 TRAIN pairs')
    budgets = []
    for phase, arm in (('ordinary', 'ordinary_teacher_skills'), ('scope', 'budget_matched_SCOPE_adaptation')):
        final = main['training']['actual_control_completion_evidence'][arm]['comparison_budget']
        if final != main['libraries'][arm, 8]['comparison_budget']:
            raise ValueError('Final comparison evidence differs from the B8 frozen budget')
        observations = []
        for path in sorted((reader.root / 'controls' / phase / 'budget/observations').glob('*.json')):
            row = reader.read(str(path.relative_to(reader.root))); verify(row, 'observation_sha256')
            physical = ledger[row['physical_call_id']]
            if (physical['source'] != row['source'] or physical['status'] != row['status']
                    or physical['role'] != 'executor' or physical['purpose'] != 'skill_actor'
                    or digest(json.loads(physical['result'])) != row['physical_result_sha256']):
                raise ValueError('A logical comparison receipt differs from its original physical response')
            if row['usage'] != usage_summary([(physical['id'], physical['status'], physical['result'])],
                                             context_tokens=context_tokens):
                raise ValueError('A logical observation token charge differs from its original physical meter')
            observations.append(row)
        if (len({r['observation_key'] for r in observations}) != len(observations)
                or final['unique_logical_observations'] != len(observations)
                or final['charged_input_plus_output_tokens'] != sum(r['usage']['conservatively_charged_input_plus_output_tokens'] for r in observations)
                or final['physical_call_ids'] != sorted({r['physical_call_id'] for r in observations})):
            raise ValueError('Comparison accounting counted repeated callbacks/cache as extra physical work')
        for batch in range(1, 9):
            limit = reader.read(f'controls/{phase}/budget/limits/B{batch}.json'); verify(limit, 'limit_sha256')
            summary = main['libraries'][arm, batch]['comparison_budget']
            prefix = reader.read(f'batch_seals/B{batch}.json')['primary_comparison_cap']
            if (limit['batch'] != batch or limit['evidence'] != prefix or limit['token_cap'] != summary['token_cap']
                    or summary['charged_input_plus_output_tokens'] > summary['token_cap']):
                raise ValueError('A control exceeds or changes its frozen original primary-prefix information budget')
            budgets.append({'arm': arm, 'batch': batch, **summary,
                'cached_logical_observation_is_not_an_independent_trial_or_new_physical_request': True})
    return {'graph_pairs': local_graph_diagnostics(b8['pairs']), 'comparison_budgets': budgets,
            'physical_ids': sorted(physical_references(b8))}
