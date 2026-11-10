"""Offline original TRAIN3 subclause audit; no model dispatch or new hypothesis.

Only the already fixed original case and its original goal are executed. The
native full-parent definition is inspected, never graded as an extra question.
Old model responses remain failed and unchanged. This is a task-bound reference
control, not either proposed method contribution.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tarfile
import tempfile

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'native_subclause3_audit_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/native_subclause3_results.json'
RUNTIME=Path('/home/yndx/hhy/legal-skill-rr-v2/.local-tools/rr-v2-swipl/root/usr')


def read(path):
    return json.loads(path.read_text())


def snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def clause(text, name):
    start=re.search(r'^'+re.escape(name)+r'\(',text,re.M).start()
    end=start+re.search(r'\.[ \t]*(?:%[^\n]*)?$',text[start:],re.M).end()
    return text[start:end]


def main():
    before=snapshot()
    assert not [r for r in before['calls'] if r[6]=='reserved']
    sealed=read(BASE/'redesign_source_roles_v1_20261109/seal.json')
    key=sealed['sources']['train'][2]
    source=next(r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources'] if r['key']==key)
    grade=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources'][key]
    assert source['native_split']=='train' and grade['original_id']=='s3306_b_10_A_pos'
    member='sara_v2/cases/'+grade['original_id']+'.pl'
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as archive:
        native=archive.extractfile(member).read()
        files={m.name.removeprefix('sara_v2/'):archive.extractfile(m).read()
               for m in archive.getmembers() if m.isfile() and m.name.startswith('sara_v2/statutes/prolog/') and m.name.endswith('.pl')}
    text=native.decode()
    assert source['public']['facts'] in text and source['public']['query'] in text
    assert text.count('% Test')==1
    original_goal=re.findall(r'^:- (s3306_b_10_A\([^\n]+\))\.$',text,re.M)
    assert original_goal==['s3306_b_10_A("paid",_,_,_,_,_)']
    raw3306=files['statutes/prolog/section3306.pl']
    a=clause(raw3306.decode(),'s3306_b_10_A')
    parent=clause(raw3306.decode(),'s3306_b_10')
    b=clause(raw3306.decode(),'s3306_b_10_B')
    assert 's3306_b_10_B' not in a and 's3306_b_10_A' in parent and 's3306_b_10_B' in parent
    # Preserve the original Facts and its initialization directive verbatim;
    # replace only halt/test output plumbing to retain actual proof witnesses.
    driver=text.split('% Test',1)[0]+\
        '\nmain :- findall([Employment,Employee,Employer,Termination,Cause],\n'+\
        '  s3306_b_10_A("paid",Employment,Employee,Employer,Termination,Cause),W),\n'+\
        '  write_canonical(W),nl,(W=[]->halt(1);halt(0)).\n'
    env=dict(os.environ)
    env['SWI_HOME_DIR']=str(RUNTIME/'lib/swi-prolog')
    env['LD_LIBRARY_PATH']=str(RUNTIME/'lib')+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    binary=RUNTIME/'bin/swipl'
    with tempfile.TemporaryDirectory(prefix='lsg-original-train3-') as temp:
        work=Path(temp)
        for name,raw in files.items():
            dest=work/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(raw)
        (work/'original_train3_driver.pl').write_text(driver)
        result=subprocess.run([str(binary),'-q','-f','none','-s',str(work/'original_train3_driver.pl'),'-g','main'],
            cwd=work,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0 and 'ERROR' not in result.stderr, (result.returncode,result.stderr[-1500:])
    assert result.stdout.strip()=='[["has employed","Bob","Alice","terminate their contract","was diagnosed as disabled"]]', result.stdout
    native_prediction='Entailment'
    assert native_prediction==grade['answer']
    saved={r[0]:json.loads(r[8]) for r in before['calls'] if r[8]}
    wrong_ids=[
        'method_runtime_reference_v5_20261108:build:d2f0e6f9aa2313cc9a64ca5797a4dad55f20b51107fc77f63b09e58767ac52b0:0',
        'method_runtime_reference_v5_20261108:build:d2f0e6f9aa2313cc9a64ca5797a4dad55f20b51107fc77f63b09e58767ac52b0:1']
    raw_errors=[]
    for cid in wrong_ids:
        response=saved[cid]
        assert '1000' in response['content'] and response['finish_reason']=='stop'
        raw_errors.append({'call_id':cid,'content':response['content'],
            'content_sha256':hashlib.sha256(response['content'].encode()).hexdigest(),
            'actual_generation_finish_reason':'stop',
            'concrete_error':'A substituted an unrelated 1000-dollar threshold and case/year or service constants for the termination/death/disability condition.',
            'source_fact_ownership_also_invalid':True,'repaired_or_accepted':False})
    prior_teacher=saved['reference_pal_teacher_sara3_v2_20261108:compile']
    teacher_code=prior_teacher['value']['code']
    assert 'b_employer_payment and b_disability_retirement_termination' in teacher_code
    inherited={
        'native_source_sha256':hashlib.sha256(raw3306).hexdigest(),
        'original_TRAIN_case_member':member,'original_TRAIN_case_sha256':hashlib.sha256(native).hexdigest(),
        'original_TRAIN_case_text':text,'original_source_packet':source,
        'original_goal':original_goal[0],'exact_A_clause':a,'exact_parent_clause':parent,'exact_B_clause':b,
        'execution_driver':driver,'native_execution_stdout':result.stdout,'native_execution_stderr':result.stderr,
        'native_prediction':native_prediction,'already_cached_original_TRAIN_grade':grade,
        'raw_model_errors':raw_errors,
        'existing_teacher_target_control':{'call_id':'reference_pal_teacher_sara3_v2_20261108:compile',
            'code':teacher_code,'code_sha256':hashlib.sha256(teacher_code.encode()).hexdigest(),
            'saw_case_and_question_not_source_only_acquisition':True,
            'employer_payment_and_termination_condition_represented':True,
            'new_generation_or_new_execution_of_this_teacher_code':False,
            'not_an_independent_method_or_accepted_repair':True},
        'current_question_scope':'Original named A condition; not an inferred new whole-payment-exemption question.',
        'native_A_proof_witnesses':[{'employment':'has employed','employee':'Bob','employer':'Alice',
            'termination':'terminate their contract','cause':'was diagnosed as disabled'}],
        'additional_conditions_for_whole_parent_not_imposed_on_native_A_query':True,
        'raw_model_error_not_reclassified_as_correct_from_native_label_match':True,
        'native_reference_execution_not_model_main_path_success':True,
        'new_native_pair_or_counterfactual_created':False,
        'annotation_read_is_original_TRAIN_only':True,
        'annotation_date_not_claimed_as_public_text_extraction':'2019-10-10 payment date is in native TRAIN annotation, not explicit in public prose.',
        'TEST_or_DEV_read':False,
    }
    immutable_json(STAGE/'evidence.json',inherited)
    assert snapshot()==before
    report={
        'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'pending':0,'new_model_calls':0,'new_oracle_views':0,'new_original_sources':0,'new_native_pairs':0,
        'new_model_native_predictions_or_grades':0,
        'original_TRAIN_reference_cases_replayed':1,
        'original_TRAIN_cached_label_reused':True,'original_TRAIN_annotation_inspected':True,
        'original_TRAIN_ordinal':3,'source':key,'native_reference_prediction':native_prediction,
        'actual_model_semantic_failures_retained':len(raw_errors),
        'wrong_model_responses_were_complete_not_truncated':True,
        'native_A_does_not_depend_on_B_plan_witness':True,
        'not_a_new_zero_branch_failure_or_full_source_compilation_acceptance_gate':True,
        'not_a_new_method_or_main_path_model_success':True,
        'ordinary_target_specific_teacher_control_already_available':True,
        'two_contributions_established':False,'goal_complete':False,
        'ledger_rows_unchanged':True,'ledger_logical_sha256':digest(before),
        'evidence_path':str((STAGE/'evidence.json').relative_to(ROOT)),
        'current_next_research_question':'Can an acquired reusable legal rule preserve actor, causal and temporal bindings beyond ordinary source programmes on the original fixed tasks? Existing TRAIN3 semantic errors alone do not show such an advantage.',
        'new_source_collection_full_training_DEV_TEST_or_paper_started':False,
    }
    immutable_json(REPORT,report)
    print(json.dumps({k:report[k] for k in ['counts_total','new_model_calls','ledger_rows_unchanged','original_TRAIN_reference_cases_replayed','actual_model_semantic_failures_retained','native_A_does_not_depend_on_B_plan_witness','goal_complete']},ensure_ascii=False))


if __name__=='__main__':main()
