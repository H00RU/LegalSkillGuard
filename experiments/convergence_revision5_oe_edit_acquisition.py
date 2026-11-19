"""Compare equal-budget source-first and native-disagreement selection on B7 EV."""

import argparse
import base64
from collections import Counter
from copy import deepcopy
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from experiments.convergence_revision5_oe_m2_source_placement import compile_edit
from experiments.convergence_revision5_oe_native_amount_edits import ROLES, amount, evaluate, projection
from legal_skill_guard.openexempt import UPSTREAM
from legal_skill_guard.paired_interfaces.control_answers import source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_edit_acquisition_20261119'
POINTER = HANDOFF / 'revision5_OE_edit_acquisition_current.json'
ACQUISITIONS = ('source_context', 'native_disagreement')
BATCH = 7


def claim_maps(answer, scope):
    return {asset: {c['citation']: c['claim_value'] for c in claims if c['citation'] in scope}
            for asset, claims in answer.items()}


def choose(inventory, base, scope, slots):
    """Choose one intervention from the same pre-response source and prediction pool."""
    assets = list(inventory)
    incumbent, candidate = (claim_maps(base[r], scope) for r in ROLES)
    priority = {}
    for key in slots:
        row = inventory[key]
        siblings_after = sum(inventory[k]['source_quote'] == row['source_quote']
                             for k in assets[assets.index(key) + 1:])
        a, b = (answers[row['description']] for answers in (incumbent, candidate))
        disagreement = sum(a.get(c) != b.get(c) for c in a.keys() | b.keys())
        priority[key] = {'downstream_siblings': siblings_after, 'native_disagreement': disagreement,
                         'amount': amount(row['amount_quote'])}
    source = max(slots, key=lambda k: (priority[k]['downstream_siblings'], -assets.index(k)))
    direct = max(slots, key=lambda k: (priority[k]['native_disagreement'], priority[k]['amount'], -assets.index(k)))
    return dict(zip(ACQUISITIONS, (source, direct), strict=True)), priority


def edited_messages(payload, source, revision):
    """Recompute the public inventory in the old wire from the same edited source."""
    messages = deepcopy(payload['messages'])
    user, = (m for m in messages if m['role'] == 'user')
    document = json.loads(user['content'])
    native, = document['public']['native_views']
    public = native['public']
    assert native['id'] == 'EV' and public['original_input'] == source
    assert public['asset_inventory'] == public_inventory(source)
    for ascii_only in (False, True):
        if json.dumps(document, ensure_ascii=ascii_only) == user['content']:
            break
    else:
        raise ValueError('The archive must have its original user-message serialization')
    revised_inventory = public_inventory(revision)
    assert revised_inventory is not None and set(revised_inventory) == set(public['asset_inventory'])
    public['original_input'] = revision
    public['asset_inventory'] = {slot: {k: revised_inventory[slot][k] for k in old}
                                 for slot, old in public['asset_inventory'].items()}
    user['content'] = json.dumps(document, ensure_ascii=ascii_only)
    return messages, public


