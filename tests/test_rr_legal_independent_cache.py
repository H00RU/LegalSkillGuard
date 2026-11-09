import json
from pathlib import Path
import pytest
from experiments.rr_v2_legal_independent_cache import check_code, execute_code, check_fixtures

ROOT = Path(__file__).resolve().parents[1]


def test_ordinary_collection_function_executes_without_requiring_a_rule_format():
    code = "def law_cache(facts, query):\n    return {'answer': None, 'n': len(facts)}\n"
    assert execute_code(code, [], {}, []) == {'answer': None, 'n': 0}


@pytest.mark.parametrize('code', [
    "import os\ndef law_cache(facts,query):\n    return {'answer':None}",
    "def law_cache(facts,query):\n    return facts.__class__",
    "def law_cache(facts,query):\n    return open('anything')",
])
def test_no_environment_or_file_capability_is_exposed(code):
    with pytest.raises(ValueError): check_code(code)


def test_a_blanket_negative_is_rejected_by_the_source_checks():
    checked = check_fixtures("def law_cache(facts, query):\n    return {'answer': 'Contradiction'}\n", [])
    row = next(r for r in checked['rows'] if r['name'] == 'absence_is_not_false')
    assert not row['passed']


def test_public_solver_is_usable_by_the_independent_control():
    base = ROOT / 'artifacts/rr_method_redesign_20261109'
    program = json.loads((base / 'legal_library_runtime_v1_20261109/frozen_library.json').read_text())['program']
    policies = json.loads((base / 'legal_relations_exceptions_native_v1_20261109/seal.json').read_text())['policies']
    source63 = next(r['public']['rules'] for r in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
                     if r['dataset'] == 'SARA_v2_Binary' and r['public']['rules'].startswith('§63.'))
    code = 'def law_cache(facts, query):\n    return solve(' + repr(program) + ', facts, query)\n'
    out = check_fixtures(code, [p['rules'] for p in policies] + [source63])
    assert out['all_passed'], out
