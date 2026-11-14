"""Actual TRAIN source/program edit binding, with fixed old/new code and no LLM.

This is a finite update-policy prototype. It does not certify either contribution
or start a new full training run. Whole-repair and additive-reuse controls remain.
"""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from experiments import legal_skill_evolution_source_gap_acquisition as e
from experiments import legal_skill_evolution_source_scope_repair as repair
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.source_patch_composition import compose_libraries, retirement_effects
from legal_skill_guard.skill_evolution.scoped_grammar import constructors
from legal_skill_guard.skill_evolution.source_composition import render_composition, statement_fingerprint
from legal_skill_guard.skill_evolution.bound_edit_learning import learn_effects

RUN = 'legal_skill_evolution_bound_edits_20261114'
OUT = e.ROOT / 'artifacts' / RUN
TRAIN_PREFIXES = ('de427b59', '6fce8464', 'e7b78d42')


class NoCalls:
    def generate(self, *args, **kwargs):
        raise AssertionError('No model calls in actual edit learning')


def setup():
    _, _, public = e.setup()
    task = e.read(repair.OUT / 'teacher_task.json')
    before = task['actual_current_libraries_both_available']['ConstraintAcquire']
    proposed = e.read(repair.OUT / 'ConstraintAcquire/compiled.json')
    sources = e.read(e.OUT / 'protocol.json')['acquisition_sources']
    training = [k for k in sources if any(k.startswith('ContractNLI:' + p) for p in TRAIN_PREFIXES)]
    other = [k for k in sources if k not in training]
    assert len(training) == 3 and len(other) == 5
    immutable_json(OUT / 'fixed_sources.json', {'training': training, 'after_policy_freeze': other,
        'two_actual_repairs_and_one_supported_old_capability_negative': True,
        'original_TRAIN_and_previous_exposure_disclosed': True,
        'no_new_sources_DEV_TEST_or_model_calls': True, 'goal_complete': False})
    return public, before, proposed, training, other


def snapshot(phase):
    files = [Path(__file__), e.ROOT / 'legal_skill_guard/skill_evolution/source_patch_composition.py',
        e.ROOT / 'tests/test_skill_evolution_source_patch_composition.py']
    hashes = {}
    for f in files:
        body = f.read_bytes(); key = str(f.relative_to(e.ROOT)); hashes[key] = hashlib.sha256(body).hexdigest()
        dst = OUT / 'source_snapshot' / phase / key
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            assert dst.read_bytes() == body
        else:
            dst.write_bytes(body)
    immutable_json(OUT / ('source_binding_' + phase + '.json'), {'files': hashes, 'new_model_requests': 0})


def baseline():
    public, before, proposed, training, other = setup(); snapshot('baseline')
    combined = compose_libraries(before, proposed)
    immutable_json(OUT / 'additive_library.json', combined)
    for key in training + other:
        dst = OUT / 'additive' / e.name_for(key)
        if dst.exists():
            continue
        pub, units, _ = e.previous.prior.prior.source_material(e.previous.PARENT, public, key)
        obs = observe(NoCalls(), RUN + ':additive:' + key, key, combined,
            source_text=pub['source_text'], units=units,
            source_output=e.read(e.OUT / 'upstream' / e.name_for(key))['source_output'])
        # No new five-source native feedback is opened before the policy freeze.
        actual = e.previous.prior.prior.evaluate_source(combined, obs, public[key], None)
        immutable_json(dst, {'source': key, 'observation': obs, 'actual': actual,
            'native_feedback_not_used': True, 'new_model_requests': 0})
        print(json.dumps({'source': key, 'additive_program_executed': True, 'native_scores_opened': False}), flush=True)


def nodes(term, path=()):
    if isinstance(term, list):
        for i, item in enumerate(term[1:], 1):
            yield from nodes(item, (*path, i))
    else:
        yield list(path), term


def code_bindings(library):
    by_ctor = {}
    for rule in library['language']['rules']:
        for atom in rule['body']:
            if atom['predicate'] == 'term_constructor' and isinstance(atom['arguments'][1], str):
                by_ctor.setdefault(atom['arguments'][1], []).append(rule['id'])
    return by_ctor


