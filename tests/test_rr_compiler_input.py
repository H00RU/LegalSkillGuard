"""Complete original inputs survive prompt compaction; no label/model access."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.coverage import SourceLedger,digest
from legal_skill_guard.rr.source_inference import _compiler_request,predict_source
from legal_skill_guard.rr.source_program import compiler_prompt
from legal_skill_guard.rr.source_format import native_schema
from legal_skill_guard.rr.source_structure import SourceStructure,compact_contexts,inspect_source


def reach(key,graph):
    pending=[key];seen=set()
    while pending:
        item=pending.pop()
        if item not in seen:seen.add(item);pending.extend(graph[item])
    return seen


def test_every_original_TRAIN_source_line_and_context_closure_is_preserved():
    root=Path(__file__).resolve().parents[1]
    sources=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
    for source in sources:
        original=inspect_source(source);before=original.version
        system,user=compiler_prompt(source);payload=json.loads(user)
        assert 'public_task' not in payload
        units=payload['units'];assert len(units)==len(original.ledger.clauses)
        assert [u['id'] for u in units]==[c.id for c in original.ledger.clauses]
        graph={u['id']:u['context'] for u in units}
        full={c.id:c.context for c in original.ledger.clauses}
        for unit,clause in zip(units,original.ledger.clauses):
            assert unit['text']==original.ledger.text[clause.start:clause.end]
            assert reach(unit['id'],graph)==reach(unit['id'],full)
        assert original.version==before


def test_compaction_preserves_cyclic_contexts_instead_of_dropping_external_reachability():
    ledger=SourceLedger.from_text('a\nb\nc\nd')
    contexts=[('s1','s2'),('s0','s2'),('s3',),()]
    ledger.clauses=[replace(c,context=context) for c,context in zip(ledger.clauses,contexts)]
    structure=SourceStructure(ledger,{},(),{},{});reduced=compact_contexts(structure)
    original={c.id:c.context for c in ledger.clauses}
    assert all(reach(key,reduced)==reach(key,original) for key in original)


def test_prompt_menu_omits_source_identifiers_and_retains_every_available_pattern():
    root=Path(__file__).resolve().parents[1]
    source=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())['source']
    library=json.loads((root/'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B8.frozen.json').read_text())['content']
    before=digest(library);_,user=compiler_prompt(source,library);menu=json.loads(user)['available_learned_patterns']
    assert len(menu)==len(library['patterns']) and all(set(item)=={'pattern_hash','pattern'} for item in menu)
    assert digest(library)==before


def test_long_rejected_candidate_can_be_omitted_while_complete_source_and_specific_errors_stay():
    root=Path(__file__).resolve().parents[1]
    value=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    source,program=value['source'],value['canonical_program']
    def measured(messages,*,thinking):
        payload=json.loads(messages[1]['content'])
        return {'count':500 if payload['accepted_program_code'] is not None else 100}
    messages,_,action=_compiler_request(source,None,ARMS['M11'],program,{'type':'IRTypeError','message':'bad Boolean guard'},
        measured,{'context_tokens':300,'max_tokens':0},False)
    payload=json.loads(messages[1]['content'])
    assert payload['accepted_program_code'] is None and 'previous_candidate' not in payload
    assert payload['validation_feedback']['previous_error']['type']=='IRTypeError'
    assert len(payload['units'])==len(inspect_source(source).ledger.clauses)
    assert action['raw_candidate_preserved_in_prior_wire']


def test_source_too_large_is_recorded_without_a_physical_model_request_or_source_truncation():
    root=Path(__file__).resolve().parents[1]
    source=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())['source']
    def forbidden(*args,**kwargs):raise AssertionError('No generation can be dispatched')
    result=predict_source(source,arm='M11',library={'frozen':False,'patterns':[]},generate=forbidden,
        tokenize=lambda *args,**kwargs:{'count':1000000},request_config={'context_tokens':100,'max_tokens':0},
        thinking=False,partition='train',controlled_shortcut=False)
    assert result['model_calls']==0 and result['calls']==[]
    assert result['result']['program_status']=='request_preparation_unavailable'
    assert result['result']['answer'] is None


def test_actual_paid_wire_omission_is_fixed_in_messages_not_only_response_grammar():
    from legal_skill_guard.rr.interfaces import CONNECTORS
    from legal_skill_guard.rr.source_program import compile_source,program_schema
    from legal_skill_guard.rr.source_inference import _decode,native_fallback
    root=Path(__file__).resolve().parents[1]
    sources={s['key']:s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    records=json.loads((root/'tests/fixtures/rr_actual_method_prompt_c1.json').read_text())['records']
    assert len(records)==6
    for record in records:
        source=sources[record['source']]
        system,user=compiler_prompt(source);payload=json.loads(user);contract=payload['language_contract']
        wire=program_schema(source)
        expected={item['properties']['type']['enum'][0]:item['properties']['value']
                  for item in wire['$defs']['binding']['anyOf']}
        assert contract['binding_value_schemas']==expected
        assert {s['op'] for s in contract['connector_syntax']['signatures']}==CONNECTORS
        assert contract['query_result_schema']==native_fallback(source)[1]['properties']['answer']
        assert 'language_contract' in system
        # Better instructions do not silently repair or accept the old errors.
        with pytest.raises(Exception):compile_source(source,_decode(record['content']))


def test_OE_actual_wrong_native_label_is_rejected_by_the_now_visible_task_contract():
    import jsonschema
    root=Path(__file__).resolve().parents[1]
    records=json.loads((root/'tests/fixtures/rr_actual_method_prompt_c1.json').read_text())['records']
    program=json.loads(records[1]['content']);wrong=program['query']['args'][1]
    assert wrong=='Entailment'
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(wrong,native_schema('OpenExempt'))
    jsonschema.validate({'EC':{'public asset':[]},'EV':{'public asset':[]}},native_schema('OpenExempt'))


def test_native_contract_all_five_datasets_has_only_public_format_constraints():
    from legal_skill_guard.rr.source_inference import native_fallback
    root=Path(__file__).resolve().parents[1]
    sources=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
    seen=set()
    for source in sources:
        _,user=compiler_prompt(source);contract=json.loads(user)['language_contract']
        assert contract['query_result_schema']==native_fallback(source)[1]['properties']['answer']
        seen.add(source['dataset'])
    assert len(seen)==5
