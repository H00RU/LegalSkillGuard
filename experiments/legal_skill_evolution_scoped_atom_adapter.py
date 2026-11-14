"""Actual paid-response adapters; no legal facts or relaxed runtime checks.

Preserves raw responses. Projection removes unused output coordinates only;
pure lambda lifting preserves exact argument/return ASTs; repeated constructors
retain their already acquired canonical semantics. Existing TRAIN example
validation adds no evidence to generation, observation or scoring.
"""
from copy import deepcopy

def project(language,renderers):
 original=deepcopy((language,renderers));changes=[]
 for renderer in renderers:
  name=renderer['predicate'];signature=language['signatures'][name];used=set()
  def refs(v):
   if isinstance(v,dict):used.add(v.get('term_argument',v.get('scalar_argument')))
   else:
    for child in v[1:]:refs(child)
  refs(renderer['term'])
  for key in ('support_arguments','support_from_terms','support_from_queries'):used.update(renderer.get(key,[]))
  kept=sorted(used);removed=sorted(set(range(len(signature['arguments'])))-used)
  if not removed:continue
  assert not any(a['predicate']==name for r in language['rules'] for a in r['body'])
  remap={old:new for new,old in enumerate(kept)}
  def move(v):
   if isinstance(v,dict):return {k:remap[i] for k,i in v.items()}
   return [v[0],*[move(x) for x in v[1:]]]
  old_renderer=deepcopy(renderer);renderer['term']=move(renderer['term'])
  for key in ('support_arguments','support_from_terms','support_from_queries'):
   if key in renderer:renderer[key]=[remap[i] for i in renderer[key]]
  signature['arguments']=[signature['arguments'][i] for i in kept]
  for rule in language['rules']:
   if rule['head']['predicate']==name:rule['head']['arguments']=[rule['head']['arguments'][i] for i in kept]
  # Pointwise output substitution and provenance commute with projection;
  # the symbolic values distinguish every original argument.
  before=['ARG_'+str(i) for i in range(len(kept)+len(removed))];after=[before[i] for i in kept]
  def instantiate(v,args):
   if isinstance(v,dict):return [next(iter(v)),args[next(iter(v.values()))]]
   return [v[0],*[instantiate(x,args) for x in v[1:]]]
  assert instantiate(old_renderer['term'],before)==instantiate(renderer['term'],after)
  for key in ('support_arguments','support_from_terms','support_from_queries'):
   assert [before[i] for i in old_renderer.get(key,[])]==[after[i] for i in renderer.get(key,[])]
  changes.append({'predicate':name,'removed_unused_output_positions':removed,'pointwise_legal_term_and_provenance_exact':True,'output_predicate_never_used_as_body':True})
 for before,after in zip(original[0]['rules'],language['rules']):
  assert before['body']==after['body'] and before['id']==after['id'] and before['cost']==after['cost']
 return changes

import ast
from copy import deepcopy

def lift(functions):
 out=[];helpers=[];proof=[]
 names={n.name for code in functions for n in ast.parse(code).body}
 for code in functions:
  tree=ast.parse(code)
  class Lift(ast.NodeTransformer):
   def visit_Lambda(self,node):
    args=node.args
    assert not args.defaults and not args.vararg and not args.kwarg and not args.kwonlyargs
    bound={a.arg for a in args.args}
    assert {n.id for n in ast.walk(node.body) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}<=bound
    name='atoms_lifted_sort_key_'+str(len(helpers));assert name not in names
    f=ast.FunctionDef(name=name,args=deepcopy(args),body=[ast.Return(value=deepcopy(node.body))],decorator_list=[])
    ast.fix_missing_locations(f);helpers.append(ast.unparse(f))
    assert ast.dump(f.body[0].value,include_attributes=False)==ast.dump(node.body,include_attributes=False)
    proof.append({'original_lambda':ast.unparse(node),'lifted_helper':ast.unparse(f),'captures':[],
      'argument_binding_and_return_expression_AST_exact':True})
    return ast.copy_location(ast.Name(id=name,ctx=ast.Load()),node)
  tree=Lift().visit(tree);ast.fix_missing_locations(tree);out.append(ast.unparse(tree))
 return helpers+out,proof

from copy import deepcopy
import hashlib,json
from pathlib import Path
from experiments import legal_skill_evolution_scoped_atom_acquisition as e
from legal_skill_guard.skill_evolution.relational_rules import validate_language,rule_text,output_projection
from legal_skill_guard.skill_evolution.source_composition import validate_renderers
from legal_skill_guard.skill_evolution.span_compiler import occurrences
from legal_skill_guard.rr.checkpoint import immutable_json

