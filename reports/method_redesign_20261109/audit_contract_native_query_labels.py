"""Freeze ordinary controls before inspecting existing fixed TRAIN labels.

This is a native-task interpretation diagnostic, not learned source acquisition.
No new documents/hypotheses, model requests, DEV/TEST or counterfactual oracles.
"""
import argparse,hashlib,json,re,sqlite3,zipfile
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'artifacts/rr_method_redesign_20261109/contract_native_query_profiles_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/contract_native_query_label_results.json'
TRAIN=ROOT/'data/packets/rr_v2/public_train.json'
GRADES=ROOT/'data/packets/rr_v2/grading_only/train.json'
REGEX=r'reverse[ -]?engineer|decompil|disassembl'


def read(path):return json.loads(path.read_text())


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def prepare():
    before=ledger();sources={s['key']:s for s in read(TRAIN)['sources']}
    order=read(ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109/seal.json')['sources']['train']
    rows=[]
    for ordinal,key in enumerate(order,1):
        source=sources[key]
        if source['dataset']!='ContractNLI':continue
        text=source['public']['document'];matches=list(re.finditer(REGEX,text,re.I))
        rows.append({'ordinal':ordinal,'source':key,'document_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'lexical_hit_count':len(matches),'prediction':'Entailment' if matches else 'NotMentioned',
            'query':source['public']['query']})
    assert len(rows)==24 and len({r['query'] for r in rows})==1
    profiles=[]
    for ordinal,unit_id in [(111,'s21'),(115,'s30')]:
        recorded=read(ROOT/f'artifacts/rr_method_redesign_20261109/recorded_contract_failure_audit_v1_20261110/TRAIN{ordinal}_attempt0.json')
        current=json.loads(recorded['exact_sent_body']['messages'][-1]['content'])['CURRENT']
        unit=next(u for u in current['units'] if u['id']==unit_id)
        assert unit['role']=='rule' and 'except' in unit['text'].lower()
        profiles.append({'ordinal':ordinal,'source':next(r['source'] for r in rows if r['ordinal']==ordinal),
            'original_rule_unit':unit,'author_diagnostic_abstraction_not_model_output':{
                'general_prohibition':True,'written_authorization_exception':True,'exception_event_occurrence':None},
            'frozen_profile_predictions':{
                'conditional_prohibition_statement_present':'Entailment',
                'operative_prohibition_in_all_unknown_event_completions':None,
                'feasible_exception_refutes_unqualified_prohibition':'Contradiction'},
            'profiles_are_interpretation_probes_not_approved_native_semantics':True})
    plan={'phase':'predictions_frozen_before_cached_TRAIN_label_inspection',
        'public_TRAIN_packet_sha256':hashlib.sha256(TRAIN.read_bytes()).hexdigest(),
        'simple_control':{'regex':REGEX,'hit':'Entailment','no_hit':'NotMentioned',
            'not_a_general_NLI_solver':True,'no_label_fitting_or_post_label_feature_changes':True},
        'ordinary_control_predictions':rows,'authored_interpretation_profile_probes':profiles,
        'new_sources':0,'new_hypotheses':0,'DEV_or_TEST_labels_opened':False,
        'existing_grading_file_only_in_next_phase':str(GRADES.relative_to(ROOT)),
        'counterfactual_oracle_views':0,'new_model_calls':0,'two_contributions_established':False,'goal_complete':False}
    immutable_json(STAGE/'predictions_before_labels.json',plan)
    assert ledger()==before
    print(json.dumps({'phase':'prepared','fixed_TRAIN_controls':len(rows),'profile_sources':[111,115],
                      'cached_TRAIN_label_inspections':0,'new_model_calls':0}))


def grade():
    before=ledger();plan=read(STAGE/'predictions_before_labels.json')
    assert plan['public_TRAIN_packet_sha256']==hashlib.sha256(TRAIN.read_bytes()).hexdigest()
    # The original native labels already reside in this frozen TRAIN cache.
    # MethodLedger.reserve_oracle forbids invented ContractNLI counterfactuals;
    # none are requested here. This is not an external oracle/model dispatch.
    cached=read(GRADES)['sources'];rows=[]
    for prediction in plan['ordinary_control_predictions']:
        answer=cached[prediction['source']]['answer']
        rows.append({**prediction,'original_cached_TRAIN_label':answer,'control_correct':prediction['prediction']==answer})
    distribution={label:sum(r['original_cached_TRAIN_label']==label for r in rows)
                  for label in ['Entailment','Contradiction','NotMentioned']}
    probes=[]
    for probe in plan['authored_interpretation_profile_probes']:
        answer=next(r['original_cached_TRAIN_label'] for r in rows if r['source']==probe['source'])
        probes.append({'ordinal':probe['ordinal'],'source':probe['source'],'original_cached_TRAIN_label':answer,
            'frozen_predictions':probe['frozen_profile_predictions'],
            'profiles_matching_label':[k for k,v in probe['frozen_profile_predictions'].items() if v==answer],
            'author_abstraction_not_real_acquisition_or_label_repair':True})
    assert ledger()==before
    output={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'new_model_calls':0,'new_counterfactual_oracle_views':0,'ledger_rows_unchanged':True,
        'cached_fixed_TRAIN_label_inspections':len(rows),'ordinary_control_native_grades':len(rows),
        'authored_profile_label_comparisons':sum(len(r['frozen_predictions']) for r in probes),
        'new_model_native_predictions':0,'new_sources':0,'new_native_pairs':0,
        'only_native_original_nda11':True,'native_labels_not_redefined':True,'DEV_or_TEST_opened':False,
        'prelabel_predictions_sha256':hashlib.sha256((STAGE/'predictions_before_labels.json').read_bytes()).hexdigest(),
        'original_TRAIN_grade_file_sha256':hashlib.sha256(GRADES.read_bytes()).hexdigest(),
        'TRAIN_label_distribution':distribution,'simple_control_correct':sum(r['control_correct'] for r in rows),
        'simple_control_n':len(rows),'simple_control_rows':rows,'interpretation_probes':probes,
        'no_general_NLI_or_fresh_blind_effect_claim':True,'no_all_classes_or_zero_fallback_gate_added':True,
        'two_contributions_established':False,'goal_complete':False}
    immutable_json(STAGE/'postlabel_diagnostic.json',output);immutable_json(REPORT,output)
    print(json.dumps({k:v for k,v in output.items() if k not in ['simple_control_rows','interpretation_probes']},ensure_ascii=False))
    print(json.dumps(probes,ensure_ascii=False))


def evidence():
    before=ledger();result=read(REPORT)
    public={s['key']:s for s in read(TRAIN)['sources']}
    grades=read(GRADES)['sources'];selected=[]
    # Only original TRAIN. Additional hypothesis annotations and all TEST/DEV
    # members remain unselected; this evidence is not passed to any model.
    with zipfile.ZipFile(ROOT/'data/cache/rr_v2/contract-nli.zip') as archive:
        raw=archive.read('contract-nli/train.json');native=json.loads(raw)
        documents={d['id']:d for d in native['documents']}
        for row in result['simple_control_rows']:
            if row['original_cached_TRAIN_label']!='Entailment':continue
            meta=grades[row['source']];document=documents[meta['original_id']]
            assert meta['hypothesis_id']=='nda-11'
            assert hashlib.sha256(document['text'].encode()).hexdigest()==row['document_sha256']
            annotation=document['annotation_sets'][0]['annotations']['nda-11']
            assert annotation['choice']==row['original_cached_TRAIN_label']
            selected.append({'ordinal':row['ordinal'],'source':row['source'],'native_document_id':meta['original_id'],
                'native_hypothesis_id':'nda-11','choice':annotation['choice'],
                'evidence':[{'span_id':index,'character_range':document['spans'][index],
                    'text':document['text'][document['spans'][index][0]:document['spans'][index][1]]}
                    for index in annotation['spans']],
                'cache_label_and_public_document_match_native_TRAIN':True})
    assert [r['ordinal'] for r in selected]==[111,115,120]
    broad_use=[]
    # This is the old fixed first-four NDA cohort plus the control's one error,
    # not a new cohort or a post-label modification of the frozen predictor.
    for row in result['simple_control_rows']:
        if row['ordinal'] not in [5,10,15,20,120]:continue
        lines=[line for line in public[row['source']]['public']['document'].splitlines()
               if re.search(r'\bus(?:e|ed|ing)\b',line,re.I) and re.search(r'purpose|benefit',line,re.I)]
        broad_use.append({'ordinal':row['ordinal'],'source':row['source'],
            'original_cached_TRAIN_label':row['original_cached_TRAIN_label'],'public_use_purpose_benefit_lines':lines,
            'word_cooccurrence_not_a_formal_equivalence_or_legal_subsumption_proof':True})
    assert ledger()==before
    output={'counts_total':result['counts_total'],'new_model_calls':0,'new_counterfactual_oracle_views':0,
        'ledger_rows_unchanged':True,'new_native_pairs':0,'native_TRAIN_member_sha256':hashlib.sha256(raw).hexdigest(),
        'annotation_choices_and_evidence_projected_only_for_original_nda11_positives':selected,
        'original_native_TRAIN_evidence_records_inspected':3,'DEV_or_TEST_members_opened':False,
        'normative_query_not_replaced_by_factual_event_query':True,
        'broad_use_diagnostic':broad_use,'no_post_label_regex_repair_or_new_legal_rule':True,
        'similar_broad_use_restrictions_do_not_establish_one_universal_nda11_bridge':True,
        'no_annotation_error_or_inconsistency_claim':True,'no_core_learning_or_fresh_model_validation_claim':True,
        'goal_complete':False}
    immutable_json(STAGE/'original_native_evidence_and_scope.json',output)
    print(json.dumps({k:v for k,v in output.items() if k not in ['annotation_choices_and_evidence_projected_only_for_original_nda11_positives','broad_use_diagnostic']},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','grade','evidence']);args=parser.parse_args()
    {'prepare':prepare,'grade':grade,'evidence':evidence}[args.phase]()
