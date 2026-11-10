"""Host regression on preserved real failures; oracle fixtures are not learning."""
import json
import ast
import re
from copy import deepcopy
from pathlib import Path

import pytest

from legal_skill_guard.rr.contract_attachment_update import annotations, apply, assess, production_code, select

OLD = Path(__file__).resolve().parents[1] / 'artifacts/rr_method_redesign_20261109/contract_compiler_induction_v1_20261110'


def material():
    graph = next(r['result']['value'] for r in json.loads((OLD / 'source_only_15_20_raw_graphs.json').read_text())['results']
                 if r['ordinal'] == 20 and r['arm'] == 'ordinary_program')
    document = next(r['document'] for r in json.loads((OLD / 'source_only_15_20_plan.json').read_text())['sources'] if r['ordinal'] == 20)
    feedback = {'id': 'real_negated_breach', 'key': 'p20', 'anchor_contains': 'shall not have breached',
                'kind': 'no_breach', 'action': 'share', 'head_contains': 'not have breached',
                'behavior_contains': 'disclosed', 'reference_contains': '',
                'condition_contains': 'if the Confidential Information is disclosed',
                'forbidden_effects_on_anchor': ['permission', 'prohibition', 'obligation']}
    return {'key': 'p20', 'document': document, 'graph': graph}, feedback


def software_oracle():
    # Exact actual failure spans test runtime plumbing only. This production is
    # NEVER in the model prompt, proposal bank or claimed learned result.
    return {'id': 'software_only_oracle', 'pattern': r'(?P<anchor>(?P<head>shall not have breached any obligation under this Agreement) (?P<c>if the Confidential Information is (?P<behavior>disclosed) to a third party when the Confidential Information:))',
            'kind': 'no_breach', 'action': 'share', 'condition_groups': ['c'],
            'reference_groups': [], 'clear_overrides': True}


def test_real_error_needs_positive_head_and_condition_not_deletion():
    m, f = material()
    assert not assess('def infer(document, query):\n    return []\n', [m], [f])['passed']
    result = assess(production_code([software_oracle()]), [m], [f])
    assert result['passed']
    state = result['states']['p20']
    assert state['residuals'][0]['attachment']['kind'] == 'no_breach'
    assert state['graph']['unresolved']
    assert all('shall not have breached' not in q for r in state['graph']['rules'] for q in r['source_quotes'])


def test_forged_anchor_and_conflicting_attachment_stay_rejected_or_residual():
    m, _ = material()
    code = production_code([software_oracle()])
    good = annotations(code, m['document'])[0]
    forged = {**good, 'start': good['start'] + 1}
    with pytest.raises(ValueError, match='quote differs'):
        annotations('def infer(document, query):\n    return ' + repr([forged]), m['document'])
    conflict = {**good, 'kind': 'permission'}
    state = apply('def infer(document, query):\n    return ' + repr([good, conflict]), m['document'], m['graph'])
    assert any(r['reason'] == 'ambiguous_attachment' for r in state['residuals'])
    assert state['graph']['unresolved']


def test_exact_finite_selection_and_unlearnable_bank():
    m, f = material()
    p = software_oracle()
    duplicate = deepcopy(p)
    duplicate['id'] = 'redundant_software_oracle'
    selected = select([p, duplicate], [m], [f])
    assert selected['accepted'] and len(selected['productions']) == 1
    assert selected['selection_trace'][0]['ids'] == []
    assert not selected['selection_trace'][0]['passed']
    wrong = {**p, 'kind': 'permission'}
    failed = select([wrong], [m], [f])
    assert not failed['accepted'] and failed['code'] is None


def test_observed_regex_repair_closes_only_outer_anchor():
    from reports.method_redesign_20261109.audit_contract_attachment_update import close_only_outer_anchor
    path = OLD.parent / 'contract_attachment_update_v1_20261110/ordinary_repair_learned.json'
    raw = json.loads(path.read_text())['value']['code']
    node = next(n for n in ast.parse(raw).body if isinstance(n, ast.Assign) and n.targets[0].id == 'NO_BREACH_POST')
    original = ast.literal_eval(node.value)
    fixed, changed = close_only_outer_anchor(original)
    assert changed and fixed == original + ')'
    assert re.compile(fixed).groupindex == {'anchor':1,'head':2,'condition':3,'behavior':4}
    assert close_only_outer_anchor(fixed) == (fixed, False)
    with pytest.raises((ValueError, re.error)):
        close_only_outer_anchor('(?P<anchor>(?P<head>unfinished')
