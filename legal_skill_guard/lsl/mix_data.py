"""Fixed MIX256 data reconciliation and thin native supervision adapters.

No TEST body/annotation is returned. Legacy source IDs/hashes are verified
before expanding ContractNLI to its17 native hypotheses. Any runtime wire
format hash is recorded explicitly rather than asserted equal to an
undocumented desktop serialization.
"""
from collections import Counter,defaultdict
from copy import deepcopy
from pathlib import Path
import json
import re
import sqlite3
import tarfile
import zipfile

from legal_skill_guard.rr.adapters import _clusters,_one_per_group,rulearena_airline
from legal_skill_guard.rr.partitions import Source,normalized_text
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.oracles import airline,reference_atom,proofwriter as reference_proofwriter

from .data import NativeDataset,load_json,sha,nonspace,text_sha,SOURCE_SHA256,write_json
from .projection import native_projection
from .composition_data import gold_graph

DATASETS=('NormBench','SARA_v2_Binary','ContractNLI','ProofWriter_OWA_depth5','RuleArena_Airline')
QUOTA={d:{'train':128 if d=='NormBench' else 32,'dev':16,'test':32} for d in DATASETS}

# Conservative direct interpretation lineages. Sharing a generic citation or
# legal topic alone is not a union operation. Source metadata only, no scores.
FAMILY_GROUPS={
 'CRIMINAL_CODE_LINEAGE':[
  '刑法','最高人民法院、最高人民检察院关于办理妨害文物管理等刑事案件适用法律若干问题的解释',
  '最高人民法院、最高人民检察院关于办理组织、强迫、引诱、容留、介绍卖淫刑事案件适用法律若干问题的解释',
  '最高人民法院、最高人民检察院关于办理贪污贿赂刑事案件适用法律若干问题的解释',
  '最高人民法院关于抢劫过程中故意杀人案件如何定罪问题的批复'],
 'CIVIL_CODE_LINEAGE':[
  'CIVIL_CODE_LINEAGE','最高人民法院关于审理人身损害赔偿案件适用法律若干问题的解释',
  '最高人民法院关于审理民事案件适用诉讼时效制度若干问题的规定',
  '最高人民法院关于审理存单纠纷案件的若干规定','最高人民法院关于审理银行卡民事纠纷案件若干问题的规定',
  '最高人民法院关于审理海上货运代理纠纷案件若干问题的规定',
  '最高人民法院关于审理道路交通事故损害赔偿案件适用法律若干问题的解释',
  '最高人民法院关于出借银行账户的当事人是否承担民事责任问题的批复'],
 'SECURITIES_LINEAGE':['证券法','最高人民法院关于审理证券市场因虚假陈述引发的民事赔偿案件的若干规定'],
 'CIVIL_PROCEDURE_LINEAGE':['民事诉讼法','最高人民法院关于人民法院办理执行异议和复议案件若干问题的规定',
  '最高人民法院关于在审理经济纠纷案件中涉及经济犯罪嫌疑若干问题的规定',
  '最高人民法院关于知识产权侵权诉讼中被告以原告滥用权利为由请求赔偿合理开支问题的批复'],
 'CRIMINAL_PROCEDURE_LINEAGE':['刑事诉讼法','最高人民法院关于刑事再审案件开庭审理程序的具体规定（试行）'],
}
FAMILY_EVIDENCE=[
 'https://www.court.gov.cn/zixun/xiangqing/19612.html',
 'https://data.court.gov.cn/pages/judicialInterpretationPage/4.html',
 'https://www.court.gov.cn/fabu/xiangqing/357071.html',
 'https://ipc.court.gov.cn/zh-cn/news/view-6226.html',
 'https://www.court.gov.cn/zixun/xiangqing/14404.html',
 'https://www.court.gov.cn/zixun/xiangqing/304781.html',
 'https://www.court.gov.cn/fabu/xiangqing/282631.html',
 'https://www.court.gov.cn/shenpan/xiangqing/4884.html',
 'https://www.csrc.gov.cn/csrc/c100028/c1780919/content.shtml',
]


