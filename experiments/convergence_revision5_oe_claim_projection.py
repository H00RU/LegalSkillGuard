"""Factor source-span binding and claim-wise execution on archived OpenExempt TRAIN reads."""

from collections import Counter, defaultdict
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_train_observe import load_roster, pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_oe_asset_projection import (
    DATASET, FROZEN_ASSET_SKILL, HOME as PREVIOUS, ORIGINAL, PREFLIGHT, REDECODE,
    bound_asset, certify, inputs, same_phrase,
)
from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill
from legal_skill_guard.paired_interfaces.asset_port_decoder_v2 import consume, decode
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.program_residual import specialize
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_claim_projection_20261119'
MODES = ('exact_name_whole_asset', 'span_name_whole_asset', 'exact_name_claimwise',
         'span_name_claimwise', 'article_anchor_span_name_claimwise')
VALUATION = re.compile(r' (?:appraised at|worth|valued at|with a value of|with an appraisal value of) (\$[\d,]+(?:\.\d{2})?)')


def anchor_leading_articles(raw, units):
    """Use the uniquely located source quote when only a leading article changes case."""
    if 'assets' not in raw:
        return raw, 0
    by_id = {u['id']: u['text'] for u in units}
    rows, count = [], 0
    for row in raw['assets']:
        quote = row['quote']
        text = by_id.get(row['unit_id'], '')
        if quote and quote not in text and re.match(r'^(?:an?|the) ', quote, flags=re.I):
            candidate = quote[0].swapcase() + quote[1:]
            if text.count(candidate) == 1:
                row = {**row, 'quote': candidate}
                count += 1
        rows.append(row)
    return {**raw, 'assets': rows}, count


def span_names(record, inventory):
    """Normalize a literal inventory name with its own anchored valuation suffix."""
    assets = []
    for row in record['assets']:
        fields = row['fields']
        name = fields['asset_descriptions']
        raw = name['value']
        if bound_asset(row, inventory) is None and isinstance(raw, str):
            matches = []
            for asset in inventory.values():
                canonical = asset['description']
                marked = re.sub(r'^(?:an?|the) ', '', raw, count=1, flags=re.I)
                if not marked.startswith(canonical) or row['quote'].count(canonical) != 1:
                    continue
                suffix = marked[len(canonical):]
                valuation = VALUATION.fullmatch(suffix) if suffix else None
                if suffix and (valuation is None or valuation[1] != asset['amount_quote']
                               or marked not in row['quote']):
                    continue
                if same_phrase(asset['source_quote'], row['quote']):
                    matches.append(canonical)
            if len(matches) == 1:
                row = {**row, 'fields': {**fields, 'asset_descriptions': {**name, 'value': matches[0]}}}
        assets.append(row)
    return {**record, 'assets': assets}


def claim_projection(plan, record, family, skill):
    """Recover exactly the invariant claims in each source-verified asset row."""
    if digest(skill) != FROZEN_ASSET_SKILL:
        raise ValueError('The locality and positive claim guards apply to the pinned program only')
    required = set(plan['residual_required_fields'])
    debtors = record['globals'].get('number_of_debtors', {}).get('value')
    if 'number_of_debtors' in required and (type(debtors) is not int or debtors < 1):
        return {}, {}
    whole, claimwise = {}, {}
    for row in record['assets']:
        fields = row['fields']
        name = fields['asset_descriptions']['value']
        unknown = sorted(f for f in required & fields.keys() if fields[f]['value'] is None)
        if any(not f.startswith('asset_is_') for f in unknown):
            raise ValueError('The archived claim projection requires a finite Boolean completion domain')
        completions = []
        for values in product((False, True), repeat=len(unknown)):
            complete = {**fields, **{f: {'value': v, 'status': 'stated'} for f, v in zip(unknown, values)}}
            singleton = {**record, 'assets': [{**row, 'fields': complete}],
                         'inventory_complete': True, 'unresolved': []}
            result = consume(plan, singleton, family)
            if not result['handled'] or set(result['answer']) != {name}:
                raise ValueError('The pinned singleton consumer must execute on each complete input')
            completions.append(result['answer'][name])
        common = [claim for claim in completions[0] if all(claim in other for other in completions[1:])]
        # The pinned program only appends claims under positive single-field guards.
        # False/true endpoints independently give the minimum and maximum claim sets.
        if common != completions[0] or any(claim not in completions[-1]
                                           for other in completions for claim in other):
            raise ValueError('The exhaustive result disagrees with the direct endpoint control')
        certain = completions[0] == completions[-1]
        if certain:
            whole[name] = common
        if certain or common:
            claimwise[name] = common
    return whole, claimwise


