"""Score the already saved frozen executions; no recomputation of learned G."""
import hashlib
from pathlib import Path
from datetime import datetime,timezone
from experiments import legal_skill_evolution_scoped_atom_frozen_reuse as r
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
from legal_skill_guard.rr.checkpoint import immutable_json


def run():
    p,_,public=r.setup();e=r.e
    before=e.read(r.OUT/'execution_before_scoring.json')
    for name,value in before['files'].items():assert hashlib.sha256((r.OUT/name).read_bytes()).hexdigest()==value
    immutable_json(r.OUT/'scoring_protocol.json',{'original_protocol_sha256':e.digest(p),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'actual_saved_source_output_and_execution_retained':True,'new_model_requests':0,
        'original_scoring_receipt_comparison_failure':'Rerunning the solver changes composition timing metadata; it did not change source output. Score the saved actual output directly.',
        'all4_execution_file_hashes_verified_before_grading_load':True})
    grading=e.read(e.prior.prior.GRADING)
    for arm in e.ARMS:
        lib=e.read(r.OUT/'libraries'/arm/'library.json')
        for key in p['reuse_sources']:
            dst=r.OUT/'scores'/arm/e.name_for(key)
            if dst.exists():continue
            row=e.read(r.OUT/'unscored'/arm/e.name_for(key));saved=row['unscored_execution']
            feedback=contract_checker(lib['spec'],public[key],grading[key])(saved['execution']['source_output'])
            for actual,old in zip(feedback['views'],saved['feedback']['views']):
                assert actual['execution']['value']==old['execution']['value']
            immutable_json(dst,{'source':key,'execution':saved['execution'],'feedback':feedback})
            print(e.json.dumps({'arm':arm,'source':key,'correct':sum(bool(v['score'] and v['score']['correct']) for v in feedback['views']),
                'core':sum(v['core_executed'] for v in feedback['views']),'saved_execution_unchanged':True}),flush=True)
    immutable_json(r.OUT/'scoring_complete.json',{'captured_utc':datetime.now(timezone.utc).isoformat(),
        'original4_executions_unchanged':True,'new_model_requests':0,'goal_complete':False})


if __name__=='__main__':run()
