"""Bind old M2 proposal measurements to native-view title and realizable TRAIN edits."""

from collections import Counter
from itertools import product
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, _group_digest, pointer
from experiments.convergence_m2_train_scope import ownership_groups
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from experiments.convergence_revision5_oe_joint_native_gate import slot_records
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.paired_interfaces.shared_semantics import SourceCase, Theory, allowed_relation, source_variant
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_M2_source_placement_20261119'
BATCHES = (3, 4, 7, 8)


def title_conditional_support(ec, ev, title_ec, title_ev):
    """Assess a shared statutory category under the distinct facts stated in the two views."""
    admissible = {(category and t_ec, category and t_ev and available)
                  for category, available in product((False, True), repeat=2)
                  for t_ec in ((False, True) if title_ec is None else (title_ec,))
                  for t_ev in ((False, True) if title_ev is None else (title_ev,))}
    return any((ec is None or ec is a) and (ev is None or ev is b) for a, b in admissible)


def direct_title_scope(ec, ev, title_ec, title_ev):
    return not ((ec is True and title_ec is False) or (ev is True and title_ev is False)
                or (ec is False and ev is True and title_ec is True))


def reference(primitives, law):
    return {'title': primitives['title'], 'amount': primitives['amount']}


def compile_edit(source, family, text, slot, inventory, decisions):
    """Compile a change to one unambiguously located amount while preserving title."""
    asset = inventory[slot]
    if asset['filing_interest_established'] is not None:
        return None
    quote, token = (asset[k] for k in ('source_quote', 'amount_quote'))
    if text.count(quote) != 1 or quote.count(token) != 1:
        return None
    scope = supplied_jurisdiction_scope(text)
    if scope is None:
        return None
    amount = int(token[1:].replace(',', '').replace('.', ''))
    decision = decisions[quote]
    proof = digest({'source_quote': quote, 'decision': decision, 'public_premise': scope})
    theory = Theory({scope['premise']: [{}]}, {source: [{'title': False}, {'title': True}]},
                    reference, sha(Path(__file__)),
                    provenance=({'kind': 'independent_source_audit', 'evidence_sha256': proof,
                                 'interpretation': 'Pinned renderer, source-bound filing alias and title-unresolved relationship.'},),
                    allowed_edits=frozenset({'amount'}))
    start = text.index(quote) + quote.index(token)
    first = SourceCase(source+':'+family+':'+slot, source, scope['premise'],
                       {'text': text, 'asset': asset['description']}, {'amount': amount},
                       spans={'amount': ('text', start, start + len(token))})
    def render(cents):
        value = f'${cents//100:,}.{cents%100:02d}'
        return value if ',' in token else value.replace(',', '')

    cents = amount + 100
    value = render(cents)
    patch = source_variant(first, theory, {'amount': cents}, {'amount': render})
    assert patch['status'] == 'REALIZABLE'
    edited = patch['case']
    revised = edited.public['text']
    assert revised == text[:start] + value + text[start + len(token):]
    _, inventory_after, _ = title_inventory(revised)
    assert set(inventory_after) == set(inventory)
    assert supplied_jurisdiction_scope(revised) == scope
    for key, row in inventory_after.items():
        before = inventory[key]
        assert row['description'] == before['description']
        assert row['filing_interest_established'] == before['filing_interest_established']
        assert row['amount_quote'] == (value if key == slot else before['amount_quote'])
    shared = allowed_relation(theory, [first, edited])
    independent = allowed_relation(theory, [first, edited], mode='independent_completions')
    assert len(shared['signatures']) == 2 and len(independent['signatures']) == 4
    receipt = {'source': source, 'view': family, 'slot': slot, 'public_scope_sha256': digest(scope),
               'source_sha256': digest(text), 'edited_sha256': digest(revised),
               'edit_sha256': digest(patch['receipt']), 'title_scope_sha256': proof,
               'shared_signatures': 2, 'independent_signatures': 4}
    return {'theory': theory, 'cases': (first, edited), 'receipt': receipt}


def read_physical(db, expected_source, result, known):
    for view in result['reads']:
        trace, = (r for r in view['execution']['traces'] if 'physical_call_id' in r)
        ident = trace['physical_call_id']
        if ident not in known:
            known[ident] = (expected_source, physical_wire(db, {expected_source}, ident, expected_source))
        assert known[ident][0] == expected_source
        raw = json.loads(db.execute('select result from calls where id=?', (ident,)).fetchone()[0])
        assert raw['content'] == trace['raw_content']