def replay(row, archived, plan, card, inventory, units, skill):
    assert row['physical_call_id'] == archived['physical_call_id']
    assert row['source'] == archived['source'] and row['plan'] == archived['layout']
    family = archived['family']
    answers = {m: {} for m in MODES}
    added_anchors, quote_anchors = 0, 0
    raw = row.get('raw_port_read')
    if archived['decoded'] or row['v2_production_errors'] == [
            'ValueError: A port quote is not contiguous current-source evidence']:
        context = {**plan['public_context'], 'output_family': family}
        residual = specialize(skill['procedure'], context, allowed_context_fields=set(context))
        local = {**plan, 'residual_program': residual, 'residual_required_fields': residual['input_fields']}
        if archived['decoded']:
            record, anchors = decode(plan, raw, units)
            assert digest(anchors) == digest(row['decoder_receipt'])
            exact = certify(record, card, inventory)
            normalized = certify(span_names(record, inventory), card, inventory)
            added_anchors = len(normalized['assets']) - len(exact['assets'])
            answers[MODES[0]], answers[MODES[2]] = claim_projection(local, exact, family, skill)
            answers[MODES[1]], answers[MODES[3]] = claim_projection(local, normalized, family, skill)
            answers[MODES[4]] = answers[MODES[3]]
        else:
            anchored, quote_anchors = anchor_leading_articles(raw, units)
            if quote_anchors:
                record, _ = decode(plan, anchored, units)
                verified = certify(span_names(record, inventory), card, inventory)
                _, answers[MODES[4]] = claim_projection(local, verified, family, skill)
    assert answers[MODES[0]] == archived['audited_projection']
    return {**{k: archived[k] for k in ('source', 'family', 'layout', 'decoded', 'physical_call_id')},
            'net_additional_source_verified_assets': added_anchors,
            'quotes_reanchored_by_article_case': quote_anchors, 'answers': answers}


