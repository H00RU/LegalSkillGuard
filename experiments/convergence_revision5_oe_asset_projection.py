"""Audit asset-local partial execution on sealed OpenExempt TRAIN reads."""

import base64
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.convergence_formal_train_observe import load_roster, pointer
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.two_method_asset_port_redecode import ORIGINAL, PREFLIGHT, inputs
from legal_skill_guard.paired_interfaces.asset_graph_pairs import reference_world
from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill
from legal_skill_guard.paired_interfaces.asset_port_decoder_v2 import consume, decode
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import INVENTORY_FILES, public_inventory
from legal_skill_guard.paired_interfaces.program_residual import specialize
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


# This exact program reads each asset only at the loop index. It initializes
# claims for each iteration and never reads the result map inside the loop.
# With distinct keys its only cross-asset inputs are immutable shared scalars.
FROZEN_ASSET_SKILL = '1200287c0d5d3c256790d87f5878cd35c7f9eaf4792eddcee9ee48a334b33ff7'
DATASET = 'OpenExempt'
REDECODE = ORIGINAL.parents[1] / 'asset_port_redecode_v2' / (
    '20afd6a84d91af3a71f16a0ab5d6d850c1f1cda6420edc7c31d14b8b5ca513c6')
HOME = BASE / 'revision5_OE_asset_projection_20261119'
UNKNOWN = {'value': None, 'status': 'unknown'}
ARTICLES = ('A ', 'a ', 'An ', 'an ', 'The ', 'the ')


def same_phrase(first, second):
    return first in second or second in first


def physical(db, row, task, units):
    identity = row['physical_call_id']
    settled = db.execute('select status,role,source,purpose,request_hash,result from calls where id=?',
                         (identity,)).fetchone()
    assert settled[:4] == ('completed', 'executor', row['source'], 'skill_actor')
    response = json.loads(settled[5])
    directory = ORIGINAL / 'calls' / digest(identity)
    assert Path(response['artifact_directory']) == directory
    assert read(directory / 'result.json') == response
    request, wire = (read(directory / name) for name in ('request.json', 'wire_request.json'))
    raw = base64.b64decode(wire['body_b64'], validate=True)
    payload = request['payload']
    assert sha256(raw).hexdigest() == wire['body_sha256']
    assert json.loads(raw) == payload and digest(payload) == task['wire_payload_sha256']
    assert request['request_hash'] == response['request_hash'] == settled[4]
    assert request['source'] == row['source'] and request['id'] == identity
    assert payload['model'] == 'Qwen/Qwen3-8B' and response['thinking_requested'] is False
    assert payload['chat_template_kwargs']['enable_thinking'] is False
    assert payload['messages'] == task['messages']
    assert json.loads(payload['messages'][-1]['content'])['source_units'] == units
    return response


def bound_asset(row, inventory):
    name = row['fields']['asset_descriptions']['value']
    if not isinstance(name, str) or name not in row['quote']:
        return None
    matches = []
    for asset in inventory.values():
        description = asset['description']
        names = {description, *(article + description for article in ARTICLES)}
        if name in names and same_phrase(asset['source_quote'], row['quote']):
            matches.append(asset)
    return matches[0] if len(matches) == 1 else None


def certify(record, card, inventory):
    """Discard unestablished assertions without filling any source-review port."""
    expected = card['port_record']
    reference = {a['fields']['asset_descriptions']['value']: a for a in expected['assets']}
    observed = []
    for row in record['assets']:
        fields = row['fields']
        public = bound_asset(row, inventory)
        if public is None:
            continue
        description = public['description']
        if description not in reference:
            continue
        known = reference[description]['fields']
        amount = fields['asset_values']['value']
        if amount != float(public['amount_quote'][1:].replace(',', '')) or amount != known['asset_values']['value']:
            continue
        verified = {
            field: cell if cell['value'] is not None and cell['value'] == known[field]['value'] else UNKNOWN
            for field, cell in fields.items()
        }
        verified['asset_descriptions'] = {**fields['asset_descriptions'], 'value': description}
        observed.append({**row, 'fields': verified})
    names = Counter(row['fields']['asset_descriptions']['value'] for row in observed)
    assets = [row for row in observed if names[row['fields']['asset_descriptions']['value']] == 1]
    globals_ = {}
    for field, cell in record['globals'].items():
        known = expected['globals'][field]
        if (cell['value'] == known['value'] and cell['unit_id'] == known['unit_id']
                and same_phrase(cell['quote'], known['quote'])):
            globals_[field] = cell
    return {**record, 'assets': assets, 'globals': globals_,
            'inventory_complete': (record['inventory_complete'] and len(assets) == len(record['assets'])
                                   and len(assets) == len(inventory) == len(reference))}


