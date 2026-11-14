from pathlib import Path
from copy import deepcopy
import json,hashlib,fcntl
import jsonschema
from experiments import legal_skill_evolution_residual_observation as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,grade_view
from legal_skill_guard.skill_evolution.runtime import render_messages,decoder_schema
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter,execute_alternatives,checked_witnesses
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.observation_slice import resolve
from legal_skill_guard.skill_evolution.objects import digest
root=prior.ROOT;run='legal_skill_evolution_joint_scoped_observations_20261114';out=root/'artifacts'/run
with (root/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
 fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 parent=prior.prior.read(prior.OUT/'protocol.json');packet=prior.prior.read(prior.OUT/'packet.json')
 contract=packet['contract'];kernel=packet['kernel'];src=packet['source'];pub=src['views'][0]['public'];original=packet['original_observation'];assert len(original['views'])==1
 schema_root=json.loads(contract['observation_schema_json']);view_schema=resolve(schema_root,['views',0]);fields={}
 witness={'type':'array','items':record_schema({'field':{'type':'string','enum':['facts','question']},'quote':{'type':'string'}})}
 for name,spec in view_schema['properties'].items():
  types=spec.get('type',[]);types=[types] if isinstance(types,str) else types
  if name=='witnesses' or 'array' not in types:continue
  positive=deepcopy(spec);positive['type']='array'
  fields[name]={'oneOf':[record_schema({'status':{'type':'string','enum':[status]},'value':positive if status=='records' else {'type':'null'},'witnesses':witness}) for status in ['records','none_stated','unread']]}
 schema=record_schema(fields)
 for name in ['$defs','definitions']:
  if name in schema_root:schema[name]=deepcopy(schema_root[name])
 jsonschema.Draft202012Validator.check_schema(schema)
 system='''Jointly re-read ALL declared factual channels of the current finite case in this ONE request. For each channel, records means actual stated facts; none_stated means you read the complete supplied case text and found no matching statement in that channel; unread means extraction failed or is ambiguous. This is the same source-scoped status language as the selective method, not a weaker nullable-only baseline. For none_stated/unread value is null. Preserve roles, source-native event/state forms and dates. Do not invent an end date, an event or a native legal conclusion. Use verbatim current facts/question witnesses. You may correct all coupled channels together; you are not limited to the selective method's chosen port. Output only the factual JSON.\nLearned factual-view instruction:\n'''+contract['observation_prompt']
 task={'current_case':{k:pub[k] for k in contract['observation_context_fields']},'previous_view':original,
       'shared_binding_program':contract['binding_program'],'later_source_presence_diagnostic_not_supplied':True}
 before=prior.prior.base.old.rows();assert not any(r[6]=='reserved' for r in before)
 proto={'run_id':run,'source':src['key'],'same_goal':True,'goal_complete':False,'one_development_case_only':True,
 'planned_model_requests':1,'same_source_status_grammar_and_learned_view_as_selective_path':True,
 'shared_assets_execution_control_not_independent_acquisition':True,'executor_profile':parent['executor_profile'],
 'task_sha256':digest(task),'schema':schema,'system':system,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 immutable_json(out/'protocol.json',proto);immutable_json(out/'task.json',task);immutable_json(out/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in before});(out/'driver.py').write_bytes(Path(__file__).read_bytes())
 ledger=EvolutionLedger(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run,sources={'train':[src['key']],'dev':[],'test':[]},binding=digest(proto))
 result=FrozenExecutor(ledger,out,parent['executor_profile']).generate(run+':JointScopedRead',source=src['key'],purpose='skill_actor',messages=render_messages(system,task,schema),thinking=False,schema=decoder_schema(schema)[0])
 assert result['finish_reason']=='stop';value=json.loads(result['content']);jsonschema.validate(value,schema)
 updated=deepcopy(original);changed=[]
 for name,r in value.items():
  if r['status']=='unread':continue
  checked_witnesses(r['witnesses'],pub);updated['views'][0][name]=[] if r['status']=='none_stated' else r['value'];updated['views'][0]['witnesses'].extend(r['witnesses']);changed.append(name)
 grounded=apply_adapter(contract,kernel,pub,updated,literal_context=literal_bindings({'public':pub}));execution=execute_alternatives(kernel,grounded)
 ann=prior.prior.read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json');view=src['views'][0]
 final={'source':src['key'],'observation':value,'updated_full_view':updated,'changed_channels':changed,'grounded':grounded,'execution':execution,
 'native_score':grade_view(src['dataset'],view,ann[src['key']][view['id']],execution['answer']),
 'one_logical_joint_read':True,'not_an_independent_acquisition_or_full_method_comparison':True,'goal_complete':False}
 immutable_json(out/'result.json',final);print(json.dumps({'statuses':{k:v['status'] for k,v in value.items()},'handled':execution['handled'],'answer':execution['answer']}),flush=True)
