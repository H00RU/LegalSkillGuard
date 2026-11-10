"""Induce reusable legal source procedures from exactly the approved TRAIN.

One teacher acquisition per arm learns a procedure, not a per-document cache.
No DEV text or label is loaded by preparation, induction or TRAIN execution.
The future frozen DEV comparison is separate; TRAIN fit is not method success.
"""
import argparse,hashlib,json,sqlite3,time
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.contract_scope_learning import GRAPH,QUERIES
from legal_skill_guard.rr.contract_compiler_runtime import check,predict,offline
from legal_skill_guard.rr.method_client import MethodTeacher,MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='contract_compiler_induction_v1_20261110';STAGE=BASE/RUN
DATA=BASE/'contract_authorized_pairs_v1_20261110'
PROTOCOL=ROOT/'reports/method_redesign_20261109/contract_compiler_induction_protocol.md'
S={'type':'string'};SCHEMA=obj({'code':S,'learned_operations':{'type':'array','items':S},'limitations':{'type':'array','items':S}})

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}

def prepare():
    data=read(DATA/'seal.json');truth=read(DATA/'train_native_supervision.json');old=read(BASE/'contract_scope_acquisition_v1_20261110/seal.json')
    labels={r['pair_id']:r for r in truth['pairs']};groups={}
    for pair in data['train_pairs']:
        key='p'+str(pair['parent_TRAIN_ordinal'])
        record=groups.setdefault(key,{'training_document':key,'document':pair['document'],'examples':[]})
        grade=labels[pair['pair_id']]
        record['examples'].append({'id':pair['new_hypothesis_id'],'text':pair['new_hypothesis_text'],
          'answer':grade['answer'],'native_evidence':[e['text'] for e in grade['evidence']]})
    feedback=[{'training_document':'p10','id':'nda-5','earlier_prediction':'NotMentioned','native_answer':'Entailment'},
              {'training_document':'p115','id':'nda-20','earlier_prediction':'Entailment','native_answer':'NotMentioned'}]
    common=('Learn an executable procedure for NEW contracts from the provided four TRAIN contracts and eight native annotated examples. '
      'This is supervised program induction, not an invitation to output these contracts answers or a document cache. '
      'The examples and two earlier error observations are the entire authorized training corpus. No DEV data is supplied. '
      'Define infer(document,query), plus ordinary helper functions or literal constants if useful. The future document has no source ID, name lookup or answer cache. '
      'Infer reusable lexical/syntactic patterns and their role/condition relationships, including definitions where needed. '
      'Avoid hardcoded company names, training-document identifiers, full-document strings or label lookup tables for known texts. '
      'Use the native annotation convention; a conditional norm may exist without its event having occurred. Some authorized recipients/information can suffice for a may-some query. '
      'Do not conflate the other party staff with the Receiving Party employees. Do not turn every generic written-approval exception into a post-return retention authorization. '
      'These are TRAIN lessons supplied equally to both arms, not hidden evaluation rules. Preserve unsupported scope as null when your procedure cannot acquire it. '
      'Source quotes emitted at runtime must be exact nonempty substrings of that NEW document, not copied quotes from these examples or normalized text. '
      'You may use ordinary Python collections, conditionals, loops, comprehensions, helper functions and regex. '
      'Available builtins: set,frozenset,list,dict,tuple,str,int,float,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance,range,abs,next,reversed. '
      'The host supplies re with compile,search,match,fullmatch,findall,finditer,sub,split,escape and I,S,M flags. Match group/groups/groupdict/start/end/span are allowed. '
      'No imports, classes, lambdas, exceptions, annotations/defaults/decorators, global/nonlocal statements, tools, filesystem, network or environment access. '
      'The shared scope_answer(graph,document,query_id) helper implements the supplied public graph/query interface. BOTH arms may use it, or the ordinary arm may use other logic. '
      'Return JSON code, learned_operations and limitations. Be specific about what the procedure can generalize and leave unsupported interpretations unresolved. ')
    candidate=(common+'Candidate target: infer(document,query) is called with query=null and must compile a SOURCE GRAPH using the supplied graph schema. '
      'It must work without seeing the future question; produce supported norms in the four public query families and mark incomplete scope via unresolved/complete_query_ids. '
      'Scopes bind actual authorized receiver groups and exact defining/authorizing quotes; rules link effect, action, scope, actual source triggers, all qualifications and exact quotes. '
      'The fixed public matcher then answers the actual questions. Learn the text-to-scope/rule procedure; do not pre-store training source graphs. '
      'For after_return_or_destruction, acquire the relation to that state, not only the word retain. Do not label arbitrary adviser/employee mentions as a permission. '
      'The policy_id can be a fixed neutral string since graph objects are stored by the host under each actual source. ')
    ordinary=(common+'Strong ordinary program learner target: infer(document,query) receives query={id,text}, and returns '
      '{answer:Entailment|Contradiction|NotMentioned|null,evidence:[exact source quotes]}. You may return diagnostics. '
      'Independently learn any reusable source/query classifier, parser, definition lookup, rule system or graph compiler that best uses these examples. '
      'You have the same regex, graph schema and scope_answer helper, so you may implement structured reasoning too. There is no requirement to use only keywords or a simpler hypothesis class. '
      'Explicitly acquired absence can yield native NotMentioned; failed parsing or unsupported input must yield null. '
      'Use the entire source where needed and preserve conditional scopes. Do not require irrelevant full-contract translation. ')
    paths=['experiments/rr_v2_contract_compiler_induction.py','legal_skill_guard/rr/contract_compiler_runtime.py',
      'legal_skill_guard/rr/contract_scope_learning.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:sha(ROOT/p) for p in paths}
    seal={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source_ids':old['source_ids'],
      'training':list(groups.values()),'error_observations':feedback,'schema':SCHEMA,
      'systems':{'scope_compiler':candidate,'ordinary_program':ordinary},
      'user':json.dumps({'training_contracts':list(groups.values()),'earlier_native_training_errors':feedback,
        'public_query_interface':{k:list(v) for k,v in QUERIES.items()},'shared_graph_schema':GRAPH},ensure_ascii=False),
      'data_seal_sha256':sha(DATA/'seal.json'),'TRAIN_supervision_sha256':sha(DATA/'train_native_supervision.json'),
      'approved_DEV_metadata':data['dev_pairs_metadata_only'],'DEV_text_or_labels_loaded':False,
      'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
      'protocol_sha256':sha(PROTOCOL),'offline':offline(),'candidate_and_control_independent':True,
      'hypothesis_independent_graph_extraction_is_an_inductive_bias_not_claimed_innovation_alone':True,
      'goal_complete':False}
    assert strict_output_schema_issues(SCHEMA)==[]
    immutable_json(STAGE/'training_seal.json',seal)
    for path in files:
        p=STAGE/'frozen'/path;p.parent.mkdir(parents=True,exist_ok=True);raw=(ROOT/path).read_bytes()
        if p.exists():assert p.read_bytes()==raw
        else:p.write_bytes(raw)
    return seal

def make_ledger(seal):
    return MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
      binding=seal['binding'],sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
      question='Can a reusable source-scope compiler induced from eight authorized native TRAIN pairs preserve receiver and post-return scope on unseen mother contracts better or more cheaply than an independently induced unrestricted ordinary program? Fixed supervision and resources; no TRAIN repair loop; DEV only after a separate method/baseline/scoring freeze.')