def family(row):
    original=row['family_id']
    for canonical,values in FAMILY_GROUPS.items():
        if original in values:return canonical
    return original


def reconcile_manifest(candidate_path,old_norm_path,out):
    candidate=load_json(candidate_path)
    unsigned={k:v for k,v in candidate.items() if k!='sha256'}
    if digest(unsigned)!=candidate['sha256']:raise ValueError('Desktop manifest canonical hash mismatch')
    frozen=deepcopy(candidate);norm=frozen['datasets']['NormBench'];old=load_json(old_norm_path)['items']
    changes=[]
    for split,rows in norm.items():
        for r in rows:r['original_family_id']=r['family_id'];r['family_id']=family(r)
    train_families={r['family_id'] for r in norm['train']}
    # Keep the provided128 TRAIN exactly, preserving disclosed mechanism
    # coverage. Repair only genuine heldout family conflicts from the same old
    # heldout partition, before any new training or DEV evaluation.
    for split,forbidden in [('dev',set(train_families)),('test',None)]:
        if split=='test':forbidden=train_families|{r['family_id'] for r in norm['dev']}
        kept=[];removed=[]
        for r in norm[split]:
            (removed if r['family_id'] in forbidden else kept).append(r)
        pool=sorted([deepcopy(r) for r in old if r['split']==split and family(r) not in forbidden],
                    key=lambda r:digest({'protocol':'LSG-MIX256-20261110:lineage-repair','item_id':r['item_id']}))
        used_ids={r['item_id'] for rows in norm.values() for r in rows}
        used_hashes={r['full_article_sha256'] for rows in norm.values() for r in rows}
        for removed_row in removed:
            replacement=None
            for r in pool:
                if r['item_id'] in used_ids or r['full_article_sha256'] in used_hashes:continue
                if sum(x['family_id']==family(r) for x in kept)>=16:continue
                replacement=r;break
            if replacement is None:raise ValueError('No same-partition lineage-safe reserve')
            replacement['original_family_id']=replacement['family_id'];replacement['family_id']=family(replacement)
            kept.append(replacement);used_ids.add(replacement['item_id']);used_hashes.add(replacement['full_article_sha256'])
            changes.append({'split':split,'removed_item_id':removed_row['item_id'],'removed_family':removed_row['family_id'],
                            'replacement_item_id':replacement['item_id'],'replacement_family':replacement['family_id'],
                            'reason':'Direct legal source lineage intersects TRAIN/DEV; fixed metadata hash reserve order, no model result'})
        norm[split]=kept
    old_by_id={r['item_id']:r for r in old};norm_family_splits=defaultdict(set)
    for split,rows in norm.items():
        for r in rows:
            if old_by_id[r['item_id']]['split']!=split:raise ValueError('Native NormBench split role changed')
            norm_family_splits[r['family_id']].add(split)
    if any(len(v)>1 for v in norm_family_splits.values()):raise ValueError('Reconciled legal family overlap')
    for dataset,splits in frozen['datasets'].items():
        seen=set()
        for split,rows in splits.items():
            if len(rows)!=QUOTA[dataset][split]:raise ValueError('Fixed mixed quota changed')
            for r in rows:
                identity=r.get('key',r.get('item_id'))
                if identity in seen:raise ValueError('Same source group in multiple splits')
                seen.add(identity)
    frozen['status']='runtime_lineage_reconciled_before_training_exposure_audit_bound'
    frozen['candidate_manifest_sha256']=candidate['sha256'];frozen.pop('sha256')
    frozen['runtime_sha256']=digest(frozen)
    out=Path(out);write_json(out/'manifest.json',frozen)
    write_json(out/'lineage_reconciliation.json',{'candidate_sha256':candidate['sha256'],'changes':changes,
        'TRAIN128_unchanged':True,'same_original_partition_preserved':True,'heldout_text_or_gold_used':False,
        'family_groups':FAMILY_GROUPS,'primary_source_metadata_evidence':FAMILY_EVIDENCE,
        'note':'Direct interpretation/lineage audit, not union of every shared legal citation or subject; no claim of independent legal expert reannotation'})
    return frozen


