"""Audit learned-route Diversity readings at a settled DEV checkpoint."""

import argparse
from collections import Counter, defaultdict
import sqlite3

from experiments.convergence_dev_b0 import POINTER as DEV_B0
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read
from legal_skill_guard.paired_interfaces import diversity, diversity_claim_groups, diversity_relational, residual
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


ARMS = ('method_one_only', 'common_teacher_skill_learning', 'both', 'method_two_only')


def _unit_checks(source, reading, plan):
    reference = diversity.audit_source(source['views'][0]['public']['source_text'])
    amounts = defaultdict(list)
    for claim in reference['claims']:
        amounts[claim['plaintiff'], claim['defendant']].append(claim['amount'])
    local = (reading.get('decoder_receipt') or {}).get('local_receipts', {})
    checks = {}
    for name, unit in plan['relational_program']['units'].items():
        kind = unit['template_key'].split(':', 1)[0]
        context = unit['entity_context']
        if kind == 'citizenship':
            state = {role + '_state': reference['citizenship'][context[role]] for role in ('plaintiff', 'defendant')}
        else:
            values, = {tuple(amounts[tuple(pair)]) for pair in context['covered_pairs']}
            if len(values) != context['claim_count'] or any(value < 0 or value % 1000 for value in values):
                raise ValueError('The literal claim amounts are outside the audited coordinate domain')
            state = {f'claim{i}': min(76, amount // 1000) for i, amount in enumerate(values)}
        actual = local.get(name, {}).get('source_read', {}).get('values')
        check = residual.source_fidelity(diversity_relational.module(kind), unit['asset'], actual,
            admissible_states=[state], provenance=[{'kind': 'explicit_source',
            'evidence_sha256': reference['source_text_sha256']}]) if actual is not None else {
            'status': 'unread', 'source_fidelity_verified': False}
        checks[name] = {'kind': kind, 'status': check['status'], 'source_fidelity_verified': check['source_fidelity_verified']}
    return checks


def run(batch=1):
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    dev_root = ROOT / read(DEV_B0)['artifact_root']
    dev = read(dev_root / 'public_DEV_sources.json')
    directories = {arm: root / 'dev' / f'B{batch}' / arm for arm in ARMS}
    cells = {arm: verify(read(path / 'scores.json'), 'cell_sha256') for arm, path in directories.items()}
    provider = diversity_claim_groups.Provider()
    results = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for source in dev:
            if source['dataset'] != 'LegalBench_Diversity' or source['project_split'] != 'dev':
                continue
            key = source['key']
            prediction = read(directories['method_one_only'] / 'predictions' / (digest(key) + '.json'))
            result = prediction['result']
            if result['selection']['route'] != 'synthesized_interface':
                continue
            reading, = result['reads']
            physical = reading['physical_call_id']
            if db.execute('select status,source,purpose from calls where id=?', (physical,)).fetchone() != (
                    'completed', key, 'skill_dev'):
                raise ValueError('The audited route must bind an actual settled DEV reading')
            view, = provider.views(source)
            plan, = (option for option in view['plans'] if option['version'] == reading['raw_read_version'])
            checks = _unit_checks(source, reading, plan)
            grades = {arm: next(row['grade'] for row in cell['source_scores'] if row['source'] == key)
                      for arm, cell in cells.items()}
            results.append({'source': key, 'physical_call_id': physical, 'prediction_sha256': digest(prediction),
                'all_local_relations_source_faithful': all(check['source_fidelity_verified'] for check in checks.values()),
                'checks': checks, 'baseline_native': grades['common_teacher_skill_learning'], 'M1_native': grades['method_one_only']})
    if len({row['physical_call_id'] for row in results}) != len(results):
        raise ValueError('Each audited mother needs its own measured reading')
    repaired = [row for row in results if row['M1_native'] > row['baseline_native']]
    summary = {'sources_using_synthesized_interface': len(results),
               'fully_source_faithful': sum(row['all_local_relations_source_faithful'] for row in results),
               'repaired': len(repaired), 'regressed': sum(row['M1_native'] < row['baseline_native'] for row in results),
               'repairs_fully_source_faithful': sum(row['all_local_relations_source_faithful'] for row in repaired),
               'local_checks_by_kind': {kind: dict(Counter(check['status'] for row in results
                   for check in row['checks'].values() if check['kind'] == kind))
                   for kind in ('citizenship', 'single_claim', 'same_pair_claims')},
               'used_for_inference': False, 'TEST_opened': False}
    receipt = {'DEV_cell_sha256': {arm: cell['cell_sha256'] for arm, cell in cells.items()}, 'summary': summary, 'rows': results}
    path = BASE / f'm1_B{batch}_dev_source_audit' / digest(receipt) / 'terminal.json'
    immutable_json(path, receipt)
    immutable_json(HANDOFF / f'B{batch}_M1_DEV_source_audit_20261118.json',
                   {'receipt': str(path.relative_to(ROOT)), **summary})
    print(summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=int, choices=(1, 2, 4, 8), default=1)
    run(parser.parse_args().batch)