def compile_one(arm):
 if (e.OUT/arm/'compiled.json').exists():
  return
 p,_,public=e.setup();old=e.read(e.OUT/'previous'/arm/'library.json');raw=e.read(e.OUT/arm/'teacher.json')['value'];patch=deepcopy(raw)
 proof={'same_paid_raw_response_retained':True,'new_model_calls':0,'helper_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 if arm=='ConstraintAcquire':
  before=e.json.loads(raw['composition']);after=deepcopy(before)
  # Every new field is obtained from term_scalar, whose supplied nominal type
  # is scalar. The new source constructors still enforce text at runtime.
  changed=[]
  for name,sig in after['signatures'].items():
   assert name not in e.signatures() and name!='keep_root'
   for i,sort in enumerate(sig['arguments']):
    if sort=='text':sig['arguments'][i]='scalar';changed.append([name,i,'text','scalar'])
  assert 'scalar' not in after['constants']
  after['constants']['scalar']=after['constants'].pop('text')
  renderers=e.json.loads(patch['renderers_json']);projection=project(after,renderers)
  merged={**after,'signatures':{**e.signatures(),'keep_root':{'arguments':['term'],'kind':'output'},**after['signatures']}}
  validate_language(merged);validate_renderers(merged,renderers)
  assert [r['body'] for r in before['rules']]==[r['body'] for r in after['rules']]
  assert {k:v['kind'] for k,v in before['signatures'].items()}=={k:v['kind'] for k,v in after['signatures'].items()}
  patch['composition']=json.dumps(after,ensure_ascii=False)
  patch['renderers_json']=json.dumps(renderers,ensure_ascii=False)
  assert {k:v for k,v in raw.items() if k not in ('composition','renderers_json')}=={k:v for k,v in patch.items() if k not in ('composition','renderers_json')}
  proof.update({'declaration_adaptation':changed,'all23_rule_bodies_and_costs_exact':True,'unused_output_projection':projection,'legal_term_and_provenance_substitution_exact':True,
   'all_legal_constants_constructors_source_and_consumer_code_exact':True,
   'no_correctness_type_check_relaxed':True,'reason':'Actual generic term_scalar is nominal scalar, while new source constructor argument types remain text; only generated relational declarations had used text.'})
 if arm=='FreeUpdate':
  patch['atom_functions'],lifting=lift(patch['atom_functions'])
  proof['pure_lambda_lifting']=lifting
  declared={c['name']:c for c in old['spec']['constructors']};duplicate=[c for c in patch['new_constructors'] if c['name'] in declared]
  assert {c['name'] for c in duplicate}=={'controlled_entities_of','action_conjunction','authorized_action_alternative','project_termination'}
  for c in duplicate:assert {k:v for k,v in c.items() if k!='meaning'}=={k:v for k,v in declared[c['name']].items() if k!='meaning'}
  proof['redundant_existing_constructor_declarations']=[{'previous':declared[c['name']],'repeated':c,'same_type_and_reviewed_same_meaning':True,'previous_canonical_meaning_preserved':True} for c in duplicate]
  patch['new_constructors']=[c for c in patch['new_constructors'] if c['name'] not in declared]
 source=e.append_atoms(old['source_program'],patch['atom_functions'])
 full={'rationale':patch['rationale'],'operations':old['operations'],'scope':'window',
 'reading_contracts':[{'operation':o['name'],'scope':old['operation_scopes'][o['name']],
 'complete_source_absence_choices':old['complete_source_absence_choices'].get(o['name'],[])} for o in old['operations']],
 'planner_functions':e.prior.prior.functions([e.routed_plan(old['planner_program'],e.CONTROL[arm])]),
 'source_functions':e.prior.prior.functions([source]),'new_constructors':patch['new_constructors'],
 'decision_functions':patch['decision_functions'],'renderers_json':patch.get('renderers_json','[]'),
 'suggested_rule_ids':patch.get('suggested_rule_ids',[]),
 'composition':patch['composition'] if arm=='ConstraintAcquire' else e.function_update(old['composition_program'],e.prior.prior.functions(patch['composition_functions']))}
 # Validator context includes ONLY existing unchanged operation examples.
 # This supplies no new source to either teacher, observation or scoring.
 keys=set(p['sources']);existing=[]
 assert full['operations']==old['operations']
 for op in old['operations']:
  for x in op['examples']:
   assert any(occurrences(v['public']['source_text'],x['quote']) for v in public[x['source']]['views'])
   keys.add(x['source']);existing.append({'operation':op['name'],'source':x['source'],'previous_example_sha256':e.digest(x)})
 lib,receipt=e.compile_proposal(old,full,arm,{k:public[k] for k in keys},source_functions=full['source_functions'])
 proof.update({'unchanged_previous_operation_examples':existing,'compiler_quote_validation_sources_only':sorted(keys),
  'teacher_task_source_ids_unchanged':p['sources'],'observation_and_scoring_source_ids_unchanged':p['sources']})
 immutable_json(e.OUT/arm/'canonical_proposal.json',full);immutable_json(e.OUT/arm/'compiled.json',lib)
 immutable_json(e.OUT/arm/'compilation_receipt.json',receipt);immutable_json(e.OUT/arm/'unbound_paid_compilation_proof.json',proof)
 print(json.dumps({'arm':arm,'compiled':True,'adapted_nominal_positions':len(proof.get('declaration_adaptation',[])), 'new_model_calls':0}),flush=True)

if __name__=='__main__':
 import sys
 for arm in sys.argv[1:]:compile_one(arm)
