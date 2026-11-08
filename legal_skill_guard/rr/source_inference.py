"""Current six-policy inference over source IR and the shared three-call budget.

Dispatch is supplied by a ledger-bound caller. This module has no grader,
counterfactual reference, teacher or TEST entry point.
"""
from copy import deepcopy
import json
from pathlib import Path
import time

from jsonschema import ValidationError

from .controls import ARMS,PredictionBudget
from .checkpoint import immutable_json
from .coverage import Unsupported,certificate,complete,digest
from .example_synthesis import ordinary_horn_prediction
from .ledger import BudgetError
from .public_horn import LibraryHornQuery,parse_public
from .raw_recovery import _unique_object
from .source_execution import accept_followup,assess_source,prepare_followup
from .source_interfaces import check_source_examples
from .source_format import native_schema
from .source_program import compile_source,compiler_prompt
from .compiler_contract import compiler_response_schema,decode_compiler_response
from .source_validation import incomplete_feedback,validation_feedback
from .strict_contract import obj
from .wire_validation import validate_wire


def _decode(content):
    def reject(value):raise ValueError('Nonfinite constant is not JSON: '+value)
    result=json.loads(content,object_pairs_hook=_unique_object,parse_constant=reject)
    json.dumps(result,allow_nan=False)
    return result


def controlled_prediction(source,arm,library,example_model):
    if source['dataset']!='ProofWriter_OWA_depth5':return None
    parsed=parse_public(source['public'])
    if parsed.residuals:return None
    profile=ARMS[arm]
    ordinary=None
    if arm=='MB':
        ordinary=ordinary_horn_prediction(source,example_model)
        if not ordinary or ordinary.get('answer') is None:return None
    theory=parsed.partial_theory([c.id for c in parsed.ledger.clauses])
    if profile.interface=='collision_refined':
        query=theory.query
        theory.query=LibraryHornQuery(query.fixed_facts,query.choices,query.rules,query.query,deepcopy(library))
    result=complete(theory)
    if result.status!='completion_stable' or ordinary and ordinary['answer']!=result.answer:return None
    execution=theory.query.execute(theory.facts) if isinstance(theory.query,LibraryHornQuery) else {
        'answer':result.answer,'pattern_uses':[],'predefined_components':['restricted public Horn parser and closure']}
    for use in execution['pattern_uses']:use['source_units']=[parsed.rules[use['rule_index']].source]
    return {'answer':result.answer,'certificate_status':'completion_stable',
        'certificate':certificate(theory,result),'execution':execution,'program_status':'controlled_public_grammar',
        'structural_pass':True,'fallback_used':False,'A_main_path_executed':False,
        'B_main_path_executed':any(u.get('query_relevant') for u in execution['pattern_uses']),
        'predefined_grammar_not_new_A_learning':True,'ordinary_example_synthesis':ordinary,
        'translation_faithfulness':'restricted_public_grammar_premise_not_universal_English'}


def native_fallback(source):
    dataset=source['dataset'];value=native_schema(dataset)
    schema=obj({'answer':value})
    messages=[{'role':'system','content':
        'Return the native answer to this public task. Preserve uncertainty and all required output entries. '
        'This is the one fixed fallback; it has no semantic-completeness certificate. '
        'Do not return a program, source-coverage claim or invented evidence.'},
        {'role':'user','content':json.dumps({'dataset':dataset,'public_task':source['public']},ensure_ascii=False)}]
    return messages,schema


def _compiler_request(source,active,profile,program,last_error,tokenize,config,thinking):
    feedback=None
    if program is not None:
        try:feedback=validation_feedback(source,program)
        except (ValueError,TypeError,KeyError):feedback={'compiler_error':last_error}
    if feedback and 'issues' in feedback:
        feedback=deepcopy(feedback)
        for issue in feedback['issues']:
            if isinstance(issue.get('actual'),dict):issue['actual'].pop('cited_text',None)
    if last_error:feedback={**(feedback or {}),'previous_error':last_error}
    # Rejected complete candidates caused repeated copying of invalid witness
    # tables. Preserve them in the journal, and regenerate from source plus
    # concrete diagnostics. Only accepted follow-ups receive prior code.
    system,user=compiler_prompt(source,active,validation_feedback=feedback)
    system+=' Compilation policy: '+profile.compilation+'. Interface policy: '+profile.interface+'.'
    messages=[{'role':'system','content':system},{'role':'user','content':user}]
    actual=tokenize(messages,thinking=thinking)['count'];limit=config['context_tokens']-config['max_tokens']
    action={'selection_basis':'full_source_repair_without_duplicating_rejected_candidate',
            'input_tokens':actual,'raw_candidate_preserved_in_prior_wire':True} if program is not None else None
    if actual>limit:raise Unsupported('Complete compiler request exceeds context; no source truncation')
    return messages,compiler_response_schema(source,active),action


