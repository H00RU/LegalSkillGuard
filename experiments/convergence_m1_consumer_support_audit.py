"""Replay M1 TRAIN routing when its audited support must suffice for native outputs."""

import argparse
import json
from types import SimpleNamespace

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import pointer as fit_pointer
from experiments.convergence_m1_incumbent_audit import DATASET, M1, _control, _verify_reads
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read
from legal_skill_guard.paired_interfaces import diversity_claim_groups, relational_program
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def _saved_reads(through):
    stages = [ROOT / read(HANDOFF / 'formal_b1_m1_current.json')['artifact_root']]
    stages.extend(ROOT / read(fit_pointer(batch))['artifact_root'] for batch in range(2, through + 1))
    for stage in stages:
        terminal = read(stage / 'terminal.json')
        if terminal['TEST_opened'] or not terminal['status'].startswith('completed'):
            raise ValueError('Use only completed TRAIN candidate readings')
        for path in (stage / 'interface_reads').glob('*/decoded.json'):
            result = read(path)
            yield digest(result), result


def _support(observation, reading, plan):
    if (digest(reading) != observation['actual_read_sha256']
            or reading['physical_call_id'] != observation['physical_call_id']
            or reading['raw_read_version'] != plan['version']):
        raise ValueError('Reuse the exact original reading and consumer plan')
    program = plan['relational_program']
    record = reading.get('decoder_receipt')
    if not record:
        return False
    audited = observation['source_fidelity']['per_local_unit']
    locals_ = record['local_receipts']
    if set(audited) != set(locals_) or set(audited) != set(program['units']):
        raise ValueError('Every consumer local unit needs its own independent source audit')
    supported = {name: local['consumer']['outputs'] for name, local in locals_.items()
                 if audited[name]['source_fidelity_verified'] and local['consumer']['valid']}
    masked = {name: relational_program.evaluate(expr, supported) for name, expr in program['outputs'].items()}
    return all(value is not None and value == record['outputs'][name] for name, value in masked.items())


def run(through):
    fit = ROOT / read(fit_pointer(through))['artifact_root']
    root = ROOT / read(fit / 'binding.json')['checkpoint_root']
    study = read(root / 'binding.json')
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    terminal = read(fit / 'terminal.json')
    if journal._completed_batch(M1, through)['completed_batch_sha256'] != terminal['arm_receipts'][M1]:
        raise ValueError('Use the journaled M1 fit through the target batch')
    snapshot = journal.library(M1, through)['interface_library']
    observations = snapshot['observations']
    _verify_reads(observations)
    paid = dict(_saved_reads(through))
    provider = diversity_claim_groups.Provider()
    sources = [source for cohort in batches[:through] for source in cohort]
    views = {s['key']: provider.views(s)[0] for s in sources if s['dataset'] == DATASET}
    plans = {key: {plan['version']: plan for plan in view['plans']} for key, view in views.items()}
    indexed = {}
    for row in observations:
        pair = (row['source'], row['plan_version'])
        if pair in indexed:
            raise ValueError('One source and wire must use one physical observation')
        native_support = _support(row, paid[row['actual_read_sha256']], plans[pair[0]][pair[1]])
        indexed[pair] = {'supported': native_support, 'native': row['native_utility'],
                         'fully_faithful': row['source_fidelity']['all_local_relations_source_faithful'],
                         'physical_call_id': row['physical_call_id']}

    frozen_reader = SimpleNamespace(executor=SimpleNamespace(config=study['executor']))
    roster = [source['key'] for cohort in batches for source in cohort]
    folds = []
    for batch in range(2, through + 1):
        prefix = journal.library(M1, batch - 1)['interface_library']
        current = RelationalInterfaceLibrary.restore(root, actor=frozen_reader, train_sources=roster, snapshot=prefix)
        diagnostic = RelationalInterfaceLibrary.restore(root, actor=frozen_reader, train_sources=roster, snapshot=prefix)
        for row in diagnostic.records:
            pair = (row['source'], row['plan_version'])
            support = row['source_fidelity']['all_local_relations_source_faithful'] or indexed[pair]['supported']
            row['source_fidelity']['all_local_relations_source_faithful'] = support
        common, _ = _control(journal, batch)
        for source in batches[batch - 1]:
            key = source['key']
            if key not in views:
                continue
            outcomes = {}
            for name, learner in (('current', current), ('sufficient_native_support', diagnostic)):
                selected, _ = learner.choose(source, views[key])
                if selected['is_correct_fixed_raw_control']:
                    outcomes[name] = {'native': common[key], 'path': 'ordinary'}
                else:
                    actual = indexed[key, selected['version']]
                    outcomes[name] = {**actual, 'path': 'certified_reader', 'plan_version': selected['version']}
            folds.append({'source': key, 'batch': batch, 'common': common[key], **outcomes})
    rows = list(indexed.values())
    summary = {'paid_reads': len(rows), 'fully_faithful_reads': sum(r['fully_faithful'] for r in rows),
               'native_output_preserved_by_audited_subset': sum(r['supported'] for r in rows),
               'additional_native_correct_with_audited_subset': sum(r['native'] == 1 and r['supported']
                                                                  and not r['fully_faithful'] for r in rows),
               'chronological_targets': len(folds), 'ordinary_correct': sum(r['common'] for r in folds),
               'current_correct': sum(r['current']['native'] for r in folds),
               'sufficient_support_correct': sum(r['sufficient_native_support']['native'] for r in folds)}
    result = {'scope': 'fixed TRAIN only', 'M1_library_sha256': snapshot['snapshot_sha256'], 'through_batch': through,
              'summary': summary, 'folds': folds, 'new_model_calls': 0, 'runtime_rule_edited': False}
    out = BASE / 'm1_consumer_support_audit' / digest(result) / 'terminal.json'
    immutable_json(out, result)
    index = {'receipt': str(out.relative_to(ROOT)), **summary}
    immutable_json(HANDOFF / f'M1_consumer_support_through_B{through}_20261118.json', index)
    print(json.dumps(index, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--through', type=int, required=True, choices=range(2, 9))
    run(parser.parse_args().through)
