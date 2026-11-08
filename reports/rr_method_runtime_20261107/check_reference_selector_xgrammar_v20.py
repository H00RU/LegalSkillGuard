"""Actual paid wire + pinned grammar reproduction, without model/label access."""
from pathlib import Path
import sys,os,json,base64,hashlib,copy,importlib.metadata
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
import xgrammar as xg
from xgrammar.testing import _is_grammar_accept_string
from jsonschema import Draft202012Validator
from legal_skill_guard.rr.rule_templates import matching_rule_template,instance_request

def guard(event,args):
 if event in {'socket.connect','socket.bind','socket.sendto','subprocess.Popen'}:raise RuntimeError('Backend regression cannot dispatch')
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)) and 'grading_only' in os.fsdecode(args[0]):raise RuntimeError('No answer packet in backend regression')
sys.addaudithook(guard)

def paid(run):
 stage=ROOT/'artifacts/rr_method_runtime_20261107'/run
 p=next(p for p in (stage/'calls').iterdir() if json.loads((p/'request.json').read_text())['id'].endswith(':parse:0'))
 wire=json.loads(base64.b64decode(json.loads((p/'wire_request.json').read_text())['body_b64']))
 result=json.loads((p/'result.json').read_text())
 return stage,wire,result
stage,wire,result=paid('reference_lines_airline7_v19_20261108');before=wire['response_format']['json_schema']['schema']
seal=json.loads((stage/'seal.json').read_text());match=matching_rule_template(seal['source'],seal['config']['library']);_,after=instance_request(seal['source'],match)
allowed=set(before['properties']['current_item_source']['enum']);assert allowed==set(match['item_sources'])
grammars=[xg.Grammar.from_json_schema(s,any_whitespace=False) for s in (before,after)]
body=json.loads(result['content']);rows=[]
for sid in [*['s'+str(n) for n in range(201)],'s156\n','s156x','forbidden','']:
 value=copy.deepcopy(body);value['current_item_source']=sid;raw=json.dumps(value)
 validators=[not list(Draft202012Validator(s).iter_errors(value)) for s in (before,after)]
 accepted=[_is_grammar_accept_string(g,raw) for g in grammars]
 expected=sid in allowed
 assert validators==[expected,expected] and accepted[1]==expected,(sid,validators,accepted)
 rows.append({'selector':sid,'expected':expected,'original_JSON_schema':validators[0],
  'original_pinned_grammar':accepted[0],'trie_JSON_schema':validators[1],'trie_pinned_grammar':accepted[1]})
assert any(r['selector']=='s155' and r['original_pinned_grammar'] and not r['expected'] for r in rows)
# Small existing legal instance controls use their original literal wire schema.
controls=[]
def order(value,schema):
 if isinstance(value,dict):return {k:order(value[k],v) for k,v in schema.get('properties',{}).items() if k in value}
 if isinstance(value,list):return [order(v,schema.get('items',{})) for v in value]
 return value
for name in ('reference_instance_sara77_v11_20261108','reference_instance_sara79_v12_20261108'):
 _,w,r=paid(name);s=w['response_format']['json_schema']['schema'];g=xg.Grammar.from_json_schema(s,any_whitespace=False);v=order(json.loads(r['content']),s)
 original=_is_grammar_accept_string(g,json.dumps(v));assert original,name
 e=next(iter(v['entity_bindings']));changed=copy.deepcopy(v);changed['entity_bindings'][e]='forbidden'
 rejected=not _is_grammar_accept_string(g,json.dumps(changed));assert rejected,name
 controls.append({'run':name,'wire_order_normalized_JSON_value_accepted':original,'forbidden_entity_rejected':rejected,'new_generation':False})
output={'checked_utc':datetime.now(timezone.utc).isoformat(),'pinned_xgrammar':importlib.metadata.version('xgrammar'),
 'original_actual_request_hash':result['request_hash'],'original_actual_raw_sha256':hashlib.sha256(result['content'].encode()).hexdigest(),
 'original_schema':before,'trie_schema':after,'allowed_source_set_unchanged':True,'candidate_cases':len(rows),
 'original_backend_mismatches':[r for r in rows if r['original_pinned_grammar']!=r['expected']],
 'all_fixed_backend_and_JSON_memberships_exact':True,'rows':rows,'small_legal_controls':controls,
 'network_and_subprocess_blocked':True,'new_model_requests':0,'new_oracle_views':0,'labels_read':False,
 'weights_sampling_seed_thinking_unchanged':True,'serving_process_modified_or_restarted':False,
 'conclusion':'The actual nested11-ID enum is mistranslated by pinned grammar behavior; a forbidden actual response is accepted offline. Existing factored source-ID regex preserves the exact whitelist and rejects all tested forbidden IDs. This is a schema/backend compatibility defect, not a basis for changing thinking or declaring model semantic success.','full_goal_complete':False}
p=ROOT/'reports/rr_method_runtime_20261107/reference_selector_xgrammar_v20.json';assert not p.exists();p.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in output.items() if k not in {'rows','original_schema','trie_schema'}}),flush=True)
