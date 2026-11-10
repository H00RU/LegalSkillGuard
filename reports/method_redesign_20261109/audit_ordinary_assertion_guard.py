"""Execute the simple API/citation guard on actual recorded readers, no new calls."""
from copy import deepcopy
import hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import run
from experiments.rr_v2_ordinary_assertion_guard import guarded_case
from experiments.rr_v2_legal_auto_interface_fact_search import metadata

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'ordinary_assertion_guard_control_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/legal_evidence_contract_guard_control_results.json'


def read(p):return json.loads(p.read_text())


def ledger():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    before=ledger();p=read(BASE/'legal_auto_interface_audit_v1_20261110/frozen_library_and_cases.json')['warm_program']
    grades={r['ordinal']:r['cached_TRAIN_grade'] for r in read(ROOT/'reports/method_redesign_20261109/legal_auto_interface_results.json')['native_results']}
    results={};hashes={}
    for name,runid in [('ordinary','legal_evidence_contract_ordinary_v1_20261110'),
        ('ordinary_review','legal_evidence_contract_review_v2_20261110'),('guided','legal_evidence_contract_guided_v2_20261110')]:
        path=BASE/runid/'result.json';raw=read(path);original=deepcopy(raw);rows=[];hashes[runid]=hashlib.sha256(path.read_bytes()).hexdigest()
        for c in raw['cases']:
            case={**c['raw_case'],'query':c['query_reused_unchanged']};guarded,receipt=guarded_case(p,case)
            runtime={**guarded,'facts':guarded['facts']+metadata(guarded)};out=run(p,runtime);a=out['answer']
            if c['ordinal']==86 and a!='Entailment':a=None
            assert a==grades[c['ordinal']]
            assert not receipt['unhandled_head_predicates']
            if c['ordinal']==86:
                probe={**runtime,'query':{'predicate':'dependent','arguments':['Charlie','Bob','2015'],'positive':True}}
                assert run(p,probe)['answer']=='Contradiction'
            else:probe=None
            if c['ordinal']==81:
                ablate=deepcopy(p);ablate['rules']=[r for r in ablate['rules'] if r['head']['predicate']!='section_151c_applies'];ids={r['id'] for r in ablate['rules']}
                ablate['priorities']=[e for e in ablate['priorities'] if e['higher'] in ids and e['lower'] in ids]
                assert run(ablate,runtime)['answer'] is None
            rows.append({'ordinal':c['ordinal'],'original_raw_case':case,'guarded_case':guarded,'guard_receipt':receipt,
                'runtime_case':runtime,'execution':out,'native_prediction':a,'cached_TRAIN_grade':grades[c['ordinal']],
                'exception_probe_case':probe,'no_fallback_or_model_answer_used':True})
        assert raw==original and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[runid]
        results[name]={'native_correct':len(rows),'n':len(rows),'wrong_Charlie_dependent_quarantined_and_rules_refute_it':True,
            'source81_now_requires_actual151c_rule':True,'quarantined_rows_total':sum(len(r['guard_receipt']['quarantined']) for r in rows),'rows':rows}
    bundle={'program':p,'results':results,'raw_response_sha256':hashes,
        'guard_code_sha256':hashlib.sha256((ROOT/'experiments/rr_v2_ordinary_assertion_guard.py').read_bytes()).hexdigest(),
        'same_already_acquired_API_and_public_programme_for_all_arms':True,'teacher_evidence_table_not_used':True}
    immutable_json(STAGE/'frozen_guarded_execution.json',bundle);restored=read(STAGE/'frozen_guarded_execution.json')
    for r in restored['results'].values():
        for c in r['rows']:assert run(restored['program'],c['runtime_case'])==c['execution']
    assert before==ledger()
    report={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'new_model_calls':0,'new_native_grades':0,'new_oracle_views':0,'ledger_rows_unchanged':True,
        'ledger_logical_sha256':digest(before),'results':results,'guard_code_sha256':bundle['guard_code_sha256'],
        'actual_recorded_outputs_reexecuted_with_new_partial_rejection_path':True,
        'not_a_semantics_preserving_format_adaptation_or_original_raw_success':True,
        'no_bad_value_replaced_or_legal_rule_fabricated':True,'no_teacher_contract_or_handselected_foundational_predicate_list':True,
        'self_describing_names_and_explicit_citation_forms_assumed':True,
        'may_quarantine_valid_synonyms_and_miss_wrong_roles_despite_matching_words':True,
        'not_a_general_NL_fidelity_certificate_or_two_method_contributions':True,'goal_complete':False,
        'source_case_correctness_checked_separately_not_inferred_from_lexical_match':True,
        'scope_of_simple_control':'Only these three already-known TRAIN examples and actual self-describing API; no claim of new-case generalization.'}
    immutable_json(REPORT,report)
    print(json.dumps({'new_model_calls':0,'ledger_rows_unchanged':True,'results':{n:{k:r[k] for k in ['native_correct','n','quarantined_rows_total']} for n,r in results.items()},'not_a_general_semantic_validator':True},ensure_ascii=False))


if __name__=='__main__':main()
