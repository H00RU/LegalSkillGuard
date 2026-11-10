"""Independent, label-blind source acquisition for the approved TRAIN pairs.

Candidate: learn scoped norm graphs and update a source-local library.
Control: independently learn an ordinary Python policy cache. Both receive
identical contracts, native questions and query meanings; neither sees labels,
annotator evidence, the other's output or historical acquired programs.
"""
import argparse, hashlib, json, multiprocessing, sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.contract_scope_learning import SCHEMA, ScopeLibrary, QUERIES, execute
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.rr.method_client import MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from experiments.rr_v2_legal_independent_cache import _worker, check_code

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='contract_scope_acquisition_v1_20261110';STAGE=BASE/RUN
DATA=BASE/'contract_authorized_pairs_v1_20261110'
PROTOCOL=ROOT/'reports/method_redesign_20261109/contract_scope_acquisition_protocol.md'
TEXT={'type':'string'}
BASELINE_SCHEMA=obj({'policies':{'type':'array','items':obj({'policy_id':TEXT,'code':TEXT,'unresolved':{'type':'array','items':TEXT}})}})

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ledger_snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}

def execute_cache(code,query,document):
    check_code(code);parent,child=multiprocessing.get_context('fork').Pipe(duplex=False)
    process=multiprocessing.get_context('fork').Process(target=_worker,args=(child,code,[],query,[document]))
    process.start();child.close()
    try:
        if not parent.poll(8):raise ValueError('Ordinary cache exceeded execution time')
        result=json.loads(parent.recv_bytes())
    finally:
        if process.is_alive():process.terminate()
        process.join();parent.close()
    if 'error' in result:raise ValueError(result['error_type']+': '+result['error'])
    out=result['value']
    if not isinstance(out,dict) or 'answer' not in out or out['answer'] not in ['Entailment','Contradiction','NotMentioned',None]:
        raise ValueError('Expected an explicit original ContractNLI label or unresolved null')
    if not isinstance(out.get('evidence'),list) or any(not isinstance(q,str) or not q or q not in document for q in out['evidence']):
        raise ValueError('Evidence must contain exact own-source quotes')
    if out['answer'] in ['Entailment','Contradiction'] and not out['evidence']:
        raise ValueError('A positive or contrary norm needs source evidence')
    return {**out,'fallback':False}

def offline():
    assert strict_output_schema_issues(SCHEMA)==strict_output_schema_issues(BASELINE_SCHEMA)==[]
    doc='Receiver shall return all copies on termination except that an archive copy may be retained.'
    g={'policy_id':'software','scopes':[{'id':'s','domains':['recipient'],'source_quotes':[doc]}],
       'rules':[{'id':'return','effect':'obligation','action':'return_or_destroy','scope_id':'s','triggers':['termination'],
          'conditions':['on termination'],'source_quotes':[doc],'overrides':[]},
          {'id':'retain','effect':'permission','action':'retain','scope_id':'s','triggers':['after_return_or_destruction'],
          'conditions':['archive copy only'],'source_quotes':[doc],'overrides':[]}],
       'complete_query_ids':list(QUERIES),'unresolved':[]}
    lib=ScopeLibrary();lib.update(g,doc);saved=lib.export()
    assert execute(g,doc,'nda-16')['answer']==execute(g,doc,'nda-20')['answer']=='Entailment'
    assert execute(g,doc,'nda-7')['answer']=='NotMentioned'
    assert ScopeLibrary(saved).export()==saved
    other={**g,'policy_id':'other'};lib.update(other,doc);g['rules'][0]['triggers']=['request']
    delta=lib.update(g,doc)
    assert 'nda-16' in delta['affected_queries'] and execute(g,doc,'nda-16')['answer']=='NotMentioned'
    assert lib.export()['other']['graph']['rules']==saved['software']['graph']['rules']
    assert lib.export()['other']['graph']['policy_id']=='other'
    code="def law_cache(facts, query):\n    return {'answer':'NotMentioned','evidence':[]}\n"
    assert execute_cache(code,{'id':'nda-5','text':'software query'},doc)['answer']=='NotMentioned'
    return {'software_execution_update_and_restore_checks':7,'native_or_model_success':False}

