"""Freeze, execute and score only the four approved DEV pairs.

Methods and all baselines are frozen before public DEV documents are selected.
Native DEV labels are selected only after all saved predictions exist. This
driver has no training/repair path and never opens a TEST archive member.
"""
import argparse,hashlib,json,re,sqlite3,time,zipfile
from copy import deepcopy
from pathlib import Path
from experiments.rr_v2_contract_compiler_induction import ROOT,BASE,RUN,STAGE,DATA,read,sha,make_ledger
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_compiler_runtime import predict,baseline_answer,scope_answer
from legal_skill_guard.rr.contract_scope_learning import GRAPH,QUERIES,execute,validate
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
import jsonschema

ARMS=['scope_compiler','ordinary_program','direct_nli','retrieval_correction','direct_scope_extraction']
MODELS=ARMS[2:]
FREEZE=STAGE/'DEV_freeze.json'

def train_retrieval(seal):
    examples=[]
    for m in seal['training']:
        for e in m['examples']:
            excerpts=list(e['native_evidence'])
            if not excerpts:
                # A native negative label applies to the full TRAIN document;
                # these excerpts are context, never a sufficient negative proof.
                lines=m['document'].splitlines()
                excerpts=[x for x in lines if re.search(r'\bretain|\breturn|\bdestroy',x,re.I)]
            examples.append({'id':e['id'],'question':e['text'],'native_label':e['answer'],
              'source_excerpts':excerpts,'native_evidence_exists':bool(e['native_evidence']),
              'negative_excerpt_is_not_a_complete_document_or_negative_certificate':not bool(e['native_evidence'])})
    return {'examples':examples,'actual_earlier_TRAIN_errors':seal['error_observations']}

def freeze():
    seal=read(STAGE/'training_seal.json');learned={a:read(STAGE/(a+'_learned.json')) for a in ARMS[:2]}
    assert all('value' in v and 'code' in v['value'] for v in learned.values()),'No executable learner to freeze'
    for path,h in seal['files'].items():assert sha(ROOT/path)==h,(path,'Training runtime changed')
    qids=sorted({p['new_hypothesis_id'] for p in seal['approved_DEV_metadata']});assert qids==['nda-20','nda-7']
    S={'type':'string'}
    answer=obj({'answer':{'anyOf':[{'type':'string','enum':['Entailment','Contradiction','NotMentioned']},{'type':'null'}]},
                'evidence':{'type':'array','items':S},'reason':S})
    schema=obj({'answers':obj({qid:answer for qid in qids})})
    graph=deepcopy(GRAPH);graph['properties']['policy_id']={'type':'string','enum':['D']}
    graph['properties']['complete_query_ids']['items']={'type':'string','enum':qids}
    common=('Evaluate only the supplied ORIGINAL ContractNLI hypotheses against this complete contract. '
       'These are normative questions: a conditional permission/obligation can exist without an observed event. '
       'Preserve who is authorized and the actual qualification or post-return scope. Distinguish Receiving Party people from the other party staff. '
       'Do not invent source rules or events. Original labels are Entailment,Contradiction,NotMentioned; unsupported processing may remain null. '
       'Use exact nonempty source substrings for positive/contrary support, not a paraphrase or a training quote. '
       'Keep output concise. No tools, code or text outside the required JSON. ')
    direct=common+'Return the native answers with exact evidence and a short reason, using only the current source.'
    retrieval=common+('The same authorized TRAIN supervision and actual earlier error observations are supplied as retrieval material. '
       'Apply the CURRENT source, do not copy an earlier label. Negative TRAIN excerpts are incomplete context, not universal prohibitions. '
       'Training errors are historical, not expected answers for the current contract. Return native answers, exact CURRENT-source evidence and a short reason.')
    extraction=common+('Return one SOURCE GRAPH, not final labels. Its policy_id is D. Use the supplied public graph/query interface. '
       'Acquire only source-supported receiver scopes, norms, source triggers, qualifications and exception links relevant to the supplied questions. '
       'All source_quotes must be exact CURRENT-contract substrings. All referenced scope/rule IDs must be declared in this graph. '
       'Preserve unresolved acquisition rather than claiming completed coverage. The host answers via the same public matcher used by the learned compiler.')
    files={p:sha(ROOT/p) for p in [
      'experiments/rr_v2_contract_compiler_dev.py','experiments/rr_v2_contract_compiler_induction.py',
      'legal_skill_guard/rr/contract_compiler_runtime.py','legal_skill_guard/rr/contract_scope_learning.py',
      'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']}
    for sc in [schema,graph]:assert strict_output_schema_issues(sc)==[]
    value={'training_seal_sha256':sha(STAGE/'training_seal.json'),
      'learned_files':{a:sha(STAGE/(a+'_learned.json')) for a in ARMS[:2]},'files':files,
      'approved_DEV_metadata':seal['approved_DEV_metadata'],'source_documents_loaded':False,'native_labels_selected':False,
      'systems':{'direct_nli':direct,'retrieval_correction':retrieval,'direct_scope_extraction':extraction},
      'schemas':{'answers':schema,'graph':graph},'retrieval':train_retrieval(seal),
      'public_query_interface':{k:list(v) for k,v in QUERIES.items()},
      'public_DEV_packet_sha256':sha(ROOT/'data/packets/rr_v2/public_dev.json'),
      'scoring':'Original native label equality after all five arms predictions are saved. Null/rejection is not a correct label. Provenance checks and source-meaning review remain separate.',
      'no_DEV_feedback_training':True,'no_further_model_or_parameter_selection_from_DEV':True,
      'DEV_pairs':4,'DEV_mothers':2,'goal_complete':False}
    immutable_json(FREEZE,value)
    for path in files:
        dst=STAGE/'frozen_DEV'/path;dst.parent.mkdir(parents=True,exist_ok=True);raw=(ROOT/path).read_bytes()
        if dst.exists():assert dst.read_bytes()==raw
        else:dst.write_bytes(raw)
    return value