def run():
    previous = read(HANDOFF / 'revision5_OE_asset_projection_terminal_20261119.json')
    earlier = ROOT / previous['artifact_root']
    assert earlier.parent == PREVIOUS
    prior = read(earlier / 'protocol.json')
    assert digest(prior) == earlier.name == previous['binding_sha256'] and prior['partition'] == 'TRAIN'
    assert sha(earlier / 'predictions.json') == previous['predictions_sha256']
    assert sha(REDECODE / 'paired_reads.json') == prior['historical_redecode_sha256']
    assert sha(ORIGINAL / 'paired_reads.json') == prior['original_paid_reads_sha256']
    original = read(ORIGINAL / 'protocol.json')
    assert sha(ORIGINAL / 'protocol.json') == read(REDECODE / 'protocol.json')['original_protocol_sha256']
    assert sha(PREFLIGHT / 'protocol.json') == original['preflight_protocol_sha256']
    manifest = ROOT / original['reference_manifest_path']
    assert sha(manifest) == prior['source_review_manifest_sha256'] == original['reference_manifest_sha256']
    cards = {}
    for ref in read(manifest)['reviews']:
        path = ROOT / ref['card_path']
        assert sha(path) == ref['card_sha256']
        cards[ref['source'], ref['view']] = read(path)
    old_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    assert sha(old_path) == read(PREFLIGHT / 'protocol.json')['TRAIN_public_sha256']
    old = {r['key']: r for r in read(old_path)}
    observe = ROOT / read(pointer(3))['artifact_root']
    binding = read(observe / 'binding.json')
    assert observe.name == digest(binding) and not read(observe / 'terminal.json')['TEST_opened']
    roster = load_roster(read(ROOT / binding['checkpoint_root'] / 'binding.json'))
    assert digest(roster) == prior['TRAIN_roster_sha256']
    train = {s['key']: s for batch in roster for s in batch}
    grade = ROOT / binding['native_grade_paths'][DATASET]
    assert grade.parent == old_path.parent and grade.name == 'grading.json'
    plan_path = PREFLIGHT / 'plan_assets.json'
    plans = {p['version']: p for group in read(plan_path)['OE_by_public_regime'].values() for p in group}
    skill = frozen_skill()
    assert digest(skill) == FROZEN_ASSET_SKILL
    source_files = {*prior['source_sha256'], str(Path(__file__).relative_to(ROOT))}
    for name, expected in prior['source_sha256'].items():
        assert sha(ROOT / name) == expected
    protocol = {'experiment': 'OpenExempt_source_bound_claim_projection', 'partition': 'TRAIN',
                'prior_binding_sha256': earlier.name, 'prior_prediction_sha256': previous['predictions_sha256'],
                'TRAIN_grading_sha256': prior['TRAIN_grading_sha256'], 'asset_plans_sha256': sha(plan_path),
                'source_sha256': {f: sha(ROOT / f) for f in sorted(source_files)},
                'frozen_skill_sha256': FROZEN_ASSET_SKILL, 'modes': list(MODES), 'new_model_requests': 0}
    out = HOME / digest(protocol)
    immutable_json(out / 'binding.json', protocol)
    saved = read(earlier / 'predictions.json')
    historical = read(REDECODE / 'paired_reads.json')
    assert len(saved) == len(historical) == len({row['physical_call_id'] for row in saved}) == 18
    predictions = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for row, archived in zip(historical, saved, strict=True):
            source, view, version = (row[k] for k in ('source', 'view', 'raw_read_version'))
            assert train[source]['project_split'] == 'train' and train[source]['views'] == old[source]['views']
            actual = db.execute('select status,role,source,purpose from calls where id=?',
                                (row['physical_call_id'],)).fetchone()
            assert actual == ('completed', 'executor', source, 'skill_actor')
            task, families = inputs(old[source])
            assert families[archived['family']] == view
            units, = (v['source_units'] for v in task['views'] if v['view_id'] == view)
            native, = (v for v in train[source]['views'] if v['id'] == archived['family'])
            inventory = public_inventory(native['public']['original_input'])
            assert inventory is not None
            predictions.append(replay(row, archived, plans[version], cards[source, view], inventory, units, skill))
        assert ledger == dict(db.execute('select status,count(*) from calls group by status'))
    immutable_json(out / 'predictions.json', predictions)
    assert sha(grade) == protocol['TRAIN_grading_sha256']
    labels = read(grade)
    cells, changed, paired, scores = defaultdict(list), Counter(), Counter(), []
    for row in predictions:
        key, family, layout = (row[k] for k in ('source', 'family', 'layout'))
        native, = (v for v in train[key]['views'] if v['id'] == family)
        record = {}
        for mode, answer in row['answers'].items():
            value = grade_view(DATASET, native, labels[key][family], answer)['grade']
            if value is None:
                raise ValueError('The pinned official grader did not score a replay')
            cells[layout, family, mode].append(value)
            changed[mode] += answer != row['answers'][MODES[0]]
            record[mode] = value
            if layout == 'local_records':
                fixed, = (q for q in predictions if (q['source'], q['family'], q['layout']) == (key, family, 'records'))
                paired[mode] += answer == fixed['answers'][mode]
        scores.append({'source': key, 'family': family, 'layout': layout, 'official_f1': record})
    immutable_json(out / 'scores.json', scores)
    means = defaultdict(lambda: defaultdict(dict))
    for (layout, family, mode), values in cells.items():
        means[layout][family][mode] = sum(values) / len(values)
    summary = {
        'partition': 'TRAIN', 'mothers': len({p['source'] for p in predictions}),
        'archived_responses': len(predictions), 'decodable_responses': sum(p['decoded'] for p in predictions),
        'net_additional_source_verified_assets': sum(p['net_additional_source_verified_assets'] for p in predictions),
        'views_with_added_source_verified_assets': sum(p['net_additional_source_verified_assets'] > 0 for p in predictions),
        'views_redecoded_by_article_case': sum(p['quotes_reanchored_by_article_case'] > 0 for p in predictions),
        'views_changed_from_exact_name_whole_asset': dict(changed), 'official_mean_f1': means,
        'fixed_record_and_synthesized_view_exact_agreement_of_six': dict(paired),
        'exhaustive_and_direct_endpoint_projection_agree': True,
        'prior_audit_source_reviews_mask_only': True, 'new_model_requests': 0, 'ledger': ledger,
        'binding_sha256': out.name, 'predictions_sha256': sha(out / 'predictions.json'),
        'scores_sha256': sha(out / 'scores.json'), 'runner_sha256': sha(Path(__file__)),
    }
    immutable_json(out / 'summary.json', summary)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **summary}, sort_keys=True))


if __name__ == '__main__':
    run()
