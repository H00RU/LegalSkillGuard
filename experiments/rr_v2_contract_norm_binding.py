"""Bind two original native questions to the frozen ordinary-cache API.

The executor selects a real entrypoint and polarity. Deterministic code copies
the already acquired ground arguments; it does not invent rules or answers.
This is a baseline call-routing check, not source-program synthesis or either
required contribution. No new contract or native hypothesis is introduced.
"""
import argparse,hashlib,json
from pathlib import Path
from experiments.rr_v2_legal_independent_cache import execute_code
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
PARENT=BASE/'contract_norm_cache_v1_20261110'
RUN='contract_norm_binding_v1_20261110';STAGE=BASE/RUN


def read(p):return json.loads(p.read_text())


def compile_binding(binding,policy,interface):
    if type(binding['positive']) is not bool:raise ValueError('Polarity must be an explicit Boolean')
    if binding['entrypoint'] is None:return None
    routes={policy[k]['predicate']:policy[k] for k in ['normative_query','applicability_query']}
    if len(routes)!=2:raise ValueError('Two query meanings need distinct declared entrypoints')
    if binding['entrypoint'] not in routes:raise ValueError('Entrypoint is outside this policy cache')
    route=routes[binding['entrypoint']];signature=interface[route['predicate']]
    if len(route['arguments'])!=len(signature['roles']):raise ValueError('Stored route/signature arity mismatch')
    # Choosing this source-supplied ground call supplies its literal arguments.
    # No question entities, case events, condition truth or labels are filled.
    return {'predicate':route['predicate'],'arguments':list(route['arguments']),'positive':binding['positive']}


def offline(value,sources):
    interface={p['name']:p for p in value['interface']};passed=0
    for policy in value['policies']:
        for field,sign,want in [('normative_query',True,'Entailment'),
                                ('normative_query',False,'Contradiction'),
                                ('applicability_query',True,None)]:
            q=compile_binding({'entrypoint':policy[field]['predicate'],'positive':sign},policy,interface)
            assert execute_code(value['code'],[],q,sources)['answer']==want;passed+=1
        assert compile_binding({'entrypoint':None,'positive':True},policy,interface) is None;passed+=1
        try:compile_binding({'entrypoint':'undeclared_entrypoint','positive':True},policy,interface)
        except ValueError:passed+=1
        else:raise AssertionError('An unknown entrypoint must not become a default call')
    return {'public_call_compilation_checks':passed,'native_labels_or_model_success_claim':False}