def verified():
    f=read(FREEZE);seal=read(STAGE/'training_seal.json')
    assert sha(STAGE/'training_seal.json')==f['training_seal_sha256']
    for p,h in f['files'].items():assert sha(ROOT/p)==h,(p,'Changed after DEV freeze')
    for a,h in f['learned_files'].items():assert sha(STAGE/(a+'_learned.json'))==h
    assert sha(ROOT/'data/packets/rr_v2/public_dev.json')==f['public_DEV_packet_sha256']
    return f,seal

def cases():
    f,seal=verified()
    public={p['key']:p for p in read(ROOT/'data/packets/rr_v2/public_dev.json')['sources']};groups={}
    for p in f['approved_DEV_metadata']:
        source=public[p['parent_frozen_source_id']];doc=source['public']['document']
        assert source['dataset']=='ContractNLI' and source['group']==p['parent_document_group']
        assert hashlib.sha256(doc.encode()).hexdigest()==p['document_sha256']
        row=groups.setdefault(source['key'],{'source':source['key'],'group':source['group'],'document':doc,
                  'native_document_id':p['native_document_id'],'questions':[]})
        row['questions'].append({'id':p['new_hypothesis_id'],'text':p['new_hypothesis_text']})
    assert len(groups)==2 and sum(len(c['questions']) for c in groups.values())==4
    return list(groups.values())

def failure(error):return {'answer':None,'evidence':[],'executed':False,'fallback':False,'error_type':type(error).__name__,'error':str(error)}

def execute_learned():
    for arm in ARMS[:2]:
        path=STAGE/(arm+'_DEV_predictions.json')
        if path.exists():continue
        learned=read(STAGE/(arm+'_learned.json'));rows=[];graphs={}
        for c in cases():
            started=time.monotonic()
            try:
                values,g=predict(arm,learned['value']['code'],c['document'],c['questions'])
                if g is not None:graphs[c['source']]=g
            except Exception as e:values=[failure(e) for q in c['questions']]
            elapsed=time.monotonic()-started
            for q,v in zip(c['questions'],values):rows.append({'source':c['source'],'query':q['id'],'execution':v,'document_batch_seconds':elapsed})
        immutable_json(path,{'arm':arm,'rows':rows,'graphs':graphs,'new_model_calls':0,'labels_not_selected':True,
           'freeze_sha256':sha(FREEZE),'goal_complete':False})
    print(json.dumps({'learned_procedures_executed_on_DEV':True,'new_model_calls':0,'native_labels_selected':False}))

def generate(arm):
    f,seal=verified();ledger=make_ledger(seal);client=MethodExecutor(ledger,STAGE,seal['config']['executor']);client.readiness()
    for c in cases():
        tag=digest(c['source'])[:16];path=STAGE/(arm+'_DEV_'+tag+'.json')
        if path.exists():continue
        material={'contract':c['document'],'questions':c['questions'],'public_query_interface':f['public_query_interface']}
        if arm=='retrieval_correction':material['TRAIN_retrieval_material']=f['retrieval']
        if arm=='direct_scope_extraction':material['shared_graph_schema']=GRAPH
        messages=[{'role':'system','content':f['systems'][arm]},{'role':'user','content':json.dumps(material,ensure_ascii=False)}]
        sc=f['schemas']['graph' if arm=='direct_scope_extraction' else 'answers']
        wire=client.generate(RUN+':DEV:'+arm+':'+tag,source=c['source'],purpose='method_dev',messages=messages,thinking=False,schema=sc)
        result={'source':c['source'],'arm':arm,'physical_response':wire,'rows':[],
                 'labels_not_selected':True,'freeze_sha256':sha(FREEZE),'goal_complete':False}
        try:
            value=json.loads(wire['content']);jsonschema.validate(value,sc);result['value']=value
            for q in c['questions']:
                try:
                    v=scope_answer(value,c['document'],q['id']) if arm=='direct_scope_extraction' else baseline_answer(value['answers'][q['id']],c['document'])
                except Exception as e:v=failure(e)
                result['rows'].append({'source':c['source'],'query':q['id'],'execution':v})
        except Exception as e:result['rows']=[{'source':c['source'],'query':q['id'],'execution':failure(e)} for q in c['questions']]
        immutable_json(path,result)
        print(json.dumps({'arm':arm,'source_tag':tag,'finish_reason':wire['finish_reason'],'thinking':wire['thinking_requested'],
          'answers':[{'query':r['query'],'answer':r['execution']['answer'],'error':r['execution'].get('error')} for r in result['rows']]},ensure_ascii=False),flush=True)

