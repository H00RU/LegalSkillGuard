"""Ordinary source-cache feasibility for normative versus operative queries.

This is a common-component control, not either required method contribution.
The real compiler sees two original TRAIN contracts, never native queries or
labels. Signed exception facts in offline probes are SOFTWARE assumptions only.
"""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from experiments.rr_v2_legal_independent_cache import check_code,execute_code
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import PRED,ATOM
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.rr.method_client import MethodTeacher,TEACHER_BINARY,TEACHER_SHA
from legal_skill_guard.rr.method_ledger import MethodLedger

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='contract_norm_cache_v1_20261110';STAGE=BASE/RUN;S={'type':'string'}
SCHEMA=obj({'interface':{'type':'array','items':PRED},'code':S,
    'policies':{'type':'array','items':obj({'policy_id':S,'source_quote':S,
        'normative_query':ATOM,'applicability_query':ATOM,'exception_atom':ATOM})},
    'unresolved':{'type':'array','items':S}})


def read(path):return json.loads(path.read_text())


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def offline():
    assert strict_output_schema_issues(SCHEMA)==[]
    code='''def law_cache(facts, query):
    if query['predicate'] == 'norm_exists':
        return {'answer':'Entailment'}
    if query['predicate'] == 'ban_applies':
        yes = any(r['atom']['positive'] for r in facts if r['atom']['predicate']=='exception')
        no = any(not r['atom']['positive'] for r in facts if r['atom']['predicate']=='exception')
        if yes == no:
            return {'answer':None}
        return {'answer':'Contradiction' if yes else 'Entailment'}
    return {'answer':None}
'''
    q=lambda p:{'predicate':p,'arguments':['software_policy'],'positive':True}
    f=lambda sign:[{'atom':q('exception')|{'positive':sign},'quote':'software assumption'}]
    for facts,query,want in [([],q('norm_exists'),'Entailment'),([],q('ban_applies'),None),
                              (f(True),q('ban_applies'),'Contradiction'),(f(False),q('ban_applies'),'Entailment')]:
        assert execute_code(code,facts,query,['software source'])['answer']==want
    return {'common_runner_checks':4,'no_native_source_or_model_success':True}


