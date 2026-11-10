"""Review the real ordinary-cache acquisition without promoting a new method."""
import hashlib,json,sqlite3
from pathlib import Path
from experiments.rr_v2_contract_norm_cache import execute
from experiments.rr_v2_legal_independent_cache import execute_code
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
SOURCE=BASE/'contract_norm_cache_v1_20261110';STAGE=BASE/'contract_norm_cache_audit_v1_20261110'
BACKUP=Path('/media/sangfor/vdb/legal-skill-backups/contract_norm_cache_20261110')
REPORT=ROOT/'reports/method_redesign_20261109/contract_norm_cache_results.json'


def read(p):return json.loads(p.read_text())


def ledger(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
        return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
    dbpath=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    before=ledger(BACKUP/'ledger.before.sqlite3');after=ledger(dbpath)
    assert not any(r[6]=='reserved' for r in after['calls'])
    assert all(r in after['calls'] for r in before['calls']) and all(r in after['meta'] for r in before['meta'])
    assert before['oracle_views']==after['oracle_views']
    delta=[r for r in after['calls'] if r not in before['calls']]
    assert len(delta)==1 and delta[0][0]=='contract_norm_cache_v1_20261110:source' and delta[0][1]=='teacher' and delta[0][6]=='completed'
    seal=read(SOURCE/'seal.json');raw=read(SOURCE/'source.json');value=raw['value']
    for path,sha in seal['files'].items():assert hashlib.sha256((SOURCE/'frozen'/path).read_bytes()).hexdigest()==sha
    assert raw['all_controls_passed'] and raw['status']=='captured_pending_source_semantic_review'
    interface={p['name']:p for p in value['interface']};source_review=[]
    for policy,source in zip(value['policies'],seal['material']):
        assert policy['source_quote'] in source['contract']
        exception=interface[policy['exception_atom']['predicate']]
        source_review.append({'policy_id':policy['policy_id'],'source_quote':policy['source_quote'],
            'exception_interface':exception,'exception_atom':policy['exception_atom'],
            'bounded_author_review':'Source qualifications preserved in the meaning of one complete-exception predicate. The program consumes an explicit signed assertion of that whole condition; it does not infer the composite condition from partial events.',
            'source_to_native_query_mapping_not_independently_generated':True})
    # The meaning strings are part of the actual model output. These checks
    # locate the clauses reviewed by the author, not an NL fidelity certificate.
    assert all(s in source_review[0]['exception_interface']['meaning'] for s in ['Discloser','in advance','in writing','specifically'])
    assert all(s in source_review[1]['exception_interface']['meaning'] for s in ['pursuant','mutually acceptable','written','executed'])
    immutable_json(STAGE/'source_semantic_review.json',{'reviews':source_review,
        'approved_only_for_supplied_complete_exception_interface':True,
        'author_supplied_two_query_views_and_reverse_engineering_target_hint':True,
        'actual_event_reader_and_native_question_mapper_not_validated':True,
        'no_full_contract_source_equivalence_or_new_method_claim':True})
    bundle={'value':value,'policies':seal['material'],'source_ids':seal['source_ids'],
        'source_response_sha256':hashlib.sha256((SOURCE/'source.json').read_bytes()).hexdigest(),
        'code_sha256':hashlib.sha256(value['code'].encode()).hexdigest()}
    immutable_json(STAGE/'frozen_ordinary_cache.json',bundle)
    restored=read(STAGE/'frozen_ordinary_cache.json');assert restored==bundle
    cold=execute(restored['value'],seal);assert cold==raw['controls']
    assert all(r['passed'] for r in cold) and len(cold)==16
    sources=[p['contract'] for p in seal['material']];scope=[]
    for i,policy in enumerate(value['policies']):
        other=value['policies'][1-i]
        foreign=[{'atom':other['exception_atom'],'quote':'SOFTWARE assumption about other policy'}]
        foreign_result=execute_code(value['code'],foreign,policy['applicability_query'],sources)
        assert foreign_result['answer'] is None
        changed=json.loads(json.dumps(policy['exception_atom']))
        changed['arguments'][2]='unsupported_other_authorizer_or_counterparty'
        incomplete=execute_code(value['code'],[{'atom':changed,'quote':'SOFTWARE nonmatching qualified exception'}],policy['applicability_query'],sources)
        assert incomplete['answer'] is None
        scope.append({'policy_id':policy['policy_id'],'foreign_exception_answer':foreign_result['answer'],
                      'nonmatching_qualified_exception_answer':incomplete['answer'],
                      'software_scope_checks_not_native_samples':True})
    immutable_json(STAGE/'frozen_replay_and_scope_controls.json',{'cold_equals_original_execution':True,
        'controls':cold,'scope_checks':scope,'new_model_calls':0,'new_native_grades':0})
    wire=raw['physical_response'];inv=wire['invocation'];usage=inv['usage']
    assert inv['attempt']==1 and not inv['tool_events_detected'] and wire['cache_hit'] is False
    new_meta=[r for r in after['meta'] if r not in before['meta']]
    assert len(new_meta)==1 and len(after['calls'])==1465 and len(after['meta'])==225 and len(after['oracle_views'])==136
    result={'counts_total':{role:sum(r[1]==role for r in after['calls']) for role in ['executor','teacher']},
        'pending':0,'new_charged_attempts':{'executor':0,'teacher':1},'visible_teacher_dispatches':1,
        'teacher_provider_internal_retries_observable':False,'new_counterfactual_oracle_views':0,'new_native_grades':0,
        'actual_old_TRAIN_ordinals':[111,115],'new_sources':0,'new_native_pairs':0,
        'source_only_ordinary_cache_actually_acquired':True,'model_generated_interface_predicates':len(value['interface']),
        'given_query_modes_and_target_hint_not_claimed_learned':True,'source_conditions_learned_as_complete_compound_predicates':True,
        'subconditions_not_independently_parsed_or_conjunctively_learned':True,
        'source_semantic_review_bounded_not_full_contract_certificate':True,'software_execution_controls_passed':16,
        'additional_software_scope_controls_passed':4,'cold_frozen_replay_equal':True,
        'normative_exists_with_unknown_exception':'Entailment','operative_applicability_with_unknown_exception':None,
        'exception_disables_this_ban_not_whole_action_permission':True,
        'actual_event_reader_or_native_question_mapper_learned_this_turn':False,
        'new_executor_IR_claim':False,'new_method_contribution_claim':False,'two_contributions_established':False,
        'old_rows_preserved':True,'ledger_counts':{k:len(v) for k,v in after.items()},
        'costs':{'executor_new_API_cash_usd':0,'teacher_invoice_usd':None,'GPU_allocation_usd':None,
                 'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens'],
                 'reasoning_output_tokens_subset':usage['reasoning_output_tokens'],
                 'elapsed_seconds':wire['elapsed_seconds'],'visible_attempts':inv['attempt']},
        'old_call_rows':len(before['calls']),'new_call_ids':[r[0] for r in delta],
        'new_policy_meta_rows':len(new_meta),'TEST_or_DEV_labels_opened':False,
        'main_training_started':False,'goal_complete':False}
    immutable_json(REPORT,result)
    immutable_json(STAGE/'charged_delta.json',{'new_call_rows':delta,'new_policy_meta_keys':[r[0] for r in new_meta],
        'all_old_calls_and_meta_preserved':True,'oracle_rows_unchanged':True})
    target=BACKUP/'ledger.after.sqlite3'
    if not target.exists():
        with sqlite3.connect('file:'+str(dbpath)+'?mode=ro',uri=True) as db,sqlite3.connect(target) as dest:db.backup(dest)
    assert ledger(target)==after
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
