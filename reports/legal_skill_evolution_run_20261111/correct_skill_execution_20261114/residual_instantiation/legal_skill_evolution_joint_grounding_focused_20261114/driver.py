from pathlib import Path
import json,hashlib,fcntl
from copy import deepcopy
from experiments import legal_skill_evolution_joint_grounding_control as old
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.runtime import render_messages,decoder_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.case_observation_contract import kernel_execution,checked_witnesses
from legal_skill_guard.skill_evolution.native import grade_view
import jsonschema
root=old.ROOT;run='legal_skill_evolution_joint_grounding_focused_20261114';out=root/'artifacts'/run
with (root/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
 fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 p=old.prior.read(old.OUT/'protocol.json');task=old.prior.read(old.OUT/'task.json');focused=deepcopy(task)
 name=task['unchanged_legal_program']['name']
 focused['shared_already_learned_contracts']={arm:[c for c in cs if c['kernel_name']==name] for arm,cs in task['shared_already_learned_contracts'].items()}
 assert all(len(cs)==1 for cs in focused['shared_already_learned_contracts'].values())
 assert focused['current_case']==task['current_case'] and focused['unchanged_legal_program']==task['unchanged_legal_program']
 before=old.prior.base.old.rows();assert not any(r[6]=='reserved' for r in before)
 cfg=p['executor_profile'];schema=p['schema'];msgs=render_messages(old.SYSTEM,focused,schema)
 read_only=FrozenExecutor(None,out,cfg)
 counts={'full':read_only.tokenize(render_messages(old.SYSTEM,task,schema),thinking=False)['count'],
         'focused':read_only.tokenize(msgs,thinking=False)['count']}
 assert counts['focused']<counts['full']
 proto={'run_id':run,'source':p['source'],'executor_profile':cfg,'task_sha256':digest(focused),
 'change':'Retain only the two contracts for the actual kernel; all facts, program, initial state, schema, sampling and system instruction identical.',
 'offline_tokenization_not_generation':counts,'additional_model_requests_planned':1,
 'no_later_source_presence_diagnostic_or_native_label_given':True,'goal_complete':False}
 immutable_json(out/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in before});immutable_json(out/'protocol.json',proto);immutable_json(out/'task.json',focused)
 (out/'driver.py').write_bytes(Path(__file__).read_bytes())
 ledger=EvolutionLedger(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run,sources={'train':[p['source']],'dev':[],'test':[]},binding=digest(proto))
 response=FrozenExecutor(ledger,out,cfg).generate(run+':JointRepair',source=p['source'],purpose='skill_actor',messages=msgs,thinking=False,schema=decoder_schema(schema)[0])
 assert response['finish_reason']=='stop';v=json.loads(response['content']);jsonschema.validate(v,schema);checked_witnesses(v['witnesses'],task['current_case'])
 inputs={k:v for k,v in v['inputs'].items() if v is not None};execution=kernel_execution(task['unchanged_legal_program'],inputs)
 cases=old.prior.read(old.prior.direct.OUT/'fixed_development_cases.json');src=next(c['source'] for c in cases if c['source']['key']==p['source']);view=src['views'][0]
 ann=old.prior.read(root/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
 result={'observation':v,'execution':execution,'native_score':grade_view(src['dataset'],view,ann[p['source']][view['id']],execution['answer']),
 'source':p['source'],'one_development_control_not_method_validation':True,'fallback':False,'goal_complete':False}
 immutable_json(out/'result.json',result);print(json.dumps({'token_counts':counts,'execution':execution,'score':result['native_score']}),flush=True)