def candidates():
    _, before, proposed, training, _ = setup(); old_code = code_bindings(before); new_code = code_bindings(proposed)
    static = {n.value for n in ast.walk(ast.parse(proposed['source_program']))
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch('[a-z][a-z0-9_]*', n.value)}
    old_schema = constructors(before['spec']); new_schema = constructors(proposed['spec'])
    pool = {}
    for key in training:
        old = e.read(e.OUT / 'unbound_pure_preview/ConstraintAcquire' / e.name_for(key))['observation']
        new = e.read(OUT / 'additive' / e.name_for(key))['observation']
        units = new['visible_inputs']['units']; by_text = {u['text']: u['id'] for u in units}
        old_rows = old['visible_inputs']['source_output']['statements']
        new_rows = [r for r in new['visible_inputs']['source_output']['statements']
            if r['term'][0] in new_code and r['term'][0] not in old_schema]
        for a in old_rows:
            ac = a['term'][0]
            if ac not in old_code or old_schema[ac]['sort'] == 'Norm':
                continue
            for ai, quote in enumerate(a['term'][1:], 1):
                if not isinstance(quote, str) or quote not in by_text or by_text[quote] not in a['support_ids']:
                    continue
                for b in new_rows:
                    bc = b['term'][0]
                    for bi, value in enumerate(b['term'][1:], 1):
                        if value != quote or by_text[quote] not in b['support_ids']:
                            continue
                        base = {'old_constructor': ac, 'old_quote_position': ai,
                            'new_constructor': bc, 'new_quote_position': bi, 'guards': []}
                        proposals = [base]
                        for si, scope in enumerate(b['term'][1:], 1):
                            if not isinstance(scope, str) or scope == quote or not scope or scope in static or scope in by_text:
                                continue
                            for witness in new_rows:
                                wc = witness['term'][0]
                                for wi, bound in enumerate(witness['term'][1:], 1):
                                    if bound != scope:
                                        continue
                                    for path, literal in nodes(witness['term']):
                                        if not isinstance(literal, str) or literal not in static:
                                            continue
                                        guarded = deepcopy(base)
                                        guarded['guards'] = [{'constructor': wc, 'anchor_path': [si], 'witness_path': [wi],
                                            'checks': [{'path': path, 'value': literal}]}]
                                        proposals.append(guarded)
                        for policy in proposals:
                            identity = digest(policy)
                            entry = pool.setdefault(identity, {'id': identity, 'policy': policy,
                                'old_program_bridge_rules': old_code[ac], 'new_program_bridge_rules': new_code[bc],
                                'type_bindings': {'old_sort': old_schema[ac]['sort'], 'new_sort': new_schema[bc]['sort'],
                                    'old_quote_argument_sort': old_schema[ac]['arguments'][ai - 1],
                                    'new_quote_argument_sort': new_schema[bc]['arguments'][bi - 1]},
                                'actual_anchor_sources': []})
                            if key not in entry['actual_anchor_sources']:
                                entry['actual_anchor_sources'].append(key)
    return sorted(pool.values(), key=lambda p: p['id'])


def tree_nodes(term):
    if isinstance(term, list):
        yield term
        for child in term[1:]:
            yield from tree_nodes(child)


def reviewed_status(source, row):
    """Only concrete source defects/retention identified before this learning."""
    term = row['term']; support = set(row['support_ids']); parts = list(tree_nodes(term))
    if source.startswith('ContractNLI:6fce'):
        if term[0] == 'permission' and 10 in support and any(t[0] == 'acquired_disclosure_condition_v3'
                and t[3] != 'written_required' for t in parts):
            return 'bad', 'representative_member_missing_source_written_qualification'
        if term[0] == 'disposal_obligation' and 61 in support and term[2][0] != 'cause_disposal_v4':
            return 'bad', 'direct_duty_instead_of_source_cause_affiliate_duty'
    if source.startswith('ContractNLI:de42') and term[0] == 'disposal_obligation' and 39 in support:
        if any(t[:3] == ['acquired_trigger_v3', 'relationship_nonformation_or_request', 'no_explicit_timing'] for t in parts):
            return 'bad', 'nonformation_deadline_omitted_and_explicit_timing_denied'
    if source.startswith('ContractNLI:e7b7') and term[0] == 'disposal_obligation' and 34 in support:
        if any(t[:3] == ['acquired_trigger_v3', 'agreement_end_or_request', 'immediate'] for t in parts):
            return 'keep', 'actual_agreement_end_or_request_and_immediate_capability'
    return 'unreviewed', None


