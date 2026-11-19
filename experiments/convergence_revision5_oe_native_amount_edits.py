"""Measure source-local amount interventions with the exact B4 native EV wires."""

import argparse
import base64
from collections import Counter
from copy import deepcopy
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from experiments.convergence_revision5_oe_m2_source_placement import compile_edit
from legal_skill_guard.openexempt import UPSTREAM
from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_native_amount_edits_20261119'
POINTER = HANDOFF / 'revision5_OE_native_amount_edits_current.json'
ROLES = ('incumbent', 'candidate')
FIT_BATCH = 4


def change_wire(payload, source, edited):
    """Preserve the original serialization and exact native response schema."""
    messages = deepcopy(payload['messages'])
    user, = (m for m in messages if m['role'] == 'user')
    for ascii_only in (False, True):
        before = json.dumps(source, ensure_ascii=ascii_only)
        if user['content'].count(before) == 1:
            user['content'] = user['content'].replace(before, json.dumps(edited, ensure_ascii=ascii_only), 1)
            break
    else:
        raise ValueError('Cannot bind a unique source-text value in the original native request')
    return messages


def projection(view, schema, result):
    if result['finish_reason'] != 'stop':
        return None
    try:
        doc = json.loads(result['content'])
        decoded, _ = restore_enum_transport(doc, schema)
        jsonschema.validate(decoded, schema)
        answer, _ = decode_native(OE, view, decoded['value'])
        return answer['EV']
    except (ValueError, KeyError, TypeError, jsonschema.ValidationError):
        return None


def amount(text):
    if text[-3:] != '.00':
        raise ValueError('The matched native comparison needs a whole-dollar source amount')
    return int(text[1:-3].replace(',', ''))


def shared_cap(values, bases):
    """Existence of one nonnegative effective cap and fixed eligibility."""
    observed = [(v, a) for v, a in zip(values, bases, strict=True) if v is not None]
    caps = {0, *(v for v, _ in observed), *(a for _, a in observed)}
    return any(all(v == min(a, cap) for v, a in observed) for cap in caps)


def direct_cap(values, bases):
    observed = [(v, a) for v, a in zip(values, bases, strict=True) if v is not None]
    clipped = {v for v, a in observed if 0 <= v < a}
    full = max((a for v, a in observed if v == a), default=0)
    return (all(0 <= v <= a for v, a in observed) and len(clipped) <= 1
            and (not clipped or next(iter(clipped)) >= full))


def evaluate(reads, inventories, law):
    summary = Counter()
    for slot, row in inventories[0].items():
        asset = row['description']
        limits = [amount(v[slot]['amount_quote']) for v in inventories]
        placements = []
        for r in reads:
            claims = r.get(asset) if r is not None else None
            if claims is None:
                placements.append(None)
                summary['unobserved_asset_rows'] += 1
                continue
            citations = Counter(c['citation'] for c in claims)
            summary['out_of_scope_claims'] += sum(n for c, n in citations.items() if c not in law)
            summary['duplicate_citations'] += sum(n - 1 for n in citations.values() if n > 1)
            placements.append({c['citation']: c['claim_value'] if citations[c['citation']] == 1 else None
                               for c in claims if c['citation'] in law})
        for citation in sorted({c for p in placements if p is not None for c in p}):
            vals = [None if p is None else p.get(citation, 0) for p in placements]
            if not any(v is not None and v > 0 for v in vals):
                continue
            summary['positive_slots'] += 1
            summary['fully_observed_slots'] += all(v is not None for v in vals)
            joint = shared_cap(vals, limits)
            assert direct_cap(vals, limits) == joint
            summary['joint_conflicts'] += not joint
            summary['local_amount_bound_conflicts'] += any(v is not None and not 0 <= v <= a
                                                          for v, a in zip(vals, limits, strict=True))
            summary['unchanged_asset_conflicts'] += any(limits[k] == limits[0] and vals[k] is not None
                                                       and vals[0] is not None and vals[0] != vals[k]
                                                       for k in range(1, len(vals)))
    return dict(summary)


