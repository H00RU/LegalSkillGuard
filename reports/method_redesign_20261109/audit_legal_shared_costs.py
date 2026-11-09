"""Account for shared preparation once; do not attribute generic execution savings."""
from datetime import datetime,timezone
from pathlib import Path
import json,time
from legal_skill_guard.rr.legal_library_runtime import execute_library
ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'reports/method_redesign_20261109'
A=ROOT/'artifacts/rr_method_redesign_20261109'


def read(p):return json.loads(p.read_text())


def main():
 calls=read(REPORT/'legal_native_pilot_ledger.json')['calls']
 source=[c for c in calls if c['role']=='teacher']
 facts=next(c for c in calls if c['id']=='legal_relations_exceptions_native_v3_20261109:facts')
 direct=next(c for c in calls if c['id']=='legal_relations_shared_direct_v1_20261109:direct')
 assert len(source)==2 and facts['physical_status']==direct['physical_status']=='completed'
 library=read(A/'legal_library_runtime_v1_20261109/frozen_library.json')
 cases=read(A/'legal_grounded_replay_v1_20261109/shared_grounded_cases.json')['cases']
 start=time.monotonic();outputs=[execute_library(library,c) for c in cases];seconds=time.monotonic()-start
 common={'teacher_physical_calls':2,'teacher_input_tokens':sum(c['input_tokens'] for c in source),'teacher_output_tokens':sum(c['output_tokens'] for c in source),'teacher_request_elapsed_seconds':sum(c['elapsed_seconds'] for c in source),
 'executor_fact_calls':1,'executor_fact_input_tokens':facts['input_tokens'],'executor_fact_output_tokens':facts['output_tokens'],'executor_fact_elapsed_seconds':facts['elapsed_seconds']}
 out={'captured_utc':datetime.now(timezone.utc).isoformat(),'cohort':'Same four already observed TRAIN sources; post-hoc cost accounting, not a new experiment',
 'common_material_acquisition_charged_once':common,
 'symbolic_library_marginal':{'additional_executor_calls':0,'additional_teacher_calls':0,'batch_cpu_wall_seconds_single_pass':seconds,'cache_warm':True,'n':4,'not_GPU_time':True},
 'ordinary_same_library_cache_marginal':{'additional_executor_calls':0,'additional_teacher_calls':0,'same_algorithm_and_inputs':True,'not_an_independent_acquisition_control':True},
 'full_shared_information_direct_marginal':{'executor_calls':1,'input_tokens':direct['input_tokens'],'output_tokens':direct['output_tokens'],'total_tokens':direct['input_tokens']+direct['output_tokens'],'elapsed_seconds':direct['elapsed_seconds']},
 'observed_extra_direct_request_avoided_by_both_symbolic_paths':{'physical_calls':1,'tokens':direct['input_tokens']+direct['output_tokens'],'request_elapsed_seconds':direct['elapsed_seconds']},
 'saving_attribution':'Shared deterministic symbolic execution, not either new legal mechanism uniquely. The ordinary same-library cache avoids exactly the same request.',
 'raw_direct_comparability':'The earlier direct control lacked later priority review and common grounded facts; its3/4 is retained, but it is not an identical-preparation end-to-end cost control.',
 'total_acquisition_or_end_to_end_superiority_established':False,
 'strong_control_gap':'An independently specified source/interface acquisition or reuse strategy has not been compared. Identical-runtime cache parity is an equivalence check, not proof that legal acquisition has no value.',
 'native_predictions':[{'ordinal':c['ordinal'],'answer':o['answer']} for c,o in zip(cases,outputs)],
 'zero_new_model_calls':True,'zero_new_labels':True,'new_sources':0,'cash_invoice_unknown':True,'goal_complete':False}
 (REPORT/'legal_shared_cost_comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'common':common,'direct_extra_tokens':direct['input_tokens']+direct['output_tokens'],'direct_extra_seconds':direct['elapsed_seconds'],'library_batch_seconds':seconds,'unique_mechanism_cost_advantage':False,'new_calls':0},ensure_ascii=False))
if __name__=='__main__':main()
