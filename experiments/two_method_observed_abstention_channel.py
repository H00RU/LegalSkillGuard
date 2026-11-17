"""Version observed production rejections separately from analysis unknowns.

No model requests, reference repairs, evaluation truth or native grading. Refit
each original version/context using the same dictionary/calibration split and
the additional declared absorbing decoder outcome. All older fits stay intact.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from experiments.two_method_graph_corpus import BASE, ROOT, read, restore_pair, serialize_pair, sha
from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit
from legal_skill_guard.paired_interfaces.observed_abstention import (
    OPERATOR, canonical_pair, edit_record, learn_dictionary)
from legal_skill_guard.paired_interfaces.structural_channel import fit, graph_key
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def fitted_groups(corpus):
    inventory, records = defaultdict(list), defaultdict(list)
    for row in corpus['inventory']:
        inventory[row['context'], row['version']].append(row)
    for row in corpus['pairs']:
        records[row['context'], row['version']].append(row)
    versions = defaultdict(set)
    for context, version in inventory:
        versions[context].add(version)
    groups = []
    for (context, version), items in sorted(inventory.items()):
        alpha = .05 / (2 * len(versions[context]))
        report = {'context': context, 'dataset': items[0]['dataset'],
            'native_tasks': items[0]['native_tasks'], 'plan': items[0]['plan'], 'version': version,
            'expected_views': len(items), 'missing_reference_reviews': 0, 'pending_reads': 0,
            'all_locked_development_and_calibration_inputs_ready': True,
            'confidence_selection_family': context, 'alpha_per_plan_and_mode': alpha}
        rows = records[context, version]
        development = [restore_pair(row['pair']) for row in rows if row['role'] == 'development']
        calibration = [restore_pair(row['pair']) for row in rows if row['role'] == 'calibration']
        try:
            dictionary = learn_dictionary(development)
            report.update(development_sources=sorted(dictionary['development_sources']),
                unmodeled_development_sources=dictionary['unmatched_development_sources'],
                reference_native_domain_views=sum(bool(row['reference_native_consumer_domain']['handled']) for row in rows),
                edit_count=len(dictionary['edits']), edits=[edit_record(edit) for edit in dictionary['edits']],
                declared_absorbing_outcome=OPERATOR,
                calibration_production_abstentions=sum(row['observed_outcome']['production_abstention']
                    for row in rows if row['role'] == 'calibration'), channels={})
            for mode in ('unrestricted', 'detectable_residual'):
                channel = fit(calibration, dictionary, version=version, alpha=alpha, unknown_mode=mode)
                report['channels'][mode] = {'A': channel.A.tolist(), 'b': channel.b.tolist(),
                    'alpha': channel.alpha, 'diagnostics': channel.diagnostics,
                    'support_graph_keys': sorted(graph_key(graph) for graph in channel.support),
                    'calibration_sources': sorted(channel.sources),
                    'conditional_detectable_unknown_assumption': mode == 'detectable_residual',
                    'unknown_mass_not_set_to_zero': True,
                    'unknown_mass_one_feasible': bool(np.all(channel.A[:, -1] <= channel.b + 1e-10))}
            report['fitted'] = True
        except (ValueError, GraphMatchLimit) as error:
            report.update(fitted=False, unsupported=type(error).__name__ + ': ' + str(error))
        groups.append(report)
    return {'groups': groups, 'confidence_design': 'fixed_public_consumer_selection_family_v1',
        'familywise_alpha_per_consumer_and_both_modes': .05,
        'all_consumer_union_error_bound': min(1., .05 * len(versions)),
        'global_95_percent_coverage_claimed': False,
        'no_selection_or_transfer_claim_from_fit_alone': True}


def run(snapshot):
    snapshot = snapshot.resolve()
    if not snapshot.is_relative_to(BASE.resolve()):
        raise ValueError('Use the immutable current-project literal graph corpus')
    initial = read(snapshot / 'corpus.json')
    old_protocol_path = snapshot.parent.parent / 'protocol.json'
    old_protocol = read(old_protocol_path)
    if snapshot.name != digest(initial) or sha(old_protocol_path) != initial['postprocessing_protocol_sha256']:
        raise ValueError('The original corpus/protocol hash changed')
    if (not initial['inventory'] or len(initial['pairs']) != len(initial['inventory'])
            or any(row['role'] not in ('development', 'calibration') for row in initial['pairs'])
            or any(not row['reference_reviewed'] or not row['read_settled'] for row in initial['inventory'])):
        raise ValueError('Use the complete locked development/calibration corpus')
    own_paths = [str(Path(__file__).relative_to(ROOT)),
        'legal_skill_guard/paired_interfaces/observed_abstention.py']
    bindings = {**old_protocol['source_sha256'], **{name: sha(ROOT / name) for name in own_paths}}
    for name, expected in bindings.items():
        if sha(ROOT / name) != expected:
            raise ValueError('A frozen consumer or decoder source changed: ' + name)
    receipts = {}
    for row in initial['pairs']:
        if sha(ROOT / row['read_path']) != row['read_sha256']:
            raise ValueError('An original paid decode changed')
        path = ROOT / row['postprocessed_read_path']
        receipt = read(path)
        if ((receipt['source'], receipt['view'], receipt['plan'], receipt['physical_call_id']) !=
                (row['source'], row['view'], row['plan'], row['physical_call_id'])):
            raise ValueError('A production decode lost its source/view/plan/physical call binding')
        receipts[row['source'], row['view'], row['version']] = receipt
    protocol = {**old_protocol, 'experiment': 'observed_production_abstention_channel_v3',
        'source_sha256': bindings, 'original_corpus_snapshot': str(snapshot.relative_to(ROOT)),
        'original_corpus_sha256': sha(snapshot / 'corpus.json'),
        'production_decode_sha256': {row['postprocessed_read_path']: sha(ROOT / row['postprocessed_read_path'])
                                   for row in initial['pairs']},
        'declared_absorbing_outcome': OPERATOR,
        'analysis_alignment_unknowns_not_reclassified': True,
        'production_rejections_not_successes_or_structural_transfer_evidence': True,
        'old_channel_versions_not_pooled': True, 'new_model_requests': 0, 'new_independent_trials': 0}
    out = BASE / 'observed_abstention_channel_v3' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for name in own_paths:
        target = out / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('An immutable abstention-channel source snapshot changed')
        if not target.exists():
            target.write_bytes(raw)
    corpus = deepcopy(initial)
    corpus.update(protocol='audited-real-literal-pairs-with-observed-abstention-v3',
                  postprocessing_protocol_sha256=sha(out / 'protocol.json'), pairs=[], inventory=[])
    versions = {row['version']: digest({'previous_graph_channel_version': row['version'],
                                      'observed_abstention_protocol_sha256': sha(out / 'protocol.json')})
                for row in initial['inventory']}
    for original in initial['inventory']:
        row = deepcopy(original)
        row.update(previous_graph_channel_version=row['version'], version=versions[row['version']])
        corpus['inventory'].append(row)
    for original in initial['pairs']:
        row = deepcopy(original)
        receipt = receipts[row['source'], row['view'], row['version']]
        pair, outcome = canonical_pair(restore_pair(row['pair']), receipt)
        previous = row['version']
        pair = replace(pair, plan_version=versions[previous], provenance=digest({
            'previous_pair_provenance': pair.provenance,
            'observed_abstention_protocol_sha256': sha(out / 'protocol.json'),
            'production_decode_sha256': protocol['production_decode_sha256'][row['postprocessed_read_path']]}))
        row.update(pair=serialize_pair(pair), previous_graph_channel_version=previous,
                   version=versions[previous], observed_outcome=outcome)
        if outcome['production_abstention']:
            row['legacy_alignment'] = row['alignment']
            row['alignment'] = {'known_production_abstention': True,
                                'source_identity_or_semantic_values_not_inferred': True}
        corpus['pairs'].append(row)
    target = out / 'snapshots' / digest(corpus)
    immutable_json(target / 'corpus.json', corpus)
    fitted = fitted_groups(corpus)
    immutable_json(target / 'fitted_channels.json', fitted)
    for name, expected in bindings.items():
        if sha(ROOT / name) != expected:
            raise ValueError('A bound source changed during fitting: ' + name)
    summary = {'artifact_root': str(out.relative_to(ROOT)), 'corpus_snapshot': str(target.relative_to(ROOT)),
        'actual_pairs': len(corpus['pairs']),
        'observed_production_abstentions': sum(row['observed_outcome']['production_abstention'] for row in corpus['pairs']),
        'analysis_alignment_unknown_pairs': sum('unknown_observation' in row['alignment'] for row in corpus['pairs']),
        'fitted_groups': sum(bool(group.get('fitted')) for group in fitted['groups']),
        'calibration_pairs': sum(channel['channels']['unrestricted']['diagnostics']['pairs']
                                 for channel in fitted['groups'] if channel.get('fitted')),
        'unmodeled_calibration_pairs': sum(channel['channels']['unrestricted']['diagnostics']['unmatched_pairs']
                                          for channel in fitted['groups'] if channel.get('fitted')),
        'unknown_mass_one_feasible_channels': sum(record['unknown_mass_one_feasible']
            for group in fitted['groups'] if group.get('fitted') for record in group['channels'].values()),
        'new_model_requests': 0, 'new_independent_trials': 0,
        'reference_graphs_changed': False, 'native_consumers_changed': False,
        'structure_evaluation_reference_or_grading_opened': False,
        'no_nontrivial_selection_or_transfer_claim': True}
    immutable_json(target / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-snapshot', type=Path, required=True)
    run(parser.parse_args().corpus_snapshot)


if __name__ == '__main__':
    main()