def materials():
    prior = read(HANDOFF / 'revision5_OE_M2_source_placement_terminal_20261119.json')
    stage = ROOT / prior['artifact_root']
    evidence = read(stage / 'terminal.json')
    assert sha(stage / 'terminal.json') == prior['artifact_terminal_sha256']
    assert sha(stage / 'local_witnesses.json') == evidence['local_witnesses_sha256']
    fit = ROOT / read(pointer(FIT_BATCH))['artifact_root']
    bound = read(fit / 'binding.json')
    done = read(fit / 'terminal.json')
    frozen = read(fit / 'matched_decisions.json')
    assert fit.name == digest(bound) and digest(frozen) == done['matched_decisions_sha256']
    assert all(sha(fit / 'source_snapshot' / f) == h for f, h in bound['source_sha256'].items())
    relation = frozen['relation'][OE]
    assert relation['status'] == 'rejected_unsupported_literal_assertion' and not done['TEST_opened']
    original_rows, = (r['edits'] for r in read(stage / 'local_witnesses.json') if r['batch'] == FIT_BATCH)
    positive = {r['source']: r for r in relation['native_comparisons'] if r['patch_utility'] > r['baseline_utility']}
    counts = Counter(r['source'] for r in original_rows if r['view'] == 'EV' and r['source'] in positive)
    source_key, = (k for k, n in counts.items() if n > 1)
    catalog = [r for r in original_rows if r['source'] == source_key and r['view'] == 'EV']
    root = ROOT / bound['checkpoint_root']
    binding = read(root / 'binding.json')
    roster = load_roster(binding)
    journal = TrainingJournal(root, binding, roster)
    source, = (s for s in roster[FIT_BATCH - 1] if s['key'] == source_key)
    assert source['project_split'] == 'train' and source['dataset'] == OE
    ev, = (v for v in source['views'] if v['id'] == 'EV')
    text = ev['public']['original_input']
    _, inv, decisions = title_inventory(text)
    assert len(inv) == len(catalog) == 2
    assert len({a['source_quote'] for a in inv.values()}) == 1
    slots = [r['slot'] for r in catalog]
    revisions = []
    for spec in catalog:
        group = compile_edit(source_key, 'EV', text, spec['slot'], inv, decisions)
        assert group['receipt'] == spec
        revisions.append(group['cases'][1].public['text'])
    forecast = {'perturbation': 'One-dollar edit on either of two unresolved-title assets in the same source sentence.',
                'mechanism': 'The official EV allocator starts each asset/citation from a fresh case state.',
                'prediction': 'The native-positive B4 candidate will have fewer violations than the incumbent in the observed in-scope valuation slots.',
                'retains_prior_literal_rejection': True, 'same_information_direct_cap_control': True}

    observations = journal._observations(M2, FIT_BATCH)
    old = read(journal.directory(M2, FIT_BATCH) / 'predictions' / (digest(source_key) + '.json'))
    assert digest(old) == observations['predictions'][source_key]
    candidate = read(fit / 'candidates' / ORDINARY / OE / 'measurements.json')
    sel = read(fit / 'candidates' / ORDINARY / OE / 'decision.json')
    assert digest(candidate['candidate']) == relation['matched_proposal_sha256']
    assert digest(candidate['predictions']) == sel['predictions_sha256']
    view = source_bundle({**source, 'views': [ev]})
    schema = wire_schema(OE, view)
    prior_calls = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for role, bundle in zip(ROLES, (old['result'], candidate['predictions'][source_key]), strict=True):
            native, = (r for r in bundle['reads'] if 'EV' in r['native'])
            trace, = (r for r in native['execution']['traces'] if 'physical_call_id' in r)
            identity = trace['physical_call_id']
            physical_wire(db, {source_key}, identity, source_key)
            response = json.loads(db.execute('select result from calls where id=?', (identity,)).fetchone()[0])
            path = Path(response['artifact_directory'])
            wire = read(path / 'wire_request.json')
            payload = json.loads(base64.b64decode(wire['body_b64'], validate=True))
            wire_schema_archive = payload['response_format']['json_schema']['schema']
            assert wire_schema_archive['properties'] == {'value': schema}
            answer = projection(view, wire_schema_archive, response)
            assert answer == native['native']['EV']['answer'] and answer is not None
            prior_calls[role] = {'id': identity, 'wire_sha256': wire['body_sha256'], 'payload': payload, 'answer': answer}
    scope = supplied_jurisdiction_scope(text)
    assert all(supplied_jurisdiction_scope(v) == scope for v in revisions)
    for role in ROLES:
        baseline = evaluate([prior_calls[role]['answer']], [inv], set(scope['citations']))
        assert baseline['positive_slots'] >= 4 and not baseline['local_amount_bound_conflicts']
    solver = UPSTREAM / 'source/solver.py'
    files = [Path(__file__), solver, ROOT/'experiments/convergence_revision5_oe_m2_source_placement.py',
             ROOT/'legal_skill_guard/paired_interfaces/convergence_oe_title_scope.py',
             ROOT/'legal_skill_guard/paired_interfaces/control_answers.py',
             ROOT/'legal_skill_guard/skill_evolution/native.py',
             ROOT/'legal_skill_guard/skill_evolution/clients.py', ROOT/'legal_skill_guard/rr/client.py']
    sealed = {'study': 'OE_B4_original_EV_renderer_amount_edits', 'TRAIN_only': True,
              'fit_sha256': sha(fit / 'terminal.json'), 'source_coverage_sha256': prior['artifact_terminal_sha256'],
              'source': source_key, 'edits': [digest(v) for v in revisions], 'slots': slots,
              'executor': bound['executor'], 'prior_wires': {r: prior_calls[r]['wire_sha256'] for r in ROLES},
              'forecast': forecast, 'native_original_score': positive[source_key],
              'source_files': {str(f.relative_to(ROOT)): sha(f) for f in files},
              'direct_comparator': 'Same-information analytic shared cap and fixed zero-or-eligible support',
              'labels_for_edited_inputs': False, 'n_planned_requests': 4}
    return sealed, text, revisions, inv, view, scope, prior_calls


