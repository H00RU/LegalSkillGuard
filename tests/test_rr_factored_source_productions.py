"""Regression on actual paid productions, not an invented legal benchmark."""
import json
from pathlib import Path
import re

import pytest

from legal_skill_guard.rr.factored_source_productions import factor, named_body, recombine
from legal_skill_guard.rr.contract_attachment_update import annotations, production_code

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'artifacts/rr_method_redesign_20261109/contract_attachment_update_v1_20261110'


def paid():
    return json.loads((OLD / 'minimum_attachment_learned.json').read_text())['update']['productions']


def test_actual_capture_factorization_preserves_source_records():
    ps = paid()
    lib = factor(ps)
    combos = recombine(lib)
    observed = [c['production'] for c in combos if c['observed_combination']]
    docs = json.loads((OLD / 'training_seal.json').read_text())['documents']
    for m in docs:
        assert annotations(production_code(ps), m['document']) == annotations(production_code(observed), m['document'])
    assert len(combos) == 8 and len(observed) == 2


def test_nested_escaped_and_class_parentheses_do_not_corrupt_regex():
    p = r'(?P<head>(?:is|are)\s+prohibited\(literal\)[()]) (?P<behavior>disclos\w*)'
    a, b = named_body(p, 'head')
    assert p[a:b] == r'(?:is|are)\s+prohibited\(literal\)[()]'
    re.compile(p)
    with pytest.raises(ValueError):
        named_body(r'(?P<head>(?:is|are)', 'head')


def test_recombinations_have_only_acquired_semantic_and_lexical_parts():
    ps = paid()
    lib = factor(ps)
    for c in recombine(lib):
        p = c['production']
        re.compile(p['pattern'])
        assert p['kind'] == lib['heads'][c['head_id']]['kind']
        assert p['action'] == lib['actions'][c['action_id']]['action']
        assert c['recombined_hypothesis_not_semantic_adaptation']
        assert set(c['source_production_origins']['head']) <= {p['id'] for p in ps}
    assert not lib['new_surface_lexemes_supplied'] and not lib['new_semantics_supplied']
