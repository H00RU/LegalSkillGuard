import ast,copy,json
from pathlib import Path
from legal_skill_guard.skill_evolution.semantic_operations import finish
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.rr.checkpoint import immutable_json
root=Path('.');base=root/'artifacts/legal_skill_evolution_semantic_operations_v2_20261113'
out=root/'artifacts/legal_skill_evolution_scope_learning_20261113/execution'
bundle=json.load(open(base/'LearnedOperations/compiled.json'))
file=next((base/'smoke/LearnedOperations').glob('*semantic.json'));semantic=json.load(open(file));answers=semantic['answers']
inputs=json.load(open(out/'input.json'));source=next(k for k in inputs['sources'] if ':354623' in k);units=inputs['sources'][source]
public={r['key']:r for r in json.load(open(root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'))}
text=public[source]['views'][0]['public']['source_text'];program=bundle['program']
fn=next(n for n in ast.parse(program).body if isinstance(n,ast.FunctionDef) and n.name=='_sr_get')
code=ast.get_source_segment(program,fn);lines=code.splitlines();qid=fn.args.args[1].arg;errors=fn.args.args[3].arg
traced='\n'.join([lines[0],f"    {errors}.append('__OBSERVED_LOOKUP__:'+str({qid}))",*lines[1:]])
probe=function_update(program,[traced]);original=finish(program,text,units,answers);trace=finish(probe,text,units,answers)
assert trace['statements']==original['statements']
read_ids=[s.split(':',1)[1] for s in trace['unresolved'] if s.startswith('__OBSERVED_LOOKUP__:')]
assert 'sr_3_action' not in read_ids and 'sr_3_retention_info' in read_ids
changed=copy.deepcopy(answers)
for a in changed:
 if a['id']=='sr_3_action':a['choice']='return_to_information_supplier'
assert finish(program,text,units,changed)==original
review={'new_model_calls':0,'raw_semantic_file':str(file),'lookup_calls_observed':read_ids,
 'instrumentation_preserved_actual_statements':True,'no_general_equivalence_claim':True,
 'cases':[
 {'operation':'principal_disposal_action','focus_unit_id':30,'status':'inactive_for_actual_retention_only_branch','evidence':'Actual lookup trace never reads sr_3_action; changing it to the acquired example target leaves the full original output identical. Do not train it as an outcome-causing error.'},
 {'operation':'disposal_retention_actor_role','focus_unit_id':29,'status':'semantic_equivalence_unresolved','evidence':'designated_recipient_holder and named_service_actor can both describe Volunteer in this agreement. Acquired one-label example is not a negative judgment on the other; no alias or incorrectness asserted.'},
 {'operation':'retained_information_scope','focus_unit_id':30,'status':'two_source_contradicted_scope_choices','evidence':'No-retained-information-scope asserts no information governed by retention effect, while actual focus30 explicitly prohibits retaining copies, notes and abstracts. Lookup is consumed. Both physical answers are one parent, not two independent cases.'}],
 'usable_negative_observations':2,'inactive_label_disagreements':1,'semantic_equivalence_unresolved_observations':1,
 'single_label_disagreement_does_not_mean_legal_error':True,'first_contribution_established':False,'goal_complete':False}
immutable_json(out/'training_feedback_semantic_review.json',review)
print('Four label disagreements reviewed:2 consumed source-contradicted scope choices,1 inactive field,1 unresolved equivalence.')