def evaluate(plan, record, card, inventory, family):
    skill = frozen_skill()
    if digest(skill) != FROZEN_ASSET_SKILL:
        raise ValueError('Asset locality was checked for a different program')
    regime = plan['public_context']['governing_regime']
    context = {'governing_regime': regime, 'output_family': family}
    residual = specialize(skill['procedure'], context, allowed_context_fields=set(context))
    local = {**plan, 'residual_program': residual, 'residual_required_fields': residual['input_fields']}
    verified = certify(record, card, inventory)
    full = consume(local, verified, family)
    projection = {}
    for row in verified['assets']:
        key = row['fields']['asset_descriptions']['value']
        singleton = {**verified, 'assets': [row], 'inventory_complete': True, 'unresolved': []}
        result = consume(local, singleton, family)
        if result['handled']:
            assert set(result['answer']) == {key}
            projection.update(result['answer'])
    if full['handled']:
        assert full['answer'] == projection and len(projection) == len(verified['assets'])
    return {'audited_whole': full['answer'] if full['handled'] else {},
            'audited_projection': projection, 'audited_whole_handled': full['handled'],
            'source_bound_input_rows': len(verified['assets']),
            'asset_keys_unresolved': sorted({v['description'] for v in inventory.values()} - projection.keys()),
            'original_inventory_complete': record['inventory_complete'],
            'original_unresolved': record['unresolved']}


def collect(training, old_train, paid, historical, tasks, plans, cards):
    outputs = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        before = dict(db.execute('select status,count(*) from calls group by status'))
        assert not before.get('reserved')
        for saved, row in zip(paid, historical, strict=True):
            source, view, version = (row[key] for key in ('source', 'view', 'raw_read_version'))
            task, plan, card = tasks[source, view, version], plans[version], cards[source, view]
            assert all(row[k] == saved[k] for k in ('source', 'view', 'plan', 'raw_read_version', 'physical_call_id'))
            assert plan['name'] == task['plan'] == row['plan'] and plan['schema'] == task['schema']
            current, older = training[source], old_train[source]
            assert current['project_split'] == 'train' and current['views'] == older['views']
            port_task, view_map = inputs(older)
            family, = (name for name, opaque in view_map.items() if opaque == view)
            units, = (r['source_units'] for r in port_task['views'] if r['view_id'] == view)
            native, = (v for v in current['views'] if v['id'] == family)
            assert card['source'] == source and card['view_id'] == view
            reference_world(card, units, plan['public_context']['governing_regime'])
            physical_response = physical(db, row, task, units)
            inventory = public_inventory(native['public']['original_input'])
            assert inventory is not None
            details = {'audited_whole': {}, 'audited_projection': {}, 'audited_whole_handled': False,
                       'source_bound_input_rows': 0,
                       'asset_keys_unresolved': sorted(a['description'] for a in inventory.values())}
            old = row['native_outputs_recomputed_offline'].get(family, {})
            try:
                restored, _ = restore_enum_transport(strict_json(physical_response['content']), task['schema'])
                record, anchors = decode(plan, restored, units)
            except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
                assert type(error).__name__ + ': ' + str(error) in row['v2_production_errors']
            else:
                assert physical_response['finish_reason'] == 'stop' and not row['v2_production_errors']
                assert restored == row['raw_port_read']
                assert digest(anchors) == digest(row['decoder_receipt'])
                assert consume(plan, record, family) == old
                details = evaluate(plan, record, card, inventory, family)
            outputs.append({
                'source': source, 'family': family, 'layout': row['plan'], 'source_asset_count': len(inventory),
                'physical_call_id': row['physical_call_id'], 'decoded': not row['v2_production_errors'],
                'historical_whole': old['answer'] if old.get('handled') else {},
                'historical_whole_handled': bool(old.get('handled')), **details,
            })
        assert before == dict(db.execute('select status,count(*) from calls group by status'))
    return outputs, before


def score(outputs, training, grade_path):
    labels = read(grade_path)
    summaries, details = defaultdict(lambda: defaultdict(list)), []
    modes = ('historical_whole', 'audited_whole', 'audited_projection')
    for row in outputs:
        source, family = row['source'], row['family']
        native, = (v for v in training[source]['views'] if v['id'] == family)
        metrics = {}
        for mode in modes:
            answer = row[mode]
            grade = grade_view(DATASET, native, labels[source][family], answer)['grade']
            if grade is None:
                raise ValueError('The pinned official metric could not score a saved prediction')
            metrics[mode] = grade
            summaries[row['layout'], family][mode].append((len(answer), bool(answer), grade))
        details.append({'source': source, 'family': family, 'layout': row['layout'], 'native_f1': metrics})
    summary = {}
    for (layout, family), by_mode in summaries.items():
        summary.setdefault(layout, {})[family] = {
            mode: {'views': len(rows), 'assets': sum(r[0] for r in rows), 'views_with_assets': sum(r[1] for r in rows),
                   'mean_official_f1': sum(r[2] for r in rows) / len(rows)}
            for mode, rows in by_mode.items()
        }
    return summary, details