def prepare():
    parent=read(PARENT/'seal.json');source=read(PARENT/'source.json');value=source['value']
    review=read(BASE/'contract_norm_cache_audit_v1_20261110/source_semantic_review.json')
    assert review['approved_only_for_supplied_complete_exception_interface']
    public={s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    interface={p['name']:p for p in value['interface']};material=[];bindings={}
    for ordinal,policy in zip([111,115],value['policies']):
        source_id=parent['policy_source_mapping'][policy['policy_id']];native=public[source_id]
        assert native['dataset']=='ContractNLI'
        calls=[]
        for field in ['normative_query','applicability_query']:
            route=policy[field];calls.append({'entrypoint':route['predicate'],'stored_call':route,
                'meaning':interface[route['predicate']]['meaning']})
        material.append({'policy_id':policy['policy_id'],'original_TRAIN_ordinal':ordinal,
            'original_native_question':native['public']['query'],'source_quote':policy['source_quote'],
            'available_calls':calls,'event_facts':[]})
        bindings[policy['policy_id']]=obj({'entrypoint':{'anyOf':[
            {'type':'string','enum':[c['entrypoint'] for c in calls]},{'type':'null'}]},
            'positive':{'type':'boolean'},'unresolved':{'type':'array','items':{'type':'string'}}})
    schema=obj({'bindings':obj(bindings),'unresolved':{'type':'array','items':{'type':'string'}}})
    assert strict_output_schema_issues(schema)==[]
    system=('Bind each supplied ORIGINAL QUESTION to one actual source-cache call. Return only the structured bindings, never a final answer. '
        'The interface and calls were acquired from the source contracts without these questions or labels. '
        'Choose the entrypoint by what the question asks and choose its logical polarity relative to the meaning of that predicate. '
        'Do not negate a prohibition predicate merely because its name/meaning already contains a prohibition and the question uses shall not. '
        'Distinguish a statement that a conditional norm exists from whether that norm applies in a concrete event context. '
        'The stored source-qualified arguments are part of each available call; deterministic code will copy them exactly after your selection. '
        'You are selecting an existing ground call, not discovering argument roles or translating the whole source to code. '
        'No event facts are supplied. Do not treat source exceptions as observations that they occurred or did not occur. '
        'Do not invent facts, approval events, source rules, new aliases, objects, query names or missing semantic bridges. '
        'If the question cannot be supported by a supplied call, set entrypoint to null and explain the mismatch concisely in unresolved. '
        'A null entrypoint will not become NotMentioned, a default call or a guessed answer. No tools, code or other text.')
    user=json.dumps({'interface':value['interface'],'questions_and_calls':material},ensure_ascii=False)
    protocol=ROOT/'reports/method_redesign_20261109/contract_norm_binding_protocol.md'
    paths=['experiments/rr_v2_contract_norm_binding.py','experiments/rr_v2_legal_independent_cache.py',
        'legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py',
        'legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    sources=[m['contract'] for m in parent['material']]
    seal={'run_id':RUN,'config':parent['config'],'sources':parent['sources'],'source_ids':parent['source_ids'],
        'interface':value['interface'],'policy_calls':value['policies'],'source_contracts':parent['material'],
        'source_code':value['code'],'material':material,'schema':schema,
        'messages':[{'role':'system','content':system},{'role':'user','content':user}],
        'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(parent['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
        'parent_source_sha256':hashlib.sha256((PARENT/'source.json').read_bytes()).hexdigest(),
        'offline':offline(value,sources),'thinking':False,'native_answers_not_in_prompt':True,
        'source_given_ground_arguments_not_executor_generated':True,'no_event_facts_supplied':True,
        'original_known_TRAIN_not_blind_cohort':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal)
    for path,sha in files.items():
        raw=(ROOT/path).read_bytes();assert hashlib.sha256(raw).hexdigest()==sha
        dest=STAGE/'frozen'/path;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
    return seal


def main(generate):
    output=STAGE/'execution_before_cached_grading.json'
    if generate and output.exists():print(json.dumps({'existing':str(output),'no_redispatch':True}));return
    seal=prepare()
    if not generate:print(json.dumps({'prepared':True,'offline':seal['offline'],'new_model_calls':0}));return
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=seal['binding'],
        sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
        question='Can Qwen/OFF bind the two original native TRAIN questions to the independently source-acquired ordinary-cache calls without labels, guessed event facts or default routing? Only entrypoint and polarity are generated; arguments/code already acquired. Baseline feasibility, not new method or full-source executor synthesis.')
    client=MethodExecutor(ledger,STAGE,seal['config']['executor']);client.readiness()
    wire=client.generate(RUN+':binding',source=seal['source_ids'][0],purpose='method_primitive_observation',
        messages=seal['messages'],thinking=False,schema=seal['schema'])
    result={'physical_response':wire,'cases':[],'native_labels_opened_by_this_driver':False,'new_counterfactual_oracle_views':0,'goal_complete':False}
    try:
        value=json.loads(wire['content']);result['value']=value
        interface={p['name']:p for p in seal['interface']}
        for policy,material in zip(seal['policy_calls'],seal['material']):
            row={'policy_id':policy['policy_id'],'ordinal':material['original_TRAIN_ordinal'],
                 'original_native_question':material['original_native_question'],'binding':value['bindings'][policy['policy_id']]}
            try:
                q=compile_binding(row['binding'],policy,interface);row['compiled_query']=q
                if q is None:row['status']='unmapped_no_fallback'
                else:
                    execution=execute_code(seal['source_code'],[],q,[s['contract'] for s in seal['source_contracts']])
                    row.update(status='executed_pending_native_semantic_review',execution=execution)
            except Exception as error:row.update(status='rejected',error_type=type(error).__name__,error=str(error))
            result['cases'].append(row)
    except Exception as error:result.update(status='binding_rejected',error_type=type(error).__name__,error=str(error))
    immutable_json(output,result)
    print(json.dumps({'cases':[{'ordinal':r['ordinal'],'status':r['status'],'answer':r.get('execution',{}).get('answer')} for r in result['cases']],
        'finish_reason':wire['finish_reason'],'thinking':wire['thinking_requested'],'elapsed_seconds':wire['elapsed_seconds'],'goal_complete':False},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--generate',action='store_true');args=parser.parse_args();main(args.generate)