def finalize(out, sealed, source_inventory, revisions, scope, all_reads, tokens, ledger):
    inventories = [source_inventory, *(title_inventory(s)[1] for s in revisions)]
    counts = {role: evaluate(rows, inventories, set(scope['citations'])) for role, rows in all_reads.items()}
    comparable = all(row is not None for rows in all_reads.values() for row in rows)
    all_read = comparable and all(c.get('unobserved_asset_rows', 0) == 0 for c in counts.values())
    result = {'status': 'settled_OE_B4_native_amount_edits', 'archived_native_reads_reused': 2,
              'new_requests': sum(len(reads) - 1 for reads in all_reads.values()),
              'tokens': dict(tokens), 'ledger': ledger, 'all_reads_decoded': comparable,
              'all_same_asset_rows_observed': all_read, 'by_role': counts,
              'prior_update_selection_retained': 'rejected_unsupported_literal_assertion',
              'native_edited_label_score_measured': False, 'DEV_or_TEST_used': False,
              'dispatch_runner_sha256': sealed['source_files'][str(Path(__file__).relative_to(ROOT))],
              'settlement_runner_sha256': sha(Path(__file__))}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'completed_calls': result['new_requests']}, POINTER)
    print(json.dumps(result), flush=True)


def settle():
    """Recover settlement from the original exact wires without requesting a model."""
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    archived = read(out / 'binding.json')
    current, text, revisions, inv, view, scope, prior = materials()
    runner = str(Path(__file__).relative_to(ROOT))
    current['source_files'][runner] = archived['source_files'][runner]
    assert current == archived and out.name == digest(archived)
    assert all(sha(out/'source_snapshot'/f) == h for f, h in archived['source_files'].items())
    identity = 'convergence-revision5-OE-native-edits-' + out.name[:16]
    readings = {role: [prior[role]['answer']] for role in ROLES}
    tokens = Counter()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for index, variant in enumerate(revisions):
            for role in ROLES:
                call = f'{identity}:{index}:{role}'
                payload = prior[role]['payload']
                schema = payload['response_format']['json_schema']['schema']
                physical_wire(db, {archived['source']}, call, archived['source'])
                response = json.loads(db.execute('select result from calls where id=?', (call,)).fetchone()[0])
                wire = read(Path(response['artifact_directory']) / 'wire_request.json')
                expected = json.dumps({**payload, 'messages': change_wire(payload, text, variant)},
                                      ensure_ascii=False).encode()
                assert base64.b64decode(wire['body_b64'], validate=True) == expected
                answer = projection(view, schema, response)
                saved = read(out / 'reads' / f'{index}_{role}.json')
                assert saved == {'call_id': call, 'wire_sha256': wire['body_sha256'], 'answer': answer}
                readings[role].append(answer)
                tokens[role] += response['usage']['total_tokens']
        counts = dict(db.execute('select status,count(*) from calls group by status'))
    finalize(out, archived, inv, revisions, scope, readings, tokens, counts)