def evaluate(arm,code,training):
    rows=[];graphs={}
    for material in training:
        queries=[{'id':q['id'],'text':q['text']} for q in material['examples']]
        try:
            values,graph=predict(arm,code,material['document'],queries)
            if graph is not None:graphs[material['training_document']]=graph
            for query,value in zip(material['examples'],values):
                rows.append({'training_document':material['training_document'],'query':query['id'],
                  'native_answer':query['answer'],'execution':value,'native_correct':value['answer']==query['answer'],
                  'executed':value.get('executed',True),'fallback':False})
        except Exception as e:
            for query in material['examples']:
                rows.append({'training_document':material['training_document'],'query':query['id'],
                   'native_answer':query['answer'],'executed':False,'native_correct':False,'fallback':False,
                   'error_type':type(e).__name__,'error':str(e)})
    return rows,graphs

def learn(arm):
    output=STAGE/(arm+'_learned.json')
    if output.exists():print(json.dumps({'existing':True,'arm':arm,'no_redispatch':True}));return
    seal=prepare()
    for path,h in seal['files'].items():assert sha(ROOT/path)==h
    ledger=make_ledger(seal)
    wire=MethodTeacher(ledger,STAGE,seal['config']['teacher']).summarize(RUN+':train:'+arm,
      source_ids=seal['source_ids'],system_prompt=seal['systems'][arm],user_prompt=seal['user'],output_schema=seal['schema'])
    result={'arm':arm,'physical_response':wire,'training_fit_not_validation':True,'goal_complete':False}
    try:
        value=wire['value'];check(value['code']);rows,graphs=evaluate(arm,value['code'],seal['training'])
        result.update(value=value,training_rows=rows,training_graphs=graphs,
          train_correct=sum(r['native_correct'] for r in rows),train_executed=sum(r['executed'] for r in rows),
          status='learned_pending_frozen_DEV_and_source_review',code_sha256=hashlib.sha256(value['code'].encode()).hexdigest())
    except Exception as e:result.update(status='rejected',error_type=type(e).__name__,error=str(e))
    immutable_json(output,result)
    print(json.dumps({'arm':arm,'status':result['status'],'train_correct':result.get('train_correct'),
      'train_executed':result.get('train_executed'),'elapsed_seconds':wire.get('elapsed_seconds'),
      'error':result.get('error'),'goal_complete':False},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['scope_compiler','ordinary_program']);a=p.parse_args()
    if a.arm:learn(a.arm)
    else:print(json.dumps({'prepared':True,'offline':prepare()['offline'],'new_model_calls':0}))
