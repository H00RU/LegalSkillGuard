"""Actual learned-library reuse; synthetic applications remain uncertified controls."""
from copy import deepcopy
import json
from pathlib import Path
import re
import pytest
from jsonschema import ValidationError

from legal_skill_guard.rr.airline_application import matching_application,literal_case_bindings
from legal_skill_guard.rr.rule_templates import matching_rule_template,instance_request,instantiate_rule_template
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.coverage import Unsupported,digest
from legal_skill_guard.rr.pal_frontend import parse_pal
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.grounding import _numbers
from legal_skill_guard.rr.compiler_templates import validate_template

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
    value={'current_item_source':'s156','program_lines':['query = ticket_price + number_field(first_bag_other_south_america_fees(), cabin)']}
    return source,library,match,value


def test_actual_70_learned_definitions_are_reused_without_old_facts_helpers_or_case_rules():
    source,library,match,value=material();before=digest(library)
    assert match['kind']=='airline_case_program' and len(match['program']['clauses'])==70
    assert len(match['program']['bindings'])==49 and match['program']['nodes']==[]
    assert {c['name'] for c in match['case_clauses']}=={'current_bag_linear_dimensions','applicable_excess_bag_fees'}
    assert 's116' in match['untranslated_units'] and 's125' in match['untranslated_units']
    program,compiled,audit=instantiate_rule_template(source,match,value,library=library)
    assert program['scopes']==match['program']['scopes']
    assert program['clauses']==match['program']['clauses']
    assert program['bindings']==match['program']['bindings']
    values={b['name']:b['value'] for b in program['bindings']}
    assert values['ticket_price']==875 and values['bag1_length']==21 and values['traveler']=='Emily'
    by_name={o['name']:o for o in program['observations']}
    assert by_name['b_first_other_south_america']['entity']=='Emily'
    assert by_name['b_small_storage_fit']['entity']==by_name['b_small_sizer_fit']['entity']==audit['current_item_observations'][0]['entity']
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


def test_literal_input_extraction_covers_exact_original_train_format_without_labels():
    packet=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
    sources=[s for s in packet if s['dataset']=='RuleArena_Airline']
    assert len(sources)==24
    for source in sources:
        structure=inspect_source(source);bindings=literal_case_bindings(structure)
        facts={c.id for c in structure.ledger.clauses if structure.roles[c.id]['role']=='fact'}
        assert {u for b in bindings for u in b['sources']}==facts
        assert len({b['name'] for b in bindings})==len(bindings)
    _,_,match,_=material()
    assert {b['name']:b for b in match['previous_input_bindings']}=={b['name']:b for b in validate_template(match['template'])['program']['bindings']}


@pytest.mark.parametrize('kind',['missing_selector','multiple_items','passenger_as_item','ticket_as_item','overwrite_rule','overwrite_literal','overwrite_observation','unbound_old_helper','answer_literal'])
def test_case_application_rejects_ambiguous_inputs_overwrites_or_unlinked_outputs(kind):
    source,library,match,value=material();value=deepcopy(value)
    if kind=='missing_selector':value.pop('current_item_source')
    elif kind=='multiple_items':value['current_item_source']=['s156','s157']
    elif kind=='passenger_as_item':value['current_item_source']='s155'
    elif kind=='ticket_as_item':value['current_item_source']='s167'
    elif kind=='overwrite_rule':value['program_lines'].append('first_bag_other_south_america_fees = 1 # s155')
    elif kind=='overwrite_literal':value['program_lines'].insert(0,'ticket_price = 563 # s167')
    elif kind=='overwrite_observation':value['program_lines'].insert(0,'b_small_storage_fit = True # s156')
    elif kind=='unbound_old_helper':value['program_lines']=['query = '+match['case_example']['nodes'][0]['name']+' + number_field(first_bag_other_south_america_fees(), cabin)']
    else:value['program_lines']=['query = 999999']
    with pytest.raises((Unsupported,ValueError,ValidationError,TypeError,KeyError)):
        instantiate_rule_template(source,match,value,library=library)


def test_only_immutable_library_functions_can_be_called_from_case_fragments():
    _,_,_,value=material()
    with pytest.raises(Unsupported):parse_pal('\n'.join(value['program_lines']))
    with pytest.raises(Unsupported):parse_pal('query = unknown_tool()',external_functions=['first_bag_other_south_america_fees'])


def test_current_case_prompt_does_not_ask_to_regenerate_known_rules_and_controls_share_them():
    source,library,match,_=material();messages,schema=instance_request(source,match)
    payload=json.loads(messages[1]['content'])
    # Eight empty Markdown alignment rows are formatting, not missing rules.
    assert 'known_rule_library_code' in payload and len(payload['CURRENT']['untranslated_source_units'])==17
    assert 'Do not regenerate' in messages[0]['content']
    assert 'witness_parameters' not in payload and len(payload['fixed_item_observations'])==2
    assert set(schema['properties'])=={'current_item_source','program_lines'}
    from legal_skill_guard.rr.wire_validation import validate_wire
    for sid in match['item_sources']:
        validate_wire({'current_item_source':sid,'program_lines':['query = ticket_price']},schema)
    for sid in ['s155','s167','s156\n']:
        with pytest.raises(ValidationError):validate_wire({'current_item_source':sid,'program_lines':['query = ticket_price']},schema)
    assert all(o['entity'] not in payload['known_rule_library_code'] for o in match['item_observations'])
    assert payload['CURRENT']['facts'][0]['text'].startswith('Emily is a Premium Economy')
    masked=deepcopy(library);masked['patterns']=[]
    other,_=instance_request(source,matching_rule_template(source,masked))
    masked_payload=json.loads(other[1]['content'])
    assert payload['known_rule_library_code']==masked_payload['known_rule_library_code']
    assert payload['earlier_TRAIN_case_application']==masked_payload['earlier_TRAIN_case_application']


def test_complete_real_example_query_preserves_every_exact_sum_term():
    from legal_skill_guard.rr.airline_application import complete_case_example
    _,_,match,_=material()
    functions=[row['name'] for field in ('scopes','clauses') for row in match['program'][field]]
    parsed=parse_pal('\n'.join(complete_case_example(match)),external_functions=functions)
    def terms(expression):
        if isinstance(expression,dict) and expression.get('op')=='add':return [x for a in expression['args'] for x in terms(a)]
        return [expression]
    assert parsed['query']['args']==terms(match['case_example']['query'])
    assert all(parsed[k]==match['case_example'][k] for k in ('bindings','observations','rule_residuals','nodes','scopes','clauses'))
    assert not any(isinstance(a,dict) and a.get('op')=='add' for a in parsed['query']['args'])


def test_identical_current_literal_redeclaration_is_idempotent_but_does_not_fill_a_query():
    source,library,match,value=material()
    value['program_lines'].insert(0,'ticket_price = 875 # s167')
    program,compiled,audit=instantiate_rule_template(source,match,value,library=library)
    assert program['bindings']==match['program']['bindings']
    assert [b['name'] for b in audit['identical_current_literal_redeclarations_removed']]==['ticket_price']
    assert assess_source(compiled)['certificate'] is None
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_lines_airline7_v19_20261108'
    paid=json.loads((stage/'calls'/digest(stage.name+':parse:0')/'result.json').read_text())
    raw=json.loads(paid['content']);code='\n'.join(raw['program_lines'])
    facts=parse_pal(code,require_query=False)['bindings']
    assert {b['name']:b for b in facts}=={b['name']:b for b in match['program']['bindings']}
    with pytest.raises(Unsupported,match='explicit query'):parse_pal(code)
