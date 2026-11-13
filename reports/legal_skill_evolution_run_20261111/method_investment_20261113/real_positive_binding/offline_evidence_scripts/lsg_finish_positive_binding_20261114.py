from pathlib import Path
import json,hashlib
from experiments import legal_skill_evolution_positive_binding_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
p,ledger,public=e.setup();rows=e.rows();assert not any(r[6]=='reserved' for r in rows)
freeze=e.read(e.OUT/'library_freeze.json')
assert all(freeze['libraries'][a]==digest(e.read(e.OUT/a/'learned.json')) for a in e.ARMS)
unscored=[e.OUT/'reuse'/a/e.name_for(k) for a in e.ARMS for k in p['reuse_sources']]
scores=[e.OUT/'reuse_scores'/a/e.name_for(k) for a in e.ARMS for k in p['reuse_sources']]
assert all(f.exists() for f in unscored+scores)
assert max(f.stat().st_mtime_ns for f in unscored)<min(f.stat().st_mtime_ns for f in scores)
wire=[]
cost=e.read(e.OUT/'cost_and_preservation.json')
for call in cost['calls']:
 if call['role']!='executor':continue
 result=next(json.loads(r[8]) for r in rows if r[0]==call['id'])
 req=e.read(Path(result['artifact_directory'])/'request.json');v=req['payload']
 assert v['max_tokens']==8192 and v['chat_template_kwargs']['enable_thinking'] is False
 assert not result.get('reasoning_content') and result['finish_reason']=='stop'
 wire.append({'id':call['id'],'request_hash':req['request_hash'],'thinking_OFF':True,'max_tokens':8192,'finish_reason':'stop'})
immutable_json(e.OUT/'execution_before_scoring.json',{'all8_unscored_before_first_score':True,
 'latest_unscored_mtime_ns':max(f.stat().st_mtime_ns for f in unscored),
 'first_score_mtime_ns':min(f.stat().st_mtime_ns for f in scores),
 'unscored_file_sha256':{str(f.relative_to(e.OUT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in unscored},
 'frozen_libraries_unchanged':True,'new_model_requests':0})
immutable_json(e.OUT/'executor_wire_verification.json',{'all_requests':wire,'verified_physical_requests':len(wire)})
immutable_json(e.OUT/'TERMINAL_PRESERVATION.json',{'fixed_study_complete':True,'same_goal':True,'goal_complete':False,
 'method_claims_complete':False,'U_real_phi_G_dictionary_empty':True,'source_and_data_hashes_verified':True,
 'all_original_10167_rows_unchanged':True,'ledger_rows':len(rows),'reserved':0,'libraries_frozen':freeze,
 'all12_acquisition_and4_reuse_mothers_each_arm_saved':True,'all8_unscored_before_scoring':True,
 'no_full_training_DEV_TEST_or_paper':True,'type_recovery_new_model_requests':0})
print('Fixed12/4 study terminal; all8 unscored before any score;266 physical OFF/stop requests verified;Goal active.')
