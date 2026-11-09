from copy import deepcopy
import json
from pathlib import Path
import pytest
from experiments.rr_v2_legal_cache_review import extract_literals, apply_review

ROOT = Path(__file__).resolve().parents[1]


def original():
    return json.loads((ROOT/'artifacts/rr_method_redesign_20261109/legal_independent_cache_v1_20261110/source.json').read_text())['value']['code']


def test_identity_review_preserves_every_program_literal_and_execution_statement():
    code = original(); before = extract_literals(code)[1]
    after, evidence = apply_review(code, {'rule_updates': [], 'new_rules': [], 'priorities': before['priorities']})
    assert extract_literals(after)[1] == before
    assert evidence['predicate_signatures_unresolved_and_execution_function_unchanged']


def test_undeclared_rule_edit_is_rejected():
    code = original(); before = extract_literals(code)[1]
    bad = deepcopy(before['rules'][0]); bad['id'] = 'not_an_existing_rule'
    with pytest.raises(ValueError, match='existing rule'):
        apply_review(code, {'rule_updates': [bad], 'new_rules': [], 'priorities': before['priorities']})
