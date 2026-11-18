"""Replay same-grammar M1 controls on the four locked Diversity pilot mothers."""

import argparse
import json
from types import SimpleNamespace

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_m1_incumbent_audit import DATASET, M1, _profile, _verify_reads
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


DESIGN = HANDOFF / 'm1_same_grammar_controls_prepared.json'
CONTROLS = ('fixed_raw', 'static_shortest_schema', 'generic_native_search', 'M1_source_faithful_search')


def _study():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    study = read(root / 'binding.json')
    if root.name != digest(study):
        raise ValueError('Use the originally bound convergence study')
    return root, study, load_roster(study)


def _length(plan):
    return len(json.dumps(plan['schema'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def prepare():
    _, study, batches = _study()
    pilot = ROOT / read(HANDOFF / 'source_audit_current.json')['artifact_root'] / 'pilot20.json'
    roster = read(pilot)
    keys = {r['source'] for r in roster if r['dataset'] == DATASET}
    provider = diversity_claim_groups.Provider()
    if len(roster) != 20 or len(keys) != 4:
        raise ValueError('Use the Diversity slice of the original fixed 20-source pilot')
    entries = []
    for batch, cohort in enumerate(batches, 1):
        for source in cohort:
            if source['key'] not in keys:
                continue
            view, = provider.views(source)
            entries.append({'source': source['key'], 'batch': batch, 'source_sha256': digest(source),
                            'candidate_versions': [p['version'] for p in view['plans']]})
    if {r['source'] for r in entries} != keys:
        raise ValueError('All pilot mothers must belong to the fixed TRAIN matrix')
    design = {'study_binding_sha256': digest(study), 'locked_pilot_sha256': sha(pilot), 'mothers': entries,
              'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in (
                  ROOT / 'experiments/convergence_m1_pilot_controls.py',
                  ROOT / 'experiments/convergence_m1_incumbent_audit.py',
                  ROOT / 'legal_skill_guard/paired_interfaces/formal_training.py')},
              'controls': CONTROLS, 'static_cost': 'UTF-8 bytes of the compact serialized certified schema',
              'generic_fit': 'mean native utility, fixed-first stable ties, identical compatible candidate set',
              'calibration': 'other fixed Diversity pilot mothers matched on reader condition',
              'design_uses_model_outputs_or_native_scores': False, 'new_model_calls': 0}
    immutable_json(DESIGN, design)
    return read(DESIGN)


def _choose_generic(plans, observations, learner, fixed):
    grouped = {plan['version']: {} for plan in plans}
    for plan in plans:
        profile = _profile(plan)
        reader = learner.reader_condition(plan)
        grouped[plan['version']] = {r['source']: r['native_utility'] for r in observations
                                    if tuple(map(tuple, r['profile'])) == profile
                                    and r['reader_condition_sha256'] == reader}
    matched = sorted(set.intersection(*(set(rows) for rows in grouped.values())))
    if not matched:
        return fixed, matched
    selected = min(plans, key=lambda p: (-sum(grouped[p['version']][key] for key in matched),
                                        not p['is_correct_fixed_raw_control'], p['name']))
    return selected, matched


def replay():
    design = prepare()
    root, study, batches = _study()
    journal = TrainingJournal(root, study, batches)
    sealed = journal._completed_batch(M1, 8)
    snapshot = journal.library(M1, 8)['interface_library']
    members = {r['source']: r for r in design['mothers']}
    paid = [r for r in snapshot['observations'] if r['source'] in members]
    _verify_reads(paid)
    sources = {r['key']: r for batch in batches for r in batch if r['key'] in members}
    adapter = SimpleNamespace(executor=SimpleNamespace(config=study['executor']))
    provider = diversity_claim_groups.Provider()
    results = []
    for target in design['mothers']:
        key = target['source']
        source = sources[key]
        view, = provider.views(source)
        plans = view['plans']
        versions = [p['version'] for p in plans]
        if target['source_sha256'] != digest(source) or target['candidate_versions'] != versions:
            raise ValueError('Use the same locked source, certified schema and composer')
        recorded = [r for r in paid if r['source'] == key]
        by_version = {r['plan_version']: r for r in recorded}
        if len(by_version) != len(recorded) or set(by_version) != set(versions):
            raise ValueError('Every choice requires its exact measured candidate read on the held-out pilot mother')
        fixed, = (p for p in plans if p['is_correct_fixed_raw_control'])
        shortest = min(plans, key=lambda p: (_length(p), not p['is_correct_fixed_raw_control'], p['name']))
        calibration = [r for r in paid if r['source'] != key]
        learner = RelationalInterfaceLibrary(root, actor=adapter, train_sources=members,
                                              initial_common_library_sha256=snapshot['initial_common_library_sha256'])
        learner.records = calibration
        learned, receipt = learner.choose(source, view)
        generic, matched = _choose_generic(plans, calibration, learner, fixed)
        if matched != receipt['paired_learning_sources']:
            raise ValueError('Generic and source-faithful selection require the same matched calibration cohort')
        selected = {}
        for name, plan in zip(CONTROLS, (fixed, shortest, generic, learned), strict=True):
            row = by_version[plan['version']]
            selected[name] = {'profile': _profile(plan), 'plan_sha256': plan['version'],
                              'native_utility': row['native_utility'], 'source_faithful':
                                  row['source_fidelity']['all_local_relations_source_faithful'],
                              'executor_tokens': row['usage']['total_tokens'], 'call_id': row['physical_call_id']}
        results.append({'source': key, 'matched_calibration_mothers': matched, 'selected': selected})
    aggregates = {}
    for name in CONTROLS:
        rows = [r['selected'][name] for r in results]
        aggregates[name] = {'native_correct': sum(r['native_utility'] for r in rows),
                            'source_faithful': sum(r['source_faithful'] for r in rows),
                            'referenced_executor_tokens': sum(r['executor_tokens'] for r in rows)}
    terminal = {'design_sha256': digest(design), 'sealed_B8_M1_receipt': sealed['completed_batch_sha256'],
                'matched_pilot_mothers': len(results), 'results': results, 'aggregates': aggregates,
                'new_model_calls': 0, 'heldout_opened': False}
    out = BASE / 'm1_pilot_controls' / digest(terminal) / 'terminal.json'
    immutable_json(out, terminal)
    print(json.dumps({'receipt': str(out.relative_to(ROOT)), 'aggregates': aggregates}, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'replay'))
    args = parser.parse_args()
    if args.phase == 'prepare':
        print(json.dumps(prepare(), sort_keys=True), flush=True)
    else:
        replay()
