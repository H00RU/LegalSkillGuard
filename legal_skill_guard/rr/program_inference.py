"""Compact, ledger-dispatched TRAIN/DEV inference for the six original arms.

Logic atoms and PAL programs share the existing completion, scope, connector,
resource and native-output checks. Teacher material is supplied in the frozen
library; this module has no labels, teacher, oracle or TEST entry point.
"""
from copy import deepcopy
import json
from pathlib import Path
import time
from jsonschema import ValidationError

from .atom_frontend import atom_prompt,atom_schema,decode_atom_response
from .checkpoint import immutable_json
from .controls import ARMS,PredictionBudget
from .coverage import Unsupported,digest
from .example_synthesis import ordinary_horn_prediction
from .ledger import BudgetError
from .model_horn import parse_model_horn,assess_model_horn
from .pal_frontend import pal_prompt,pal_schema,lower_pal
from .rule_templates import matching_rule_template,instance_request,instantiate_rule_template
from .source_execution import assess_source,prepare_followup,accept_followup
from .source_inference import _decode,native_fallback,controlled_prediction
from .source_interfaces import check_source_examples
from .source_program import compile_source
from .source_validation import validation_feedback,incomplete_feedback
from .wire_validation import validate_wire


FRONTEND='source_aligned_atoms_and_PAL_v1'


