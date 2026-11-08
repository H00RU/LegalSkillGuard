"""Specific paid-response format recovery, offline; never a fresh model run."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.pal_frontend import parse_pal
from legal_skill_guard.rr.rule_templates import matching_rule_template,instantiate_rule_template
from legal_skill_guard.rr.source_execution import accept_followup,assess_source

ROOT=Path(__file__).resolve().parents[2]
base=ROOT/'artifacts/rr_method_runtime_20261107/reference_instance_sara79_v12_20261108'
seal=json.loads((base/'seal.json').read_text());library=seal['config']['library']
paid=[json.loads((base/'calls'/digest(base.name+':parse:'+str(i))/'result.json').read_text()) for i in range(2)]
value=json.loads(paid[0]['content']);program,compiled,_=instantiate_rule_template(seal['source'],matching_rule_template(seal['source'],library),value)
prepared=json.loads((base/'request1.json').read_text())['prepared'];raw=json.loads(paid[1]['content'])
assert raw['code']=='b_domestic_remuneration_test = (b_private_home_domestic_service and (3200 >= 1000))'
assert len(raw['factual_observations'])==1
row=raw['factual_observations'][0];spec=compiled['observations'][row['name']]
assert row['evidence']==spec['entity_source']+'#'+seal['source']['public']['facts']
# Exactly this model-authored constant is moved to an explicit current source
# binding. Neither its value, the predicate nor any operator is changed.
recovered={'code':'_fact_literal_0 = 3200 # s52\n'+raw['code'].replace('3200','_fact_literal_0'),
    'factual_observations':[{**row,'evidence':row['evidence'][len(spec['entity_source'])+1:]}]}
old_fragment=parse_pal(raw['code'],require_query=False);new_fragment=parse_pal(recovered['code'],require_query=False)
def inline(value):
    if value=={'var':'_fact_literal_0'}:return 3200
    if isinstance(value,dict):return {k:inline(v) for k,v in value.items()}
    if isinstance(value,list):return [inline(v) for v in value]
    return value
assert inline(new_fragment['nodes'])==old_fragment['nodes']
updated,observed=accept_followup(compiled,prepared,recovered,library=library)
assert all(updated['program'][field]==compiled['program'][field] for field in ('query','scopes','clauses','observations'))
assessment=assess_source(updated,observed)
assert assessment['status']=='completion_stable' and assessment['answer']=='Contradiction'
evidence={'run_id':base.name,'raw_response_sha256':hashlib.sha256(paid[1]['content'].encode()).hexdigest(),
    'original_physical_run_was_rejected':True,'recovered_response':recovered,'expression_AST_after_inlining_fixed_input_identical':True,
    'unchanged_accepted_query_rules_scopes_observations':True,'evidence_prefix_exact_correct_source_ID_only':True,
    'native_answer_or_training_label_used_for_repair':False,'assessment':assessment,'observed':observed,
    'kind':'offline deterministic adaptation of a real rejected response, not new live verification',
    'new_model_calls':0,'full_goal_complete':False}
path=ROOT/'reports/rr_method_runtime_20261107/paid_legal_fragment_v12_deterministic_recovery.json'
assert not path.exists();path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:evidence[k] for k in ('kind','new_model_calls','expression_AST_after_inlining_fixed_input_identical','full_goal_complete')}))