def score():
    f,seal=verified();predictions={};pred_hash={}
    for a in ARMS:
        paths=[STAGE/(a+'_DEV_predictions.json')] if a in ARMS[:2] else [STAGE/(a+'_DEV_'+digest(c['source'])[:16]+'.json') for c in cases()]
        assert all(p.exists() for p in paths),('All arms must finish before native DEV labels',a)
        predictions[a]=[r for p in paths for r in read(p)['rows']]
        pred_hash[a]={p.name:sha(p) for p in paths}
        assert len(predictions[a])==4
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    with zipfile.ZipFile(ROOT/'data/cache/rr_v2/contract-nli.zip') as z:raw=z.read('contract-nli/dev.json');native=json.loads(raw)
    docs={d['id']:d for d in native['documents']};labels={};views=[]
    for p in f['approved_DEV_metadata']:
        d=docs[p['native_document_id']];qid=p['new_hypothesis_id'];source=p['parent_frozen_source_id']
        assert hashlib.sha256(d['text'].encode()).hexdigest()==p['document_sha256']
        assert native['labels'][qid]['hypothesis']==p['new_hypothesis_text']
        a=d['annotation_sets'][0]['annotations'][qid]
        labels[(source,qid)]={'answer':a['choice'],'evidence':[d['text'][d['spans'][i][0]:d['spans'][i][1]] for i in a['spans']]}
        views.append({'source':source,'hypothesis_id':qid,'view_hash':digest({'kind':'user_approved_frozen_native_DEV_evaluation_only',
          'freeze':sha(FREEZE),'source':source,'hypothesis':qid,'label':labels[(source,qid)]})})
    arms={}
    for a,rs in predictions.items():
        rows=[{**r,'native_label':labels[(r['source'],r['query'])]['answer'],
              'native_correct':r['execution']['answer']==labels[(r['source'],r['query'])]['answer']} for r in rs]
        arms[a]={'rows':rows,'correct':sum(r['native_correct'] for r in rows),'n':4,
          'answered':sum(r['execution']['answer'] is not None for r in rows),'fallback_n':0,'mother_contracts':2}
    # Record evaluation-only views; TRAIN oracle method remains unchanged and
    # still refuses DEV feedback. No training/repair is performed after this.
    receipt={'freeze_sha256':sha(FREEZE),'prediction_hashes_before_labels':pred_hash,'DEV_views':views,'evaluation_only_not_training_feedback':True}
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        db.execute('begin immediate')
        for v in views:
            if not db.execute('select 1 from oracle_views where source=? and view_hash=?',(v['source'],v['view_hash'])).fetchone():
                db.execute('insert into oracle_views values (?,?,?)',(v['source'],v['view_hash'],time.time()))
        key='frozen_native_DEV_evaluation:'+RUN;prior=db.execute('select value from meta where key=?',(key,)).fetchone()
        if prior:assert json.loads(prior[0])==receipt
        else:db.execute('insert into meta values (?,?)',(key,json.dumps(receipt,sort_keys=True)))
        db.commit()
    result={'arms':arms,'freeze_sha256':sha(FREEZE),'prediction_hashes_before_labels':pred_hash,
      'native_DEV_member_sha256':hashlib.sha256(raw).hexdigest(),'labels':[{**{'source':k[0],'query':k[1]},**v} for k,v in labels.items()],
      'DEV_pairs':4,'DEV_mothers':2,'new_DEV_evaluation_views':4,'new_TRAIN_feedback_views':0,
      'no_DEV_feedback_training':True,'TEST_opened':False,'goal_complete':False}
    immutable_json(STAGE/'DEV_native_score.json',result)
    print(json.dumps({'DEV':{a:{k:v[k] for k in ['correct','n','answered','mother_contracts']} for a,v in arms.items()},'goal_complete':False},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','programs','direct_nli','retrieval_correction','direct_scope_extraction','score']);a=p.parse_args()
    if a.phase=='freeze':freeze();print(json.dumps({'DEV_methods_baselines_scoring_frozen':True,'DEV_text_or_labels_loaded':False}))
    elif a.phase=='programs':execute_learned()
    elif a.phase=='score':score()
    else:generate(a.phase)
