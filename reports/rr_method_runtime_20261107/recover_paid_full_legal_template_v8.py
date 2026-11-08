"""Recover the paid complete teacher material without any model or label read."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,sqlite3
from datetime import datetime,timezone
from legal_skill_guard.rr.preflight import science_files,scientific_code_binding
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.pal_frontend import parse_pal,lower_pal,render_pal
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.source_program import compile_source,source_theory
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.source_bindings import decode_source_bindings
from legal_skill_guard.rr.scoped_program import compile_query
from legal_skill_guard.rr.clause_scope import lower_clauses
from legal_skill_guard.rr.compiler_templates import make_template
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.method_client import TEACHER_BINARY,TEACHER_SHA

root=Path(__file__).resolve().parents[2]
origin='reference_pal_teacher_sara3_full_v3_20261108'
base=root/'artifacts/rr_method_runtime_20261107'/origin
stage=root/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_sara3_template_v8_20261108'
files=science_files(root);offline=json.loads((root/'reports/rr_method_runtime_20261107/offline_reference_frontend_v8_20261108.json').read_text())
assert offline['exit_code']==0 and offline['network_blocked'] and offline['files']==files
cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text());manifest=json.loads((root/cfg['source_manifest']).read_text())
pubpath=root/'data/packets/rr_v2/public_train.json'
assert hashlib.sha256(pubpath.read_bytes()).hexdigest()==manifest['packet_sha256']['public_train']
public={s['key']:s for s in json.loads(pubpath.read_text())['sources']}
oldseal=json.loads((base/'seal.json').read_text());source=oldseal['source']
assert source==public[source['key']] and manifest['formal_train_order'].index(source['key'])==2
assert oldseal['config']['compiler_role']=='teacher'
assert oldseal['config']['teacher']=={**cfg['teacher'],'executable':TEACHER_BINARY}
assert hashlib.sha256(Path(TEACHER_BINARY).read_bytes()).hexdigest()==TEACHER_SHA
book=root/cfg['ledger_path'];db=sqlite3.connect('file:'+str(book.resolve())+'?mode=ro',uri=True)
def counters():
 return {'roles':db.execute('select role,status,count(*) from calls group by role,status').fetchall(),
 'meta_hash':digest(db.execute('select key,value from meta order by key').fetchall()),
 'oracle_rows':db.execute('select count(*) from oracle_views').fetchone()[0]}
before=counters();assert not db.execute("select 1 from calls where status='reserved'").fetchone()
call_id=origin+':compile';row=db.execute('select role,source,status,request_hash,result from calls where id=?',(call_id,)).fetchone()
assert row[:3]==('teacher',source['key'],'completed')
path=base/'calls'/digest(call_id)/'result.json';paid=json.loads(path.read_text());assert paid==json.loads(row[4])
assert paid['source_ids']==[source['key']] and paid['model']==cfg['teacher']['model']
code=paid['value']['code'];raw=parse_pal(code);program,audit=lower_pal(source,code);structure=inspect_source(source)
assert all(raw[k]==program[k] for k in ('bindings','nodes','scopes','query'))
for a,b in zip(raw['clauses'],program['clauses']):
 assert all(a[k]==b[k] for k in ('name','value','otherwise'))
 assert b['sources']==[u for u in a['sources'] if structure.roles[u]['role']=='rule']
domains=lambda p:{o['name']:(False,True) for o in p['observations']+p['rule_residuals']}
assert domains(raw)==domains(program)
assert {o['entity_source'] for o in raw['observations']}=={o['entity_source'] for o in program['observations']}
compiled=compile_source(source,program)
# Reconstruct the original symbolic executable after only provenance typing;
# no forbidden factual observation is resolved and no correctness check relaxed.
ownership_only=deepcopy(raw)
for clause in ownership_only['clauses']:
 clause['sources']=[u for u in clause['sources'] if structure.roles[u]['role']=='rule']
lowered=lower_clauses(structure,ownership_only)
original_query=compile_query(lowered['nodes'],raw['query'],compiled['slots'],domains=domains(raw),boolean_nodes=lowered['scope_names'])
assert original_query.__rr_state__()==compiled['query'].__rr_state__()
theory=source_theory(compiled);assessment=assess_source(compiled)
assert not any(r.unknown_scope for r in theory.residuals)
canonical=render_pal(program);reparsed,again=lower_pal(source,canonical)
assert reparsed==program and not again
origin_record={'role':'teacher','call_id':call_id,'request_hash':row[3],'model':paid['model'],
 'result_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
 'raw_code_sha256':hashlib.sha256(code.encode()).hexdigest(),'canonical_code_sha256':hashlib.sha256(canonical.encode()).hexdigest(),
 'normalization_audit_sha256':digest(audit),'generation_binding':oldseal['binding'],
 'normalization':'source-role provenance partition and unchanged symbolic Boolean meaning; no missing rule or fact truth supplied',
 'new_model_calls_for_material':0}
template=make_template(source,canonical,origin_record)
immutable_json(stage/'compiler_template.json',template)
library=SkillLibrary();library.add_compiler_template(template)
frozen=library.freeze(stage/'library.frozen.json')
assert SkillLibrary.restore(stage/'library.frozen.json').export()==library.export()
assert science_files(root)==files and counters()==before
receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'paid_origin':origin_record,
 'source':source['key'],'template_hash':template['template_hash'],'canonical_program_hash':digest(program),
 'analysis_binding':scientific_code_binding(files),'offline_evidence':'offline_reference_frontend_v8_20261108.json',
 'source_units':len(structure.ledger.clauses),'unknown_source_scopes':assessment['unknown_scope'],
 'normalization_audit':audit,'residual_context_proofs':compiled['residual_context_proofs'],
 'all_executable_DAGs_and_51_Boolean_domains_identical':True,'Boolean_domain_count':len(theory.domains),
 'no_new_inputs_or_rules_or_truth_values':True,'canonical_roundtrip_and_frozen_restore_exact':True,
 'assessment_before_any_observation':assessment,'teacher_usage':paid['invocation']['usage'],
 'teacher_elapsed_seconds':paid['elapsed_seconds'],'ledger_and_all_prior_meta_unchanged':True,
 'ledger_snapshot':before,'new_model_calls':0,'new_oracle_views':0,'labels_read':False,
 'independent_executor_core_success':False,'full_goal_complete':False,
 'frozen_library_path':str((stage/'library.frozen.json').relative_to(root))}
immutable_json(stage/'normalization_receipt.json',receipt)
immutable_json(root/'reports/rr_method_runtime_20261107/reference_pal_full_teacher_recovery_v8.json',receipt)
print(json.dumps({k:receipt[k] for k in ('source','template_hash','source_units','unknown_source_scopes','Boolean_domain_count','new_model_calls','independent_executor_core_success','frozen_library_path')},ensure_ascii=False))
