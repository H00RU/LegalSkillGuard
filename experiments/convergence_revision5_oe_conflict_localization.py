"""Attribute measured EV conflicts and score the consequences of dropping base claims."""

import base64
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import sqlite3

from experiments import convergence_revision5_oe_edit_acquisition as b7
from experiments import convergence_revision5_oe_native_amount_edits as b4
from experiments.convergence_formal_train_fit import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_conflict_localization_20261119'
MODES = ('original', 'local_bounds', 'drop_every_conflict', 'drop_only_localized_base_conflicts')


def claim_triplets(values):
    return {(asset, c['citation'], c['claim_value'])
            for asset, claims in values.items() for c in claims}


def explain(values, limits):
    """Identify which single changed read, if any, restores cap consistency."""
    if len(values) != 3 or len(limits) != 3:
        raise ValueError('Localization requires a base read and two distinct edits')
    if any(v is None for v in values):
        return {'state': 'missing_read', 'possible_single_outliers': []}
    complete = b4.shared_cap(values, limits)
    assert complete == b4.direct_cap(values, limits)
    if complete:
        return {'state': 'consistent', 'possible_single_outliers': []}
    possible = []
    for a, b in combinations(range(3), 2):
        observed, bounds = (values[a], values[b]), (limits[a], limits[b])
        fits = b4.shared_cap(observed, bounds)
        assert fits == b4.direct_cap(observed, bounds)
        if fits:
            possible.append(3 - a - b)
    return {'state': 'conflict', 'possible_single_outliers': sorted(possible)}


def evaluate(readings, inventories, citations):
    original = readings[0]
    predicted = {'original': original, 'local_bounds': {}}
    evidence, disputed, base_refuted = [], set(), set()
    for slot, asset in inventories[0].items():
        key = asset['description']
        limits = [b4.amount(inv[slot]['amount_quote']) for inv in inventories]
        maps = []
        for output in readings:
            if key not in output:
                maps.append(None)
                continue
            row = output[key]
            frequency = Counter(c['citation'] for c in row)
            maps.append({c['citation']: c['claim_value'] if frequency[c['citation']] == 1 else None
                         for c in row if c['citation'] in citations})
        if key in original:
            predicted['local_bounds'][key] = [
                c for c in original[key] if c['citation'] in maps[0]
                and maps[0][c['citation']] is not None and 0 < c['claim_value'] <= limits[0]]
        shared_citations = {c for m in maps if m is not None for c in m}
        for citation in sorted(shared_citations):
            values = [None if m is None else m.get(citation, 0) for m in maps]
            if not any(v is not None and v > 0 for v in values):
                continue
            result = explain(values, limits)
            anchor = key, citation
            if result['state'] == 'conflict':
                disputed.add(anchor)
                if result['possible_single_outliers'] == [0]:
                    base_refuted.add(anchor)
            evidence.append({'asset': key, 'citation': citation, 'amount_limits': limits, 'observed': values, **result})
    for mode, rejected in zip(MODES[2:], (disputed, base_refuted), strict=True):
        predicted[mode] = {a: [c for c in claims if (a, c['citation']) not in rejected]
                           for a, claims in predicted['local_bounds'].items()}
    return predicted, evidence


def archived(batch):
    if batch == 4:
        spec, source_text, edits, inv, view, scope, originals = b4.materials()
        filenames = ('0', '1')
        laws = set(scope['citations'])
        terminal_name = 'revision5_OE_native_amount_edits_terminal_20261119.json'
        variant_text = dict(zip(filenames, edits, strict=True))
    else:
        spec, source, ev, source_text, inv, laws, variant_text, originals = b7.materials()
        filenames = b7.ACQUISITIONS
        terminal_name = 'revision5_OE_edit_acquisition_terminal_20261119.json'
    receipt = read(HANDOFF / terminal_name)
    stage = ROOT / receipt['artifact_root']
    binding = read(stage / 'binding.json')
    terminal = read(stage / 'terminal.json')
    assert digest(binding) == stage.name and sha(stage / 'terminal.json') == receipt['artifact_terminal_sha256']
    assert all(sha(stage / 'source_snapshot' / f) == h for f, h in binding['source_files'].items())
    root = spec['source']
    fit = ROOT / read(pointer(batch))['artifact_root']
    recorded = read(fit / 'binding.json')
    study = read(ROOT / recorded['checkpoint_root'] / 'binding.json')
    roster = b4.load_roster(study)
    mother, = (s for s in roster[batch-1] if s['key'] == root and s['dataset'] == b4.OE)
    assert mother['project_split'] == 'train'
    native, = (v for v in mother['views'] if v['id'] == 'EV')
    assert native['public']['original_input'] == source_text
    return {'batch': batch, 'root': root, 'stage': stage, 'terminal': terminal, 'receipt': receipt,
            'filenames': filenames, 'native': native, 'mother': mother,
            'source_text': source_text, 'variants': variant_text,
            'laws': laws, 'inventory': inv, 'originals': originals}


