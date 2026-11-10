"""Admit exactly the user-approved ContractNLI diagnostic pairs.

Original proposal and 128-source packets remain unchanged. Only the eight
specified native TRAIN annotations are projected. DEV annotations are never
selected here. Pair views are logged against their original document source;
this is not a counterfactual oracle and does not create twelve mother sources.
"""
import argparse,hashlib,json,sqlite3,time,zipfile
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ledger import BudgetLedger

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
PROPOSAL=BASE/'legal_scope_task_coverage_v1_20261110/proposed_native_pairs_NOT_AUTHORIZED.json'
STAGE=BASE/'contract_authorized_pairs_v1_20261110'
LEDGER=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
EXPECTED={(196,'nda-5'),(196,'nda-7'),(208,'nda-5'),(208,'nda-7'),(161,'nda-16'),(161,'nda-20'),(91,'nda-16'),(91,'nda-20')}


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare():
    p=read(PROPOSAL);pairs=p['pairs'];assert len(pairs)==12
    train=[x for x in pairs if x['native_split']=='train'];dev=[x for x in pairs if x['native_split']=='dev']
    assert {(x['native_document_id'],x['new_hypothesis_id']) for x in train}==EXPECTED
    assert len(dev)==4 and {x['new_hypothesis_id'] for x in dev}=={'nda-7','nda-20'}
    assert {x['native_document_id'] for x in dev}=={478,20}
    tg={x['parent_document_group'] for x in train};dg={x['parent_document_group'] for x in dev}
    assert len(tg)==4 and len(dg)==2 and not tg&dg
    pub={r['key']:r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    rows=[]
    for x in train:
        d=pub[x['parent_frozen_source_id']];text=d['public']['document']
        assert d['group']==x['parent_document_group'] and hashlib.sha256(text.encode()).hexdigest()==x['document_sha256']
        rows.append({'pair_id':digest({'parent':x['parent_frozen_source_id'],'hypothesis':x['new_hypothesis_id']}),
                     **x,'document':text,'status':'authorized_TRAIN'})
    seal={'scope':'independent diagnostic extension approved by latest user instruction on 2026-11-10',
          'proposal_sha256':sha(PROPOSAL),'train_pairs':rows,'dev_pairs_metadata_only':dev,
          'train_mothers':sorted(tg),'dev_mothers':sorted(dg),'original128_unchanged':True,
          'pair_count_not_independent_source_count':True,'train_annotations_selected':False,
          'DEV_annotations_not_selected':True,'TEST_member_not_opened':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal)
    return seal


def acquire_train_supervision():
    seal=prepare()
    # MethodLedger.reserve_oracle deliberately continues to reject invented
    # ContractNLI counterfactuals. This explicit projection is limited to the
    # approved, existing native annotations in the TRAIN archive member.
    with zipfile.ZipFile(ROOT/'data/cache/rr_v2/contract-nli.zip') as z:
        raw=z.read('contract-nli/train.json');data=json.loads(raw)
    docs={d['id']:d for d in data['documents']};labels=[]
    for pair in seal['train_pairs']:
        d=docs[pair['native_document_id']];h=pair['new_hypothesis_id']
        assert hashlib.sha256(d['text'].encode()).hexdigest()==pair['document_sha256']
        assert data['labels'][h]['hypothesis']==pair['new_hypothesis_text']
        a=d['annotation_sets'][0]['annotations'][h]
        row={'pair_id':pair['pair_id'],'parent_source':pair['parent_frozen_source_id'],
             'parent_ordinal':pair['parent_TRAIN_ordinal'],'hypothesis_id':h,'answer':a['choice'],
             'evidence':[{'span_id':j,'range':d['spans'][j],'text':d['text'][d['spans'][j][0]:d['spans'][j][1]]} for j in a['spans']],
             'native_document_id':d['id'],'document_sha256':pair['document_sha256']}
        row['view_hash']=digest({'kind':'user_approved_original_native_TRAIN_pair','proposal_sha256':seal['proposal_sha256'],
             'source':row['parent_source'],'document':row['document_sha256'],'hypothesis':h,
             'answer':row['answer'],'evidence':row['evidence']})
        labels.append(row)
    output={'train_member_sha256':hashlib.sha256(raw).hexdigest(),'pairs':labels,
            'DEV_TEST_not_selected':True,'new_model_calls':0,'new_training_mother_sources':0}
    immutable_json(STAGE/'train_native_supervision.json',output)
    db=sqlite3.connect(LEDGER)
    try:
        db.execute('begin immediate')
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for r in labels:
            exists=db.execute('select 1 from oracle_views where source=? and view_hash=?',(r['parent_source'],r['view_hash'])).fetchone()
            if not exists:db.execute('insert into oracle_views values (?,?,?)',(r['parent_source'],r['view_hash'],time.time()))
        db.commit()
    except BaseException:db.rollback();raise
    finally:db.close()
    print(json.dumps({'train_pairs':len(labels),'train_mothers':len(seal['train_mothers']),
        'DEV_pairs_reserved':4,'DEV_mothers':2,'DEV_labels_selected':False,'new_model_calls':0,
        'TRAIN_answers':[{'ordinal':x['parent_ordinal'],'hypothesis':x['hypothesis_id'],'answer':x['answer']} for x in labels]},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--train-supervision',action='store_true');a=p.parse_args()
    if a.train_supervision:acquire_train_supervision()
    else:print(json.dumps({'prepared':True,'train_pairs':len(prepare()['train_pairs']),'new_model_calls':0}))
