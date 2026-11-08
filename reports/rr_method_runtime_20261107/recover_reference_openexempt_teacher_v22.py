"""Recover only actual reachable paid code; missing operative rules stay missing."""
from pathlib import Path
import ast
from copy import deepcopy
import hashlib
from itertools import product
import json
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.clause_scope import syntax_only_source_unit
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.pal_frontend import lower_pal,render_pal
from legal_skill_guard.rr.source_program import compile_source,source_theory
from legal_skill_guard.rr.compiler_templates import make_template
from legal_skill_guard.rr.learning import SkillLibrary

origin=ROOT/'artifacts/rr_method_runtime_20261107/reference_pal_teacher_openexempt1_v21_20261108'
cid=origin.name+':compile';raw_path=origin/'calls'/digest(cid)/'result.json'
raw_bytes=raw_path.read_bytes();paid=json.loads(raw_bytes);source=json.loads((origin/'seal.json').read_text())['source']
code=paid['value']['code'];tree=ast.parse(code);structure=inspect_source(source)
units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
fact_ids=[c.id for c in structure.ledger.clauses if structure.roles[c.id]['role']=='fact']
assumption='Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.'
assert assumption in units['s1'] and assumption in units['s162']
assert all(not any(word in units[s].lower() for word in ['business use','commercial use','not for personal use']) for s in fact_ids)
defaults={'ec_personal_use','ev_personal_use'}
discard=[n for n in tree.body if isinstance(n,ast.FunctionDef) and '_unresolved_' in n.name]
discard_names={n.name for n in discard}
assert not discard_names&{n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}

def edit_text(text,edits):
    for start,end,value in sorted(edits,reverse=True):text=text[:start]+value+text[end:]
    return text

def positions(text):
    rows=[0]
    for line in text.splitlines(keepends=True):rows.append(rows[-1]+len(line))
    return rows

offset=positions(code);edits=[]
for node in discard:
    start=min(node.lineno,*[d.lineno for d in node.decorator_list])
    edits.append((offset[start-1],offset[node.end_lineno],''))
for n in tree.body:
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in defaults:
        assert isinstance(n.value,ast.Constant) and n.value.value is True
        expected='s1' if n.targets[0].id.startswith('ec_') else 's162'
        assert code.splitlines()[n.lineno-1].endswith('# '+expected)
        edits.append((offset[n.lineno-1],offset[n.end_lineno],''))
for n in ast.walk(tree):
    if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id in defaults:
        edits.append((offset[n.lineno-1]+n.col_offset,offset[n.end_lineno-1]+n.end_col_offset,'True'))
partial=edit_text(code,edits);program,_=lower_pal(source,partial);before=compile_source(source,program)

tree=ast.parse(partial);offset=positions(partial);edits=[];identities=[]
for n in tree.body:
    if not isinstance(n,ast.FunctionDef):continue
    dec=n.decorator_list[0]
    if (isinstance(dec,ast.Call) and isinstance(dec.func,ast.Name) and dec.func.id=='scope' and
            isinstance(n.body[0],ast.Return) and isinstance(n.body[0].value,ast.Constant) and
            n.body[0].value.value is True and syntax_only_source_unit(units[dec.args[0].value])):
        identities.append(n.name);start=min(n.lineno,*[d.lineno for d in n.decorator_list])
        edits.append((offset[start-1],offset[n.end_lineno],''))
for n in ast.walk(tree):
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in identities:
        assert not n.args and not n.keywords
        edits.append((offset[n.lineno-1]+n.col_offset,offset[n.end_lineno-1]+n.end_col_offset,'True'))
compact=edit_text(partial,edits);program,_=lower_pal(source,compact);after=compile_source(source,program)
left=source_theory(before);right=source_theory(after)
assert left.domains==right.domains and before['observations']==after['observations']
assert {r.source for r in left.residuals if r.unknown_scope}=={r.source for r in right.residuals if r.unknown_scope}
names=sorted(left.domains);checks=[]
for values in product(*(left.domains[n] for n in names)):
    choices=dict(zip(names,values))
    a=before['query'].execute({**before['slots'],**choices})['answer']
    b=after['query'].execute({**after['slots'],**choices})['answer']
    assert digest(a)==digest(b)
    checks.append(digest([choices,a]))
canonical=render_pal(program);assert lower_pal(source,canonical)[0]==program
with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
    role,status,request_hash=db.execute('select role,status,request_hash from calls where id=?',(cid,)).fetchone()
assert (role,status)==('teacher','completed')
template=make_template(source,canonical,{'role':'teacher','call_id':cid,'request_hash':request_hash,
    'model':paid['model'],'raw_result_sha256':hashlib.sha256(raw_bytes).hexdigest(),
    'adaptation':'Unreferenced invalid wrapper functions omitted with every missing source obligation retained; existing provided True assumption inlined; pure citation-identity scopes algebraically eliminated.',
    'not_full_statutory_semantics_or_executor_success':True})
stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_frontend_prior_openexempt1_partial_v22_20261109'
immutable_json(stage/'compiler_template.json',template)
library=SkillLibrary(stage='formal_train');library.add_compiler_template(template);library.freeze(stage/'library.frozen.json')
audit={'source':source['key'],'origin_call_id':cid,'raw_result_sha256':hashlib.sha256(raw_bytes).hexdigest(),
    'raw_program_bytes_unchanged':raw_path.read_bytes()==raw_bytes,'new_model_or_oracle_calls':0,'labels_read':False,
    'unreferenced_invalid_wrappers_removed':sorted(discard_names),
    'existing_public_personal_use_defaults_inlined':sorted(defaults),'public_assumption_sources':['s1','s162'],
    'pure_identity_scopes_eliminated':len(identities),'whole_original_native_query_retained':True,
    'all_declared_Boolean_completions_compared':len(checks),'completion_results_hash':digest(checks),
    'observations_and_domains_unchanged':True,'untranslated_operative_sources_unchanged':True,
    'unknown_source_units':sorted(r.source for r in right.residuals if r.unknown_scope),
    'guarded_rule_outputs':len(program['clauses']),'real_scopes':len(program['scopes']),
    'original_code_chars':len(paid['value']['code']),'compact_code_chars':len(canonical),
    'partial_material_only':True,'executor_core_success':False,'full_goal_complete':False,'template_hash':template['template_hash']}
immutable_json(stage/'recovery_audit.json',audit)
immutable_json(ROOT/'reports/rr_method_runtime_20261107/reference_openexempt_partial_recovery_v22.json',audit)
print(json.dumps({k:v for k,v in audit.items() if k not in {'unknown_source_units','unreferenced_invalid_wrappers_removed'}},ensure_ascii=False))
