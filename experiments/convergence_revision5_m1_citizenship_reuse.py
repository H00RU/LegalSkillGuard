"""Audit repeated citizenship bindings in the original Diversity TRAIN reads."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER
from experiments.convergence_m1_incumbent_audit import DATASET, M1, _verify_reads
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces import diversity_claim_groups, relational_program, residual
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_m1_citizenship_reuse_20261119'
ROLES = ('plaintiff', 'defendant')


def reusable_coordinates(program, value, anchors):
    """Share only identical observations attached to the same unique public statement."""
    shared = {}
    targets = {}
    counts = Counter()
    for key, unit in program['units'].items():
        if not key.startswith('citizenship_pair_'):
            continue
        row = value[key]
        if row['status'] != 'complete' or row['observation']['source_anchor'] != key:
            raise ValueError('An unsupported attachment cannot be counted as a reusable observation')
        quotes = anchors[key]['source_excerpts']
        actual_quotes = {ev['quote'] for ev in row['evidence'] if ev['field'] == 'source_text'}
        if set(quotes) != actual_quotes:
            raise ValueError('Both verified name-specific quotations are needed')
        bindings = []
        for role, quote in zip(ROLES, quotes, strict=True):
            person = unit['entity_context'][role]
            if not quote.startswith(person + ' is from '):
                raise ValueError('The original public quote lost its named source attachment')
            binding = (person, quote)
            port = role + '_state'
            observed = row['observation']['relations'][port]
            if binding in shared and observed != shared[binding]:
                raise ValueError('A conflicting reader observation cannot be deduplicated')
            shared[binding] = observed
            counts[binding] += 1
            bindings.append((port, binding))
        targets[key] = bindings
    rebuilt = deepcopy(value)
    for key, bindings in targets.items():
        rebuilt[key]['observation']['relations'] = {port: shared[p] for port, p in bindings}
    return rebuilt, {'pair_units': len(targets), 'coordinate_slots': sum(counts.values()),
                     'person_slots': len(counts), 'repeated_person_bindings': sum(v > 1 for v in counts.values())}


def graph_consistent(edges):
    parent = {party: party for pair in edges for party in pair}

    def root(party):
        while parent[party] != party:
            party = parent[party]
        return party

    for (p, d), different in edges.items():
        if different is False:
            parent[root(p)] = root(d)
    return all(root(p) != root(d) for (p, d), diff in edges.items() if diff is True)


def run():
    checkpoint = ROOT / read(POINTER)['artifact_root']
    study = read(checkpoint/'binding.json')
    batches = load_roster(study)
    sources = {s['key']: s for batch in batches for s in batch if s['dataset'] == DATASET}
    provider = diversity_claim_groups.Provider()
    views = {key: provider.views(s)[0] for key, s in sources.items()}
    reviews = {key: diversity_claim_groups.unit_reviews(s, views[key]) for key, s in sources.items()}
    library = TrainingJournal(checkpoint, study, batches).library(M1, 8)['interface_library']
    bank = library['observations']
    _verify_reads(bank)
    saved_forward = ROOT / read(HANDOFF/'M1_incumbent_through_B8_20261118.json')['receipt']
    forward = read(saved_forward)
    assert not forward['DEV_opened'] and not forward['TEST_opened']
    chosen = {row['current']['physical_call_id'] for row in forward['folds'] if row['current_profile'] is not None}
    uses = Counter()
    summaries = {'fixed_coordinates': Counter(), 'synthesized_relation': Counter()}
    directions = Counter()
    shapes = Counter()

    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        db.execute('begin')
        ledger_rows = db.execute('select count(*) from calls').fetchone()[0]
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for readout in bank:
            key = readout['source']
            view = views[key]
            plan, = (p for p in view['plans'] if p['version'] == readout['plan_version'])
            program = plan['relational_program']
            fixed = plan['choices']['citizenship'] == 0
            group = 'fixed_coordinates' if fixed else 'synthesized_relation'
            usage = summaries[group]
            usage['reads'] += 1
            physical = readout['physical_call_id']
            if physical in chosen:
                uses[group] += 1
            response, = db.execute('select result from calls where id=?', (physical,)).fetchone()
            value, _ = restore_enum_transport(json.loads(json.loads(response)['content']), plan['schema'])
            edges = {}
            participants = {role: set() for role in ROLES}
            for name, unit in program['units'].items():
                if not name.startswith('citizenship_pair_'):
                    continue
                context = unit['entity_context']
                p, d = (context[role] for role in ROLES)
                participants['plaintiff'].add(p)
                participants['defendant'].add(d)
                state, = reviews[key][name]['admissible_states']
                expected = residual.encode(unit['asset']['features'], state)
                raw = value[name]
                found = raw['observation']['relations'] if raw['status'] == 'complete' else None
                usage['source_faithful_pairs'] += found == expected
                if fixed:
                    usage['coordinate_slot_errors'] += sum(found.get(port) != truth for port, truth in expected.items())
                else:
                    sign, = found.values() if found is not None else (None,)
                    correct, = expected.values()
                    if sign != correct:
                        directions[(str(correct).lower(), str(sign).lower())] += 1
                    edges[p, d] = sign
            if not fixed:
                usage['impossible_equality_graphs'] += not graph_consistent(edges)
                usage['pair_units'] += len(edges)
                continue

            public = view['relational_public_source']
            anchors = {u['source_anchor']: u for u in view['read_input']['unit_requests']}
            shared_value, figures = reusable_coordinates(program, value, anchors)
            usage.update(figures)
            assert relational_program.decode(program, shared_value, public) == relational_program.decode(program, value, public)
            usage['complete_decodes_identical_after_reuse'] += 1
            amount_choice, = (n for kind, n in plan['choices'].items() if kind != 'citizenship')
            if amount_choice == 0:
                shapes[tuple(len(participants[role]) for role in ROLES)] += 1

    assert len(bank) == 96 and len(sources) == 24 and sum(uses.values()) == len(chosen) == 15
    totals = summaries['fixed_coordinates']
    assert totals['pair_units'] == totals['source_faithful_pairs'] == 96 and totals['coordinate_slot_errors'] == 0
    assert totals['person_slots'] == 136 and totals['coordinate_slots'] == 192
    outcome = {'scope': 'All 96 paid candidate reads of the original 24 Diversity TRAIN mothers',
               'source_shape_counts': {f'{p}x{d}': n for (p,d),n in shapes.items()},
               'read_totals_by_citizenship_representation': {k: dict(v) for k,v in summaries.items()},
               'relational_errors_by_expected_and_read': {f'{a}_to_{b}': n for (a,b),n in directions.items()},
               'learned_chronological_route_citizenship_profiles': dict(uses),
               'coordinates_removed_by_exact_sharing': totals['coordinate_slots']-totals['person_slots'],
               'coordinate_reuse_only_in_existing_responses': True, 'native_or_physical_savings_claimed': False,
               'original_forward_selection_sha256': sha(saved_forward),
               'original_interface_library_sha256': library['snapshot_sha256'],
               'original_candidate_public_sha256': digest({k: digest(v) for k,v in sources.items()}),
               'audit_source_sha256': sha(Path(__file__)), 'ledger_rows': ledger_rows, 'new_model_calls': 0,
               'DEV_or_TEST_content_or_labels_opened': False}
    immutable_json(HOME/'terminal.json', outcome)
    print(json.dumps(outcome, indent=2), flush=True)


if __name__ == '__main__':
    run()
