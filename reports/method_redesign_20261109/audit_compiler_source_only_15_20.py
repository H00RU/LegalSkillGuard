import hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_compiler_runtime import run
R=Path(__file__).resolve().parents[2];B=R/'artifacts/rr_method_redesign_20261109';S=B/'contract_compiler_induction_v1_20261110'
def read(p):return json.loads(p.read_text())
def snap():
 with sqlite3.connect('file:'+str(R/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}
before=snap();old=read(S/'training_seal.json');pub={p['key']:p for p in read(R/'data/packets/rr_v2/public_train.json')['sources']}
selections=[]
for ordinal in [15,20]:
 key=old['sources']['train'][ordinal-1];p=pub[key];assert p['dataset']=='ContractNLI'
 selections.append({'ordinal':ordinal,'source':key,'document':p['public']['document'],'group':p['group'],'document_sha256':hashlib.sha256(p['public']['document'].encode()).hexdigest()})
plan={'source_mothers_fixed_before_program_execution':[15,20],'selection_after_source_literature_review_not_blind':True,
      'sources':selections,'no_native_queries_predictions_labels_or_new_pairs':True,'new_model_calls':0}
immutable_json(S/'source_only_15_20_plan.json',plan)
results=[]
for arm in ['scope_compiler','ordinary_program']:
 raw=read(S/(arm+'_learned.json'))['physical_response']['value']['code']
 code=raw
 if arm=='ordinary_program':code+='\n\ndef infer(document, query):\n    return _compile_graph(document)\n'
 for p in selections:
  entry=run(code,p['document'],[None])[0]
  results.append({'arm':arm,'ordinal':p['ordinal'],'source':p['source'],'original_learned_code_sha256':hashlib.sha256(raw.encode()).hexdigest(),
   'source_graph_entrypoint_wrapper_only':arm=='ordinary_program','native_question_not_executed':True,'result':entry})
immutable_json(S/'source_only_15_20_raw_graphs.json',{'plan_sha256':hashlib.sha256((S/'source_only_15_20_plan.json').read_bytes()).hexdigest(),
 'results':results,'new_model_calls':0,'new_native_pairs_or_labels':0,'ledger_rows_unchanged':before==snap()})
assert before==snap()
for row in results:
 g=row['result'].get('value',{});print(json.dumps({'arm':row['arm'],'ordinal':row['ordinal'],'scopes':g.get('scopes'),'rules':g.get('rules'),'error':row['result'].get('error')},ensure_ascii=False))
