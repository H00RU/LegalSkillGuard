"""Current production dispatcher with explicit offline wire responses."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.source_inference import predict_source
from legal_skill_guard.rr.source_code import encode_compiler_program
from legal_skill_guard.rr.wire_validation import validate_wire


def actual():
    root=Path(__file__).resolve().parents[1]
    value=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    return value['source'],value['canonical_program']


def run(source,generate,*,arm='M11',partition='dev',library=None):
    return predict_source(source,arm=arm,partition=partition,library=library or {'frozen':True,'patterns':[]},
        generate=generate,tokenize=lambda messages,thinking:{'count':len(json.dumps(messages,ensure_ascii=False))},
        request_config={'context_tokens':100000,'max_tokens':8192},thinking=False)


def wire(value):return {'content':json.dumps(value),'request_hash':digest(value),'usage':{
    'prompt_tokens':10,'completion_tokens':20},'elapsed_seconds':.1,'cache_hit':False}


def test_actual_A_dispatch_selects_facts_and_uses_two_calls_without_fallback():
    source,program=actual();calls=[]
    def generate(messages,*,purpose,step,schema):
        calls.append((purpose,messages))
        value=encode_compiler_program(program) if step==0 else {'observations':[{'name':'b_legally_separated','value':True,
            'evidence':'Alice and Bob were legally separated under a decree of divorce on September 16th, 2017.'}]}
        validate_wire(value,schema);return wire(value)
    result=run(source,generate)
    assert result['call_purposes']==['parse','repair'] and len(calls)==2
    assert result['result']['A_main_path_executed'] and not result['result']['fallback_used']
    assert result['translation_actions'][0]['joint_separation_complete']
    assert result['translation_actions'][0]['selected']==['s10']
    assert result['observation_rows'][0]['value'] is True


def test_full_control_does_not_claim_core_success_from_a_correct_native_fallback():
    source,program=actual();calls=[]
    def generate(messages,*,purpose,step,schema):
        calls.append(purpose)
        if step==0:value=encode_compiler_program(program)
        elif step==1:
            request=json.loads(messages[1]['content'])
            value={'program':encode_compiler_program(program),'factual_observations':[{'name':r['name'],'value':None,'evidence':''}
                for r in request['requested_factual_observations']]}
        else:value={'answer':'Entailment'}
        validate_wire(value,schema);return wire(value)
    result=run(source,generate,arm='M00')
    assert calls==['parse','repair','fallback']
    assert result['result']['answer']=='Entailment' and result['result']['fallback_used']
    assert not result['result']['A_main_path_executed'] and not result['result']['B_main_path_executed']


def test_training_has_two_joint_attempts_and_no_third_native_request():
    source,_=actual();root=Path(__file__).resolve().parents[1]
    bad=json.loads((root/'tests/fixtures/rr_actual_executor_source_v1.json').read_text());calls=[]
    def generate(messages,*,purpose,step,schema):calls.append(messages);return wire(bad)
    result=run(source,generate,partition='train')
    assert len(calls)==2 and result['model_calls']==2
    assert result['result']['answer'] is None and not result['result']['fallback_used']
    assert calls[0]!=calls[1]


def test_pending_physical_request_is_not_swallowed_as_an_ordinary_model_error():
    source,_=actual();calls=[]
    def generate(*args,**kwargs):calls.append(kwargs);raise BudgetError('Existing reserved request must be reconciled')
    with pytest.raises(BudgetError):run(source,generate)
    assert len(calls)==1


def test_test_partition_is_rejected_before_dispatch():
    source,_=actual()
    with pytest.raises(ValueError,match='TRAIN/DEV'):run(source,lambda *a,**k:None,partition='test')


def test_known_public_grammar_keeps_learned_graph_and_predefined_A_flags_distinct():
    root=Path(__file__).resolve().parents[1]
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
        if s['key']=='ProofWriter_OWA_depth5:f39b4cd5a6faf7e199c568e2487db5b6b0e27fadefef4f319d42655e4fe04d94')
    library=json.loads((root/'artifacts/rr_v2_formal_build_20261106/run_citation_fix/B1.frozen.json').read_text())['content']
    before=digest(library)
    def forbidden(*args,**kwargs):raise AssertionError('No model needed for the supported frozen public grammar')
    result=run(source,forbidden,library=library)
    assert result['model_calls']==0 and result['result']['certificate_status']=='completion_stable'
    assert not result['result']['A_main_path_executed'] and result['result']['B_main_path_executed']
    assert result['result']['execution']['pattern_uses'] and digest(library)==before


def test_interrupted_source_resumes_the_exact_followup_without_regenerating_paid_initial_output(tmp_path):
    source,program=actual();first=[];second=[]
    def interrupted(messages,*,purpose,step,schema):
        first.append(step)
        if step==1:raise SystemExit('offline interruption before second generation')
        return wire(encode_compiler_program(program))
    kwargs={'source':source,'arm':'M11','partition':'train','library':{'frozen':False,'patterns':[]},
        'tokenize':lambda messages,thinking:{'count':len(json.dumps(messages,ensure_ascii=False))},
        'request_config':{'context_tokens':100000,'max_tokens':8192},'thinking':False,'journal':tmp_path/'journal'}
    with pytest.raises(SystemExit):predict_source(generate=interrupted,**kwargs)
    assert first==[0,1]
    request=json.loads((tmp_path/'journal/request1.json').read_text())
    def resume(messages,*,purpose,step,schema):
        second.append(step);assert step==1
        assert json.dumps({'messages':messages,'schema':schema},ensure_ascii=False)==request['dispatch_json']
        return wire({'observations':[{'name':'b_legally_separated','value':True,
            'evidence':'Alice and Bob were legally separated under a decree of divorce on September 16th, 2017.'}]})
    result=predict_source(generate=resume,**kwargs)
    assert second==[1] and result['result']['A_main_path_executed']
    def forbidden(*args,**kw):raise AssertionError('Completed source cannot dispatch again')
    assert predict_source(generate=forbidden,**kwargs)==result


@pytest.mark.parametrize('content',['NaN','Infinity','1e309','{"bindings":[],"bindings":[]}'])
def test_nonfinite_and_duplicate_json_values_never_enter_the_request_journal(content):
    from legal_skill_guard.rr.source_inference import _decode
    with pytest.raises((ValueError,OverflowError)):_decode(content)
