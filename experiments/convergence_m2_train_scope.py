"""Recover natural ownership groups from the unchanged original TRAIN source reviews."""

import argparse
from pathlib import Path
import re

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_oe_natural_relation import OLD_TRAIN, REGISTRY, build_natural_group
from experiments.convergence_pilot_b0 import BASE, ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def ownership_groups(cohort):
    """Select one audited possession anchor per eligible mother, in cohort order."""
    if any(row['project_split'] != 'train' for row in cohort):
        raise ValueError('Natural supervision can use only the declared TRAIN mothers')
    sources = {row['key']: row for row in cohort if row['dataset'] == 'OpenExempt'}
    prior = {row['key']: row for row in read(OLD_TRAIN) if row['key'] in sources}
    registry = read(REGISTRY)
    reviews, covered, groups = {}, set(), {}
    for entry in sorted(registry['reviews'], key=lambda row: (row['source'], row['view'])):
        key = entry['source']
        if key not in sources or entry['kind'] != 'asset_program_ports':
            continue
        source, previous = sources[key], prior.get(key)
        if (previous is None or digest(previous) != registry['source_public_sha256'][key]
                or source['views'] != previous['views']):
            raise ValueError('Ownership supervision requires the unchanged audited native source')
        card_path = ROOT / entry['path']
        card_hash = sha(card_path)
        if card_hash != entry['sha256']:
            raise ValueError('The original source-only review may not be replaced')
        reviews[entry['path']] = card_hash
        card = read(card_path)
        if (card['source_semantic_truth_verified'] is not True or card['native_answers_used'] is not False
                or card.get('native_answers_used_to_create_or_repair_graph') is not False):
            continue
        covered.add(key)
        if key in groups:
            continue
        text = next(view['public']['original_input'] for view in source['views'] if view['id'] == 'EC')
        for asset in card['port_record']['assets']:
            ownership, amount = asset['ownership_evidence'], asset['fields']['asset_values']
            quote, label = ownership['quote'], asset['fields']['asset_descriptions']['value']
            if (ownership['status'] != 'unknown' or amount['status'] != 'stated' or not isinstance(quote, str)
                    or not isinstance(label, str) or label not in quote or text.count(quote) != 1
                    or not re.search(r'\bpossess(?:es)?\b', quote, re.I)):
                continue
            values = list(re.finditer(r'\$[\d,]+\.00\b', quote))
            if len(values) != 1:
                continue
            value = int(values[0].group()[1:-3].replace(',', ''))
            if value != amount['value']:
                continue
            offset = text.index(quote)
            start, end = values[0].span()
            group = build_natural_group(source, card_hash, label, (offset + start, offset + end), value)
            if not group['shared']['signatures'].keys() < group['independent']['signatures'].keys():
                raise ValueError('The confirmed EDIT must retain a shared ownership restriction')
            groups[key] = group
            break
    return ({key: groups[key] for key in sources if key in groups},
            {'all_review_hashes': reviews, 'mothers': len(sources), 'fully_verified_review_mothers': len(covered)})


def prepare():
    checkpoint = ROOT / read(BOOTSTRAP)['artifact_root']
    binding = read(checkpoint / 'binding.json')
    batches = load_roster(binding)
    results = []
    for batch, cohort in enumerate(batches, 1):
        groups, coverage = ownership_groups(cohort)
        results.append({'batch': batch, **coverage, 'groups': [{
            'source': key, 'source_edits_sha256': digest([case.public for case in group['cases']]),
            'allowed_shared': len(group['shared']['signatures']),
            'allowed_independent': len(group['independent']['signatures']),
        } for key, group in groups.items()]})
    source = Path(__file__).resolve()
    receipt = {'ordered_train_sha256': binding['TRAIN_ordered_batches_sha256'], 'registry_sha256': sha(REGISTRY),
               'source_sha256': sha(source), 'by_batch': results, 'physical_calls': 0, 'TEST_opened': False}
    immutable_json(BASE / 'm2_natural_train_scope' / digest(receipt) / 'terminal.json', receipt)
    print([(row['batch'], row['mothers'], row['fully_verified_review_mothers'], len(row['groups'])) for row in results])
    print(digest(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    prepare()
