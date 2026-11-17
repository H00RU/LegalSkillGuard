"""Compile an amount edit around naturally unresolved TRAIN ownership."""
import hashlib
import inspect
import json
from pathlib import Path
import re

from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase, Theory, allowed_relation, source_variant,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/legal_skill_convergence_20261117'
HANDOFF = BASE / 'handoff'
REGISTRY = (
    ROOT / 'artifacts/two_method_followthrough_20261116/formal_reference_registry_v1'
    / '428168f0c9a92d5ebda0a435d2919647380adb262207466bcd3debae9a8a1fd6'
    / 'manifest.json'
)
OLD_TRAIN = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(primitives, law):
    return {'ownership': primitives['ownership'], 'stated_value': primitives['amount']}


def eligible_assets():
    metadata = read(HANDOFF / 'normalized_inputs_current.json')
    current = {source['key']: source for source in read(ROOT / metadata['artifact_root'] / 'train/public.json')}
    pilot_root = ROOT / read(HANDOFF / 'source_audit_current.json')['artifact_root']
    pilot = {row['source'] for row in read(pilot_root / 'pilot20.json') if row['dataset'] == 'OpenExempt'}
    old = {source['key']: source for source in read(OLD_TRAIN) if source['key'] in pilot}
    registry = read(REGISTRY)
    for entry in sorted(registry['reviews'], key=lambda row: (row['source'], row['view'])):
        key = entry['source']
        if key not in pilot or entry['kind'] != 'asset_program_ports':
            continue
        normalized = current[key]
        if (digest(old[key]) != registry['source_public_sha256'][key]
                or normalized['views'] != old[key]['views']):
            raise ValueError('Reusing a review requires the same complete native source views')
        card_file = ROOT / entry['path']
        if sha(card_file) != entry['sha256']:
            raise ValueError('The frozen source-only review was changed')
        card = read(card_file)
        if (card['source_semantic_truth_verified'] is not True or card['native_answers_used'] is not False
                or card.get('native_answers_used_to_create_or_repair_graph') is not False):
            continue
        # The unresolved ownership is tied to the old literal EC view. This
        # does not borrow a later EV view or its solved assumptions.
        view = next(view for view in normalized['views'] if view['id'] == 'EC')
        sentence_source = view['public']['original_input']
        for asset in card['port_record']['assets']:
            ownership = asset['ownership_evidence']
            amount = asset['fields']['asset_values']
            if (ownership['status'] != 'unknown' or amount['status'] != 'stated'
                    or not re.search(r'\bpossess(?:es)?\b', ownership['quote'], re.I)):
                continue
            quote = ownership['quote']
            label = asset['fields']['asset_descriptions']['value']
            if label not in quote or sentence_source.count(quote) != 1:
                continue
            quotes = list(re.finditer(r'\$[\d,]+\.00\b', quote))
            if len(quotes) != 1:
                continue
            value = int(quotes[0].group()[1:-3].replace(',', ''))
            if value != amount['value']:
                continue
            start = sentence_source.index(quote) + quotes[0].start()
            end = sentence_source.index(quote) + quotes[0].end()
            yield normalized, card_file, label, (start, end), value


def build_natural_group(source, card_hash, label, span, amount):
    root = source['key']
    text = next(view['public']['original_input'] for view in source['views'] if view['id'] == 'EC')
    scope = 'OpenExempt:Illinois:unchanged_literal_EC'
    theory = Theory(
        {scope: [{'ownership_projection': 'ownership by a current debtor'}]},
        {root: [{'ownership': False}, {'ownership': True}]},
        reference, hashlib.sha256(inspect.getsource(reference).encode()).hexdigest(),
        provenance=({
            'kind': 'independent_source_audit',
            'evidence_sha256': card_hash,
            'interpretation': 'literal possession does not establish title',
        },),
        allowed_edits=frozenset({'amount'}),
    )
    case = SourceCase(
        root, root, scope, {'text': text, 'asset': label}, {'amount': amount},
        spans={'amount': ('text', *span)})
    with_commas = ',' in text[slice(*span)]
    renderers = {'amount': lambda value: f'${value:,}.00' if with_commas else f'${value}.00'}
    edit = source_variant(case, theory, {'amount': amount + 100}, renderers)
    if edit['status'] != 'REALIZABLE':
        raise ValueError('The amount edit did not map to its exact literal EC source')
    cases = [case, edit['case']]
    return {
        'cases': cases,
        'theory': theory,
        'shared': allowed_relation(theory, cases),
        'independent': allowed_relation(theory, cases, mode='independent_completions'),
        'edit': edit['receipt'],
    }


def run():
    found = next(eligible_assets(), None)
    if found is None:
        raise ValueError('The fixed TRAIN pilot has no unchanged, independently audited possession anchor')
    source, card, label, span, amount = found
    group = build_natural_group(source, sha(card), label, span, amount)
    shared = group['shared']['signatures']
    independent = group['independent']['signatures']
    if len(shared) != 2 or len(independent) != 4 or not shared.keys() < independent.keys():
        raise ValueError('Ownership was not shared within the edited source mother')
    binding = {
        'reason': 'Some fixed TRAIN sources state possession and leave ownership unidentified.',
        'source': source['key'], 'registry_sha256': sha(REGISTRY), 'review_sha256': sha(card),
        'source_sha256': sha(Path(__file__)), 'native_literal_view': 'EC',
        'case_public_sha256': [digest(case.public) for case in group['cases']],
        'edit_receipt': group['edit'],
        'shared_allowed': list(shared.values()),
        'independent_allowed': list(independent.values()),
        'naturally_unresolved_factual_field': 'ownership', 'all_admissible_boolean_completions_retained': True,
        'native_answer_or_grading_used': False, 'physical_requests': 0,
    }
    out = BASE / 'natural_OE_relation' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'public_TRAIN_variants.json', [case.public for case in group['cases']])
    receipt = {
        'artifact_root': str(out.relative_to(ROOT)), 'naturally_unresolved_factual_field': 'ownership',
        'shared_signature_count': len(shared), 'independent_signature_count': len(independent),
        'native_effect_validated': False, 'physical_requests': 0,
    }
    (HANDOFF / 'natural_OE_relation_current.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    run()
