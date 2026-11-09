"""Local source-condition interface controls, not learned/native successes."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from experiments.rr_v2_legal_primitive_chain import HEAD,PRIMITIVES,c6_software_checks,reference_f68,schemas,normalize_obligations
from legal_skill_guard.rr.semantic_contracts import ContractError
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109'


def control():
    source=next(t['rules'] for t in json.loads((OLD/'seal.json').read_text())['targets'] if t['id']=='sara63_basic_deduction')
    quote='a married individual filing a separate return where either spouse itemizes deductions'
    def atom(p,args):return {'predicate':p,'arguments':args,'positive':True}
    program={'predicates':[{'name':k,'roles':v['roles'],'meaning':v['meaning'],'functional':False} for k,v in PRIMITIVES.items()]+[
        {'name':HEAD,'roles':['subject','year'],'meaning':'local applicability','functional':False}],
        'rules':[],'priorities':[],'unresolved':[]}
    for item in ('?P','?S'):
        program['rules'].append({'id':'r'+item[1:],'head':atom(HEAD,['?P','?Y']),
            'body':[atom('married',['?P','?S','?Y']),atom('separate_return',['?P','?Y']),atom('itemized_deduction',[item,'?Y'])],
            'different':[],'guard_quote':quote,'quote':quote,'authority':'§63(c)(6)(A)'})
    return program,source


def test_actual_source_interface_supports_either_spouse_without_defaulting_absence_false():
    p,s=control();out=c6_software_checks(p,s)
    assert len(out['positive_witness_boundary_checks'])==16
    assert sum(r['answer']=='Entailment' for r in out['positive_witness_boundary_checks'])==3


def test_missing_conjunction_is_detected_beyond_a_single_positive_case():
    p,s=control()
    for r in p['rules']:r['body']=[a for a in r['body'] if a['predicate']!='separate_return']
    with pytest.raises(ContractError,match='truth-table mismatch'):c6_software_checks(p,s)


def test_target_as_input_is_rejected():
    p,s=control();p['rules'][0]['head']['predicate']='itemized_deduction'
    with pytest.raises(ContractError,match='derived positive'):c6_software_checks(p,s)


def test_structured_schemas_do_not_alias_year_enum_into_quotes_or_expressions():
    source,reader=schemas(['literal source sentence.'])
    assert strict_output_schema_issues(source)==[] and strict_output_schema_issues(reader)==[]
    f=source['properties']['f68_module']['properties']
    assert f['inputs']['items']['properties']['name']['enum']==['year']
    assert f['expression']=={'type':'string'} and f['rule_quote']=={'type':'string'}


def test_temporal_reference_is_built_from_the_original_source_dates():
    s=next(t['rules'] for t in json.loads((OLD/'seal.json').read_text())['targets'] if t['id']=='sara68_f_activation')
    assert reference_f68(s)=='year > 2017 and year < 2026'


def test_actual_output_dependent_postconditions_are_reoriented_without_changing_semantics():
    path=ROOT/'artifacts/rr_method_redesign_20261109/legal_primitive_chain_v1_20261110/source.json'
    old=json.loads(path.read_text())['value']['f68_module'];adapted,proof=normalize_obligations(old)
    assert adapted['expression']==old['expression']
    assert all(r['original_condition_reachable_with_program'] for r in proof['checks'])
    assert all(r['implication_normalization_equivalent_for_all_inputs_and_results'] for r in proof['checks'])
    bad=deepcopy(old);bad['expression']='False'
    with pytest.raises(ContractError,match='vacuous'):normalize_obligations(bad)
