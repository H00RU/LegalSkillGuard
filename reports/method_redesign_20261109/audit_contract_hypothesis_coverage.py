"""Inspect frozen public task coverage and prepare an UNAUTHORIZED pair proposal.

Native TRAIN/DEV JSON is mechanically parsed only to project hypothesis text and
document ID/text hashes. Annotation choices/evidence labels are not selected,
returned, fitted or scored. No TEST member is opened. No Source, packet, grading
record, policy, oracle view, or dispatch is created for the proposed pairs.
"""
import ast,hashlib,json,re,sqlite3,zipfile
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from experiments.rr_v2_norm_query_prototype import offline_probes

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_scope_task_coverage_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_scope_task_coverage_results.json'


def read(p):return json.loads(p.read_text())


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=ledger();train=read(ROOT/'data/packets/rr_v2/public_train.json')['sources']
    order=read(BASE/'redesign_source_roles_v1_20261109/seal.json')['sources']['train'];bykey={r['key']:r for r in train}
    training=[{'ordinal':i,'source':bykey[k]} for i,k in enumerate(order,1) if bykey[k]['dataset']=='ContractNLI']
    dev=[r for r in read(ROOT/'data/packets/rr_v2/public_dev.json')['sources'] if r['dataset']=='ContractNLI']
    hypotheses={r['source']['public']['query'] for r in training};dh={r['public']['query'] for r in dev}
    assert len(training)==24 and len(dev)==8 and len(hypotheses)==len(dh)==1 and hypotheses==dh
    code=(ROOT/'legal_skill_guard/rr/adapters.py').read_text();tree=ast.parse(code)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='contractnli')
    hypothesis_default=ast.literal_eval(fn.args.kw_defaults[0]);assert hypothesis_default=='nda-11'
    hit_rows=[]
    for r in training:
        d=r['source']['public']['document'];hits=list(re.finditer(r'reverse[ -]?engineer|decompil|disassembl',d,re.I))
        spans=[]
        for m in hits:
            a=max(0,m.start()-180);z=min(len(d),m.end()+500)
            spans.append({'start_character':a,'end_character':z,'text':d[a:z]})
        hit_rows.append({'TRAIN_ordinal':r['ordinal'],'source_id':r['source']['key'],
            'document_sha256':hashlib.sha256(d.encode()).hexdigest(),'lexical_hits':len(hits),'source_contexts':spans,
            'keyword_absence_is_not_a_native_NLI_label':True})
    native={};catalog={}
    with zipfile.ZipFile(ROOT/'data/cache/rr_v2/contract-nli.zip') as z:
        for split in ['train','dev']:
            data=json.loads(z.read('contract-nli/'+split+'.json'))
            if split=='train':catalog={k:v['hypothesis'] for k,v in data['labels'].items()}
            bytext={}
            for doc in data['documents']:bytext.setdefault(hashlib.sha256(doc['text'].encode()).hexdigest(),doc['id'])
            native[split]=bytext
    assert len(catalog)==17 and catalog['nda-11']==next(iter(hypotheses))
    proposal=[]
    def add(split,parent,hyp,ordinal=None):
        h=hashlib.sha256(parent['public']['document'].encode()).hexdigest()
        proposal.append({'status':'proposed_not_authorized_not_instantiated','native_split':split,
            'parent_frozen_source_id':parent['key'],'parent_document_group':parent['group'],
            'parent_TRAIN_ordinal':ordinal,'native_document_id':native[split][h],'document_sha256':h,
            'new_hypothesis_id':hyp,'new_hypothesis_text':catalog[hyp],
            'annotation_choice_not_projected_or_opened_as_oracle':True})
    for ordinal,ids in [(5,['nda-5','nda-7']),(10,['nda-5','nda-7']),
                        (111,['nda-16','nda-20']),(115,['nda-16','nda-20'])]:
        for hyp in ids:add('train',bykey[order[ordinal-1]],hyp,ordinal)
    for parent in sorted(dev,key=lambda r:r['key'])[:2]:
        for hyp in ['nda-7','nda-20']:add('dev',parent,hyp)
    assert len(proposal)==12 and sum(r['native_split']=='train' for r in proposal)==8
    assert not ({r['parent_document_group'] for r in proposal if r['native_split']=='train'} &
                {r['parent_document_group'] for r in proposal if r['native_split']=='dev'})
    probes=offline_probes();immutable_json(STAGE/'software_semantics_probes.json',probes)
    immutable_json(STAGE/'proposed_native_pairs_NOT_AUTHORIZED.json',{'status':'proposal_only','pairs':proposal,
        'new_documents':0,'new_native_document_hypothesis_pairs':12,'existing_fixed_packets_unchanged':True,
        'requires_user_data_scope_authorization':True,'no_automatic_model_dispatch':True,'goal_complete':False})
    assert ledger()==before
    report={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'new_model_calls':0,'new_oracle_views':0,'new_native_grades':0,'ledger_rows_unchanged':True,
        'ledger_logical_sha256':digest(before),'fixed_contract_hypothesis':hypothesis_default,
        'public_TRAIN_documents':24,'public_DEV_documents':8,'unique_TRAIN_hypotheses':1,'unique_DEV_hypotheses':1,
        'single_hypothesis_was_deliberate_pre_model_configuration_not_adapter_bug':True,
        'adapter_source_sha256':hashlib.sha256(code.encode()).hexdigest(),'metadata_catalog_hypotheses':17,
        'native_json_mechanically_parsed_fields_projected':['labels.*.hypothesis','documents.*.id','documents.*.text'],
        'annotation_choices_not_selected_returned_fitted_or_scored':True,'TEST_member_not_opened':True,
        'TRAIN_lexical_scope_audit':hit_rows,'lexical_target_hit_documents':[r['TRAIN_ordinal'] for r in hit_rows if r['lexical_hits']],
        'two_document_mention_count_not_a_label_distribution':True,
        'proposal_only_new_pairs':12,'proposal_TRAIN_pairs':8,'proposal_DEV_pairs':4,'new_documents_proposed':0,
        'proposal_not_added_to_current_sources_or_ledger':True,
        'software_probe_distinctions_not_real_model_or_native_validation':True,
        'no_all_seventeen_hypotheses_acceptance_requirement_added':True,'two_contributions_established':False,'goal_complete':False}
    immutable_json(REPORT,report)
    print(json.dumps({k:report[k] for k in ['counts_total','new_model_calls','ledger_rows_unchanged','public_TRAIN_documents','public_DEV_documents','unique_TRAIN_hypotheses','lexical_target_hit_documents','proposal_only_new_pairs','proposal_not_added_to_current_sources_or_ledger']},ensure_ascii=False))


if __name__=='__main__':main()