def prepare():
    old=read(BASE/'legal_auto_interface_cache_v1_20261110/seal.json')
    public={s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    source_ids=[old['sources']['train'][i-1] for i in [111,115]]
    material=[{'policy_id':'p'+str(i),'contract':public[key]['public']['document']} for i,key in enumerate(source_ids,1)]
    assert all(public[key]['dataset']=='ContractNLI' for key in source_ids)
    system=('Acquire an ordinary reusable Python policy cache from the two contracts, focusing on the prohibition of reverse engineering and its own explicit exception. '
        'No native hypotheses, case facts, labels, prior responses or expected predicates are supplied. This is not a whole-contract formalization. '
        'Keep two DIFFERENT query meanings: (1) a normative query asks whether this contract states this conditional prohibition as a norm; '
        '(2) an applicability query asks whether that particular prohibition applies in an explicit context. A norm exists even while an exception event is unknown. '
        'Do not turn either result into a claim that reverse engineering is permitted by every other clause. '
        'Choose your own predicate names and ordered roles. Declare each in interface. For each policy supply a source_quote, normative_query, applicability_query and exception_atom. '
        'All atoms use {predicate,arguments,positive}; all arguments must be ground strings. The exception atom means that the ENTIRE source-qualified exception applies, '
        'so its interface meaning must preserve every actual qualification: who authorizes, timing, writing, mutual acceptance/execution as applicable in that particular contract. '
        'Use the actual source conditions; do not invent case events. The metadata atoms are routing declarations, not observed facts. '
        'source_quote must be an exact nonempty substring containing the prohibition and its exception from that policy. '
        'Return code defining one function law_cache(facts,query). facts is a list of signed atom records {atom:{predicate,arguments,positive},quote}; query is one signed ground atom. '
        'Return a dict containing answer: Entailment, Contradiction or null. Null means unresolved, not false or NotMentioned. '
        'Do not assume a missing exception is false. An explicitly absent exception enables this prohibition; an explicitly applicable exception disables this prohibition. '
        'Conflicting exception inputs must stay unresolved. In a normative query do not demand an observed instance of the exception or of the regulated action. '
        'You may use ordinary collections, loops, conditionals and set,frozenset,list,dict,tuple,str,int,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance. '
        'Optionally call solve(program,facts,query), the existing signed-source-rule solver. Do not require it if ordinary code suffices. '
        'No imports, classes, nested functions, decorators, annotations/defaults, tools, filesystem, network or dynamic calls. '
        'The same cache runner and solver are public baseline components. Return only the schema, with unresolved describing unsupported aspects. '
        'This acquisition tests source-dependent conditions and two supplied query modes, not discovery of native annotation conventions or a new algorithm.')
    protocol=ROOT/'reports/method_redesign_20261109/contract_norm_cache_protocol.md'
    paths=['experiments/rr_v2_contract_norm_cache.py','experiments/rr_v2_legal_independent_cache.py',
           'legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py',
           'legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    assert hashlib.sha256(Path(TEACHER_BINARY).read_bytes()).hexdigest()==TEACHER_SHA
    seal={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source_ids':source_ids,
        'policy_source_mapping':dict(zip(['p1','p2'],source_ids)),'material':material,
        'system':system,'user':json.dumps({'policies':material},ensure_ascii=False),'schema':SCHEMA,
        'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'offline':offline(),
        'author_supplied_query_views_not_claimed_learned':True,'native_queries_labels_and_cases_not_supplied':True,
        'common_component_not_a_method_contribution':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal)
    for path,sha in files.items():
        raw=(ROOT/path).read_bytes();assert hashlib.sha256(raw).hexdigest()==sha
        dest=STAGE/'frozen'/path;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
    return seal


def execute(value,seal):
    check_code(value['code']);interface={p['name']:p for p in value['interface']}
    if len(interface)!=len(value['interface']):raise ValueError('Duplicate interface names')
    if [p['policy_id'] for p in value['policies']]!=['p1','p2']:raise ValueError('Policy IDs/order differ')
    rows=[]
    for policy,material in zip(value['policies'],seal['material']):
        quote=policy['source_quote']
        if not quote or quote not in material['contract']:raise ValueError('Source quote does not match its own contract')
        for field in ['normative_query','applicability_query','exception_atom']:
            atom=policy[field];pred=interface.get(atom['predicate'])
            if pred is None or len(atom['arguments'])!=len(pred['roles']) or any(t.startswith('?') for t in atom['arguments']):
                raise ValueError('Unknown, non-ground or wrong-arity routing atom')
            if atom['positive'] is not True:raise ValueError('Routing atoms must name positive concepts')
        for condition in ['unknown','applies','absent','conflict']:
            facts=[]
            for positive in ([True] if condition=='applies' else [False] if condition=='absent' else [True,False] if condition=='conflict' else []):
                facts.append({'atom':policy['exception_atom']|{'positive':positive},'quote':'SOFTWARE assumption: complete source-qualified exception '+str(positive)})
            for mode,field in [('normative','normative_query'),('applicability','applicability_query')]:
                result=execute_code(value['code'],facts,policy[field],[m['contract'] for m in seal['material']])
                expected='Entailment' if mode=='normative' else {'unknown':None,'applies':'Contradiction','absent':'Entailment','conflict':None}[condition]
                rows.append({'policy_id':policy['policy_id'],'mode':mode,'exception_context':condition,
                    'answer':result['answer'],'expected_control':expected,'passed':result['answer']==expected,
                    'context_is_software_not_a_new_native_case':True,'execution':result})
    return rows


def main(generate):
    output=STAGE/'source.json'
    if generate and output.exists():print(json.dumps({'existing':str(output),'no_redispatch':True}));return
    seal=prepare()
    if not generate:print(json.dumps({'prepared':True,'offline':seal['offline'],'new_model_calls':0}));return
    before=ledger();assert not any(r[6]=='reserved' for r in before['calls'])
    ledger_client=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=seal['binding'],
        sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
        question='Can an ordinary source-only cache preserve two actual contracts conditional prohibitions while separating supplied normative and applicability query modes? Fixed TRAIN111/115; no native questions/labels. Common-component feasibility, not method novelty.')
    wire=MethodTeacher(ledger_client,STAGE,seal['config']['teacher']).summarize(RUN+':source',source_ids=seal['source_ids'],
        system_prompt=seal['system'],user_prompt=seal['user'],output_schema=seal['schema'])
    result={'physical_response':wire,'goal_complete':False,'new_counterfactual_oracle_views':0,'new_native_grades':0,
            'common_component_not_method_evidence':True}
    try:
        value=wire['value'];result['value']=value;rows=execute(value,seal)
        result.update(status='captured_pending_source_semantic_review',controls=rows,all_controls_passed=all(r['passed'] for r in rows))
    except Exception as error:result.update(status='rejected',error_type=type(error).__name__,error=str(error))
    immutable_json(output,result)
    print(json.dumps({'status':result['status'],'all_controls_passed':result.get('all_controls_passed'),
        'elapsed_seconds':wire['elapsed_seconds'],'error':result.get('error'),'goal_complete':False},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--generate',action='store_true');args=parser.parse_args();main(args.generate)
