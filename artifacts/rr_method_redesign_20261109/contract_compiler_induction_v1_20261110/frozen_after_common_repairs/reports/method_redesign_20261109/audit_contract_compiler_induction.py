"""Replay learned procedures after common fixes; retain source-only failures.

No new model, native pair or label is obtained. TRAIN fit, query-local recovery,
source-only reuse and a validated contribution are separate evidence categories.
"""
import copy,hashlib,json,sqlite3
from pathlib import Path
from experiments.rr_v2_contract_compiler_induction import evaluate
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_compiler_runtime import offline,resolve_existing_return_reference,scope_answer
from legal_skill_guard.rr.contract_scope_learning import validate,execute
from legal_skill_guard.rr.coverage import digest

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'contract_compiler_induction_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/contract_compiler_induction_results.json'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}

def regressions():
    base=offline();text='SOFTWARE: return is required; an archive copy may remain.'
    scope={'id':'s','domains':['recipient'],'source_quotes':[text]}
    ret={'id':'return','effect':'obligation','action':'return_or_destroy','scope_id':'s','triggers':['termination'],
         'conditions':[],'source_quotes':[text],'overrides':[]}
    keep={'id':'retain','effect':'permission','action':'retain','scope_id':'s','triggers':['after_return_or_destruction'],
          'conditions':[],'source_quotes':[text],'overrides':['return or destruction obligation']}
    graph={'policy_id':'software','scopes':[scope],'rules':[ret,keep],'complete_query_ids':['nda-16','nda-20'],'unresolved':[]}
    bound,changes=resolve_existing_return_reference(graph)
    assert len(changes)==1 and bound['rules'][1]['overrides']==['return'];validate(bound,text)
    ambiguous=copy.deepcopy(graph);ambiguous['rules'].append({**ret,'id':'return2'})
    b,c=resolve_existing_return_reference(ambiguous);assert not c and b['rules'][1]['overrides']==['return or destruction obligation']
    try:scope_answer(ambiguous,text,'nda-20')
    except ValueError:pass
    else:raise AssertionError('An ambiguous reference was guessed')
    partial=copy.deepcopy(bound)
    partial['scopes'].append({'id':'third','domains':['third_parties'],'source_quotes':[text]})
    partial['rules'].append({'id':'share','effect':'permission','action':'share','scope_id':'third','triggers':['unconditional'],
                           'conditions':[],'source_quotes':[text],'overrides':['not_declared']})
    try:validate(partial,text)
    except ValueError:pass
    else:raise AssertionError('Malformed whole graph was accepted')
    assert scope_answer(partial,text,'nda-16')['answer']==execute(bound,text,'nda-16')['answer']
    try:scope_answer(partial,text,'nda-7')
    except ValueError:pass
    else:raise AssertionError('Query-relevant missing target was ignored')
    for q in ['nda-16','nda-20']:
        old=execute(bound,text,q);new=scope_answer(bound,text,q)
        assert all(old[k]==new[k] for k in ['answer','evidence','rule_ids','preserved_conditions'])
    return {**base,'unique_existing_target_only':True,'ambiguous_and_missing_target_still_rejected':True,
      'malformed_whole_graph_not_reclassified_valid':True,'query_slice_used_path_semantics_retained':True,
      'fixtures_are_software_not_native_cases_or_training_data':True}

