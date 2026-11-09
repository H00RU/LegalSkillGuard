import pytest
from legal_skill_guard.rr.python_scalar_module import compile_function
from legal_skill_guard.rr.semantic_contracts import ContractError,evaluate


def test_ordinary_assignments_branch_updates_and_early_returns_keep_python_meaning():
    code='''def amount(base: int, special: bool, blocked: bool) -> int:
    value = base
    if special:
        value *= 2
    if blocked:
        return 0
    return max(0, value)
'''
    signature={'base':'integer','special':'boolean','blocked':'boolean'}
    out=compile_function(code,signature)
    assert evaluate(out['expression'],signature,{'base':7,'special':True,'blocked':False})==14
    assert evaluate(out['expression'],signature,{'base':7,'special':True,'blocked':True})==0
    assert evaluate(out['expression'],signature,{'base':-7,'special':False,'blocked':False})==0


def test_nested_conditional_returns_do_not_run_a_returned_branch_continuation():
    code='''def choose(x: int, first: bool, second: bool) -> int:
    if first:
        if second:
            return x + 1
        else:
            return x + 2
    return x - 1
'''
    signature={'x':'integer','first':'boolean','second':'boolean'}
    out=compile_function(code,signature)
    assert evaluate(out['expression'],signature,{'x':10,'first':True,'second':False})==12
    assert evaluate(out['expression'],signature,{'x':10,'first':False,'second':True})==9


def test_unbound_branch_defaulted_input_and_foreign_effects_stay_rejected():
    bad=['def f(x: int, c: bool) -> int:\n    if c:\n        a = x\n    return a',
         'def f(x: int, c: bool = False) -> int:\n    return x',
         'import os\ndef f(x: int, c: bool) -> int:\n    return x',
         'def f(x: int, c: bool) -> int:\n    return eval("x")',
         'def f(x: int, c: bool) -> int:\n    return __import__("os").system("echo bad")']
    for code in bad:
        with pytest.raises(ContractError):compile_function(code,{'x':'integer','c':'boolean'})


def test_pure_function_fence_is_removed_without_fixing_body_or_types():
    out=compile_function('```python\ndef f(x: int) -> int:\n    return x * 2\n```',{'x':'integer'})
    assert evaluate(out['expression'],out['signature'],{'x':3})==6
    with pytest.raises(ContractError):compile_function('def f(x: bool) -> int:\n    return x',{'x':'integer'})
