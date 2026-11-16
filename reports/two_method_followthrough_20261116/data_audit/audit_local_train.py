"""Read existing project TRAIN only; no inference, network, or evaluation."""
import collections, hashlib, json, re, tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
inputs={}
def read(rel):
 p=ROOT/rel; b=p.read_bytes(); inputs[rel]={'absolute_path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)};return b
def js(rel): return json.loads(read(rel))
def save(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
m=js('outputs/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
meta=js('work/five-dataset-20261110/repo_evidence/train.json')['sources']
pub={x['key']:x for x in js('work/five-dataset-20261110/repo_evidence/public_train.json')['sources']}
opportunity=js('outputs/legal_skill_execution_design_20261116/train_task_fit.json')
failure=js('work/research-reset-20261116/raw_audit/M2_responsibility_review_actual_failure_evidence.json')
controls=js('work/research-reset-20261116/raw_audit/legal_skill_evolution_observation_link_refutation_20261115_selected_method_reuse_controls.json')
js('work/research-reset-20261116/raw_audit/legal_skill_evolution_C_diagnostic_refinement_20261115_result.json')
for p in ['outputs/ten_paper_review_20261116/MECHANISM_DECISION.md','work/research-reset-20261116/c_diagnosis.md','work/research-reset-20261116/m2_review.md']:read(p)
archive='work/final-plan/data-audit/sara_v2.tar.gz';read(archive)
members={}; deps=collections.defaultdict(set);selected=[]
with tarfile.open(ROOT/archive) as t:
 def member(n):
  b=t.extractfile(n).read();members[n]=hashlib.sha256(b).hexdigest();return b.decode('utf8')
 native_train=set(member('sara_v2/splits/train').split())
 for n in t.getnames():
  if re.fullmatch(r'sara_v2/structure/(section\d+|tax)',n):
   text=member(n)
   for clause in text.split('.'):
    names=re.findall(r'\b(s\d+(?:_[A-Za-z0-9]+)*)\s*\(',clause)
    if names:deps[names[0]].update(names[1:])
 for row in m['datasets']['SARA_v2_Binary']['train']:
  case=meta[row['key']]['original_id']; assert case in native_train
  text=member('sara_v2/cases/'+case+'.pl')
  target=re.sub(r'_(pos|neg)$','',case);seen=set();todo=[target]
  while todo:
   z=todo.pop()
   if z not in seen:seen.add(z);todo.extend(deps[z]-seen)
  selected.append({'source_key':row['key'],'original_case':case,'target':target,'section':target.split('_')[0],'dependency_closure':sorted(seen),'dependency_closure_sha256':hashlib.sha256('\n'.join(sorted(seen)).encode()).hexdigest(),'native_train_confirmed':True,'case_member_sha256':members['sara_v2/cases/'+case+'.pl']})
  if row['key']==failure['source']:failure_case=text
# Connected components of target dependency overlap; conservative rule-leakage groups.
components=[]
for r in selected:
 current=[r]; overlap=[g for g in components if any(set(x['dependency_closure']) & set(r['dependency_closure']) for x in g)]
 for g in overlap:current+=g;components.remove(g)
 components.append(current)
rule_groups=[{'group':i+1,'cases':[x['original_case'] for x in g],'sections':sorted(set(x['section'] for x in g))} for i,g in enumerate(components)]
fixed={}
for d in ['OpenExempt','RuleArena_Airline','SARA_v2_Binary']:
 hashes=[]
 for r in m['datasets'][d]['train']:
  p=pub[r['key']]['public']
  if d=='OpenExempt':
   v=p['views']['EC'];law=v.split('Statutes:',1)[1].split('Facts:',1)[0].split('Solved Reasoning Steps:',1)[0].strip()
  else:law=p['rules']
  hashes.append(hashlib.sha256(law.encode()).hexdigest())
 fixed[d]={'train_sources':len(hashes),'distinct_supplied_rule_text_sha256':dict(collections.Counter(hashes))}
facts=pub[failure['source']]['public']['facts'];quote=failure['actual_observation']['views'][0]['payments'][0]['witnesses'][0]['quote'];assert quote in facts
payment=failure['actual_observation']['views'][0]['payments'][0]
pair={'pair_id':'sara_bb6_source_checked_partial_v1','source_key':failure['source'],'split':'TRAIN','reference_status':'manually_source_checked_partial_projection_not_gold_complete_graph','reference_source_text':facts,'reference_fields':{'payment.payer':'Alice','payment.payee':'Bob','payment.amount':3200,'payment.service_link':'domestic service','service.worker':'Bob','service.employer':'Alice','service.start_date':'2017-02-01','service.end_date':'2017-09-02','payment.date':{'status':'not_stated'},'payment.year':{'status':'not_stated'}},'observed_fields':{'payment.payer':payment['payer'],'payment.payee':payment['payees'][0],'payment.amount':payment['amount'],'payment.service_link':payment['purpose_entity'],'service.worker':payment['linked_service']['worker'],'service.employer':payment['linked_service']['employer'],'service.start_date':payment['linked_service']['start_date'],'service.end_date':payment['linked_service']['end_date'],'payment.date':payment['payment_date'],'payment.year':payment['stated_year'],'payment.temporal_precision':payment['temporal_precision']},'observed_conversion':failure['actual_component_conversion'],'plan':{'component_id':failure['component_id'],'component_prompt':failure['component_prompt'],'converter_sha256':failure['converter_sha256'],'source_artifact_sha256':failure['source_artifact_sha256'],'model_revision':'not_present_in_local_receipt','full_prompt_schema_hash':'not_present_in_local_receipt','usable_for_channel_pooling':False},'provenance':{'raw_json':'work/research-reset-20261116/raw_audit/M2_responsibility_review_actual_failure_evidence.json','observation_pointer':'/actual_observation/views/0/payments/0','text_pointer':'public_train.json sources[key]/public/facts','native_case_member':'sara_v2/cases/s3306_c_2_neg.pl','native_case_caution':'Native case includes payment start 2017-09-02 and s3306_b given absent from natural-language sentence; these are NOT adopted as reference.'},'permitted_use':'real partial fixture and error-dictionary evidence; not accuracy gain or fitted population channel','joint_error':'unsupported payment year together with internally inconsistent temporal_precision; converter discards whole payment while source-supported core survives in reference','native_label_used_to_construct_reference':False}
save('empirical_partial_pairs.json',{'pairs':[pair],'complete_calibration_pairs':0,'new_model_calls':0})
result={'scope':'existing local project TRAIN and existing failure audit; no project DEV/TEST examples inspected; manifest split metadata only','new_model_calls':0,'server_inspected':False,'counts':{'train_mothers':{d:len(v['train']) for d,v in m['datasets'].items()},'complete_verified_reference_observed_graph_pairs_locally':0,'source_checked_partial_pairs_created':1,'actual_raw_observation_sources_in_raw_audit':1,'same_source_two_strategy_summary_sources':len(set(r['source'] for r in controls['rows'])),'same_source_two_strategy_summary_rows':len(controls['rows']),'fully_versioned_two_plan_graph_pairs_locally':0,'airline_structured_reference_arguments':sum('reference_arguments' in meta[r['key']] for r in m['datasets']['RuleArena_Airline']['train']),'openexempt_construction_records':sum('construction_only_case' in meta[r['key']] for r in m['datasets']['OpenExempt']['train'])},'SARA':{'selected_cases':selected,'target_groups':len(set(x['target'] for x in selected)),'section_counts':dict(collections.Counter(x['section'] for x in selected)),'dependency_overlap_components':rule_groups,'warning':'Structure dependency overapproximation, not certified executable dependency split. Shared lower-level rules connect targets; sections alone do not ensure holdout independence. Existing B8 exposure precludes retroactive blind novelty.'},'supplied_rule_texts':fixed,'native_task_opportunity_not_gain':{'ContractNLI':opportunity['ContractNLI'],'MAUD':opportunity['MAUD']},'availability_boundary':'Counts describe inspected local material only. Reports reference fuller server raw responses and snapshots not downloaded here; missing locally is not absent on server. Teacher output is not gold; Airline construction arguments and OE construction records require alignment to displayed facts before serving as reference.', 'required_minimal_additions':['Retrieve existing raw responses + immutable model/prompt/schema/converter/program hashes for the two existing strategies on the same two TRAIN sources before any new calls.','Annotate event identities, evidence spans, reference relations and unknown/completeness masks for those same sources; preserve ambiguous alignments. Source-check both correct and incorrect reads, not only failures.','Use SARA original target/dependency metadata to predeclare held-out-rule groups; inventory prior exposure and rule-program support. Existing source split is not a rule split.','Add only missing complementary TRAIN structure contexts needed to distinguish candidate edits; no count guarantees identifiability. Rank/ambiguity check decides sufficiency.','If no second stable-version plan observation exists on server, a small paired TRAIN calibration is required and remains future work; annotation alone cannot create missing observations.'],'inputs':inputs,'archive_member_sha256':members}
save('audit.json',result)
print(json.dumps({'counts':result['counts'],'sara_sections':result['SARA']['section_counts'],'dependency_components':len(rule_groups),'fixed_rule_text_counts':{k:len(v['distinct_supplied_rule_text_sha256']) for k,v in fixed.items()}},indent=2))
