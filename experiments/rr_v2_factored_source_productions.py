"""Offline learning/recombination test on preserved real source productions.

No request dispatcher, new native labels, DEV, or TEST is used. The eight
historical source cases are development replay, never a fresh validation set.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import time

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_attachment_update import apply, assess, production_code
from legal_skill_guard.rr.factored_source_productions import factor, learn_consistent_bank, recombine

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rr_method_redesign_20261109'
OLD = BASE / 'contract_attachment_update_v1_20261110'
STAGE = BASE / 'factored_source_productions_v1_20261110'


def read(p):
    return json.loads(p.read_text())


def ledger():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as c:
        return {t: c.execute('select * from ' + t + ' order by 1').fetchall() for t in ['calls', 'meta', 'oracle_views']}


def main():
    before = ledger()
    seed = read(OLD / 'minimum_attachment_learned.json')
    ordinary = read(OLD / 'current_update_state.json')['arms']['ordinary_repair']
    training = read(OLD / 'training_seal.json')
    paths = ['legal_skill_guard/rr/factored_source_productions.py',
             'experiments/rr_v2_factored_source_productions.py',
             'tests/test_rr_factored_source_productions.py']
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    inputs = [OLD / p for p in ['minimum_attachment_learned.json', 'current_update_state.json', 'training_seal.json', 'frozen_source_only_reuse.json']]
    immutable_json(STAGE / 'seal.json', {'files': files,
        'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'real_paid_productions_reused': True, 'new_model_calls': 0,
        'historical_replay_is_development_not_fresh_validation': True,
        'third_joint_binding_constraint_not_expressible_in_this_interface': True,
        'DEV_started': False, 'TEST_started': False, 'goal_complete': False})
    for p in paths:
        out = STAGE / 'frozen' / p
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((ROOT / p).read_bytes())
    library = factor(seed['update']['productions'])
    immutable_json(STAGE / 'factored_library.json', library)
    started = time.monotonic()
    learned = learn_consistent_bank(library, training['documents'], training['feedback'])
    elapsed = time.monotonic() - started
    immutable_json(STAGE / 'learned_bank.json', learned)
    all_productions = [c['production'] for c in recombine(library)]
    selected = [c['production'] for c in learned['selected']]
    codes = {'paid_original_bank': seed['update']['code'], 'factored_all': production_code(all_productions),
             'factored_selected': production_code(selected), 'independent_paid_free_program': ordinary['update']['code']}
    fit = {name: assess(code, training['documents'], training['feedback']) for name, code in codes.items()}
    immutable_json(STAGE / 'training_replay.json', fit)
    historical = []
    for m in read(OLD / 'frozen_source_only_reuse.json')['results']:
        historical.append({'key': 'p' + str(m['ordinal']), 'document': m['document'],
                           'graph': m['initial_graph_entry']['value'], 'source': m['source']})
    for key in ['p114', 'p116', 'p117', 'p118']:
        historical.append(read(BASE / 'source_attachment_learning_v6_20261110' / (key + '_forest.json'))['material'])
    results = []
    for m in historical:
        states = {name: apply(code, m['document'], m['graph']) for name, code in codes.items()}
        results.append({'key': m['key'], 'source': m['source'], 'states': states,
            'attachments': {name: len(s['attachments']) for name, s in states.items()},
            'changes': {name: len(s['changes']) for name, s in states.items()},
            'all_factor_equals_original': states['factored_all'] == states['paid_original_bank'],
            'selected_equals_original': states['factored_selected'] == states['paid_original_bank']})
    immutable_json(STAGE / 'historical_source_replay.json', {'results': results, 'new_native_predictions_or_labels': 0,
        'already_observed_development_sources_not_unseen_validation': True})
    after = ledger()
    assert before == after
    summary = {'counts_total': {role: sum(r[1] == role for r in before['calls']) for role in ['executor', 'teacher']},
        'ledger_unchanged': True, 'new_physical_calls': 0, 'new_native_label_views': 0,
        'learned_from_actual_paid_productions': len(seed['update']['productions']),
        'head_lexemes': len(library['heads']), 'action_lexemes': len(library['actions']),
        'composition_templates': len(library['templates']), 'recombinations': len(all_productions),
        'selected': len(selected), 'offline_fit_seconds': elapsed,
        'TRAIN_constraints_each_arm': {name: {'passed': sum(r['passed'] for r in f['constraints']), 'n': len(f['constraints'])} for name, f in fit.items()},
        'historical_sources': [{k: r[k] for k in ['key', 'attachments', 'changes', 'all_factor_equals_original', 'selected_equals_original']} for r in results],
        'joint_exception_binding_expressible': False,
        'no_new_source_words_or_semantic_facts_acquired': True,
        'not_a_full_FUBL_or_CCG_reproduction': True,
        'DEV_started': False, 'TEST_started': False, 'main_training_started': False,
        'goal_complete': False, 'first_contribution_established': False}
    immutable_json(STAGE / 'results.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