def prepare():
    data=read(DATA/'seal.json');old=read(BASE/'contract_norm_cache_v1_20261110/seal.json')
    groups={}
    for pair in data['train_pairs']:
        ordinal=pair['parent_TRAIN_ordinal'];key='p'+str(ordinal)
        groups.setdefault(key,{'policy_id':key,'parent_source':pair['parent_frozen_source_id'],
          'document':pair['document'],'questions':[]})['questions'].append({'id':pair['new_hypothesis_id'],'text':pair['new_hypothesis_text']})
    assert list(groups)==['p5','p10','p111','p115']
    common=('Acquire reusable contract norms from the full source contracts for the supplied native questions. '
      'No native labels, annotator spans or previous programs are supplied. Do not invent case events. '
      'These are normative ContractNLI questions, not claims that a particular event already occurred. '
      'Conditional permission can support may share SOME information with SOME qualifying recipients; preserve all qualifications. '
      'A qualified retention exception can coexist with an obligation to return/destroy. Absence of an applicable statement is NotMentioned, '
      'not a prohibition. Treat inability to acquire the requested scope as unresolved, not NotMentioned. '
      'Distinguish Receiving Party employees/representatives from the other party employees. Resolve definitions and source-local exceptions. '
      'Use exact own-contract evidence quotes for every supported statement; quotes alone do not guarantee semantic fidelity. '
      'No tools, filesystem, network, answers from other sources or fabricated rules. Return only the required JSON. ')
    cand=(common+'Return one source graph per policy_id. scopes assign source-qualified receiver groups to the public query domains '
      'employees,third_parties,recipient,other; record exact defining/authorizing quotes. Rules link their receiver scope, effect, action, '
      'actual source triggers, ALL conditions and exact quotes. Link an exception to a suppressed general rule using overrides only if supported. '
      'For return-or-destroy obligations, termination is a trigger only if source-supported; request alone does not mean termination. '
      'For retention surviving return/destruction use after_return_or_destruction. No event truth values are requested. '
      'complete_query_ids lists supplied queries whose source-relevant coverage you actually completed; unresolved is empty only if none remain. '
      'A query receives Entailment only from a matching effect/action/receiver/required trigger; explicit prohibition can yield Contradiction. '
      'If complete coverage has no matching norm, it yields NotMentioned. The engine does not learn labels or fill missing conditions. '
      'Declare only source-supported scopes/rules; do not add artificial prohibitions to implement a general restriction except where its domain is accurate.')
    baseline=(common+'Independently compile an ordinary reusable Python policy cache for each policy_id. '
      'Each code field defines exactly law_cache(facts,query). facts is empty for these normative questions. '
      'query contains id and the full original text. Return {answer:Entailment|Contradiction|NotMentioned|null,evidence:[exact quotes]}; '
      'you may also return explanation or other diagnostic fields. Infer from your own acquired source rules, not source ID or external labels. '
      'Use any ordinary Boolean/collection/control-flow logic that retains roles, definitions, source conditions and exceptions. '
      'There is no requirement to adopt the candidate graph or to translate irrelevant portions of the full contract. '
      'Allowed builtins: set,frozenset,list,dict,tuple,str,int,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance. '
      'No imports, classes, nested functions, lambdas, decorators, default arguments, exceptions, annotations, files, network or dynamic calls. '
      'A NotMentioned answer requires your actual source review, not a catch-all for failed compilation. '
      'unresolved records unsupported requested aspects; preserve them as null, not a default answer.')
    paths=['experiments/rr_v2_contract_scope_acquisition.py','legal_skill_guard/rr/contract_scope_learning.py',
      'experiments/rr_v2_legal_independent_cache.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:sha(ROOT/p) for p in paths};material=list(groups.values())
    seal={'run_id':RUN,'config':old['config'],'sources':old['sources'],'material':material,
      'source_ids':[m['parent_source'] for m in material],'data_seal_sha256':sha(DATA/'seal.json'),
      'systems':{'candidate':cand,'ordinary_cache':baseline},'schemas':{'candidate':SCHEMA,'ordinary_cache':BASELINE_SCHEMA},
      'user':json.dumps({'policies':material,'public_query_interface':{k:list(v) for k,v in QUERIES.items()}},ensure_ascii=False),
      'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
      'protocol_sha256':sha(PROTOCOL),'offline':offline(),'native_supervision_not_in_acquisition_input':True,
      'independent_acquisition_not_shared_gold_rules':True,'DEV_not_started':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal)
    for path,h in files.items():
        dest=STAGE/'frozen'/path;dest.parent.mkdir(parents=True,exist_ok=True);raw=(ROOT/path).read_bytes()
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
    return seal

def generate(arm):
    seal=prepare();output=STAGE/(arm+'_execution_before_grading.json')
    if output.exists():print(json.dumps({'arm':arm,'existing':True,'no_redispatch':True}));return
    for path,h in seal['files'].items():assert sha(ROOT/path)==h
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=seal['binding'],
      sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
      question='Does source-scoped norm acquisition retain actual authorization domains, triggers and retention exceptions more reliably or cheaply than an independently acquired ordinary policy cache? Exactly eight approved TRAIN pairs/four mother contracts; labels not sent; no DEV/TEST.')
    wire=MethodTeacher(ledger,STAGE,seal['config']['teacher']).summarize(RUN+':'+arm,source_ids=seal['source_ids'],
      system_prompt=seal['systems'][arm],user_prompt=seal['user'],output_schema=seal['schemas'][arm])
    result={'physical_response':wire,'arm':arm,'rows':[],'updates':[],
      'native_labels_selected_by_driver':False,'goal_complete':False}
    try:
        value=wire['value'];policies=value['policies'];result['value']=value
        if [x['policy_id'] for x in policies]!=[m['policy_id'] for m in seal['material']]:raise ValueError('Policy IDs/order differ')
        lib=ScopeLibrary()
        for policy,material in zip(policies,seal['material']):
            try:
                if arm=='candidate':result['updates'].append(lib.update(policy,material['document']))
                for query in material['questions']:
                    r=execute(policy,material['document'],query['id']) if arm=='candidate' else execute_cache(policy['code'],query,material['document'])
                    result['rows'].append({'policy_id':policy['policy_id'],'hypothesis_id':query['id'],'execution':r})
            except Exception as error:
                result['rows'].append({'policy_id':policy['policy_id'],'rejected':True,'error_type':type(error).__name__,'error':str(error)})
        if arm=='candidate':
            result['library']=lib.export();result['cold_restore_equal']=ScopeLibrary(lib.export()).export()==lib.export()
        result['status']='executed_pending_source_review_and_native_grade'
    except Exception as error:result.update(status='rejected',error_type=type(error).__name__,error=str(error))
    immutable_json(output,result)
    print(json.dumps({'arm':arm,'status':result['status'],'elapsed_seconds':wire.get('elapsed_seconds'),
       'rows':[{'policy':r['policy_id'],'query':r.get('hypothesis_id'),'answer':r.get('execution',{}).get('answer'),'error':r.get('error')} for r in result['rows']]},ensure_ascii=False),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['candidate','ordinary_cache']);a=p.parse_args()
    if a.arm:generate(a.arm)
    else:print(json.dumps({'prepared':True,'offline':prepare()['offline'],'new_model_calls':0}))

if __name__=='__main__':main()
