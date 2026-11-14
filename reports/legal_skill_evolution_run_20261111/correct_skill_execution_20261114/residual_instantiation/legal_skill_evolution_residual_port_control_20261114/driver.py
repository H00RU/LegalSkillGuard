from pathlib import Path
from copy import deepcopy
import json,hashlib,fcntl
import jsonschema
from experiments import legal_skill_evolution_temporal_contract_learning as old
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import kernel_execution,checked_witnesses
from legal_skill_guard.skill_evolution.kernel_residual import execution_residual
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.runtime import decoder_schema,render_messages
from legal_skill_guard.skill_evolution.objects import digest
root=old.ROOT;run='legal_skill_evolution_residual_port_control_20261114';out=root/'artifacts'/run
with (root/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
 fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 parent=old.read(old.OUT/'protocol.json');row=next(r for r in old.read(old.OUT/'scored_results.json')['rows'] if r['arm']=='DirectRead' and '8175fcb9' in r['source'])
 sid=row['source'];kernel=next(k for k in old.read(old.OUT/'kernel_bank.json') if k['name']==row['kernel']);pub=next(c['source']['views'][0]['public'] for c in old.read(old.direct.OUT/'fixed_development_cases.json') if c['source']['key']==sid)
 inputs={k:v for k,v in row['observation']['inputs'].items() if v is not None};residual=execution_residual(kernel,inputs)
 ports=list(dict.fromkeys(p[0] for p in residual['return_cause_input_paths']));assert len(ports)==1;port=ports[0]
 spec=old.direct.port_schema(json.loads(kernel['input_fields_json'])[port]);spec['type']='array'
 witness={'type':'array','items':record_schema({'field':{'type':'string','enum':['facts','question']},'quote':{'type':'string'}})}
 schema={'oneOf':[record_schema({'status':{'type':'string','enum':[status]},'value':spec if status=='records' else {'type':'null'},'witnesses':witness}) for status in ['records','none_stated','unread']]}
 system='''Read ONLY the requested factual input port from the current finite case text. You may use the actual kernel residual and the shared learned event-view instructions/programs. Recheck the uncertain temporal/role values rather than copy the previous input. Do not change a legal rule or answer the statutory claim. Use exact case witnesses. Return records for stated factual records, none_stated only for no matching statement after reading the finite text, and unread for actual extraction uncertainty. none_stated is textual absence, not a real-world negative. Never invent an actual ending date or future permanence. Output the declared factual JSON only.'''
 task={'current_case':pub,'unchanged_legal_kernel':kernel,'requested_port':port,'prior_port_value':inputs.get(port),
  'actual_return_cause':{'guards':residual['return_cause_guards'],'paths':residual['return_cause_input_paths']},
  'shared_relevant_contracts':{arm:[c for c in old.read(old.OUT/arm/'teacher.json')['value']['contracts'] if c['kernel_name']==kernel['name']] for arm in old.ARMS},
  'later_source_presence_diagnostic_withheld':True}
 before=old.base.old.rows();assert not any(r[6]=='reserved' for r in before)
 proto={'run_id':run,'source':sid,'planned_new_executor_requests':1,'same_goal':True,'goal_complete':False,
  'port_selected_by_actual_program_return_not_native_label':port,'executor_profile':parent['executor_profile'],'task_sha256':digest(task),
  'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'schema':schema,'system':system}
 immutable_json(out/'protocol.json',proto);immutable_json(out/'task.json',task);immutable_json(out/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in before});(out/'driver.py').write_bytes(Path(__file__).read_bytes())
 ledger=EvolutionLedger(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run,sources={'train':[sid],'dev':[],'test':[]},binding=digest(proto))
 response=FrozenExecutor(ledger,out,parent['executor_profile']).generate(run+':PortRead',source=sid,purpose='skill_actor',messages=render_messages(system,task,schema),thinking=False,schema=decoder_schema(schema)[0])
 assert response['finish_reason']=='stop';value=json.loads(response['content']);jsonschema.validate(value,schema)
 after=deepcopy(inputs)
 if value['status']!='unread':
  checked_witnesses(value['witnesses'],pub);after[port]=[] if value['status']=='none_stated' else value['value']
 execution=kernel_execution(kernel,after)
 immutable_json(out/'result.json',{'source':sid,'selected_port':port,'observation':value,'binding_before':inputs,'binding_after':after,'execution':execution,
  'remaining_residual':execution_residual(kernel,after),'native_answer_not_used_to_select_or_fill':True,'goal_complete':False})
 print(json.dumps({'selected_port':port,'observation_status':value['status'],'execution':execution}),flush=True)