def run(phase):
    if phase == 'settle' or (POINTER.exists() and read(POINTER)['status'] == 'settled_OE_B4_native_amount_edits'):
        settle()
        return
    sealed, text, revisions, inv, view, scope, prior = materials()
    out = HOME / digest(sealed)
    immutable_json(out / 'binding.json', sealed)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    if phase == 'prepare':
        write_status(out, {'status': 'prepared', 'planned_physical_calls': 4}, POINTER)
        print(str(out.relative_to(ROOT)), flush=True)
        return
    assert ROOT / read(POINTER)['artifact_root'] == out
    driver = (out / 'driver.lock').open('a')
    fcntl.flock(driver, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for filename, expected in sealed['source_files'].items():
        dest = out / 'source_snapshot' / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as stream:
                stream.write((ROOT/filename).read_bytes())
        assert sha(dest) == expected
    identity = 'convergence-revision5-OE-native-edits-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=identity, sources={'train': [sealed['source']], 'dev': [], 'test': []},
                             binding=sealed)
    executor = FrozenExecutor(ledger, out, sealed['executor'])
    executor.readiness()
    all_reads = {r: [prior[r]['answer']] for r in ROLES}
    tokens, n = Counter(), 0
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for index, variant in enumerate(revisions):
            for role in (ROLES if index % 2 == 0 else ROLES[::-1]):
                call = f'{identity}:{index}:{role}'
                payload = prior[role]['payload']
                schema = payload['response_format']['json_schema']['schema']
                messages = change_wire(payload, text, variant)
                assert executor.payload(messages=messages, thinking=False, schema=schema) == {**payload, 'messages': messages}
                write_status(out, {'status': 'running', 'completed_calls': n, 'current_call_id': call}, POINTER)
                response = executor.generate(call, source=sealed['source'], purpose='skill_actor',
                                             messages=messages, thinking=False, schema=schema)
                physical_wire(db, {sealed['source']}, call, sealed['source'])
                doc = read(Path(response['artifact_directory']) / 'wire_request.json')
                actual_wire = base64.b64decode(doc['body_b64'], validate=True)
                expected_wire = json.dumps({**payload, 'messages': messages}, ensure_ascii=False).encode()
                assert actual_wire == expected_wire and sha256(actual_wire).hexdigest() == doc['body_sha256']
                ans = projection(view, schema, response)
                all_reads[role].append(ans)
                tokens[role] += response['usage']['total_tokens']
                n += 1
                immutable_json(out / 'reads' / f'{index}_{role}.json',
                               {'call_id': call, 'wire_sha256': doc['body_sha256'], 'answer': ans})
                print(json.dumps({'settled': n, 'decoded': ans is not None}), flush=True)
        status = dict(db.execute('select status,count(*) from calls group by status'))
        assert not status.get('reserved') and n == 4
    finalize(out, sealed, inv, revisions, scope, all_reads, tokens, status)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run', 'settle'))
    run(parser.parse_args().phase)
