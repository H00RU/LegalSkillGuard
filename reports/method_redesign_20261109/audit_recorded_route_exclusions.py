"""A source-only necessary-condition control for existing TRAIN route fields.

Only the official source-code city dictionaries and original public TRAIN rules
are read. No generated native problems, fee labels or new cases are opened.
This control falsifies an old true flag; it never repairs or accepts old IR.
"""
import ast,hashlib,json,re,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'recorded_fact_inventory_v1_20261110'
REPORT=ROOT/'reports/method_redesign_20261109/recorded_fact_inventory_with_controls_results.json'


def read(p):return json.loads(p.read_text())


def snapshot():
 with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
  return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
 before=snapshot();inventory=read(STAGE/'frozen_inventory.json')
 pub={s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
 official=read(ROOT/'reports/method_redesign_20261109/M1M2_fixed_pool_reuse_audit.json')['official_semantics']
 path=ROOT/'data/cache/rr_v2/RuleArena/airline/gen_questions.py';raw=path.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==official['files']['gen_questions.py']
 values={}
 for n in ast.parse(raw).body:
  if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ['us_city_collection','international_city_collection']:
   values[n.targets[0].id]=ast.literal_eval(n.value)
 assert values['international_city_collection']['Lima']=='Peru' and 'Orlando' in values['us_city_collection']
 calls={r[0]:r for r in before['calls']};checked=[];falsified=[];unassessed=[]
 for row in inventory['records']:
  source=pub[row['ledger_primary_source']]
  if source['dataset']!='RuleArena_Airline' or row['kind']!='reported_named_factual_values':continue
  wire=json.loads(calls[row['call_id']][8]);response=json.loads(wire['content'])
  flags=[(i,r) for i,r in enumerate(response.get('factual_observations',[])) if r['name']=='b_first_other_south_america' and r['value'] is not None]
  if not flags:continue
  prompt=source['public']['prompt'];rules=source['public']['rules']
  routes=re.findall(r'\bflying from (.+?) to (.+?) with the following items:',prompt)
  request=read(Path(wire['artifact_directory'])/'request.json')
  user=json.loads(request['payload']['messages'][-1]['content'])
  tasks=[t for t in user.get('factual_observation_tasks',[]) if t.get('name')=='b_first_other_south_america']
  predicates={t['predicate'] for t in tasks if t['predicate'] in rules}
  exclusions=[]
  for predicate in predicates:
   exclusions.extend(re.findall(r'Between South America \(excluding ([^)]+)\) and U\.S\.',predicate))
  if len(routes)!=1 or len(set(exclusions))!=1:
   unassessed.append({'call_id':row['call_id'],'reason':'No unique source route/exclusion expression'});continue
  origin,destination=routes[0]
  is_us=lambda city:city in values['us_city_collection']
  if is_us(origin)==is_us(destination):
   unassessed.append({'call_id':row['call_id'],'reason':'Control requires one explicit U.S. endpoint'});continue
  foreign=destination if is_us(origin) else origin
  country=values['international_city_collection'].get(foreign)
  if country is None:
   unassessed.append({'call_id':row['call_id'],'reason':'No provided source-code location mapping'});continue
  excluded=[s.strip() for s in exclusions[0].split(',')]
  for i,flag in flags:
   r={'call_id':row['call_id'],'ordinal':row['ordinal'],'row_index':i,'model_name':flag['name'],
      'model_value':flag['value'],'model_quote':flag['evidence'],'origin':origin,'destination':destination,
      'foreign_country_from_official_code':country,'explicit_source_excluded_countries':excluded,
      'source_mapping_is_common_reference_infrastructure_not_learned_skill':True}
   if country in excluded:
    r.update(source_necessary_condition_value=False,model_true_falsified=flag['value'] is True,
      reason='The original source excludes this actual route country from this particular row. No fee/answer label is needed.')
    if flag['value'] is True:falsified.append(r)
   else:r.update(source_necessary_condition_value=None,model_true_falsified=False,
      reason='This necessary exclusion check alone makes no full membership/truth claim.')
   checked.append(r)
 assert any(r['ordinal']==50 and r['model_true_falsified'] for r in checked)
 evidence={'official_repository':official['repository'],'official_commit':official['commit'],
  'generator_code_sha256':hashlib.sha256(raw).hexdigest(),
  'original_code_constant_lookup_only_not_generator_execution':True,
  'checked_existing_observation_rows':checked,'actual_model_rows_falsified_by_explicit_country_exclusion':falsified,
  'unassessed':unassessed,'raw_model_values_or_old_IR_modified':False,
  'no_native_fee_labels_or_new_teacher_truths_used':True,
  'no_full_fee_recovery_or_new_method_claim':True,
  'no_inference_of_nonexcluded_country_membership':True}
 immutable_json(STAGE/'ordinary_native_location_exclusion_control.json',evidence)
 assert before==snapshot()
 report=read(ROOT/'reports/method_redesign_20261109/recorded_fact_inventory_results.json')
 report.pop('Airline50_primitive_truth_and_strong_control_still_require_review')
 report.update(Airline50_first_row_model_true_falsified_without_native_fee_label=True,
   route_rows_with_explicit_source_necessary_condition_checked=len(checked),
   physical_responses_with_first_row_true_falsified=len({r['call_id'] for r in falsified}),
   distinct_original_primary_sources_with_first_row_true_falsified=len({r['ordinal'] for r in falsified}),
   route_primitive_correctness_beyond_this_exclusion_control_not_claimed=True,
   not_a_new_learned_noise_model_or_two_method_success=True,
   raw_nonJSON_bucket_also_contains_valid_raw_Python_program_text_not_all_generation_failures=True,
   inventory_does_not_verify_every_other_embedded_literal_or_claim_no_further_research_is_possible=True,
   current_next_action='Before proposing a factoring/noise learner for these records, retain exact input dedup and structured source-country/exception computation as strong common controls. A new independent learning mechanism remains unspecified.',
   ledger_rows_unchanged=True,ledger_logical_sha256=digest(before))
 immutable_json(REPORT,report)
 print(json.dumps({k:report[k] for k in ['counts_total','new_model_calls','reported_named_value_responses','reported_named_value_unique_primary_sources','physical_responses_with_first_row_true_falsified','distinct_original_primary_sources_with_first_row_true_falsified','goal_complete']},ensure_ascii=False))


if __name__=='__main__':main()