def verify_outputs(db, data, role):
    root = data['root']
    stage = data['stage']
    old = data['originals'][role]
    payload = old['payload']
    physical_wire(db, {root}, old['id'], root)
    readings = [old['answer']]
    proven = [old['id']]
    for name in data['filenames']:
        saved = read(stage / 'reads' / f'{name}_{role}.json')
        identity = saved['call_id']
        physical_wire(db, {root}, identity, root)
        response = json.loads(db.execute('select result from calls where id=?', (identity,)).fetchone()[0])
        wire = read(Path(response['artifact_directory']) / 'wire_request.json')
        data_bytes = base64.b64decode(wire['body_b64'], validate=True)
        assert sha256(data_bytes).hexdigest() == saved['wire_sha256']
        revised = data['variants'][name]
        native = data['native']
        if data['batch'] == 4:
            messages = b4.change_wire(payload, data['source_text'], revised)
        else:
            messages, public = b7.edited_messages(payload, data['source_text'], revised)
            native = {**native, 'public': public}
        assert data_bytes == json.dumps({**payload, 'messages': messages}, ensure_ascii=False).encode()
        view = source_bundle({**data['mother'], 'views': [native]})
        assert b4.projection(view, payload['response_format']['json_schema']['schema'], response) == saved['answer']
        assert saved['answer'] is not None
        readings.append(saved['answer'])
        proven.append(identity)
    return readings, proven


def run():
    cases = [archived(4), archived(7)]
    grade_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json'
    observed = ROOT / read(HANDOFF / 'formal_B4_observe_current.json')['artifact_root']
    study = read(observed / 'binding.json')
    grade_relative = str(grade_path.relative_to(ROOT))
    assert study['native_grade_paths'][b4.OE] == grade_relative
    expected_grade = study['native_grade_sha256'][grade_relative]
    binding = {'study': 'OpenExempt_native_EV_conflict_localization', 'partition': 'TRAIN',
               'original_edits_terminal_sha256': {c['batch']: c['receipt']['artifact_terminal_sha256'] for c in cases},
               'grader_sha256': expected_grade, 'runner_sha256': sha(Path(__file__)), 'modes': list(MODES),
               'release_rule': 'Only removal, with source scope and local bounds shared before comparing repairs.'}
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    rows, physical = [], set()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        db.execute('begin')
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for case in cases:
            inventories = [case['inventory'], *(title_inventory(case['variants'][k])[1] for k in case['filenames'])]
            for role in b4.ROLES:
                readings, proven = verify_outputs(db, case, role)
                physical.update(proven)
                predicted, evidence = evaluate(readings, inventories, case['laws'])
                rows.append({'batch': case['batch'], 'role': role, 'predictions': predicted, 'evidence': evidence})
    assert len(physical) == 12
    immutable_json(out / 'predictions.json', rows)
    assert sha(grade_path) == expected_grade
    grade = read(grade_path)
    by_case = {d['batch']: d for d in cases}
    results = {}
    for row in rows:
        batch, role = row['batch'], row['role']
        case = by_case[batch]
        scores = {k: grade_view(b4.OE, case['native'], grade[case['root']]['EV'], v)['grade']
                  for k, v in row['predictions'].items()}
        assert all(score is not None for score in scores.values())
        evidence = [z for z in row['evidence'] if z['state'] == 'conflict']
        truth = claim_triplets(grade[case['root']]['EV']['answer'])
        loss = (claim_triplets(row['predictions']['local_bounds'])
                - claim_triplets(row['predictions']['drop_every_conflict']))
        results[f'B{batch}_{role}'] = {'F1': scores, 'joint_conflicts': len(evidence),
                                     'outliers': dict(Counter(str(z['possible_single_outliers']) for z in evidence)),
                                     'claims_removed_by_blanket_rule': len(loss),
                                     'exact_gold_claims_removed_by_blanket_rule': len(loss & truth)}
    summary = {'binding_sha256': out.name, 'old_physical_requests_verified': len(physical),
               'new_model_requests': 0, 'original_mothers': len(cases), 'official_EV_results': results,
               'partition': 'TRAIN', 'ledger': ledger, 'runner_sha256': sha(Path(__file__)),
               'predictions_sha256': sha(out/'predictions.json')}
    immutable_json(out / 'terminal.json', summary)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **summary}, sort_keys=True))


if __name__ == '__main__':
    run()
