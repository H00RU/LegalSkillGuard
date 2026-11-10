"""Ordinary fact-only repair using the same foundational fact scope as the candidate.

The source cache keeps its actual independently acquired vocabulary and roles.
This is a strong-control reader repair, not a new method or a hidden raw-frame
rewrite. Previously inferred assertions and question-derived facts remain saved.
"""
import argparse,hashlib,json
from itertools import permutations
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import FACT,validate_case,validate,run
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='legal_auto_interface_fact_search_v1_20261110';STAGE=BASE/RUN
PARENT=BASE/'legal_auto_interface_cache_v1_20261110'
OLD=BASE/'legal_auto_interface_reader_v2_20261110'
NAMES=['case_subject_year','qualifying_child','qualifying_relative','dependent','deduction_under_151_allowable_to','taxable_year_begins_in_2018_through_2025']
SCHEMA=obj({'cases':{'type':'array','items':obj({'ordinal':{'type':'integer'},'facts':{'type':'array','items':FACT},'unresolved':{'type':'array','items':{'type':'string'}}})}})


def read(p):return json.loads(p.read_text())


def metadata(case):
    roster=sorted({tuple(r['atom']['arguments']) for r in case['facts'] if r['atom']['predicate']=='case_subject_year' and r['atom']['positive']})
    people=sorted({p for p,y in roster});out=[]
    for p,y in roster:
        if len(y)!=4 or not y.isdigit():raise ValueError('Native annual-year metadata requires a four-digit year')
        out.append({'atom':{'predicate':'taxable_year_begins_in_calendar_year','arguments':[p,y,y],'positive':True},
            'quote':'native SARA annual calendar-year representation; from checked roster'})
    for a,b in permutations(people,2):
        out.append({'atom':{'predicate':'different','arguments':[a,b],'positive':True},
            'quote':'native distinct canonical person identifiers; from checked roster'})
    return out


