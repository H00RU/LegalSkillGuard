"""Actual learned-library reuse; synthetic applications remain uncertified controls."""
from copy import deepcopy
import json
from pathlib import Path
import re
import pytest
from jsonschema import ValidationError

from legal_skill_guard.rr.airline_application import matching_application
from legal_skill_guard.rr.rule_templates import matching_rule_template,instance_request,instantiate_rule_template
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.coverage import Unsupported,digest
from legal_skill_guard.rr.pal_frontend import parse_pal
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.grounding import _numbers

ROOT=Path(__file__).resolve().parents[1]


def test_actual_complimentary_bag_ordinals_are_literals_without_factual_bag_numbers():
    assert _numbers('1st - 5th bags free of charge')=={1,5}
    assert _numbers('1st 2nd 3rd 4th 11th 12th 13th 23rd')=={1,2,3,4,11,12,13,23}
    assert not _numbers('11st 2th 3nd 4rd')


def material():
    path=ROOT/'artifacts/rr_method_runtime_20261107/reference_pal_airline7_v14_20261108/seal.json'
    seal=json.loads(path.read_text());source=seal['source'];library=seal['config']['library']
    match=matching_rule_template(source,library);structure=inspect_source(source)
    fact={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses if structure.roles[c.id]['role']=='fact'}
    ticket=next((sid,text) for sid,text in fact.items() if 'flight ticket is $' in text)
    price=re.search(r'\$([0-9]+)',ticket[1])[1]
    # This tests composition only. No totals, source completeness or model
    # success are invented: omitted current rules stay unknown and block A.
    value={'witness_bindings':{'w0':{'entity_source':'s156','entity':fact['s156']}},
        'code':f'current_ticket = {price} # {ticket[0]}\ncabin = "Premium Economy" # s155\nquery = current_ticket + number_field(first_bag_other_south_america_fees(), cabin)'}
    return source,library,match,value


def test_actual_70_learned_definitions_are_reused_without_old_facts_helpers_or_case_rules():
    source,library,match,value=material();before=digest(library)
    assert match['kind']=='airline_case_program' and len(match['program']['clauses'])==70
    assert match['program']['bindings']==[] and match['program']['nodes']==[]
    assert {c['name'] for c in match['case_clauses']}=={'current_bag_linear_dimensions','applicable_excess_bag_fees'}
    assert 's116' in match['untranslated_units'] and 's125' in match['untranslated_units']
    program,compiled,audit=instantiate_rule_template(source,match,value,library=library)
    assert program['scopes']==match['program']['scopes']
    assert program['clauses']==match['program']['clauses']
    assert {b['name'] for b in program['bindings']}=={'current_ticket','cabin'}
    by_name={o['name']:o for o in program['observations']}
    assert by_name['b_first_other_south_america']['entity']=='Emily'
    assert by_name['b_small_storage_fit']['entity']==by_name['b_small_sizer_fit']['entity']==value['witness_bindings']['w0']['entity']
    result=assess_source(compiled)
    assert result['answer'] is None and result['certificate'] is None
    assert set(match['untranslated_units'])<=set(result['unknown_scope'])
    assert not audit['prior_facts_case_helpers_and_query_reused'] and not audit['missing_rules_or_factual_truth_filled']
    assert digest(library)==before


def test_statute_reuse_and_earlier_source_rules_remain_exact():
    source,library,match,value=material()
    changed=deepcopy(source);changed['public']['rules']=changed['public']['rules'].replace('$40','$41',1)
    changed['content_hash']=digest(changed['public'])
    assert matching_application(changed,library) is None
    item=match['template']
    with pytest.raises(ValueError,match='own current application'):matching_application(item['source'],library)


@pytest.mark.parametrize('kind',['stale_witness','ticket_as_item','overwrite_rule','unbound_old_fact','answer_literal'])
def test_case_application_rejects_stale_or_unlinked_data_and_immutable_rule_changes(kind):
    source,library,match,value=material();value=deepcopy(value)
    if kind=='stale_witness':value['witness_bindings']['w0']['entity']=match['witnesses'][0]['old_entity']
    elif kind=='ticket_as_item':value['witness_bindings']['w0']['entity_source']='s167'
    elif kind=='overwrite_rule':value['code']+='\nfirst_bag_other_south_america_fees = 1 # s155'
    elif kind=='unbound_old_fact':value['code']='query = bag5_length + number_field(first_bag_other_south_america_fees(), "Premium Economy")'
    else:value['code']='query = 999999'
    with pytest.raises((Unsupported,ValueError,ValidationError,TypeError,KeyError)):
        instantiate_rule_template(source,match,value,library=library)


def test_only_immutable_library_functions_can_be_called_from_case_fragments():
    _,_,_,value=material()
    with pytest.raises(Unsupported):parse_pal(value['code'])
    with pytest.raises(Unsupported):parse_pal('query = unknown_tool()',external_functions=['first_bag_other_south_america_fees'])


def test_current_case_prompt_does_not_ask_to_regenerate_known_rules_and_controls_share_them():
    source,library,match,_=material();messages,schema=instance_request(source,match)
    payload=json.loads(messages[1]['content'])
    assert 'known_rule_library_code' in payload and len(payload['CURRENT']['untranslated_source_units'])==25
    assert 'Do not regenerate' in messages[0]['content']
    assert payload['CURRENT']['facts'][0]['text'].startswith('Emily is a Premium Economy')
    masked=deepcopy(library);masked['patterns']=[]
    other,_=instance_request(source,matching_rule_template(source,masked))
    masked_payload=json.loads(other[1]['content'])
    assert payload['known_rule_library_code']==masked_payload['known_rule_library_code']
    assert payload['earlier_TRAIN_case_application']==masked_payload['earlier_TRAIN_case_application']
