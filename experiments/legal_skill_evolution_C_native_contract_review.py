"""Check the three preserved C residuals against original TRAIN annotations.

No root search, model call, label alteration, new source or held-out data read.
The check distinguishes faithful source distinctions from native interpretation;
it does not declare annotations wrong or authorize changing legal semantics.
"""
import hashlib
import json
from pathlib import Path
import zipfile

from experiments import legal_skill_evolution_current_source_residual_diagnosis as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT=prior.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_C_native_contract_review_20261115'


def run():
    read=prior.current.update.train.read
    prepared=prior.current.update.train.parent.PREPARED
    public={s['key']:s for s in read(prepared/'public.json')if s['dataset']=='ContractNLI'}
    grading=read(prepared/'grading.json')
    path=ROOT/'history/rr_v2_20261106/data/cache/rr_v2/contract-nli.zip'
    with zipfile.ZipFile(path)as archive:
        raw=archive.read('contract-nli/train.json')
    original=json.loads(raw);rows=[]
    notes={
        'nda-5':{'source_distinction':'Employees of controlled companies, not an explicit permission for the recipient own employees.',
            'layer':'Native recipient-class interpretation versus already represented source ownership.',
            'unauthorized_shortcut_rejected':'Do not collapse controlled-company employment into direct employment.'},
        'nda-16':{'source_distinction':'Return obligation is expressly conditional on request; no agreement-end trigger is stated in that return clause.',
            'layer':'Native trigger interpretation versus already represented source request condition.',
            'unauthorized_shortcut_rejected':'Do not invent request implies agreement termination.'},
        'nda-20':{'source_distinction':'Source disposal covers stated material and alternatives; no positive retention permission is stated.',
            'layer':'Consumer derives Contradiction from full-disposal scope; original native annotation is NotMentioned. The justification for that derived negation is unresolved.',
            'unauthorized_shortcut_rejected':'Do not strengthen OR to destroy, invent retention permission or silently change the original label.'}}
    for case in read(prior.OUT/'result.json')['results']:
        sid=case['source'];s=public[sid];assert s['split']=='train'
        text=s['views'][0]['public']['source_text']
        matches=[d for d in original['documents']if d['text']==text]
        assert len(matches)==1
        doc=matches[0];annotations=doc['annotation_sets'][0]['annotations']
        views=[]
        for residual in case['views']:
            vid=residual['view'];view=next(v for v in s['views']if v['id']==vid)
            annotation=annotations[vid];grade=grading[sid][vid]
            assert view['public']['question']==original['labels'][vid]['hypothesis']
            assert grade['answer']==annotation['choice']
            expected_spans=annotation.get('spans')if annotation['choice']!='NotMentioned'else None
            assert grade['evidence']==expected_spans
            evidence=[{'index':i,'offsets':doc['spans'][i],
                'text':doc['text'][doc['spans'][i][0]:doc['spans'][i][1]]}
                for i in annotation.get('spans',[])]
            views.append({'view':vid,'question':view['public']['question'],
                'original_native_answer':annotation['choice'],'existing_consumer_value':residual['original_value'],
                'original_evidence':evidence,'native_label_and_question_join_exact':True,
                **notes[vid]})
        actual=next(read(p)for p in (prior.current.OUT/'ConstraintAcquire/results').glob('*.json')if read(p)['source']==sid)
        rows.append({'source':sid,'original_TRAIN_document_id':doc['id'],
            'original_source_text_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'fixed_prepared_source_sha256':digest(s),'views':views,
            'actual_legal_output_statements':actual['source_output']['statements']})
    result={'new_model_calls':0,'TEST_DEV_read':False,'original_TRAIN_member_only':'contract-nli/train.json',
        'original_TRAIN_member_sha256':hashlib.sha256(raw).hexdigest(),
        'preserved_original_archive':str(path.relative_to(ROOT)),
        'rows':rows,'source_label_question_join_fault_found':False,
        'no_missing_legal_rule_inferred_from_native_disagreement_alone':True,
        'not_an_annotation_error_certificate_or_a_new_method_gain':True,
        'decision':'Preserve the three source-valid distinctions and native residuals. Do not buy another rule-acquisition call for them without a justified consumer/task contract change.',
        'primary_protocol_sources':['https://stanfordnlp.github.io/contract-nli/',
            'https://aclanthology.org/2021.findings-emnlp.164.pdf'],
        'source_of_native_hypothesis_conventions_not_a_license_to_flatten_law':True,
        'goal_complete':False}
    immutable_json(OUT/'result.json',result)
    print(json.dumps({'TRAIN_sources':len(rows),'exact_original_joins':sum(len(r['views'])for r in rows),
        'new_calls':0,'next_action_changed':'Keep source acquisition fixed for these three; diagnose native interpretation separately.'}),flush=True)


if __name__=='__main__':run()