def grade_for(prepared,source):
    return prepared.grading[digest({'key':source.key,'split':source.native_split,'content':source.content_key})]


def open_sara(archive):
    """Same audited grouping, native TRAIN file only (also supplies DEV)."""
    rows=[]
    with tarfile.open(archive) as t:
        sections={Path(m.name).name:t.extractfile(m).read().decode() for m in t.getmembers()
                  if m.isfile() and m.name.startswith('sara_v2/statutes/source/section')}
        ids=t.extractfile('sara_v2/splits/train').read().decode().splitlines()
        for cid in ids:
            if not cid.startswith('s'):continue
            text=t.extractfile('sara_v2/cases/'+cid+'.pl').read().decode()
            fact=re.search(r'% Text\s*\n(.*?)\n\s*% Question',text,re.S)
            question=re.search(r'% Question\s*\n(.*?)\n\s*% Facts',text,re.S)
            if not fact or not question:raise ValueError('SARA native schema')
            facts=' '.join(s.removeprefix('% ') for s in fact[1].splitlines())
            combined=' '.join(s.removeprefix('% ') for s in question[1].splitlines())
            q=re.fullmatch(r'(.*?)\s+(Entailment|Contradiction)\s*',combined)
            section=re.match(r's(\d+)',cid)[1]
            public={'rules':sections['section'+section],'facts':facts,'query':q[1],'answer_type':'binary_entailment'}
            rows.append({'id':cid,'facts':facts,'public':public,'answer':q[2]})
    keys=[['stem:'+re.sub(r'_(pos|neg)$','',r['id']),'facts:'+normalized_text(r['facts'])] for r in rows]
    groups=_clusters(rows,keys)
    result=_one_per_group([(Source('SARA_v2_Binary',g,r['public'],'train'),{'answer':r['answer'],'original_id':r['id']}) for r,g in zip(rows,groups)])
    result.audit.update(native_test_file_opened=False,grouping='same stem/fact connected-component rule; selected groups are TRAIN-only in fixed metadata')
    return result


def open_proofwriter(root):
    rows=[]
    for split in ('train','dev'):
        with (Path(root)/('meta-'+split+'.jsonl')).open() as f:
            for line in f:
                theory=json.loads(line)
                facts=sorted(x['text'] for x in theory['triples'].values());rules=sorted(x['text'] for x in theory['rules'].values())
                group=digest({'facts':[normalized_text(t) for t in facts],'rules':[normalized_text(t) for t in rules]})
                qid,q=min(theory['questions'].items(),key=lambda p:digest(p[1]['question']))
                label='True' if q['answer'] is True else 'False' if q['answer'] is False else q['answer']
                public={'facts':facts,'rules':rules,'query':q['question'],'answer_type':'three_valued_owa'}
                grade={'answer':label,'original_theory_id':theory['id'],'original_question_id':qid,
                       'reference_representation':{'facts':[t['representation'] for t in theory['triples'].values()],
                         'rules':[r['representation'] for r in theory['rules'].values()],'query':q['representation']}}
                rows.append((Source('ProofWriter_OWA_depth5',group,public,split),grade))
    result=_one_per_group(rows);result.audit.update(native_test_file_opened=False,one_query_without_labels=True)
    return result


