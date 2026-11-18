"""Materialize the fixed-cohort score rows for the completed PARSE comparator."""

import json
import math
import sqlite3

from experiments.convergence_parse_pilot import FAMILY, POINTER
from experiments.convergence_pilot_b0 import HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def materialize():
    current = ROOT / read(POINTER)['artifact_root']
    binding = read(current / 'binding.json')
    terminal = read(current / 'terminal.json')
    if terminal['status'] != 'completed' or not all(row['status'] == 'completed'
                                                    for row in terminal['libraries'].values()):
        raise ValueError('The fixed external candidate must have actual measures in all five libraries')
    ordinary = ROOT / binding['ordinary_root']
    source_rows = read(ordinary / 'train_sources.json')
    baseline = read(ordinary / 'incumbent_scores.json')
    original = read(ordinary / 'binding.json')
    if (digest(original) != binding['ordinary_binding_sha256']
            or digest(source_rows) != binding['public_cohort_sha256']
            or digest(baseline) != original['native_incumbent_sha256']):
        raise ValueError('The comparison must use the exact fixed native cohort and baseline')
    cohorts = {dataset: [source for source in source_rows if source['dataset'] == dataset]
               for dataset in terminal['libraries']}
    parsed = []
    for dataset, libraries in cohorts.items():
        summary = terminal['libraries'][dataset]
        record = read(current / 'measured_libraries' / (dataset + '.json'))
        if record['summary'] != summary:
            raise ValueError('One library comparison differs from the terminal report')
        candidate = record['candidate_score_rows']
        expected = {(source['key'], task['id']) for source in libraries for task in source['views']}
        checked = summarize(candidate, expected)
        if len(libraries) != 4 or checked['mother_macro'] != summary['candidate_native']:
            raise ValueError('The normalized score must retain all measured original TRAIN outcomes')
        if summary['selected'] == 'candidate':
            parsed.extend(candidate)
            continue
        origin = 'cni_indexed_evidence_current.json' if dataset == 'ContractNLI' else 'pilot_b0_current.json'
        common = ROOT / read(HANDOFF / origin)['artifact_root']
        boundary = str(common.relative_to(ROOT))
        if sha(common / 'terminal.json') != original['common_terminal_receipts'][boundary]:
            raise ValueError('The referenced terminal incumbent evidence changed')
        for source in libraries:
            key = source['key']
            original_scores = read(common / 'source_results' / (digest(key) + '.json'))
            for task in source['views']:
                name = task['id']
                grade = baseline[key][name]
                handled = original_scores['native'][name]['handled']
                if grade != original_scores['grades'][name]['grade']:
                    if dataset != 'RuleArena_Airline' or grade != 1:
                        raise ValueError('Only the verified common Airline fee correction can replace the original scores')
                    handled = True
                parsed.append({'source': key, 'dataset': dataset, 'view': name, 'grade': grade, 'handled': handled})
    roots = [current]
    if recovery := binding.get('recovery'):
        parent = ROOT / recovery['root']
        if sha(parent / 'terminal.json') != recovery['terminal_sha256']:
            raise ValueError('The original complete teacher and valid program records changed')
        roots.append(parent)
    totals = {'teacher': {'calls': 0, 'tokens': 0}, 'executor': {'calls': 0, 'tokens': 0}}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for root in roots:
            prefix = 'convergence-parse-pilot-' + root.name[:16] + ':%'
            for role, status, raw in db.execute('select role,status,result from calls where id like ?', (prefix,)):
                if status != 'completed':
                    raise ValueError('The final comparison has an unsettled or unmeasured physical call')
                receipt = json.loads(raw)
                usage = receipt['usage'] if role == 'executor' else receipt['invocation']['usage']
                cost = usage['total_tokens'] if role == 'executor' else usage['input_tokens'] + usage['output_tokens']
                totals[role]['calls'] += 1
                totals[role]['tokens'] += cost
    if totals['teacher']['calls'] != 5 or totals['executor']['calls'] != 24:
        raise ValueError('The comparison must bind five actual proposals and twenty-four distinct native reads')
    result = {'family': FAMILY, 'rows': parsed,
              'matched_public_conditions_sha256': digest(binding['matched_public_conditions']),
              'comparison_logical_tokens': sum(role['tokens'] for role in totals.values()),
              'actual_calls_and_tokens': totals, 'paired_terminal_sha256': sha(current / 'terminal.json')}
    utilities = {dataset: max(row['candidate_native'], row['incumbent_native'])
                 for dataset, row in terminal['libraries'].items()}
    immutable_json(current / 'external_ranking_input.json', result)
    receipt = {'external_family': FAMILY, 'per_library_selection_utility': utilities,
               'equal_library_selection_utility': math.fsum(utilities.values()) / len(utilities),
               'candidate_rows': len(parsed), 'ranking_input_sha256': digest(result),
               'actual_calls_and_tokens': totals, 'strongest_family_selected': False}
    immutable_json(HANDOFF / 'parse_complete_fixed20_ranking_receipt_20261118.json', receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    materialize()