def materials():
    probe_receipt = read(HANDOFF / 'revision5_OE_native_amount_edits_terminal_20261119.json')
    prior_result = ROOT / probe_receipt['artifact_root'] / 'terminal.json'
    assert sha(prior_result) == probe_receipt['artifact_terminal_sha256']
    placement = read(HANDOFF / 'revision5_OE_M2_source_placement_terminal_20261119.json')
    pool = ROOT / placement['artifact_root']
    placement_terminal = read(pool / 'terminal.json')
    assert sha(pool / 'terminal.json') == placement['artifact_terminal_sha256']
    assert sha(pool / 'local_witnesses.json') == placement_terminal['local_witnesses_sha256']
    stage = ROOT / read(pointer(BATCH))['artifact_root']
    locked = read(stage / 'binding.json')
    end = read(stage / 'terminal.json')
    decisions = read(stage / 'matched_decisions.json')
    assert stage.name == digest(locked) and end['matched_decisions_sha256'] == digest(decisions)
    assert all(sha(stage / 'source_snapshot' / f) == h for f, h in locked['source_sha256'].items())
    record = decisions['relation'][OE]
    assert record['status'] == 'insufficient_positive_supervision' and not end['TEST_opened']
    native_scores = {x['source']: x for x in record['native_comparisons']}
    edits, = (r['edits'] for r in read(pool / 'local_witnesses.json') if r['batch'] == BATCH)
    eligible = Counter(e['source'] for e in edits if e['view'] == 'EV')
    source_key, = (k for k, n in eligible.items() if n == 3)
    assert native_scores[source_key]['patch_utility'] > native_scores[source_key]['baseline_utility']
    root = ROOT / locked['checkpoint_root']
    study = read(root / 'binding.json')
    roster = load_roster(study)
    source, = (s for s in roster[BATCH - 1] if s['key'] == source_key and s['dataset'] == OE)
    assert source['project_split'] == 'train'
    journal = TrainingJournal(root, study, roster)
    base = read(journal.directory(M2, BATCH) / 'predictions' / (digest(source_key) + '.json'))
    assert journal._observations(M2, BATCH)['predictions'][source_key] == digest(base)
    candidate = read(stage / 'candidates' / ORDINARY / OE / 'measurements.json')
    decision = read(stage / 'candidates' / ORDINARY / OE / 'decision.json')
    assert digest(candidate['candidate']) == record['matched_proposal_sha256']
    assert digest(candidate['predictions']) == decision['predictions_sha256']
    ev, = (v for v in source['views'] if v['id'] == 'EV')
    text = ev['public']['original_input']
    _, inv, title_decisions = title_inventory(text)
    assert len(inv) == 3 and len({r['source_quote'] for r in inv.values()}) == 1
    scope = supplied_jurisdiction_scope(text)
    law = set(scope['citations'])
    archive = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for role, bundle in zip(ROLES, (base['result'], candidate['predictions'][source_key]), strict=True):
            output, = (r for r in bundle['reads'] if 'EV' in r['native'])
            trace, = (r for r in output['execution']['traces'] if 'physical_call_id' in r)
            call = trace['physical_call_id']
            physical_wire(db, {source_key}, call, source_key)
            result = json.loads(db.execute('select result from calls where id=?', (call,)).fetchone()[0])
            wire = read(Path(result['artifact_directory']) / 'wire_request.json')
            payload = json.loads(base64.b64decode(wire['body_b64'], validate=True))
            messages, public = edited_messages(payload, text, text)
            assert messages == payload['messages']
            view = source_bundle({**source, 'views': [{**ev, 'public': public}]})
            schema = payload['response_format']['json_schema']['schema']
            assert schema['properties']['value'] == wire_schema(OE, view)
            native = projection(view, schema, result)
            assert native == output['native']['EV']['answer'] and native is not None
            assert set(native) == {r['description'] for r in inv.values()}
            assert sha256(json.dumps(request_payload(locked['executor'], messages=messages, thinking=False,
                                                    schema=schema), ensure_ascii=False).encode()).hexdigest() == wire['body_sha256']
            archive[role] = {'id': call, 'payload': payload, 'wire_sha256': wire['body_sha256'], 'answer': native}
    candidates = {r['slot']: r for r in edits if r['source'] == source_key and r['view'] == 'EV'}
    selected, scores = choose(inv, {r: a['answer'] for r, a in archive.items()}, law, list(candidates))
    assert len(set(selected.values())) == 2
    variants = {}
    for name, slot in selected.items():
        edit = compile_edit(source_key, 'EV', text, slot, inv, title_decisions)
        assert edit['receipt'] == candidates[slot]
        variants[name] = edit['cases'][1].public['text']
    files = [Path(__file__), UPSTREAM / 'source/solver.py',
             ROOT / 'experiments/convergence_revision5_oe_native_amount_edits.py',
             ROOT / 'experiments/convergence_revision5_oe_m2_source_placement.py',
             ROOT / 'legal_skill_guard/paired_interfaces/convergence_ev_inventory.py',
             ROOT / 'legal_skill_guard/paired_interfaces/convergence_oe_title_scope.py',
             ROOT / 'legal_skill_guard/paired_interfaces/control_answers.py',
             ROOT / 'legal_skill_guard/skill_evolution/native.py',
             ROOT / 'legal_skill_guard/skill_evolution/clients.py', ROOT / 'legal_skill_guard/rr/client.py']
    binding = {'study': 'M2_equal_budget_B7_native_EV_acquisition', 'TRAIN_only': True,
               'B4_calibration_sha256': sha(prior_result), 'B7_fit_sha256': sha(stage / 'terminal.json'),
               'placement_sha256': sha(pool / 'terminal.json'), 'source': source_key,
               'source_files': {str(f.relative_to(ROOT)): sha(f) for f in files},
               'prior_wires': {r: a['wire_sha256'] for r, a in archive.items()},
               'selected': selected, 'same_public_pool_scores': scores,
               'variant_sha256': {name: digest(t) for name, t in variants.items()},
               'executor': locked['executor'], 'original_selection_preserved': record['status'],
               'forecast': 'The earlier valuation in a shared source sentence exposes more unchanged-asset conflicts '
                           'on the same originally observed in-scope slots than the native-disagreement rule.',
               'unit_of_budget': 'One local edit with two physical policy reads per rule.',
               'selection_endpoint': 'Whether exactly one policy admits the shared cap on all common slots.'}
    return binding, source, ev, text, inv, law, variants, archive


