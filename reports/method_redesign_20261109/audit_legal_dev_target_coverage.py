"""Static learned-target availability on original public DEV queries only.

No facts, grades, teacher prompts, fitting, or new model calls. This is not a
DEV evaluation pass or an acquisition queue derived from DEV content.
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
from legal_skill_guard.rr.legal_case_grounding import compile_question,citation
ROOT=Path(__file__).resolve().parents[2]


def main():
 p=ROOT/'data/packets/rr_v2/public_dev.json';public=json.loads(p.read_text())['sources']
 lib=json.loads((ROOT/'artifacts/rr_method_redesign_20261109/legal_library_runtime_v1_20261109/frozen_library.json').read_text())['program']
 rows=[]
 for source in public:
  if not source['key'].startswith('SARA_v2_Binary:'):continue
  query=source['public']['query'];target=citation(query)
  candidates=[r for r in lib['rules'] if citation(r['authority'])==target]
  try:compiled=compile_question(query,lib);available=True;error=None
  except ValueError as e:compiled=None;available=False;error=str(e)
  rows.append({'source':source['key'],'query':query,'authority':target,'matching_source_rule_ids':[r['id'] for r in candidates],'target_available':available,'compiled_question':compiled,'reason':error})
 assert len(rows)==8
 out={'captured_utc':datetime.now(timezone.utc).isoformat(),'packet_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scope':'Original SARA DEV public query target metadata only','rows':rows,'target_available':sum(r['target_available'] for r in rows),'n':8,'is_an_accuracy_or_semantic_evaluation':False,'DEV_facts_or_labels_used_for_training':False,'DEV_labels_opened':False,'source_learning_or_selection_performed_by_this_audit':False,'new_model_calls':0,'teacher_DEV_calls':0,'new_sources':0,'goal_complete':False}
 q=ROOT/'reports/method_redesign_20261109/legal_dev_target_coverage.json';q.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'available_targets':out['target_available'],'n':8,'not_DEV_accuracy':True,'new_calls':0}))
if __name__=='__main__':main()
