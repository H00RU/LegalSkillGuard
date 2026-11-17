"""Version the common source scope and native tasks, without scoring TEST.

All source expansion is label independent and shared by every arm. Test source
content stays in sealed_test. Native CNI/MAUD labels are copied only into their
grading file; they never drive context expansion or task inclusion.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import zipfile

from legal_skill_guard.paired_interfaces.source_context import enclosing_section, SourceContextUnavailable
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.data import MAUD_ARCHIVE_SHA256, MAUD_QUESTIONS
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'
CNI=ROOT/'history/rr_v2_20261106/data/cache/rr_v2/contract-nli.zip'
MAUD=Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip')


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare():
    metadata=read(BASE/'handoff/source_metadata_current.json');prior=ROOT/metadata['artifact_root']
    diversity_train=read(BASE/'handoff/diversity_train_current.json')
    diversity_holdout=read(BASE/'handoff/diversity_holdout_current.json')
    partitions={'train':read(prior/'TRAIN_raw_public.json'),
        'dev':read(prior/'DEV_exposed_raw_public.json'),
        'test':read(prior/'sealed_test_candidate/public.json')}
    partitions['train']=[s for s in partitions['train'] if s['dataset']!='LegalBench_Diversity']+read(ROOT/diversity_train['artifact_root']/'public.json')
    for split in ('dev','test'):
        folder='dev' if split=='dev' else 'sealed_test'
        partitions[split]+=read(ROOT/diversity_holdout['artifact_root']/folder/'public.json')
    with zipfile.ZipFile(CNI) as archive:
        native={p:json.loads(archive.read('contract-nli/'+p+'.json')) for p in ('train','dev','test')}
    docs={(p,str(d['id'])):d for p,data in native.items() for d in data['documents']}
    native_manifest=read(ROOT/'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    train_cni={s['key']:s for p in ('train','dev','test') for s in native_manifest['datasets']['ContractNLI'][p]}
    if sha(MAUD)!=MAUD_ARCHIVE_SHA256:raise ValueError('Native MAUD archive changed')
    with zipfile.ZipFile(MAUD) as archive:
        fulltexts={Path(n).stem:archive.read(n).decode('utf-8-sig') for n in archive.namelist()
                   if n.startswith('data/contracts/') and n.endswith('.txt')}
        maud_rows=defaultdict(list)
        for p in ('train','dev','test'):
            for row in csv.DictReader(StringIO(archive.read('data/MAUD_'+p+'.csv').decode('utf-8-sig'))):
                if row['data_type']=='main' and row['question'] in MAUD_QUESTIONS:
                    maud_rows[row['contract_name'],row['question']].append((p,row))
    receipts=[];partial_grading={p:{} for p in partitions};identity=[]
    for split,rows in partitions.items():
        for source in rows:
            source['split']=split;source['project_split']=split
            old=digest(source['views']);local=[]
            if source['dataset']=='ContractNLI':
                if source['key'] in train_cni:
                    selected=train_cni[source['key']];ns=selected['native_split'];oid=str(selected['original_document_id'])
                else:ns,oid=source['native_split'],str(source['original_id'])
                doc=docs[ns,oid]
                if any(v['public']['source_text']!=doc['text'] for v in source['views']):
                    raise ValueError('CNI parent identity/text mismatch; do not silently bind another revision')
                queries=sorted(native[ns]['labels'],key=lambda x:int(x.split('-')[-1]))
                if len(queries)!=17:raise ValueError('Full native CNI hypothesis family changed')
                source['views']=[{'id':q,'public':{'source_text':doc['text'],'sentence_spans':doc['spans'],
                    'question':native[ns]['labels'][q]['hypothesis']},
                    'answer_schema':{'type':'string','enum':['Entailment','Contradiction','NotMentioned']}} for q in queries]
                partial_grading[split][source['key']]={q:{'answer':doc['annotation_sets'][0]['annotations'][q]['choice'],
                    'evidence':doc['annotation_sets'][0]['annotations'][q].get('spans')} for q in queries}
                source.update({'native_split':ns,'original_id':oid})
                local.append({'kind':'full_native_hypotheses','native_views':17,'original_native_id':oid})
            elif source['dataset']=='MAUD':
                parent=fulltexts[source['parent_id']]
                partial_grading[split][source['key']]={}
                for view in source['views']:
                    matches=maud_rows[source['parent_id'],view['id']]
                    if len(matches)!=1:raise ValueError('Ambiguous native MAUD task row')
                    ns,row=matches[0]
                    if view['public']['source_text']!=row['text']:
                        raise ValueError('MAUD native excerpt provenance changed')
                    try:
                        text,receipt=enclosing_section(parent,row['text'])
                        view['public']['source_text']=text
                        local.append({'task':view['id'],'expanded':True,**receipt})
                    except SourceContextUnavailable as error:
                        local.append({'task':view['id'],'expanded':False,'reason':str(error),
                            'native_excerpt_sha256':hashlib.sha256(row['text'].encode()).hexdigest(),
                            'semantic_context_completeness_certified':False})
                    partial_grading[split][source['key']][view['id']]={'answer':row['answer'],
                        'native_file':'data/MAUD_'+ns+'.csv','native_row_question_id':row['id']}
            source['runtime_actor_views_sha256']=digest(source['views'])
            receipts.append({'source':source['key'],'dataset':source['dataset'],'split':split,
                'old_views_sha256':old,'new_views_sha256':digest(source['views']),
                'common_fix_all_arms':True,'old_review_reusable_without_reaudit':old==digest(source['views']),
                'scope_receipts':local})
            identity.append({'source':source['key'],'dataset':source['dataset'],'project_split':split,
                'original_dataset':source['dataset'],'original_id':source.get('original_id',source.get('native_id',source['parent_id'])),
                'native_split':source.get('native_split','historical_packet'),
                'native_views':[v['id'] for v in source['views']],'public_content_sha256':digest(source),
                'exposure_status':'sealed_fresh_candidate' if split=='test' else 'TRAIN_or_exposed_project_DEV'})
    quota={'train':128,'dev':80,'test':160}
    if any(len(partitions[p])!=n for p,n in quota.items()):raise ValueError('Five-source quotas changed')
    sets=[{s['key'] for s in partitions[p]} for p in quota]
    if any(sets[i]&sets[j] for i in range(3) for j in range(i)):raise ValueError('Partition source overlap')
    protocol={'name':'convergence_common_input_scope_v1','source_candidate_root':str(prior.relative_to(ROOT)),
        'Diversity_TRAIN_root':diversity_train['artifact_root'],'Diversity_holdout_root':diversity_holdout['artifact_root'],
        'CNI_archive_sha256':sha(CNI),'MAUD_archive_sha256':MAUD_ARCHIVE_SHA256,
        'source_sha256':{p:sha(ROOT/p) for p in ('experiments/convergence_normalize_inputs.py',
            'legal_skill_guard/paired_interfaces/source_context.py')},
        'CNI_family':'full17','MAUD_family':list(MAUD_QUESTIONS),'scope_expansion':'unique_literal_enclosing_section',
        'context_closure_is_syntactic_not_legal_reference_audit':True,'all_arms_identical_public_repairs':True,
        'source_or_model_final_freeze':False,'TEST_labels_used_for_repairs_or_filtering':False,'model_calls':0}
    out=BASE/'normalized_inputs_v1'/digest(protocol)
    immutable_json(out/'protocol.json',protocol);immutable_json(out/'identity_metadata.json',identity)
    immutable_json(out/'scope_receipts.json',receipts)
    for split,rows in partitions.items():
        folder='sealed_test' if split=='test' else split
        immutable_json(out/folder/'public.json',rows)
        immutable_json(out/folder/'CNI_MAUD_grading_only.json',partial_grading[split])
    summary={'artifact_root':str(out.relative_to(ROOT)),'mother_counts':quota,
        'by_dataset':{p:dict(Counter(s['dataset'] for s in rows)) for p,rows in partitions.items()},
        'CNI_native_views':17,'MAUD_native_views':3,
        'MAUD_scope_expansion_counts':{p:dict(Counter('expanded' if r.get('expanded') else 'native_excerpt_only'
            for s in receipts if s['dataset']=='MAUD' and s['split']==p for r in s['scope_receipts'])) for p in partitions},
        'TEST_content_or_labels_displayed':False,'native_score_computed':False,
        'final_exposure_nearduplicate_audit_and_run_binding_pending':True,'new_model_calls':0}
    immutable_json(out/'summary.json',summary)
    (BASE/'handoff/normalized_inputs_current.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':prepare()