def predict_source(source,*,arm,library,generate,tokenize,request_config,thinking,
                   partition,example_model=None,controlled_shortcut=True,journal=None):
    if arm not in ARMS or partition not in {'train','dev'}:raise ValueError('Fixed TRAIN/DEV inference only')
    if partition=='train' and arm!='M11':raise ValueError('One common TRAIN acquisition')
    if partition=='dev' and not library.get('frozen'):raise ValueError('DEV requires the frozen library')
    if arm=='MB' and example_model is None:raise ValueError('MB needs the same-material example model')
    if thinking is not False:raise ValueError('The original executor OFF selection is locked')
    before=digest(library);example_before=digest(example_model);profile=ARMS[arm]
    active=deepcopy(library)
    if profile.interface!='collision_refined':active['patterns']=[]
    logic=source['dataset']=='ProofWriter_OWA_depth5'
    match=matching_rule_template(source,active) if not logic else None
    history=[];calls=[];actions=[];observed={};observation_rows=[];program=None;logic_code=None;compiled=None
    budget=PredictionBudget();remaining=5.0;feedback=None
    result={'answer':None,'certificate_status':'translation_unresolved','program_status':'not_parsed',
        'structural_pass':False,'fallback_used':False,'A_main_path_executed':False,'B_main_path_executed':False}
    journal=Path(journal) if journal is not None else None
    def save(name,value):
        if journal is not None:immutable_json(journal/name,value)
    save('context.json',{'source':digest(source),'arm':arm,'library':before,'examples':example_before,
        'thinking':thinking,'partition':partition,'request_config':request_config,
        'controlled_shortcut':controlled_shortcut,'frontend':FRONTEND})
    if journal is not None and (journal/'outcome.json').exists():return json.loads((journal/'outcome.json').read_text())
    start=0
    if journal is not None:
        for step in range(2):
            path=journal/('state'+str(step)+'.json')
            if not path.exists():break
            state=json.loads(json.loads(path.read_text())['state_json']);start=step+1
            history,calls,actions=state['history'],state['calls'],state['actions']
            observed,observation_rows,program=state['observed'],state['observation_rows'],state['program']
            logic_code=state['logic_code'];result=state['result'];feedback=state['feedback'];remaining=state['remaining']
            budget.calls=list(state['budget_calls'])
            if state['compiled_valid']:compiled=parse_model_horn(source,logic_code) if logic else compile_source(source,program,library=active)
            if state['route_requires_change']:start=2;break
    for step in range(start,2):
        if compiled is not None and result['certificate_status']=='completion_stable':break
        started=time.monotonic();prepared=None;instantiation=None;wire=None;adaptations=[]
        try:
            request_path=journal/('request'+str(step)+'.json') if journal is not None else None
            if request_path is not None and request_path.exists():
                request=json.loads(request_path.read_text())
                if request['parent_hash']!=digest([program,logic_code]) or request['observed_hash']!=digest(observed):raise ValueError('Saved compiler request parent changed')
                dispatch=json.loads(request['dispatch_json'])
                messages,schema,prepared=dispatch['messages'],dispatch['schema'],request['prepared']
                if prepared:prepared={**prepared,'messages':messages,'schema':schema}
            elif compiled is not None and not logic:
                prepared=prepare_followup(compiled,observed,compilation=profile.compilation,tokenize=tokenize,
                    request_config=request_config,thinking=False,library=active,seconds=remaining,pal_fragments=True)
                if prepared['kind']=='no_followup':break
                messages,schema=prepared['messages'],prepared['schema']
            elif logic:messages,schema=atom_prompt(source,active,feedback=feedback),atom_schema(source)
            elif match:messages,schema=instance_request(source,match,feedback=feedback)
            else:messages,schema=pal_prompt(source,active,feedback=feedback),pal_schema()
            if prepared:actions.append({k:v for k,v in prepared.items() if k not in {'messages','schema'}})
            count=tokenize(messages,thinking=False)['count']
            if count+request_config['max_tokens']>request_config['context_tokens']:raise Unsupported('Complete request exceeds context; no source truncation')
        except Unsupported as exc:
            result.update(answer=None,certificate_status='budget_exhausted',program_status='request_preparation_unavailable',
                structural_pass=False,error=str(exc),A_main_path_executed=False,B_main_path_executed=False)
            actions.append({'selection_basis':'request_not_dispatched','error':str(exc)});history.append(deepcopy(result));break
        save('request'+str(step)+'.json',{'parent_hash':digest([program,logic_code]),'observed_hash':digest(observed),
            'dispatch_json':json.dumps({'messages':messages,'schema':schema},ensure_ascii=False),'prepared':prepared})
        remaining=max(0,remaining-(time.monotonic()-started));purpose='parse' if step==0 else 'repair';budget.reserve(purpose)
        try:
            wire=generate(messages,purpose=purpose,step=step,schema=schema)
            value=_decode(wire['content']);validate_wire(value,schema);started=time.monotonic()
            if logic:
                compiled,logic_code=decode_atom_response(source,value)
                result=assess_model_horn(compiled,active,interface=profile.interface)
                if arm=='MB':
                    ordinary=ordinary_horn_prediction(source,example_model)
                    result['ordinary_example_synthesis']=ordinary
                    if not ordinary or ordinary.get('answer')!=result['answer']:
                        result.update(answer=None,certificate_status='translation_unresolved',ordinary_example_rejected=True,
                            A_main_path_executed=False,B_main_path_executed=False)
            else:
                if prepared:
                    compiled,observed=accept_followup(compiled,prepared,value,observed,library=active)
                    rows=compiled['accepted_observation_rows']
                    by_name={r['name']:r for r in observation_rows};by_name.update({r['name']:r for r in rows});observation_rows=list(by_name.values())
                    program=compiled['program'];adaptations=compiled.get('deterministic_adaptations',[])
                elif match:
                    program,compiled,instantiation=instantiate_rule_template(source,match,value,library=active)
                else:
                    program,adaptations=lower_pal(source,value['code']);compiled=compile_source(source,program,library=active)
                assessment=assess_source(compiled,observed,compilation=profile.compilation,seconds=max(0,remaining-(time.monotonic()-started)))
                result={'answer':assessment['answer'],'certificate_status':assessment['status'],
                    'program_status':'source_IR_compiled','structural_pass':True,'fallback_used':False,
                    'assessment':assessment,'A_main_path_executed':bool(assessment['certificate']),
                    'B_main_path_executed':bool((assessment['execution'] or {}).get('pattern_uses')),
                    'translation_faithfulness':'accepted source-linked translation is conditional'}
                if arm=='MB':
                    evidence=check_source_examples(compiled,example_model);result['ordinary_example_synthesis']=evidence
                    if not evidence['accepted']:result.update(answer=None,certificate_status='translation_unresolved',
                        ordinary_example_rejected=True,A_main_path_executed=False,B_main_path_executed=False)
            remaining=max(0,remaining-(time.monotonic()-started))
            result['frontend']=FRONTEND
            result['independent_executor_compilation']=not bool(match)
            result['actual_executor_template_instantiation']=bool(match)
            feedback=None if result['certificate_status']=='completion_stable' else {
                'unresolved':result.get('missing_source_units') or result.get('assessment',{}).get('unresolved'),
                'ordinary_example_rejected':result.get('ordinary_example_rejected',False)}
        except BudgetError:raise
        except Exception as exc:
            compiled=None
            feedback={'error_type':type(exc).__name__,'error':exc.message if isinstance(exc,ValidationError) else str(exc),
                'diagnostics':getattr(exc,'diagnostics',None)}
            if isinstance(exc,ValidationError):feedback['field_path']=list(exc.path)
            if isinstance(exc,json.JSONDecodeError) and wire:feedback['incomplete_prefix']=incomplete_feedback(wire['content'])
            if program is not None:
                try:feedback['source_validation']=validation_feedback(source,program)
                except (ValueError,TypeError,KeyError):pass
            result={'answer':None,'certificate_status':'translation_unresolved','program_status':'invalid_IR',
                'structural_pass':False,'fallback_used':False,'error':feedback,'A_main_path_executed':False,'B_main_path_executed':False}
        history.append(deepcopy(result));route_change=bool(wire and wire.get('finish_reason')=='length')
        calls.append({'step':step,'purpose':purpose,'request_hash':wire.get('request_hash') if wire else None,
            'raw_content':wire.get('content') if wire else None,'usage':wire.get('usage') if wire else None,
            'elapsed_seconds':wire.get('elapsed_seconds') if wire else None,'analysis':deepcopy(result),
            'template_instantiation':instantiation,'deterministic_adaptations':adaptations,
            'reasoning_content_present':bool(wire.get('reasoning_content')) if wire else None,
            'physical_origin_call_id':wire.get('physical_origin_call_id') if wire else None,'cache_hit':wire.get('cache_hit',False) if wire else False})
        state={'history':history,'calls':calls,'actions':actions,'observed':observed,'observation_rows':observation_rows,
            'program':program,'logic_code':logic_code,'result':result,'feedback':feedback,'remaining':remaining,
            'budget_calls':budget.calls,'compiled_valid':compiled is not None,'route_requires_change':route_change}
        save('state'+str(step)+'.json',{'state_json':json.dumps(state,ensure_ascii=False,allow_nan=False)})
        if route_change:
            actions.append({'kind':'truncated_generation_requires_route_change','same_path_retry_avoided':True});break
    if controlled_shortcut and result['certificate_status']!='completion_stable' and logic:
        controlled=controlled_prediction(source,arm,active,example_model)
        if controlled:
            result={**controlled,'fallback_used':True,'fallback_kind':'restricted_public_Horn_grammar',
                'A_main_path_executed':False,'B_main_path_executed':False,'model_source_IR_still_unresolved':True}
    if partition=='dev' and result['certificate_status']!='completion_stable':
        budget.reserve('fallback');messages,schema=native_fallback(source);wire=None
        try:
            wire=generate(messages,purpose='fallback',step=len(calls),schema=schema);value=_decode(wire['content']);validate_wire(value,schema)
            answer=value['answer'];failure=None
        except BudgetError:raise
        except Exception as exc:answer=None;failure={'type':type(exc).__name__,'message':str(exc)}
        result={'answer':answer,'certificate_status':'unsupported_no_certificate','program_status':'native_fallback',
            'fallback_used':True,'structural_pass':failure is None,'error':failure,'A_main_path_executed':False,'B_main_path_executed':False}
        calls.append({'step':len(calls),'purpose':'fallback','request_hash':wire.get('request_hash') if wire else None,
            'raw_content':wire.get('content') if wire else None,'usage':wire.get('usage') if wire else None,
            'elapsed_seconds':wire.get('elapsed_seconds') if wire else None,'analysis':deepcopy(result)})
        history.append(deepcopy(result))
    if digest(library)!=before or digest(example_model)!=example_before:raise ValueError('Inference changed common/frozen material')
    outcome={'arm':arm,'frontend':FRONTEND,'result':result,'calls':calls,'history':history,'model_calls':len(budget.calls),
        'call_purposes':budget.calls,'translation_actions':actions,'program':program,'model_horn_code':logic_code,
        'model_horn_program':parse_model_horn(source,logic_code).export() if logic_code else None,
        'observation_rows':observation_rows,'frozen_library_unchanged':True,
        'core_semantic_acceptance_requires_corresponding_grading_and_source_review':True}
    outcome=json.loads(json.dumps(outcome,ensure_ascii=False,allow_nan=False))
    save('outcome.json',outcome);return outcome
