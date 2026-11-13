import ast,copy,hashlib,json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.source_influence_learning import attach_retention_exceptions
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,term_sort
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from experiments.legal_skill_evolution_scope_induction import control
root=Path('.');out=root/'artifacts/legal_skill_evolution_scope_learning_20261113/execution'
read=lambda p:json.loads(p.read_text())
# Preserve the frozen induction version; the only current change fixes the
# renderer to use the actual acquired retention_permission arity.
old=ast.parse((out/'induction/source_snapshot/legal_skill_guard/skill_evolution/source_influence_learning.py').read_text())
new=ast.parse((root/'legal_skill_guard/skill_evolution/source_influence_learning.py').read_text())
a={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)};b={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
unchanged=[n for n in a if ast.dump(a[n],include_attributes=False)==ast.dump(b[n],include_attributes=False)]
assert set(a)-set(unchanged)=={'attach_retention_exceptions'}
result=read(out/'induction/result.json');source=next(k for k in read(out/'protocol.json')['sources'] if ':442c36' in k)
rows=[r for r in result['full_fit']['qualifies']['examples'] if r['source']==source and r['focus']==51]
from legal_skill_guard.skill_evolution.source_influence_learning import predict
method=[r['target'] for r in rows if predict(result['full_fit']['qualifies']['policy'],r['features'])]
ordinary=[r['target'] for r,p in zip(rows,control(rows,'explicit_paragraph_or_nearest')) if p]
assert method==ordinary==[48,49,50]
rawfile=next((root/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/development/SourceEffect').glob('*442*.json'))
raw=read(rawfile);before=[];node_indices=[]
for i,n in enumerate(raw['interpretation']['nodes']):
 if n['term'][0] in ('retention_permission','disposal_obligation'):
  assert len(n['support_ids'])==1
  before.append({'unit_id':n['support_ids'][0],'term':n['term'],'support_ids':n['support_ids']});node_indices.append(i)
links=lambda targets:[{'unit_id':51,'relation':'qualifies','target_unit_ids':targets,
 'quote':'Notwithstanding anything in this paragraph 6 to the contrary'}]
after=attach_retention_exceptions(before,links(method));simple=attach_retention_exceptions(before,links(ordinary));assert after==simple
bundle=read(root/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/SourceEffect/compiled.json')
spec=bundle['grammar'];schema=constructors(spec)
for row in after:assert term_sort(row['term'],schema)=='Norm'
new_ir=copy.deepcopy(raw['interpretation'])
for i,row in zip(node_indices,after):
 new_ir['nodes'][i]['term']=row['term'];new_ir['nodes'][i]['support_ids']=row['support_ids']
public={r['key']:r for r in read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
views=[]
for view in public[source]['views']:
 oldvalue=apply_current(spec,{'rules':[],'disabled_rules':[],'acquired_pairs':[]},raw['interpretation'],view)
 newvalue=apply_current(spec,{'rules':[],'disabled_rules':[],'acquired_pairs':[]},new_ir,view)
 assert oldvalue['value']['answer']==newvalue['value']['answer']
 views.append({'view':view['id'],'old_value':oldvalue,'updated_value':newvalue})
immutable_json(out/'actual_scope_update.json',{'source':source,'raw_original_result':str(rawfile),
 'original_file_sha256':hashlib.sha256(rawfile.read_bytes()).hexdigest(),
 'actual_acquired_roots_before':before,'updated_roots':after,'method_targets':method,'ordinary_explicit_paragraph_targets':ordinary,
 'method_and_control_updated_IR_identical':True,'type_checked_with_original_59_constructor_spec':True,
 'native_answers_unchanged':True,'views':views,'new_executor_requests':0,
 'unrepresented_target_units':[u for u in method if u not in [r['unit_id'] for r in before]],
 'complete_source_semantics_not_certified':True,'renderer_arity_fix':'retention_permission has actor,information,after_disposal,condition; retention_exception has actor,information,condition.',
 'frozen_induction_functions_unchanged':unchanged,'first_contribution_established':False,'goal_complete':False})
print('Actual original TRAIN IR updated and typed; ordinary paragraph control produces identical result; native answers unchanged.')