def prepare():
    old=read(OLD/'seal.json');adapted=read(PARENT/'literal_programme_provenance_adaptation.json')
    assert adapted['status']=='full_structure_and_active_rule_smoke_passed_not_semantic_certificate'
    byname={p['name']:p for p in old['interface']};inputs=[byname[n] for n in NAMES]
    # These concepts were also supplied to the original candidate reader. This
    # classification is a shared source/task contract, not autonomous learning.
    system=(
        'Search only the three FACT TEXTS for explicit factual assertions using the supplied ordinary cache input interface. '
        'Questions, requested answers, source rule bodies and cached target labels are deliberately absent. '
        'This foundational input-concept scope is the same one used by the original relation reader; the predicate names and ordered roles here are the newly acquired cache API. '
        'Return only those supplied predicates. Do not derive legal consequences or emit section_*_applies, deduction amounts or target assertions. '
        'A statement that someone satisfies section152(c)(1) is an expressly given qualifying-child status for the named claimant; it is not by itself an asserted dependent status after other exceptions. '
        'Emit dependent only when the FACT TEXT explicitly calls that individual the claimant\'s dependent. '
        'An explicit entitlement to an exemption for another individual under151 is the supplied allowance-status input, not an assertion that151(d)(2) or151(d)(5) applies. '
        'Respect the actual role order: child/relative/subject first, claimant second for this cache. Do not copy the order of a different API. '
        'case_subject_year enumerates every person and explicit annual year in the facts. Distinct-identifier and annual-calendar-year metadata are supplied by the common deterministic task adapter, so do not invent separate predicates. '
        'No missing status is false. The2018-through2025 input requires explicit period-classification evidence; do not invent it from an ordinary year mention. '
        'Each substantive fact quote must be a nonempty exact substring of its own fact text. No extra predicates, tools, browsing, inference or final answers.')
    material=[{'ordinal':c['ordinal'],'facts':c['facts']} for c in old['material']]
    user=json.dumps({'input_interface':inputs,'case_fact_texts':material,'expected_ordinals':[81,86,72]},ensure_ascii=False)
    protocol=ROOT/'reports/method_redesign_20261109/legal_auto_interface_fact_search_protocol.md'
    paths=['experiments/rr_v2_legal_auto_interface_fact_search.py','legal_skill_guard/rr/ordinary_rule_literal.py','legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    validate(adapted['program'],[p['rules'] for p in old['source_policies']])
    fixture={'facts':[{'atom':{'predicate':'case_subject_year','arguments':['A','2015'],'positive':True},'quote':'fixture'},
        {'atom':{'predicate':'case_subject_year','arguments':['B','2015'],'positive':True},'quote':'fixture'}]}
    assert len(metadata(fixture))==4
    assert all(r['atom']['predicate'] in ['different','taxable_year_begins_in_calendar_year'] for r in metadata(fixture))
    s={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source_ids':old['source_ids'],'source_policies':old['source_policies'],
        'api':old['interface'],'input_interface':inputs,'program':adapted['program'],'adaptation':adapted['adaptation'],
        'old_model_queries':{str(c['ordinal']):c['raw_case']['query'] for c in read(OLD/'execution_closed_before_grading.json')['cases']},
        'original_material':old['material'],'messages':[{'role':'system','content':system},{'role':'user','content':user}],
        'schema':SCHEMA,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'thinking':False,
        'common_fact_concept_scope_given_not_claimed_automatically_discovered':True,
        'no_questions_rule_bodies_or_native_labels_in_prompt':True,'offline_structural_assertions':2,'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'offline_source_and_metadata_checks':True,'new_model_calls':0}));return
    path=STAGE/'execution_closed_before_grading.json'
    if path.exists():print(json.dumps({'existing':str(path),'no_redispatch':True}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Ordinary fact-only source-grounded reader repair after the actual cache reader inferred derived legal facts and copied the query. Same basic input concepts as candidate, own newly generated API roles, shared explicit native structural metadata, no questions/answers. Preserve bad outputs; no semantic value repair.')
    e=MethodExecutor(l,STAGE,s['config']['executor']);e.readiness()
    w=e.generate(RUN+':reader',source=s['source_ids'][0],purpose='method_primitive_observation',messages=s['messages'],thinking=False,schema=s['schema'])
    result={'physical_response':w,'cases':[],'native_labels_opened':False,'new_oracle_views':0,'goal_complete':False}
    try:
        cases=json.loads(w['content'])['cases']
        if [c['ordinal'] for c in cases]!=[81,86,72]:raise ValueError('Case order changed')
        for c,m in zip(cases,s['original_material']):
            q=s['old_model_queries'][str(c['ordinal'])];case={**c,'query':q};row={'ordinal':c['ordinal'],'raw_case':c,'old_unchanged_query':q}
            try:
                if any(f['atom']['predicate'] not in NAMES for f in c['facts']):raise ValueError('Unsupported or derived predicate in fact-only output')
                validate_case(case,m['facts'],{p['name']:p for p in s['api']})
                meta=metadata(c);execution_case={**case,'facts':c['facts']+meta}
                out=run(s['program'],execution_case)
                answer=out['answer']
                # Original86's model query binds an unasked claimant. A proven
                # witness entails the native existential; its negation does not.
                if c['ordinal']==86 and answer!='Entailment':answer=None
                row.update(status='executed_pending_independent_semantic_review',output=out,native_prediction=answer,
                    deterministic_task_metadata=meta,raw_model_facts_unchanged=True,extra_bound_claimant_positive_witness_lift_only=c['ordinal']==86)
            except Exception as exc:row.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
            result['cases'].append(row)
    except Exception as exc:result.update(error_type=type(exc).__name__,error=str(exc))
    immutable_json(path,result)
    print(json.dumps({'cases':[{'ordinal':c['ordinal'],'status':c['status'],'prediction':c.get('native_prediction'),'error':c.get('error')} for c in result['cases']],'native_labels_opened':False},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','generate']);main(p.parse_args().action)
