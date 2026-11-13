"""Replay a public native-sort correction; never rewrite a frozen result.

This repairs the extra individual gate on an explicitly GIVEN exemption
entitlement. It does not supply an absent case value or acquire a new law.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import compile_library, evaluate
from legal_skill_guard.skill_evolution.source_python import merge_functions

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/legal_skill_evolution_scoped_premise_repair_20261113'
FUNCTION = '''def section_151_deduction_allowable_from_exemption_entitlement(facts):
    direct = facts.get('deduction_under_section_151_allowable_to_another_taxpayer_for_subject')
    if isinstance(direct, bool):
        return {'value': direct, 'used_units': ['u151_a_pred'], 'open_dependencies': []}
    entitlement = facts.get('exemption_under_section_151_entitlement_of_another_taxpayer_for_subject')
    if entitlement is True:
        return {'value': True, 'used_units': ['u151_a_pred'], 'open_dependencies': []}
    deps = ['deduction_under_section_151_allowable_to_another_taxpayer_for_subject']
    if not isinstance(entitlement, bool):
        deps.append('exemption_under_section_151_entitlement_of_another_taxpayer_for_subject')
    return {'value': None, 'used_units': ['u151_a_pred'], 'open_dependencies': deps}
'''


def run():
    old = json.loads((OUT / 'IndependentCache/library.json').read_text())
    program = merge_functions(old['program'], [FUNCTION])
    before = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(old['program']).body}
    after = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(program).body}
    assert set(before) == set(after)
    changed = [name for name in before if before[name] != after[name]]
    assert changed == ['section_151_deduction_allowable_from_exemption_entitlement']
    new = compile_library({'program': program, 'units': list(old['units'].values())}, old['law_material'])
    replays = []
    for path in sorted((OUT / 'execution/calibration/IndependentCache').glob('*/result.json')):
        raw = json.loads(path.read_text())
        assert evaluate(old, raw['plan'], raw['case_values']) == raw['result']
        replays.append({'source': raw['source'], 'old_actual_result': raw['result'],
            'new_offline_result': evaluate(new, raw['plan'], raw['case_values']),
            'same_case_values': True, 'new_model_requests': 0})
    amount = next(r for r in replays if r['source'].endswith('e16240027250747ff69ead62bad04238598466042e1bf9bdc668c789366034c3'))
    assert amount['new_offline_result']['value'] == 0
    assert amount['new_offline_result']['answer'] == 'Contradiction'
    # Native negation-as-failure must not become a blanket missing-value default.
    raw = json.loads(next((OUT/'execution/calibration/IndependentCache').glob('*e162*/result.json')).read_text())
    unknown = evaluate(new, raw['plan'], {})
    negative_entitlement = evaluate(new, raw['plan'], {
        'exemption_under_section_151_entitlement_of_another_taxpayer_for_subject': False})
    assert unknown['value'] is None and negative_entitlement['value'] is None
    for r in replays:
        if r is not amount:
            assert r['old_actual_result'] == r['new_offline_result']
    immutable_json(OUT/'native_sort_replay/library.json', new)
    immutable_json(OUT/'native_sort_replay/evidence.json', {
        'scope': 'Public native-sort correctness replay on exposed calibration, not an independently acquired model result or contribution gain.',
        'reason': 'Official section151(a)/(d)(2) has no independent individual fact guard for an explicitly GIVEN exemption entitlement.',
        'official_section151_sha256': hashlib.sha256((OUT/'native_semantics_source_only/section151.pl').read_bytes()).hexdigest(),
        'changed_functions': changed, 'raw_results_or_case_values_modified': False,
        'old_library_sha256': hashlib.sha256((OUT/'IndependentCache/library.json').read_bytes()).hexdigest(),
        'replays': replays, 'missing_entitlement_still_unknown': unknown,
        'negative_entitlement_not_inverse_implication': negative_entitlement,
        'same_policy_applies_to_both_arms': True,
        'method_already_has_no_extra_guard_on_this_bridge': True,
        'official_source_code_supplied_as_learned_code': False,
        'no_new_model_requests_or_native_scores': True, 'goal_complete': False})
    print(json.dumps(replays, ensure_ascii=False))


if __name__ == '__main__':
    run()