def inspect_batch(db, batch, physical):
    stage = ROOT / read(pointer(batch))['artifact_root']
    binding = read(stage / 'binding.json')
    end = read(stage / 'terminal.json')
    saved = read(stage / 'matched_decisions.json')
    assert stage.name == digest(binding) and digest(saved) == end['matched_decisions_sha256']
    assert end['batch'] == batch and not end['TEST_opened']
    assert all(sha(stage / 'source_snapshot' / name) == expected for name, expected in binding['source_sha256'].items())
    selection = saved['relation'][OE]
    positive = {r['source'] for r in selection['native_comparisons'] if r['patch_utility'] > r['baseline_utility']}
    material = read(stage / 'candidates' / ORDINARY / OE / 'measurements.json')
    decision = read(stage / 'candidates' / ORDINARY / OE / 'decision.json')
    assert digest(material['candidate']) == selection['matched_proposal_sha256']
    assert digest(material['predictions']) == decision['predictions_sha256']
    root = ROOT / binding['checkpoint_root']
    study = read(root / 'binding.json')
    roster = load_roster(study)
    journal = TrainingJournal(root, study, roster)
    official = journal._observations(M2, batch)
    visible = [s for step in roster[:batch] for s in step]
    cohort = [s for s in roster[batch-1] if s['dataset'] == OE]
    assert len(cohort) == 4 and set(material['predictions']) == {s['key'] for s in cohort}
    original, _ = ownership_groups(visible)
    original_key = next(reversed(original))
    assert _group_digest(original[original_key]) == binding['natural_group_public_sha256']

    totals, edits, conflicts = Counter(), [], []
    for source in cohort:
        key = source['key']
        row = read(journal.directory(M2, batch) / 'predictions' / (digest(key) + '.json'))
        assert digest(row) == official['predictions'][key]
        incumbent, candidate = row['result'], material['predictions'][key]
        for result in (incumbent, candidate):
            read_physical(db, key, result, physical)
        inventories = {}
        for view in source['views']:
            family, text = view['id'], view['public']['original_input']
            try:
                _, inventory, decisions = title_inventory(text)
            except ValueError as error:
                totals['unanchored_views'] += 1
                totals['unanchored:' + str(error)] += 1
                continue
            inventories[family] = {a['description']: a for a in inventory.values()}
            for slot in inventory:
                group = compile_edit(key, family, text, slot, inventory, decisions)
                if group is not None:
                    edits.append(group['receipt'])
        if set(inventories) != {'EC', 'EV'}:
            continue
        totals['fully_anchored_native_pairs'] += 1
        for row in slot_records(source, incumbent, candidate):
            name = row['asset']
            a, b = (inventories[f][name]['filing_interest_established'] for f in ('EC', 'EV'))
            for arm, (ec, ev) in row['ports'].items():
                if ev is not True:
                    continue
                totals[arm + '_positive_allocations'] += 1
                totals[arm + '_positions_with_different_title_evidence'] += a is not b
                conventional = ec is False
                scoped = not title_conditional_support(ec, ev, a, b)
                assert (not direct_title_scope(ec, ev, a, b)) == scoped
                totals[arm + '_coarse_conflicts'] += conventional
                totals[arm + '_title_conditional_conflicts'] += scoped
                if conventional or scoped:
                    conflicts.append({'source': key, 'role': arm, 'native_root_positive': key in positive,
                                      'asset_citation_sha256': digest([name, row['citation']]),
                                      'coarse': conventional, 'title_conditional': scoped,
                                      'EC_title': a, 'EV_title': b})
    edits_available = {r['source'] for r in edits}
    return {'batch': batch, 'fit_terminal_sha256': sha(stage / 'terminal.json'), 'official_M2_status': selection['status'],
            'native_positive_mothers': len(positive), 'existing_paid_group_has_same_batch_mother': original_key in {s['key'] for s in cohort},
            'existing_paid_group_has_positive_same_mother': original_key in positive,
            'positive_mothers_with_old_legal_edit': len(positive & original.keys()),
            'positive_mothers_with_renderer_edit': len(positive & edits_available),
            'new_edit_candidates': len(edits), 'view_placement': dict(Counter(r['view'] for r in edits)),
            'rendered_edits_on_positive_mothers': sum(r['source'] in positive for r in edits),
            'native_cross_view_counts': dict(totals), 'conflicts': conflicts, 'edits': edits}


def run():
    for p in product((None, False, True), repeat=4):
        assert title_conditional_support(*p) == direct_title_scope(*p)
    physical = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        db.execute('begin')
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
        rows = [inspect_batch(db, batch, physical) for batch in BATCHES]
    public = [{k: v for k, v in row.items() if k not in ('edits', 'conflicts')} for row in rows]
    rule = 'legal_skill_guard/paired_interfaces/convergence_oe_title_scope.py'
    output = {'batches': public, 'physical_native_calls_verified': len(physical),
              'independent_same_information_control': 'Direct title-conditional implication with the same scopes',
              'renderer_title_scope_sha256': sha(ROOT / rule),
              'title_conditional_equals_direct_on_all_ternary_states': 81,
              'positive_mothers_total': sum(z['native_positive_mothers'] for z in rows),
              'positive_mothers_covered_by_old_groups': sum(z['positive_mothers_with_old_legal_edit'] for z in rows),
              'positive_mothers_covered_by_renderer_groups': sum(z['positive_mothers_with_renderer_edit'] for z in rows),
              'new_edits_have_no_physical_responses': True, 'new_requests': 0,
              'DEV_or_TEST_source_or_grade_used': False, 'ledger': counts, 'runner_sha256': sha(Path(__file__))}
    stage = HOME / digest(output)
    immutable_json(stage / 'local_witnesses.json', rows)
    immutable_json(stage / 'terminal.json', {**output, 'local_witnesses_sha256': sha(stage / 'local_witnesses.json')})
    print(json.dumps({'artifact_root': str(stage.relative_to(ROOT)), **output}, sort_keys=True))


if __name__ == '__main__':
    run()
