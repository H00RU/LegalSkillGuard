"""Counterprobe recorded fact channels, without a model call or a new grade.

The rejected first reader is used only for diagnostic execution. Its rows are
never accepted, repaired, or substituted into the recorded native results.
"""
from copy import deepcopy
import hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.legal_predicate_skills import run
from experiments.rr_v2_legal_auto_interface_fact_search import metadata

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_fact_boundary_audit_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_recorded_status_promotions_results.json'


def read(p):return json.loads(p.read_text())


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=ledger()
    oldpath=BASE/'legal_auto_interface_reader_v2_20261110/execution_closed_before_grading.json'
    newpath=BASE/'legal_auto_interface_fact_search_v1_20261110/execution_closed_before_grading.json'
    frozenpath=BASE/'legal_auto_interface_audit_v1_20261110/frozen_library_and_cases.json'
    old=read(oldpath);new=read(newpath);frozen=read(frozenpath)
    material=read(BASE/'legal_auto_interface_reader_v2_20261110/seal.json')['material']
    assert [r['ordinal'] for r in old['cases']]==[81,86,72]
    assert [r['ordinal'] for r in new['cases']]==[81,86,72]
    assert all(r['status']=='rejected' for r in old['cases'])
    probes=[]
    for index in [0,1]:
        row={'ordinal':[81,86][index],'raw_reader_remains_rejected':True}
        programme=deepcopy(frozen['warm_program'])
        if index==0:
            removed=[r['id'] for r in programme['rules'] if r['head']['predicate']=='section_151c_applies']
            programme['rules']=[r for r in programme['rules'] if r['id'] not in removed]
            ids={r['id'] for r in programme['rules']}
            programme['priorities']=[e for e in programme['priorities'] if e['higher'] in ids and e['lower'] in ids]
            row.update(intervention='remove actual151c applicability rule',removed_rules=removed)
            assert removed==['r151c_applicability']
        else:row.update(intervention='query152b1 exception consequence, keeping actual reused priorities')
        for name,records in [('raw_rejected',old),('real_fact_only',new)]:
            case=deepcopy(records['cases'][index]['raw_case'])
            case['query']=deepcopy(old['cases'][index]['raw_case']['query'])
            case['facts']+=metadata(case)
            if index==1:case['query']={'predicate':'dependent','arguments':['Charlie','Bob','2015'],'positive':True}
            result=run(programme,case)
            row[name]={'answer':result['answer'],'runtime_case':case,'execution':result,
                'not_a_new_native_grade':True,'not_fallback_or_semantic_frame_repair':True}
        if index==0:
            assert row['raw_rejected']['answer']=='Entailment' and row['real_fact_only']['answer'] is None
        else:
            assert row['raw_rejected']['answer'] is None and row['real_fact_only']['answer']=='Contradiction'
        probes.append(row)
    # Syntactic provenance cannot certify that an assertion is a factual premise.
    quote_rows=[]
    for c,m in zip(old['cases'],material):
        for f in c['raw_case']['facts']:
            quote_rows.append({'ordinal':c['ordinal'],'predicate':f['atom']['predicate'],
                'literal_fact_quote':bool(f['quote']) and f['quote'] in m['facts']})
    assert all(r['literal_fact_quote'] for r in quote_rows if r['ordinal'] in [81,86])
    leaks=[r for r in quote_rows if not r['literal_fact_quote']]
    assert leaks==[{'ordinal':72,'predicate':'exemption_amount','literal_fact_quote':False}]
    heads={r['head']['predicate'] for r in frozen['cold_program']['rules']}
    bodies={a['predicate'] for r in frozen['cold_program']['rules'] for a in r['body']}
    # These are unchanged, actual second-reader premises, independently reviewed
    # against their fact texts in the preceding audit; no new values are filled.
    explicit_also_derived=[]
    for c in new['cases']:
        for f in c['raw_case']['facts']:
            if f['atom']['predicate'] in heads:
                explicit_also_derived.append({'ordinal':c['ordinal'],'actual_fact':f})
    assert [(r['ordinal'],r['actual_fact']['atom']['predicate']) for r in explicit_also_derived]==[
        (81,'dependent'),(72,'deduction_under_151_allowable_to')]
    result={'existing_mothers':[81,86,72],'new_model_calls':0,'new_native_grades':0,'new_oracle_views':0,
        'ledger_unchanged':ledger()==before,'rejected_raw_frames_not_accepted':True,
        'counterprobes_not_new_native_cases_or_original_result_changes':True,'probes':probes,
        'quote_presence_checks':quote_rows,'question_only_leak_already_caught_by_existing_validator':leaks,
        'body_only_input_predicates':sorted(bodies-heads),'explicit_premises_also_in_rule_heads':explicit_also_derived,
        'reject_all_rule_head_predicates_would_discard_valid_actual_premises':True,
        'ordinary_real_fact_search_with_author_concept_guidance_already_solves_these_instances':True,
        'automatically_learned_fact_boundary_or_new_method_advantage_not_established':True,
        'next_question':'Can source-grounded evidence modes reduce these legal-status promotions beyond the same-information ordinary fact-only reader and definition lookup?',
        'not_a_new_zero_hint_or_full_automation_acceptance_requirement':True,
        'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [oldpath,newpath,frozenpath]},
        'two_method_contributions_established':False,'goal_complete':False,'TEST_labels_read':False}
    assert result['ledger_unchanged']
    immutable_json(STAGE/'recorded_fact_channel_counterprobes.json',result)
    immutable_json(REPORT,result)
    print(json.dumps({'new_model_calls':0,'ledger_unchanged':True,'probes':[
        {'ordinal':r['ordinal'],'raw_rejected':r['raw_rejected']['answer'],'real_fact_only':r['real_fact_only']['answer']} for r in probes],
        'valid_explicit_premises_that_head_subtraction_loses':[r['actual_fact']['atom']['predicate'] for r in explicit_also_derived]},ensure_ascii=False))


if __name__=='__main__':main()