def common_slots(archive, law):
    by_role = {r: claim_maps(row['answer'], law) for r, row in archive.items()}
    return {(asset, cite) for asset in by_role['incumbent'].keys() & by_role['candidate'].keys()
            for cite in by_role['incumbent'][asset].keys() & by_role['candidate'][asset].keys()
            if all(by_role[r][asset][cite] > 0 for r in ROLES)}


def report_counts(archive, results, inv, law, variants):
    slots = common_slots(archive, law)
    summary = {}
    for mode, answers in results.items():
        inventories = [inv, title_inventory(variants[mode])[1]]
        rows, complete = {}, {}
        for role in ROLES:
            readings = [archive[role]['answer'], answers[role]]
            complete[role] = evaluate(readings, inventories, law)
            matched = [None if output is None else {
                a: [c for c in claims if (a, c['citation']) in slots] for a, claims in output.items()}
                for output in readings]
            rows[role] = evaluate(matched, inventories, law)
        covered = all(r.get('fully_observed_slots') == len(slots) for r in rows.values())
        unique = [role for role in ROLES if not rows[role].get('joint_conflicts')] if covered else []
        summary[mode] = {'on_common_base_slots': rows, 'all_positive_slots': complete,
                         'complete_common_support': covered,
                         'diagnostic_compatible_policy': unique[0] if len(unique) == 1 else None}
    return len(slots), summary


def run(phase):
    binding, source, ev, text, inv, law, variants, archive = materials()
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    if phase == 'prepare':
        write_status(out, {'status': 'prepared', 'planned_calls': 4}, POINTER)
        print(json.dumps({'root': str(out.relative_to(ROOT)), 'chosen_slots': binding['selected']}), flush=True)
        return
    assert ROOT / read(POINTER)['artifact_root'] == out
    lock = (out / 'driver.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for file, expected in binding['source_files'].items():
        snap = out / 'source_snapshot' / file
        snap.parent.mkdir(parents=True, exist_ok=True)
        if not snap.exists():
            with snap.open('xb') as output:
                output.write((ROOT / file).read_bytes())
        assert sha(snap) == expected
    namespace = 'convergence-revision5-OE-edit-acquisition-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=namespace, sources={'train': [source['key']], 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    outputs, tokens, completed = {}, Counter(), 0
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for mode, order in zip(ACQUISITIONS, (ROLES, ROLES[::-1]), strict=True):
            outputs[mode] = {}
            for role in order:
                call = f'{namespace}:{mode}:{role}'
                payload = archive[role]['payload']
                messages, public = edited_messages(payload, text, variants[mode])
                edited = source_bundle({**source, 'views': [{**ev, 'public': public}]})
                schema = payload['response_format']['json_schema']['schema']
                assert schema['properties']['value'] == wire_schema(OE, edited)
                expected = json.dumps({**payload, 'messages': messages}, ensure_ascii=False).encode()
                assert json.dumps(executor.payload(messages=messages, thinking=False, schema=schema),
                                  ensure_ascii=False).encode() == expected
                write_status(out, {'status': 'running', 'completed': completed, 'current_call': call}, POINTER)
                response = executor.generate(call, source=source['key'], purpose='skill_actor', messages=messages,
                                             thinking=False, schema=schema)
                physical_wire(db, {source['key']}, call, source['key'])
                wire = read(Path(response['artifact_directory']) / 'wire_request.json')
                assert base64.b64decode(wire['body_b64'], validate=True) == expected
                answer = projection(edited, schema, response)
                outputs[mode][role] = answer
                tokens[role] += response['usage']['total_tokens']
                completed += 1
                immutable_json(out / 'reads' / f'{mode}_{role}.json', {
                    'call_id': call, 'answer': answer, 'wire_sha256': wire['body_sha256']})
                print(json.dumps({'settled': completed, 'arm': mode, 'decoded': answer is not None}), flush=True)
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
    common, summaries = report_counts(archive, outputs, inv, law, variants)
    result = {'status': 'settled_OE_edit_acquisition_TRAIN', 'new_requests': completed, 'archived_reads': 2,
              'tokens': dict(tokens), 'common_base_slots': common, 'by_acquisition': summaries, 'ledger': counts,
              'old_B7_selection_preserved': binding['original_selection_preserved'],
              'same_information_direct_cap_matches': True, 'edited_gold_scores_measured': False,
              'runner_sha256': sha(Path(__file__))}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'completed': completed}, POINTER)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase)
