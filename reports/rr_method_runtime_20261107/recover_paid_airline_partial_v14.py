"""Recover typed partial material; original unknown scopes and paid failure stay."""
from pathlib import Path
import hashlib,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.compiler_templates import make_template,validate_template
from legal_skill_guard.rr.pal_frontend import lower_pal,render_pal
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.checkpoint import immutable_json

run='reference_pal_teacher_airline2_v13_20261108';stage=ROOT/'artifacts/rr_method_runtime_20261107'/run
seal=json.loads((stage/'seal.json').read_text());cid=run+':compile';path=stage/'calls'/digest(cid)/'result.json';paid=json.loads(path.read_text())
with sqlite3.connect('file:'+str((ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve())+'?mode=ro',uri=True) as db:
 before=db.execute('select role,count(*) from calls group by role').fetchall()
 row=db.execute('select role,source,status,request_hash,result from calls where id=?',(cid,)).fetchone()
assert row[:3]==('teacher',seal['source']['key'],'completed') and json.loads(row[4])==paid
program,_=lower_pal(seal['source'],paid['value']['code']);compiled=compile_source(seal['source'],program)
canonical=render_pal(program);restored,_=lower_pal(seal['source'],canonical);assert restored==program
assessment=assess_source(compiled);assert len(assessment['unknown_scope'])==23 and assessment['answer'] is None
origin={'role':'teacher','call_id':cid,'request_hash':row[3],'model':paid['model'],
    'result_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'actual_partial_program_canonical_rendering':True,'untranslated_source_units':assessment['unknown_scope'],
    'no_missing_rule_or_default_filled':True,'not_executor_core_success':True}
item=make_template(seal['source'],canonical,origin)
assert assess_source(validate_template(item))==assessment
output=ROOT/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_airline2_partial_v14_20261108'
immutable_json(output/'compiler_template.json',item)
library=SkillLibrary(compiler_templates=[item]);library.freeze(output/'library.frozen.json')
assert SkillLibrary.restore(output/'library.frozen.json').export()==library.export()
with sqlite3.connect('file:'+str((ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve())+'?mode=ro',uri=True) as db:assert before==db.execute('select role,count(*) from calls group by role').fetchall()
evidence={'physical_call_id':cid,'teacher_usage':paid['invocation']['usage'],'teacher_elapsed_seconds':paid['elapsed_seconds'],
 'raw_code_sha256':hashlib.sha256(paid['value']['code'].encode()).hexdigest(),'template_hash':item['template_hash'],
 'source_IR_counts':{k:len(v) for k,v in program.items() if k!='query'},'assessment':assessment,
 'stored_as_partial_only':True,'original_failure_and_paid_raw_unchanged':True,
 'actual_numeric_record_fields_checked_without_defaults':True,'field_only_records':compiled['numeric_field_only_record_nodes'],
 'untranslated_source_units_not_discharged':True,'new_model_calls':0,'new_oracle_views':0,'full_goal_complete':False}
immutable_json(ROOT/'reports/rr_method_runtime_20261107/paid_airline_partial_recovery_v14.json',evidence)
print(json.dumps({k:v for k,v in evidence.items() if k not in {'assessment'}}),flush=True)
