"""Bounded inventory of existing fixed-TRAIN executor responses, no new labels.

Counts refer to settled physical responses and ledger primary-source buckets.
Mixed compiler/fact responses, batch readers, local role values and executable
programs are distinct. A quote-origin diagnostic never changes a truth value.
"""
from collections import Counter,defaultdict
import hashlib,json,re,sqlite3
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'recorded_fact_inventory_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/recorded_fact_inventory_results.json'
OE21='method_runtime_reference_v7_20261109:build:281028f395a355b43c9bd9687f590b88def1eec1036adfea44eb99c815ced108:1'
A50='method_runtime_reference_v8_20261109:build:44082dd853cc0b2e5ed74e2155b2d50dac326bf4a792225ecca0b30c8feacc92:1'


def read(p):return json.loads(p.read_text())


def snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def public_parts(src):
    p=src['public'];dataset=src['dataset']
    if dataset=='SARA_v2_Binary':return [p['facts']],[p['rules']]
    if dataset=='RuleArena_Airline':return [p['prompt']],[p['rules']]
    if dataset=='ProofWriter_OWA_depth5':return p['facts'],p['rules']
    if dataset=='OpenExempt':
        facts=[];rules=[]
        for text in p['views'].values():
            a=text.index('Facts:')+len('Facts:');b=text.find('Output contract:',a)
            facts.append(text[a:b if b>=0 else None].strip());rules.append(text[:a])
        return facts,rules
    return [],[p.get('document','')]


def row_origin(row,facts,rules):
    value=row.get('value');quote=row.get('evidence',row.get('quote'))
    if value is None and not quote:return 'unknown_without_assertion'
    if not isinstance(quote,str) or not quote:return 'no_quote'
    if any(quote in text for text in facts):return 'exact_public_fact_substring'
    if any(quote in text for text in rules):return 'rule_only_substring'
    return 'not_exact_fact_quote_or_other_batch_scope'


