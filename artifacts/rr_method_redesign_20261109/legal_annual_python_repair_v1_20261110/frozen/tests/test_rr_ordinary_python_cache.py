import pytest
from legal_skill_guard.rr.ordinary_python_cache import execute,validate

REAL_CODE="""law_cache = lambda facts, query: sum(min(7000, sum(p['amount'] for p in group)) for group in (group_by(facts, ['payer', 'payee', 'payment_year']) if query == 'component3306_b_1' else []))

def group_by(data, keys):
    groups = {}
    for item in data:
        key = tuple(item[k] for k in keys)
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
    return groups
"""


def row(amount,payer='A',payee='B',year=2017):return {'payer':payer,'payee':payee,'payment_year':year,'amount':amount}


FIXTURE_CORRECT=REAL_CODE.replace('for group in (group_by(', 'for group in (group_by(').replace("['payer', 'payee', 'payment_year']) if query", "['payer', 'payee', 'payment_year']).values() if query")


def test_actual_raw_programme_failure_is_preserved():
    with pytest.raises(ValueError,match='TypeError'):
        execute(REAL_CODE,[row(6771)],'component3306_b_1')


def test_explicit_software_fixture_and_annual_scope():
    assert execute(FIXTURE_CORRECT,[row(6771),row(6954)],'component3306_b_1')==7000
    assert execute(FIXTURE_CORRECT,[row(7000),row(7000,payer='C')],'component3306_b_1')==14000
    assert execute(FIXTURE_CORRECT,[row(7000),row(7000,year=2018)],'component3306_b_1')==14000


def test_input_dispatch_contract_is_explicit():
    assert execute(FIXTURE_CORRECT,[row(1000)],'component3306_b_1')==1000
    assert execute(FIXTURE_CORRECT,[row(1000)],{'component':'3306_b_1'})==0


def test_ordinary_def_style_still_supported():
    assert execute('def law_cache(facts, query):\n    return sum(facts)',[1,2],None)==3


@pytest.mark.parametrize('code',[
 'import os\ndef law_cache(facts, query):\n    return 1',
 'print(1)\ndef law_cache(facts, query):\n    return 1',
 'def law_cache(facts, query):\n    return __import__("os")',
 'def law_cache(facts, query):\n    return facts.__class__',
 'def law_cache(facts, query=None):\n    return 1'])
def test_execution_restrictions_are_preserved(code):
    with pytest.raises(ValueError):validate(code)