def main():
    dbpath=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3';before=snapshot(dbpath)
    baseline=snapshot(Path('/media/sangfor/vdb/legal-skill-backups/contract_compiler_induction_20261110/ledger.before.sqlite3'))
    assert not [r for r in before['calls'] if r[6]=='reserved']
    assert all(r in before[t] for t in baseline for r in baseline[t])
    added={t:[r for r in before[t] if r not in baseline[t]] for t in before}
    assert len(added['calls'])==2 and all(r[1]=='teacher' and r[6]=='completed' for r in added['calls'])
    assert len(added['meta'])==1 and not added['oracle_views']
    seal=read(STAGE/'training_seal.json');arms={};state={}
    for arm in ['scope_compiler','ordinary_program']:
        path=STAGE/(arm+'_learned.json');raw=read(path);wire=raw['physical_response'];value=wire['value']
        rows,graphs=evaluate(arm,value['code'],seal['training']);again,again_graphs=evaluate(arm,value['code'],seal['training'])
        assert rows==again and graphs==again_graphs
        arms[arm]={'initial_saved_status':raw['status'],'initial_saved_error':raw.get('error'),
          'initial_fit_count_if_executed':raw.get('train_correct'),'initial_executed':raw.get('train_executed',0),
          'after_common_repairs_TRAIN_correct':sum(r['native_correct'] for r in rows),
          'after_common_repairs_TRAIN_executed':sum(r['executed'] for r in rows),'TRAIN_n':8,'TRAIN_mothers':4,
          'rows':rows,'cold_replay_equal':True,'programme_code_unchanged':True,'new_programme_generation_for_repairs':0,
          'usage':wire['invocation']['usage'],'elapsed_seconds':wire['elapsed_seconds'],
          'actual_teacher_invoice_usd':None,'provider_internal_retries_observable':False,
          'input_plus_output_tokens':wire['invocation']['usage']['input_tokens']+wire['invocation']['usage']['output_tokens']}
        state[arm]={'value':value,'raw_learned_artifact_sha256':sha(path),
           'code_sha256':hashlib.sha256(value['code'].encode()).hexdigest(),'TRAIN_fit_after_common_repairs':arms[arm]['after_common_repairs_TRAIN_correct']}
    for arm in arms:
        assert arms[arm]['after_common_repairs_TRAIN_executed']==(4 if arm=='scope_compiler' else 8)
    source_only=read(STAGE/'source_only_15_20_raw_graphs.json')
    evidence=[]
    for record in source_only['results']:
        graph=record['result'].get('value',{})
        if record['arm']=='ordinary_program' and record['ordinal']==15:
            matches=[r for r in graph['rules'] if r['effect']=='permission' and any('Except as provided herein' in q for q in r['source_quotes'])]
            assert len(matches)==1
            evidence.append({'ordinal':15,'arm':'ordinary_program','actual_emitted_rule':matches[0],
              'source_check':'The quoted clause states a prohibition with a reference to existing exceptions, not a new direct grant. Its conditional authorization must be resolved through the actual referenced source; the emitted generic permission and override do not supply that support.',
              'not_a_new_native_NLI_label_or_global_claim_that_no_consent_permission_exists':True})
        if record['arm']=='ordinary_program' and record['ordinal']==20:
            matches=[r for r in graph['rules'] if r['effect']=='prohibition' and any('shall not have breached' in q for q in r['source_quotes'])]
            assert len(matches)==1
            evidence.append({'ordinal':20,'arm':'ordinary_program','actual_emitted_rule':matches[0],
              'source_check':'The negated predicate is breach of an obligation; disclosure is embedded in the condition. This passage does not assert a conduct prohibition. An exemption/absence of breach is not silently relabeled permission either.',
              'not_a_new_native_NLI_label':True})
        if record['arm']=='scope_compiler' and record['ordinal']==20:
            assert not [r for r in graph['rules'] if r['action']=='retain' and r['effect']=='permission']
            evidence.append({'ordinal':20,'arm':'scope_compiler','actual_emitted_rules':graph['rules'],
              'source_check':'The source explicitly allows a record copy required by applicable law under paragraph 6. The parser misses this paragraph-reference retention permission and attaches termination to a later obligation concerning expiry of the legal retention period.',
              'not_a_new_native_NLI_label':True})
    assert len(evidence)==3
    runtime_path=ROOT/'legal_skill_guard/rr/contract_compiler_runtime.py'
    repair={'original_training_runtime_sha256':seal['files']['legal_skill_guard/rr/contract_compiler_runtime.py'],
      'repaired_runtime_sha256':sha(runtime_path),'both_learned_programmes_unchanged':True,
      'changes':['Recognize nested helper names promised by the shared programme API.',
                 'Bind the observed return-or-destruction descriptor only to a unique existing same-quote obligation.',
                 'Validate every used query-local dependency, retain unrelated malformed whole graphs as malformed; do not impose an unrelated whole-source gate.'],
      'missing_general_nondisclosure_targets_not_created':True,'ambiguous_reference_not_guessed':True,
      'no_native_answers_used_in_adaptation':True,'remaining_candidate_unresolved_TRAIN_mothers':[5,10],
      'candidate_recovered_query_local_TRAIN_mother':111,'model_calls_for_common_repairs':0}
    checks=regressions()
    immutable_json(STAGE/'common_runtime_repair_evidence.json',{**repair,'regressions':checks})
    immutable_json(STAGE/'current_compiler_state.json',{'learned':state,'runtime_sha256':sha(runtime_path),
      'training_seal_sha256':sha(STAGE/'training_seal.json'),'repaired_execution_not_original_full_graph_acceptance':True,
      'DEV_started':False,'first_contribution_established':False,'goal_complete':False})
    for path in ['legal_skill_guard/rr/contract_compiler_runtime.py','reports/method_redesign_20261109/audit_contract_compiler_induction.py']:
        dest=STAGE/'frozen_after_common_repairs'/path;dest.parent.mkdir(parents=True,exist_ok=True)
        raw=(ROOT/path).read_bytes()
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
    primary=[
      {'work':'RuleChef','url':'https://arxiv.org/html/2607.01293v1','scope':'Executable rule/program induction and failure-driven incremental patching already exist.'},
      {'work':'Evaporate-Code+','url':'https://www.vldb.org/pvldb/vol17/p92-arora.pdf','scope':'Reusable model-generated extraction programs are not a new contribution.'},
      {'work':'SG-DT/NormBench official core-predicate and empty-effect rules',
       'url':'https://github.com/AlexJJJChen/NormBench/blob/bd56aff7eb9518db02b10e189576331f271564cc/benchmark/article2unit2structure/prompts/stage1_major_premise_extraction.md#L656',
       'scope':'Classify the actual normative predicate; separate conditions and consequences; a referential exception with no replacement consequence has empty effects. These guards alone are not new learning.'},
      {'work':'Definitional Prefix official code','url':'https://github.com/computerlawyer/definitional-prefix/blob/5e661f91bc12318d5e00ca4792334abfd96617dc/official/pipeline/dcp.py',
       'scope':'Canonical parties and definition gloss are an existing baseline; lack of explicit executable owner slots alone is not evidence of an observed role-binding failure.'}]
    immutable_json(STAGE/'source_only_semantic_review.json',{'evidence':evidence,'mothers':2,'ordinals':[15,20],
      'source_only_no_native_question_predictions_or_labels':True,'primary_related_work':primary,
      'candidate_not_promoted':True,'ordinary_TRAIN8_fit_not_general_source_correctness':True,
      'remaining_scientific_object':'Composition attachment: which predicate is negated, whether an action is a condition or a normative consequence, and which source an exception references.',
      'concrete_learning_update_not_yet_supported_beyond_independent_program_patch_and_SG_DT_controls':True})
    assert not (STAGE/'DEV_freeze.json').exists() and not (STAGE/'DEV_native_score.json').exists()
    assert before==snapshot(dbpath)
    out={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},'pending':0,
      'new_charged_attempts':{'executor':0,'teacher':2},'new_native_label_views':0,'ledger_rows':{t:len(v) for t,v in before.items()},
      'old_ledger_rows_preserved':True,'ledger_logical_sha256':digest(before),'arms':arms,'common_repairs':repair,
      'TRAIN_fit_not_validation':True,'training_materials_same_and_acquisitions_independent':True,
      'TRAIN_native_supervision_shared_with_both_learners':True,'source_only_reuse_mothers':2,'source_only_native_pairs_added':0,
      'source_only_manual_qualitative_checks':evidence,'new_model_calls_for_source_only_reuse':0,
      'related_work_guards_not_promoted_as_new_contribution':True,'DEV_started':False,'DEV_labels_opened':False,
      'DEV_harness_archived_unexecuted':True,'TEST_started':False,'new_full_training':False,
      'first_contribution_established':False,'two_contributions_established':False,'goal_complete':False,
      'decision':'Do not expand graph/code format comparisons or refit these visible answers. Reuse the learned ordinary procedure as a strong common component; any next candidate must supply a concrete compositional-attachment learning/update algorithm and face ordinary patching plus SG-DT controls. No new real call is currently justified merely by the source errors.'}
    immutable_json(STAGE/'post_repair_TRAIN_replay_and_scope_review.json',out);immutable_json(REPORT,out)
    backup=Path('/media/sangfor/vdb/legal-skill-backups/contract_compiler_induction_20261110/ledger.after.sqlite3')
    if not backup.exists():
        with sqlite3.connect(dbpath) as s,sqlite3.connect(backup) as d:s.backup(d)
    print(json.dumps({'counts':out['counts_total'],'rows':out['ledger_rows'],'post_repairs_TRAIN_fit':{a:[v['after_common_repairs_TRAIN_correct'],8] for a,v in arms.items()},
       'source_only_mothers':[15,20],'DEV_started':False,'new_source_native_pairs':0,'goal_complete':False},ensure_ascii=False))

if __name__=='__main__':main()