def main():
    before=snapshot();assert not [r for r in before['calls'] if r[6]=='reserved']
    sources=read(BASE/'redesign_source_roles_v1_20261109/seal.json')['sources']['train']
    public={s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    index={s:i+1 for i,s in enumerate(sources)};records=[];shapes=Counter();raws={};status=Counter()
    for r in before['calls']:
        cid,role,_,_,key,_,state,_,payload=r
        if role!='executor' or key not in index:continue
        status[state]+=1
        if state!='completed':continue
        meta=json.loads(payload);content=meta.get('content','')
        row={'call_id':cid,'ledger_primary_source':key,'ordinal':index[key],'purpose':r[2],
            'finish_reason':meta.get('finish_reason'),'thinking_requested':meta.get('thinking_requested'),
            'content_sha256':hashlib.sha256(content.encode()).hexdigest()}
        try:value=json.loads(content)
        except (ValueError,TypeError,RecursionError) as e:
            row.update(kind='not_a_complete_JSON_object',decode_error=type(e).__name__);records.append(row);continue
        if not isinstance(value,dict):row.update(kind='other_JSON');records.append(row);continue
        shapes[tuple(sorted(value))]+=1;raws[cid]=(meta,value)
        observed=[]
        for field in ['observations','factual_observations']:
            if isinstance(value.get(field),list):
                observed.extend(o for o in value[field] if isinstance(o,dict) and 'name' in o and 'value' in o and (type(o['value']) is bool or o['value'] is None))
        if observed:
            facts,rules=public_parts(public[key]);names=Counter(o['name'] for o in observed)
            row.update(kind='reported_named_factual_values',reported_rows=len(observed),
                distinct_names=len(names),duplicate_names=sorted(k for k,n in names.items() if n>1),
                quote_origins=dict(Counter(row_origin(o,facts,rules) for o in observed)),
                mixed_with_programme_output=bool(set(value)&{'program_lines','code','nodes','query'}))
        elif set(value)=={'b_after_employment_termination','b_retirement_for_disability','b_termination_death'}:
            row.update(kind='keyed_factual_reader',reported_rows=len(value))
        elif set(value)&{'work_is_agricultural','agricultural_remuneration'}:
            row.update(kind='local_role_classifier_not_native_programme',reported_rows=2)
        elif set(value)&{'reported_birth_dates','co_residence_intervals','events'}:
            row.update(kind='event_frame_already_separately_audited')
        elif set(value)=={'cases'}:
            row.update(kind='batch_case_frame_not_one_native_source')
        elif set(value)=={'facts','unresolved'}:
            row.update(kind='signed_fact_reader')
        elif set(value)=={'bindings'} and value['bindings'] and isinstance(value['bindings'],list) and 'asset_span' in value['bindings'][0]:
            row.update(kind='asset_amount_span_reader')
        elif set(value)&{'entrypoint','entity_bindings'} or set(value)=={'bindings','unresolved'}:
            row.update(kind='call_routing_not_fact_truth')
        else:row.update(kind='source_programme_or_other_not_a_verified_fact_frame')
        records.append(row)
    named=[r for r in records if r['kind']=='reported_named_factual_values']
    factlike=[r for r in records if r['kind'] in {'reported_named_factual_values','keyed_factual_reader','local_role_classifier_not_native_programme','event_frame_already_separately_audited','batch_case_frame_not_one_native_source','signed_fact_reader','asset_amount_span_reader'}]
    # Concrete previously uncurated original OE21: every false value cites a
    # source rule rather than the case. Existing provenance checks reject this;
    # no automatic conversion of false to true is performed.
    meta,output=raws[OE21];request=read(Path(meta['artifact_directory'])/'request.json')
    tasks=json.loads(request['payload']['messages'][-1]['content'])['factual_observation_tasks']
    observations=output['factual_observations'];facts,rules=public_parts(public[sources[20]])
    assert len(tasks)==len(observations)==8 and all(o['value'] is False for o in observations)
    origins=[row_origin(o,facts,rules) for o in observations];assert origins==['rule_only_substring']*8
    # Exact shared semantic inputs (including predicate context) coalesce EC/EV
    # duplicates; do not assume equal words imply equal law across jurisdictions.
    groups=defaultdict(list)
    for task in tasks:
        semantic={k:task[k] for k in ['entity','predicate','fact_text','predicate_context','public_reference_years']}
        groups[digest(semantic)].append(task['name'])
    assert len(groups)==4 and sorted(map(len,groups.values()))==[2]*4
    oe={'call_id':OE21,'source':public[sources[20]],'actual_response':output,'actual_predicate_tasks':tasks,
        'all_eight_nonnull_quotes_are_rules_not_facts':True,
        'already_rejected_by_existing_exact_fact_quote_contract':True,
        'new_semantic_truth_values_or_native_grades_created':False,
        'same_input_duplicate_groups':list(groups.values()),
        'ordinary_exact_dedup_reduces_requests_for_values_from8_to4':True,
        'dedup_does_not_recover_truth_or_constitute_learning':True,
        'cross_jurisdiction_equivalence_not_assumed_from_the_word_apparel':True,
        'do_not_build_new_factoring_learner_before_this_control':True}
    immutable_json(STAGE/'original_OE21_provenance_and_exact_dedup.json',oe)
    # Original Airline50 is a separate source-defined exception issue. Inventory
    # the raw task/answer, without assigning geography labels from a fee label.
    ameta,avalue=raws[A50];ar=read(Path(ameta['artifact_directory'])/'request.json')
    au=json.loads(ar['payload']['messages'][-1]['content'])
    atasks=au.get('factual_observation_tasks',[])
    aobs=avalue['factual_observations'];assert atasks and aobs
    airline={'call_id':A50,'source':public[sources[49]],'actual_response':avalue,
        'actual_predicate_tasks':atasks,'new_native_or_feature_labels_created':False,
        'not_graded_as_old_M2_test_or_new_method_advantage':True,
        'next_control_required_before_any_noise_channel':'Ordinary structured route facts plus literal source exception conditions; native fee equality does not identify every primitive truth.',
        'new_model_calls':0}
    immutable_json(STAGE/'original_Airline50_pending_semantic_control.json',airline)
    frozen={'records':records,'response_shapes':[{'keys':list(k),'physical_response_count':n} for k,n in shapes.most_common()],
        'counts_by_kind':dict(Counter(r['kind'] for r in records)),'counts_by_settled_state':dict(status),
        'named_value_primary_ordinals':sorted({r['ordinal'] for r in named}),
        'factlike_primary_ordinals':sorted({r['ordinal'] for r in factlike}),
        'sample_counts_are_not_native_success_or_new_training_mothers':True,
        'ledger_primary_source_not_expanded_for_batch_variants':True,
        'no_declarations_promoted_to_observation_truth':True}
    immutable_json(STAGE/'frozen_inventory.json',frozen)
    assert before==snapshot()
    report={'counts_total':{role:sum(r[1]==role for r in before['calls']) for role in ['executor','teacher']},
        'pending':0,'new_model_calls':0,'new_oracle_views':0,'new_native_pairs_or_sources':0,
        'fixed_TRAIN_executor_calls_by_status':dict(status),
        'completed_fixed_TRAIN_responses_inventoried':len(records),
        'response_shapes':len(shapes),'response_kinds':frozen['counts_by_kind'],
        'reported_named_value_responses':len(named),'reported_named_value_rows':sum(r['reported_rows'] for r in named),
        'reported_named_value_unique_primary_sources':len({r['ordinal'] for r in named}),
        'factlike_physical_response_count':len(factlike),
        'factlike_unique_primary_sources':len({r['ordinal'] for r in factlike}),
        'not_independent_native_samples_or_accepted_IR':True,
        'OE21_old_failure_already_caught_by_existing_provenance_check':True,
        'OE21_ordinary_exact_semantic_input_dedup_counts':[8,4],
        'Airline50_primitive_truth_and_strong_control_still_require_review':True,
        'existing_20_source_inventory_not_extrapolated_to_all128':True,
        'new_core_mechanism_or_two_contributions_established':False,
        'ledger_rows_unchanged':True,'ledger_logical_sha256':digest(before),
        'TEST_DEV_or_grading_labels_read':False,'goal_complete':False}
    immutable_json(REPORT,report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