def main():
    original, replay = (read(root / 'protocol.json') for root in (ORIGINAL, REDECODE))
    for name, bound in original['source_sha256'].items():
        assert sha(ORIGINAL / 'source_snapshot' / name) == bound
    for name, bound in replay['source_sha256'].items():
        if name != 'legal_skill_guard/skill_evolution/native.py':
            assert sha(ROOT / name) == bound
    assert sha(ORIGINAL / 'protocol.json') == replay['original_protocol_sha256']
    assert sha(ORIGINAL / 'paired_reads.json') == replay['original_paid_reads_sha256']
    assert sha(PREFLIGHT / 'protocol.json') == original['preflight_protocol_sha256']
    manifest = ROOT / original['reference_manifest_path']
    assert sha(manifest) == original['reference_manifest_sha256']
    cards = {}
    for row in read(manifest)['reviews']:
        path = ROOT / row['card_path']
        assert sha(path) == row['card_sha256']
        cards[row['source'], row['view']] = read(path)
    paid, historical = (read(root / 'paired_reads.json') for root in (ORIGINAL, REDECODE))
    assert len(paid) == len(historical) == len({r['physical_call_id'] for r in paid}) == 18
    requests = read(ORIGINAL / 'requests.json')
    assert digest(requests) == original['requests_sha256']
    tasks = {(row['source'], row['opaque_view'], row['version']): row for row in requests}
    plans = {p['version']: p for items in read(PREFLIGHT / 'plan_assets.json')['OE_by_public_regime'].values() for p in items}
    train = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    assert sha(train) == read(PREFLIGHT / 'protocol.json')['TRAIN_public_sha256']
    old_train = {r['key']: r for r in read(train)}
    observed = ROOT / read(pointer(3))['artifact_root']
    binding = read(observed / 'binding.json')
    assert observed.name == digest(binding) and not read(observed / 'terminal.json')['TEST_opened']
    roster = load_roster(read(ROOT / binding['checkpoint_root'] / 'binding.json'))
    training = {r['key']: r for batch in roster for r in batch}
    grade_path = binding['native_grade_paths'][DATASET]
    assert grade_path == str(train.with_name('grading.json').relative_to(ROOT))
    files = INVENTORY_FILES | set(replay['source_sha256']) | {str(Path(__file__).resolve().relative_to(ROOT))}
    protocol = {
        'study': 'asset_local_finite_projection_after_source_audit', 'dataset': DATASET,
        'original_paid_reads_sha256': sha(ORIGINAL / 'paired_reads.json'),
        'historical_redecode_sha256': sha(REDECODE / 'paired_reads.json'),
        'source_review_manifest_sha256': sha(manifest), 'TRAIN_roster_sha256': digest(roster),
        'TRAIN_grading_sha256': binding['native_grade_sha256'][grade_path],
        'source_sha256': {name: sha(ROOT / name) for name in sorted(files)},
        'frozen_skill_sha256': FROZEN_ASSET_SKILL, 'partition': 'TRAIN',
        'matrix': ['columns', 'records', 'local_records'], 'families': ['EC', 'EV'],
        'missing_asset_rows_omitted_from_scoring_payload': True,
        'source_review_masks_assertions_only': True,
        'prediction_sealed_before_opening_labels': True, 'new_model_requests': 0,
    }
    out = HOME / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    predictions, ledger = collect(training, old_train, paid, historical, tasks, plans, cards)
    immutable_json(out / 'predictions.json', predictions)
    assert sha(ROOT / grade_path) == protocol['TRAIN_grading_sha256']
    aggregate, scores = score(predictions, training, ROOT / grade_path)
    immutable_json(out / 'scores.json', scores)
    summary = {
        'TRAIN_mothers': len({r['source'] for r in predictions}), 'physical_responses_verified': len(predictions),
        'decoded_responses': sum(r['decoded'] for r in predictions), 'layout_family_results': aggregate,
        'paired_projection_answer_equal': sum(
            r['audited_projection'] == next(q['audited_projection'] for q in predictions
                if q['source'] == r['source'] and q['family'] == r['family'] and q['layout'] == 'records')
            for r in predictions if r['layout'] == 'local_records'),
        'original_port_consumers_and_libraries_changed': False, 'new_model_requests': 0, 'ledger': ledger,
        'bound_runner_sha256': protocol['source_sha256'][str(Path(__file__).resolve().relative_to(ROOT))],
        'prediction_sha256': sha(out / 'predictions.json'), 'sources_verified': len(original['source_sha256']),
    }
    immutable_json(out / 'summary.json', summary)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **summary}, sort_keys=True))


if __name__ == '__main__':
    main()