def contract_public_and_grade(raw,selected):
    """Legacy grouping/hash identifies the document; expose only TRAIN/DEV."""
    needed={(r['native_split'],r['original_document_id']):r for s in ('train','dev') for r in selected[s]}
    result={}
    with zipfile.ZipFile(raw) as z:
        for split in ('train','dev'):
            data=json.loads(z.read('contract-nli/'+split+'.json'))
            hypotheses={k:v['hypothesis'] for k,v in data['labels'].items()}
            if len(hypotheses)!=17:raise ValueError('Expected all17 native hypotheses')
            for doc in data['documents']:
                if (split,doc['id']) not in needed:continue
                row=needed[(split,doc['id'])]
                legacy={'document':doc['text'],'query':hypotheses['nda-11'],'answer_type':'contract_nli'}
                if digest(legacy)!=row['legacy_nda11_content_hash']:raise ValueError('Legacy document identity mismatch')
                public={'document':doc['text'],'queries':hypotheses,'sentence_spans':doc['spans'],'answer_type':'contract_nli_all_17'}
                annotations=doc['annotation_sets'][0]['annotations']
                grade={'answers':{k:annotations[k]['choice'] for k in hypotheses},
                       'evidence':{k:annotations[k]['spans'] for k in hypotheses if annotations[k]['choice']!='NotMentioned'},
                       'original_document_id':doc['id']}
                result[row['key']]=(public,grade)
    if len(result)!=48:raise ValueError('Missing selected open contracts')
    return result


def native_atom(atom):return [atom.predicate,list(atom.arguments),atom.positive]


def horn_supervision(reference):
    facts=[native_atom(reference_atom(t)) for t in reference['facts']];rules=[]
    for text in reference['rules']:
        atoms=re.findall(r'\((?:"[^"\n]*"\s*){4}\)',text)
        if not atoms or '->' not in text:raise ValueError('Unsupported native Horn representation')
        parsed=[native_atom(reference_atom(a)) for a in atoms]
        rules.append({'body':parsed[:-1],'head':parsed[-1]})
    return {'facts':facts,'rules':rules,'query':native_atom(reference_atom(reference['query']))}


def sara_contexts(archive,public):
    with tarfile.open(archive) as t:
        sections={Path(m.name).name.removeprefix('section'):t.extractfile(m).read().decode()
                  for m in t.getmembers() if m.isfile() and m.name.startswith('sara_v2/statutes/source/section')}
    references=set(re.findall(r'\bsection\s+(\d+)',public['rules'],flags=re.I));missing=references-set(sections)
    selected={s for s,text in sections.items() if text==public['rules']};queue=list(references&set(sections))
    while queue:
        section=queue.pop()
        if section in selected:continue
        selected.add(section)
        related=set(re.findall(r'\bsection\s+(\d+)',sections[section],flags=re.I))
        missing|=related-set(sections);queue.extend((related&set(sections))-selected)
    return {**public,'rules_context':{s:sections[s] for s in sorted(selected,key=int)},
            'unavailable_public_section_references':sorted(missing,key=int)}


