"""Original128 TRAIN input capacity, read-only tokenizer; no generations/labels."""
from pathlib import Path
import hashlib,json,sqlite3,sys,time
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.atom_frontend import atom_prompt
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.pal_frontend import pal_prompt
from legal_skill_guard.rr.rule_templates import matching_rule_template,instance_request
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.checkpoint import immutable_json

cfg=json.loads((ROOT/'configs/rr_v2_preflight.json').read_text());manifest=json.loads((ROOT/cfg['source_manifest']).read_text())
packet=ROOT/'data/packets/rr_v2/public_train.json'
assert hashlib.sha256(packet.read_bytes()).hexdigest()==manifest['packet_sha256']['public_train']
public={s['key']:s for s in json.loads(packet.read_text())['sources']}
materials=json.loads((ROOT/'docs/rr_v2/paid_compiler_materials_20261108.json').read_text())['materials']
code= science_files(ROOT);library=SkillLibrary(stage='formal_train');requests=[]
for number,sid in enumerate(manifest['formal_train_order'],1):
 source=public[sid];current=library.export()
 if source['dataset']=='ProofWriter_OWA_depth5':messages=atom_prompt(source,current);route='source_aligned_atoms'
 else:
  match=matching_rule_template(source,current)
  if match:messages,_=instance_request(source,match);route='same_statute_instance'
  else:messages=pal_prompt(source,current);route='PAL_program'
 requests.append({'number':number,'source':sid,'dataset':source['dataset'],'route':route,'messages':messages,
     'strictly_earlier_compiler_sources':[t['source']['key'] for t in library.compiler_templates]})
 for entry in materials:
  if entry['source']==sid:library.add_compiler_template(json.loads((ROOT/entry['path']).read_text()))
client=MethodExecutor(None,ROOT/'artifacts/rr_method_runtime_20261107',cfg['executor'])
with sqlite3.connect('file:'+str((ROOT/cfg['ledger_path']).resolve())+'?mode=ro',uri=True) as db:before=db.execute('select role,count(*) from calls group by role').fetchall()
prior=json.loads((ROOT/'reports/rr_method_runtime_20261107/reference_prefix_input_capacity_v16.json').read_text());prior_rows={r['source']:r for r in prior['rows']}
start=time.monotonic()
def measure(row):
 old=prior_rows[row['source']];unchanged=digest(row['messages'])==old['messages_hash']
 tokens=old['input_tokens'] if unchanged else client.tokenize(row['messages'],thinking=False)['count']
 return {k:v for k,v in row.items() if k!='messages'}|{'input_tokens':tokens,'fits':tokens+cfg['executor']['max_tokens']<=cfg['executor']['context_tokens'],'messages_hash':digest(row['messages']),'same_initial_messages_as_parent':unchanged}
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(measure,requests))
with sqlite3.connect('file:'+str((ROOT/cfg['ledger_path']).resolve())+'?mode=ro',uri=True) as db:after=db.execute('select role,count(*) from calls group by role').fetchall()
assert before==after and science_files(ROOT)==code
value={'scope':'original128 TRAIN, actual initial messages with existing paid compiler templates added strictly after their own source',
 'no_unknown_future_patterns_assumed':True,'known_B_pattern_payload_not_included':True,'source_count':len(rows),
 'actual_tokenizer_requests':sum(not r['same_initial_messages_as_parent'] for r in rows),'unchanged_parent_tokenizer_evidence_reused':sum(r['same_initial_messages_as_parent'] for r in rows),'generation_requests':0,'labels_read':False,'TEST_read':False,
 'ledger_call_counts_before':before,'ledger_call_counts_after':after,'code_bytes_unchanged':True,'code_files':code,
 'elapsed_seconds':time.monotonic()-start,'max_input_tokens':max(r['input_tokens'] for r in rows),
 'available_input_tokens':cfg['executor']['context_tokens']-cfg['executor']['max_tokens'],
 'all_fit':all(r['fits'] for r in rows),'rows':rows,'full_goal_complete':False}
path=ROOT/'reports/rr_method_runtime_20261107/reference_prefix_input_capacity_v17.json';immutable_json(path,value)
print(json.dumps({k:v for k,v in value.items() if k not in {'rows','code_files'}}),flush=True)