def fit():
    _, before, _, training, _ = setup(); snapshot('fit')
    library = e.read(OUT / 'additive_library.json'); by_renderer = {r['predicate']: r for r in library['renderers']}
    pool = e.read(OUT / 'candidate_policies.json')['entries']; effects = [{} for _ in pool]
    proofs = []; protected = {}; contexts = []
    for key in training:
        record = e.read(OUT / 'additive' / e.name_for(key)); observation = record['observation']
        old = e.read(e.OUT / 'unbound_pure_preview/ConstraintAcquire' / e.name_for(key))['observation']
        old_rows = old['visible_inputs']['source_output']['statements']
        old_indices = {statement_fingerprint(row): i for i, row in enumerate(old_rows)}
        matched = retirement_effects(old_rows, observation['visible_inputs']['source_output']['statements'],
            observation['visible_inputs']['units'], [x['policy'] for x in pool])
        for effect, indices in zip(effects, matched):
            effect[key] = indices
        composition = record['actual']['execution']['composition']
        for output in composition['certain_outputs']:
            one = deepcopy(composition); one['certain_outputs'] = [output]
            row, = render_composition(library['language'], library['renderers'], observation, one, library['spec'])['statements']
            status, reason = reviewed_status(key, row)
            if status == 'unreviewed':
                continue
            renderer = by_renderer.get(output['predicate'])
            if renderer is None:
                raise ValueError('Reviewed wrong/retained path needs actual acquired G provenance')
            indices = []
            for position in renderer['support_from_terms']:
                term_id = output['arguments'][position]
                root = observation['legacy_roots'].get(term_id)
                if root is not None and statement_fingerprint(root) in old_indices:
                    indices.append(old_indices[statement_fingerprint(root)])
            assert indices
            witness = {'source': key, 'reason': reason, 'root_indices': sorted(set(indices)),
                'actual_output': output, 'actual_norm': row}
            if status == 'bad':
                proofs.append(witness)
            else:
                protected.setdefault(key, []).extend(i for i in indices if i not in protected.get(key, []))
            contexts.append({'status': status, **witness})
    learned = learn_effects(pool, effects, proofs, protected)
    immutable_json(OUT / 'actual_reviewed_proof_witnesses.json', {'witnesses': contexts,
        'unreviewed_not_a_negative': True, 'new_model_requests': 0})
    immutable_json(OUT / 'learned_U.json', learned)
    assert learned['status'] == 'selected_requires_execution'
    _, old, proposed, _, _ = setup()
    updated = compose_libraries(old, proposed, [x['policy'] for x in learned['entries']])
    immutable_json(OUT / 'updated_library.json', updated)
    immutable_json(OUT / 'POLICY_FROZEN_BEFORE_OTHER5.json', {'U_sha256': digest(learned),
        'library_sha256': digest(updated), 'other5_native_feedback_used': False,
        'new_model_requests': 0, 'goal_complete': False})
    print(json.dumps({'actual_bad_proofs': len(proofs), 'candidate_count': len(pool),
        'learned_policies': len(learned['entries']), 'objective': learned['objective']}), flush=True)


def check():
    public, before, proposed, training, other = setup(); snapshot('check')
    frozen = e.read(OUT / 'POLICY_FROZEN_BEFORE_OTHER5.json')
    learned = e.read(OUT / 'learned_U.json'); lib = e.read(OUT / 'updated_library.json')
    assert digest(learned) == frozen['U_sha256'] and digest(lib) == frozen['library_sha256']
    grading = e.read(e.previous.prior.prior.GRADING)
    for key in training + other:
        dst = OUT / 'updated' / e.name_for(key)
        if dst.exists():
            continue
        pub, units, _ = e.previous.prior.prior.source_material(e.previous.PARENT, public, key)
        observation = observe(NoCalls(), RUN + ':updated:' + key, key, lib,
            source_text=pub['source_text'], units=units,
            source_output=e.read(e.OUT / 'upstream' / e.name_for(key))['source_output'])
        actual = e.previous.prior.prior.evaluate_source(lib, observation, public[key], None)
        immutable_json(dst, {'source': key, 'observation': observation, 'actual': actual,
            'policy_sha256': digest(learned), 'new_model_requests': 0})
    # All five source executions exist before scoring those new policy results.
    assert all((OUT / 'updated' / e.name_for(key)).exists() for key in other)
    rows = []
    for key in training + other:
        row = {'source': key, 'learning': key in training, 'systems': {}}
        for name, folder, library in [('additive', OUT / 'additive', e.read(OUT / 'additive_library.json')),
                ('updated', OUT / 'updated', lib)]:
            record = e.read(folder / e.name_for(key)); actual = record['actual']
            feedback = e.previous.prior.prior.checker(library, public[key], grading[key])(actual['execution']['source_output'])
            reviewed = [(reviewed_status(key, n)[0], statement_fingerprint(n))
                for n in actual['execution']['source_output']['statements']]
            row['systems'][name] = {'actual_native_feedback': feedback,
                'bad_reviewed_norms': sum(s == 'bad' for s, _ in reviewed),
                'actual_old_capability_witnesses': sum(s == 'keep' for s, _ in reviewed),
                'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in feedback['views'])}
        rows.append(row)
    immutable_json(OUT / 'source_results.json', {'rows': rows, 'all_other5_execution_saved_before_scoring': True,
        'not_new_blind_validation': True, 'new_model_requests': 0, 'goal_complete': False})
    print(json.dumps({'systems': {s: sum(r['systems'][s]['native_correct'] for r in rows) for s in ['additive', 'updated']},
        'bad_reviewed_norms': {s: sum(r['systems'][s]['bad_reviewed_norms'] for r in rows) for s in ['additive', 'updated']},
        'new_model_requests': 0}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['baseline', 'candidates', 'fit', 'check'])
    phase = parser.parse_args().phase
    if phase == 'baseline':
        baseline()
    elif phase == 'candidates':
        pool = candidates()
        immutable_json(OUT / 'candidate_policies.json', {'entries': pool, 'no_model_requests': True})
        print(json.dumps({'source_program_bound_candidates': len(pool)}), flush=True)
    elif phase == 'fit':
        fit()
    else:
        check()