def predict_source(source,*,arm,library,generate,tokenize,request_config,thinking,
                   partition,example_model=None,controlled_shortcut=True,journal=None):
    if arm not in ARMS or partition not in {'train','dev'}:raise ValueError('Current inference accepts fixed TRAIN/DEV only')
    if partition=='train' and arm!='M11':raise ValueError('There is one shared TRAIN acquisition, not six builds')
    if partition=='dev' and not library.get('frozen'):raise ValueError('DEV requires the frozen library')
    if arm=='MB' and example_model is None:raise ValueError('MB needs its same-material frozen example model')
    before=digest(library);example_before=digest(example_model);profile=ARMS[arm]
    active=library if profile.interface=='collision_refined' else None
    if active is None and library.get('compiler_examples'):
        active={'patterns':[],'compiler_examples':library['compiler_examples']}
    history=[];calls=[];actions=[];observed={};observation_rows=[];program=None;compiled=None
    budget=PredictionBudget();remaining=5.0;prepared=None;last_error=None
    result={'answer':None,'certificate_status':'translation_unresolved','program_status':'not_parsed',
        'structural_pass':False,'fallback_used':False,'A_main_path_executed':False,'B_main_path_executed':False}
    journal=Path(journal) if journal is not None else None
    def save(name,value):
        if journal is not None:immutable_json(journal/name,value)
    context={'source':digest(source),'arm':arm,'library':before,'examples':example_before,
        'thinking':thinking,'partition':partition,'request_config':request_config,
        'controlled_shortcut':controlled_shortcut}
    save('context.json',context)
    if journal is not None and (journal/'outcome.json').exists():
        return json.loads((journal/'outcome.json').read_text())
    if partition=='dev' and controlled_shortcut:
        controlled=controlled_prediction(source,arm,library,example_model)
        if controlled is not None:
            outcome={'arm':arm,'result':controlled,'calls':[],'history':[],'model_calls':0,
                'call_purposes':[],'translation_actions':[],'program':None,'observation_rows':[],
                'frozen_library_unchanged':digest(library)==before}
            save('outcome.json',outcome);return outcome
    start=0
    if journal is not None:
        for step in range(2):
            path=journal/('state'+str(step)+'.json')
            if not path.exists():break
            state=json.loads(json.loads(path.read_text())['state_json']);start=step+1
            history,calls,actions=state['history'],state['calls'],state['actions']
            observed,observation_rows,program=state['observed'],state['observation_rows'],state['program']
            result,last_error,remaining=state['result'],state['last_error'],state['remaining']
            budget.calls=list(state['budget_calls'])
            compiled=compile_source(source,program,library=active) if state['compiled_valid'] else None
    for step in range(start,2):
        if compiled is not None and result['certificate_status']=='completion_stable':break
        started=time.monotonic()
        request_path=journal/('request'+str(step)+'.json') if journal is not None else None
        try:
            if request_path is not None and request_path.exists():
                saved=json.loads(request_path.read_text())
                if saved['parent_program_hash']!=digest(program) or saved['observed_hash']!=digest(observed):
                    raise ValueError('Saved prediction request parent changed')
                dispatch=json.loads(saved['dispatch_json'])
                messages,schema,prepared=dispatch['messages'],dispatch['schema'],saved['prepared']
                if prepared:prepared.update(messages=messages,schema=schema)
                if prepared:actions.append({k:v for k,v in prepared.items() if k not in {'messages','schema'}})
            elif compiled is not None and not result.get('ordinary_example_rejected'):
                prepared=prepare_followup(compiled,observed,compilation=profile.compilation,tokenize=tokenize,
                    request_config=request_config,thinking=thinking,library=active,seconds=remaining)
                if prepared['kind']=='no_followup':break
                messages,schema=prepared['messages'],prepared['schema']
                actions.append({k:v for k,v in prepared.items() if k not in {'messages','schema'}})
            else:
                prepared=None
                messages,schema,action=_compiler_request(source,active,profile,program,last_error,
                    tokenize,request_config,thinking)
                if action:actions.append(action)
        except Unsupported as exc:
            result={'answer':None,'certificate_status':'budget_exhausted','program_status':'request_preparation_unavailable',
                'structural_pass':False,'fallback_used':False,'error':str(exc),
                'A_main_path_executed':False,'B_main_path_executed':False}
            history.append(deepcopy(result));actions.append({'selection_basis':'request_not_dispatched','error':str(exc)})
            break
        save('request'+str(step)+'.json',{'parent_program_hash':digest(program),'observed_hash':digest(observed),
            'dispatch_json':json.dumps({'messages':messages,'schema':schema},ensure_ascii=False),'prepared':prepared})
        remaining=max(0,remaining-(time.monotonic()-started));purpose='parse' if step==0 else 'repair'
        budget.reserve(purpose);wire=None
        try:
            wire=generate(messages,purpose=purpose,step=step,schema=schema)
            parsed=_decode(wire['content'])
            started=time.monotonic()
            if prepared:
                compiled,observed=accept_followup(compiled,prepared,parsed,observed,library=active)
                rows=parsed['observations'] if prepared['kind']=='factual_observation' else parsed['factual_observations']
                by_name={r['name']:r for r in observation_rows};by_name.update({r['name']:r for r in rows})
                observation_rows=list(by_name.values());program=compiled['program']
            else:
                program=decode_compiler_response(parsed,source,active)
                compiled=compile_source(source,program,library=active);observed={};observation_rows=[]
            remaining=max(0,remaining-(time.monotonic()-started));started=time.monotonic()
            assessment=assess_source(compiled,observed,compilation=profile.compilation,seconds=remaining)
            remaining=max(0,remaining-(time.monotonic()-started))
            result={'answer':assessment['answer'],'certificate_status':assessment['status'],
                'program_status':'source_IR_compiled','structural_pass':True,'fallback_used':False,
                'assessment':assessment,'A_main_path_executed':bool(assessment['certificate']),
                'B_main_path_executed':bool((assessment['execution'] or {}).get('pattern_uses')),
                'translation_faithfulness':'accepted_source_linked_translation_is_conditional'}
            if arm=='MB':
                evidence=check_source_examples(compiled,example_model);result['ordinary_example_synthesis']=evidence
                if not evidence['accepted']:
                    result.update(answer=None,certificate_status='translation_unresolved',ordinary_example_rejected=True,
                        A_main_path_executed=False,B_main_path_executed=False)
                    last_error={'ordinary_example_rejected_nodes':evidence['rejected_nodes']}
            if not result.get('ordinary_example_rejected'):last_error=None
        except BudgetError:
            raise
        except Exception as exc:
            compiled=None;last_error={'type':type(exc).__name__,'message':exc.message if isinstance(exc,ValidationError) else str(exc)}
            if isinstance(exc,ValidationError):last_error['field_path']=list(exc.path)
            if isinstance(exc,json.JSONDecodeError) and wire:
                last_error['complete_prefix_diagnosis']=incomplete_feedback(wire['content'])
            if hasattr(exc,'diagnostics'):last_error['diagnostics']=exc.diagnostics
            result={'answer':None,'certificate_status':'translation_unresolved','program_status':'invalid_IR',
                'structural_pass':False,'fallback_used':False,'error':last_error,
                'A_main_path_executed':False,'B_main_path_executed':False}
        history.append(deepcopy(result))
        calls.append({'step':step,'purpose':purpose,'request_hash':wire.get('request_hash') if wire else None,
            'raw_content':wire.get('content') if wire else None,'usage':wire.get('usage') if wire else None,
            'elapsed_seconds':wire.get('elapsed_seconds') if wire else None,'analysis':deepcopy(result),
            'reasoning_content_present':bool(wire.get('reasoning_content')) if wire else None,
            'physical_origin_call_id':wire.get('physical_origin_call_id') if wire else None,
            'cache_hit':wire.get('cache_hit') if wire else False})
        state={'history':history,'calls':calls,'actions':actions,'observed':observed,
            'observation_rows':observation_rows,'program':program,'result':result,'last_error':last_error,
            'remaining':remaining,'budget_calls':budget.calls,'compiled_valid':compiled is not None}
        save('state'+str(step)+'.json',{'state_json':json.dumps(state,ensure_ascii=False,allow_nan=False)})
    if controlled_shortcut and result['certificate_status']!='completion_stable' and source['dataset']=='ProofWriter_OWA_depth5':
        controlled=controlled_prediction(source,arm,library,example_model)
        if controlled is not None:
            controlled['model_source_IR_still_unresolved']=True;result=controlled
    if partition=='dev' and result['certificate_status']!='completion_stable':
        budget.reserve('fallback');messages,schema=native_fallback(source);wire=None
        try:
            wire=generate(messages,purpose='fallback',step=len(calls),schema=schema)
            decoded=_decode(wire['content']);validate_wire(decoded,schema)
            answer=decoded['answer'];failure=None
        except BudgetError:raise
        except Exception as exc:answer=None;failure={'type':type(exc).__name__,'message':str(exc)}
        result={'answer':answer,'certificate_status':'unsupported_no_certificate','program_status':'native_fallback',
            'fallback_used':True,'structural_pass':failure is None,'error':failure,
            'A_main_path_executed':False,'B_main_path_executed':False}
        calls.append({'step':len(calls),'purpose':'fallback','request_hash':wire.get('request_hash') if wire else None,
            'raw_content':wire.get('content') if wire else None,'usage':wire.get('usage') if wire else None,
            'elapsed_seconds':wire.get('elapsed_seconds') if wire else None,'analysis':deepcopy(result)})
        history.append(deepcopy(result))
    if digest(library)!=before or digest(example_model)!=example_before:raise ValueError('Inference changed its frozen/common material')
    outcome={'arm':arm,'result':result,'calls':calls,'history':history,'model_calls':len(budget.calls),
        'call_purposes':budget.calls,'translation_actions':actions,'program':program,
        'observation_rows':observation_rows,'frozen_library_unchanged':True,
        'core_semantic_acceptance_requires_corresponding_grading_and_source_review':True}
    save('outcome.json',outcome)
    return outcome
