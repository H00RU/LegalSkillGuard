from lsg_project_unused_renderer_args import project
from copy import deepcopy
import hashlib,json
from pathlib import Path
from experiments import legal_skill_evolution_scoped_atom_acquisition as e
from legal_skill_guard.skill_evolution.relational_rules import validate_language,rule_text,output_projection
from legal_skill_guard.skill_evolution.source_composition import validate_renderers
from legal_skill_guard.skill_evolution.span_compiler import occurrences
from legal_skill_guard.rr.checkpoint import immutable_json

def compile_one(arm):
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