def prepare_mixed(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    packet=root/'reports/legal_five_dataset_amendment_20261110'
    manifest=reconcile_manifest(packet/'mixed256_candidate_manifest.json',root/'reports/legal_semantic_learning_20261110/data_manifest/normbench_candidate_split_v1.json',out)
    norm=manifest['datasets']['NormBench'];norm_manifest={'source_sha256':SOURCE_SHA256,'items':[r for rows in norm.values() for r in rows]}
    write_json(out/'norm_manifest.json',norm_manifest)
    normdata=NativeDataset('/media/sangfor/vdb/legal-skill-data/legal_semantic_learning_20261110/normbench_v1.json',out/'norm_manifest.json')
    raw=root/'data/cache/rr_v2';rows=[];audit={};raw_hashes={}
    for name in ('sara_v2.tar.gz','contract-nli.zip','proofwriter-dataset-V2020.12.3.zip'):raw_hashes[name]=sha(raw/name)
    expected=load_json(packet/'data_availability_audit.json')
    if raw_hashes['contract-nli.zip']!=expected['contractnli_archive']['sha256'] or raw_hashes['proofwriter-dataset-V2020.12.3.zip']!=expected['proofwriter_archive']['sha256']:raise ValueError('Official release hash differs')
    for split in ('train','dev'):
        for r in normdata.split(split):
            rows.append({'dataset':'NormBench','key':r['item_id'],'split':split,'family_id':r['family_id'],
                         'public':r['input'],'grade':{'native':r['gold']},'native_record':r,
                         'masks':{'structure':1,'reference':1,'m2':1,'evidence':0},
                         'runtime_public_sha256':digest(r['input'])})
    prepared={'SARA_v2_Binary':open_sara(raw/'sara_v2.tar.gz'),
              'ProofWriter_OWA_depth5':open_proofwriter(raw/'ProofWriter'),
              'RuleArena_Airline':rulearena_airline(raw/'RuleArena/airline')}
    contracts=contract_public_and_grade(raw/'contract-nli.zip',manifest['datasets']['ContractNLI'])
    for split in ('train','dev'):
        for m in manifest['datasets']['ContractNLI'][split]:
            if 'ContractNLI:'+digest(m['group'])!=m['key']:raise ValueError('Contract source-group identity mismatch')
            public,grade=contracts[m['key']]
            rows.append({'dataset':'ContractNLI','key':m['key'],'split':split,'family_id':m['key'],
                'public':public,'grade':grade,'masks':{'structure':0,'reference':0,'m2':0,'evidence':1},
                'runtime_public_sha256':digest(public),'candidate_public_sha256':m['content_hash'],
                'legacy_public_sha256':m['legacy_nda11_content_hash']})
    audit['ContractNLI']={'open_sources_verified':48,'legacy_selected_public_hashes_verified':True,
                         'native_test_file_opened':False,'all_17_hypotheses_and_native_evidence':True}
    for dataset,p in prepared.items():
        index={(s.key,s.native_split):s for s in p.sources};verified=0
        for split in ('train','dev'):
            for m in manifest['datasets'][dataset][split]:
                source=index[(m['key'],m['native_split'])];grade=grade_for(p,source)
                if source.content_key!=m.get('legacy_nda11_content_hash',m['content_hash']):raise ValueError('Selected native public hash differs')
                public=deepcopy(source.public);masks={'structure':0,'reference':0,'m2':0,'evidence':0}
                if dataset=='ProofWriter_OWA_depth5':
                    parsed=horn_supervision(grade['reference_representation'])
                    executed=reference_proofwriter(grade['reference_representation'])
                    if executed['status']!='closure_complete' or executed['answer']!=grade['answer']:raise ValueError('Native Horn closure does not match released label')
                    grade={**grade,'horn':parsed};masks.update(structure=1,reference=1,m2=1)
                elif dataset=='RuleArena_Airline':
                    grade={**grade,'answer':airline(grade['reference_arguments'])};masks['reference']=1
                else:public=sara_contexts(raw/'sara_v2.tar.gz',public)
                rows.append({'dataset':dataset,'key':source.key,'split':split,'family_id':source.key,
                             'public':public,'grade':grade,'masks':masks,'runtime_public_sha256':digest(public),
                             'candidate_public_sha256':m['content_hash'],'legacy_public_sha256':source.content_key})
                verified+=1
        audit[dataset]={'open_sources_verified':verified,'legacy_selected_public_hashes_verified':True,
                        'TEST_metadata_only':True,'native_adapter':p.audit}
    if Counter((r['dataset'],r['split']) for r in rows)!={(d,s):QUOTA[d][s] for d in DATASETS for s in ('train','dev')}:raise ValueError('Open mixed quota differs')
    write_json(out/'open_dataset.json',{'protocol':'LSG-MIX256-20261110','manifest_sha256':manifest['runtime_sha256'],'records':rows})
    write_json(out/'native_adapter_audit.json',{'datasets':audit,'raw_hashes':raw_hashes,
        'open_counts':{d:{s:sum(r['dataset']==d and r['split']==s for r in rows) for s in ('train','dev')} for d in DATASETS},
        'ContractNLI17_runtime_shape':'document, queries{id:hypothesis}, sentence_spans, answer_type=contract_nli_all_17',
        'ContractNLI17_desktop_wire_hash_claimed_reproduced':False,
        'ContractNLI17_identity_check':'legacy document hash plus all17 official hypotheses and native sentence spans; explicit new runtime input hashes saved',
        'TEST_body_or_gold_returned':False,'native_Horn_reference_labels_checked':True})
    return rows
