"""Final native-reference condition for the isolated EC-context diagnostic."""
from __future__ import annotations

import copy
import fcntl
import json
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from jsonschema import validate
from experiments.openexempt_online import Online,_head_admission,actor_payload,native_claim_feedback
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison,now,read,sha
from legal_skill_guard.learning.legal_namespace import (
    allowable_namespaces,decode_asset_references,decode_classification,
    decode_reference,public_asset_catalog,public_catalog,
)
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.openexempt import metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

BASE=Path(__file__).resolve().parent
OUT=BASE/'own_EC_native_context_TRAIN32_run01'
PREVIOUS=ROOT/'artifacts/research/openexempt_ev_learning_20261104/bounded_train_pilot_run01'
OLD=ROOT/'runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01'
CONFIG=ROOT/'configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json'
PROTOCOL=ROOT/'docs/research/OPENEXEMPT_OWN_EC_NATIVE_CONTEXT_TRAIN32_20261105.md'
NOTICE=(' An earlier answer from this same executor is supplied as unverified working '
        'context, not a solved step, a reference answer or additional legal authority. '
        'Check it against the original facts and statutes and correct it where needed. '
        'The EV task still requires all independently applicable alternatives and their '
        'numeric whole-asset values; do not blindly copy or treat omitted citations as ineligible.')


class Diagnostic:
    check=Comparison.check
    call=Comparison.call
    progress=Online.progress
    grade=Online.grade

    def __init__(self):
        self.cfg=read(CONFIG)
        self.original_generation=copy.deepcopy(self.cfg['generation'])
        self.cfg['generation']['timeout_seconds']=600
        self.run_id='openexempt_own_EC_native_context_TRAIN32_diagnostic_20261105_run01'
        self.out=OUT
        reference=read(PREVIOUS/'protocol.json')
        self.ids=reference['source_ids']
        self.current=set(reference['current_source_ids'])
        self.bank=reference['parent_bank']
        self.parents=read(PREVIOUS/'parent_records.json')
        self.rows=read(ROOT/self.cfg['input_packet'])['rows']
        self.stop=False
        self.current_batch=4
        self.native,self.teachers,self.reuse_events=[],[],[]
        self.teacher_attempts=0
        self.started=None
        self.attempts=0
        self.lock=threading.Lock()
        self._dispatch=PhaseDispatch(self.cfg,environment=read(ROOT/self.cfg['inference_environment']),
                                    on_failure=lambda:setattr(self,'stop',True))
        self.bindings=dict(read(CONFIG.with_suffix('.frozen.json'))['files'])
        paths=[Path(__file__),PROTOCOL,BASE/'run_own_ec_context_diagnostic.py',
               BASE/'own_EC_context_TRAIN32_run01/protocol.json',
               BASE/'own_EC_context_TRAIN32_run01/scored_records.json',PREVIOUS/'protocol.json',PREVIOUS/'parent_records.json',
               OLD/'publications/b3.json',OLD/'batches/b4_prequential_records.json']
        self.bindings.update({str(p):sha(p) for p in paths})
        pub=read(OLD/'publications/b3.json')
        assert pub['bank']==self.bank
        last=next(d for d in reversed(pub['training_decisions']) if d['accepted'])
        source={(r['case_id'],r['family']):r for r in last['actual_replay']}
        source.update({(r['case_id'],r['family']):r for r in read(OLD/'batches/b4_prequential_records.json')['skills']})
        self.context={}
        for cid in self.ids:
            ec=source[cid,'EC']
            assert ec['parse_error'] is None and ec['bank_sha256']==csha(self.bank)
            row=next(r for r in self.rows if r['case_id']==cid and r['family']=='EC')
            evrow=next(r for r in self.rows if r['case_id']==cid and r['family']=='EV')
            assert public_asset_catalog(row)==public_asset_catalog(evrow)
            assert public_catalog(row)==public_catalog(evrow)
            messages,schema,_=actor_payload(row,self.bank,grounded=True,direct_numeric=True,asset_references=True)
            rawpath=ROOT/ec['raw_call_path'];inp=rawpath.with_suffix('.input.json')
            original=read(inp);raw=read(rawpath)
            assert messages==original['messages'] and schema==original['schema']
            submission=json.loads(raw['response']['content'])
            assert submission==ec['public_label_submission']
            decoded=decode_classification(decode_asset_references(copy.deepcopy(submission),
                public_asset_catalog(row)),public_catalog(row))
            assert decoded==ec['parsed']['answer']
            assert all(isinstance(cs,list) and all(isinstance(c,str) for c in cs) for cs in decoded.values())
            self.context[cid]={'answer':submission,'EC_raw_path':ec['raw_call_path'],
                'EC_raw_sha256':sha(rawpath),'EC_input_sha256':sha(inp),
                'EC_bank_sha256':ec['bank_sha256']}
            self.bindings[str(rawpath)]=sha(rawpath)
            self.bindings[str(inp)]=sha(inp)
            previous_input=BASE/'own_EC_context_TRAIN32_run01/native'/f'{cid}_EV_own_EC_context.input.json'
            self.bindings[str(previous_input)]=sha(previous_input)
        assert len(self.context)==32 and len(self.ids)==32 and len(self.current)==16
        OUT.mkdir(exist_ok=False)
        for sig in [signal.SIGINT,signal.SIGTERM]:
            signal.signal(sig,lambda *_:setattr(self,'stop',True))
        self.check()
        assert WireClient(self.cfg['generation']).readiness()['ready']
        RunStore.immutable_json(OUT/'protocol.json',{'at':now(),'seen_TRAIN_diagnostic_not_TEST_or_main_method':True,
            'source_ids':self.ids,'current_source_ids':sorted(self.current),'bank':self.bank,
            'bank_sha256':csha(self.bank),'max_teacher_calls':0,'max_EV_calls':32,
            'max_actor_wall_seconds':1800,'actual_generation':self.cfg['generation'],
            'original_generation':self.original_generation,'only_transport_timeout_differs':True,
            'system_notice':NOTICE,'EC_forecasts_allowlisted_no_scores_or_targets':self.context,
            'unverified_context_not_gold_not_forced_citation_filter':True,
            'do_not_use_unqualified_atomic_candidate':True,'frozen_files':self.bindings,
            'formal_method_adoption_requires_user_confirmation':True})

    def answer(self,row):
        self.check()
        context=self.context[row['case_id']]
        messages,schema,supplied=actor_payload(row,self.bank,grounded=True,
            direct_numeric=True,asset_references=True)
        messages=copy.deepcopy(messages)
        messages[0]['content']+=NOTICE
        messages.append({'role':'user','content':json.dumps({
            'earlier_same_model_EC_forecast_unverified':context['answer'],
            'not_ground_truth_or_a_supplied_solved_step':True,
            'may_be_incomplete_or_wrong_check_original_facts_and_law':True,
            'return_only_the_original_EV_answer_schema':True},ensure_ascii=False,separators=(',',':'))})
        catalog,assets=public_catalog(row),public_asset_catalog(row)
        previous=read(BASE/'own_EC_context_TRAIN32_run01/native'/f"{row['case_id']}_EV_own_EC_context.input.json")
        assert messages[:-1]==previous['messages'][:-1] and schema==previous['schema']
        a=json.loads(messages[-1]['content']);b=json.loads(previous['messages'][-1]['content'])
        key='earlier_same_model_EC_forecast_unverified'
        assert {k:v for k,v in a.items() if k!=key}=={k:v for k,v in b.items() if k!=key}
        assert decode_classification(decode_asset_references(copy.deepcopy(a[key]),assets),catalog)==b[key]
        path=OUT/'native'/f"{row['case_id']}_EV_own_EC_native_context.json"
        RunStore.immutable_json(path.with_suffix('.input.json'),{'messages':messages,'schema':schema,
            'bank_sha256':csha(self.bank),'public_citation_catalog':catalog,
            'public_asset_reference_catalog':assets,'public_allowable_jurisdictions':sorted(allowable_namespaces(row)),
            'delivered_skill_ids':[s['id'] for s in supplied],
            'own_EC_forecast_provenance':{k:v for k,v in context.items() if k!='answer'},
            'no_grading_targets_scores_teacher_or_private_annotations_in_actor_input':True,
            'exact_request_fingerprint':csha({'messages':messages,'schema':schema,'generation':self.cfg['generation']})})
        with self.lock:
            if self.started is None:self.started=time.monotonic()
            if self.attempts>=32 or time.monotonic()-self.started>=1200:
                raise TimeoutError('Authorized call/dispatch budget exhausted; no retries')
            self.attempts+=1
        response=self.call(path,messages,schema,self.cfg['generation']['max_tokens'],
            {'stage':'own_EC_native_context_diagnostic','arm':'same_parent_with_own_EC_context',
             'document_id':row['case_id'],'family':'EV','call_role':'openexempt','bank_sha256':csha(self.bank)})
        parsed=None;error=None;submission=None
        try:
            submission=json.loads(response['content']);validate(submission,schema)
            if response['finish_reason']!='stop':raise ValueError('Incomplete native output: '+str(response['finish_reason']))
            values=decode_asset_references(copy.deepcopy(submission),assets)
            parsed={'answer':{a:[{'citation':decode_reference(c['citation_ref'],catalog),
                'claim_value':c['claim_value']} for c in claims] for a,claims in values.items()}}
        except (ValueError,TypeError,KeyError) as exc:error=repr(exc)
        except Exception as exc:
            from jsonschema import ValidationError
            if not isinstance(exc,ValidationError):raise
            error=repr(exc)
        result={'case_id':row['case_id'],'source_key':row['source_key'],'family':'EV',
            'stage':'own_EC_native_context_diagnostic','arm':'same_parent_with_own_EC_context',
            'bank_sha256':csha(self.bank),'parsed':parsed,'parse_error':error,
            'raw_call_path':str(path.relative_to(ROOT)),'public_label_submission':submission,
            'execution_error':None,'native_program':None,'execution_receipt':None,
            'delivered_skill_ids':[s['id'] for s in supplied]}
        RunStore.immutable_json(path.with_suffix('.answer.json'),result)
        return result

    def run(self):
        rows=sorted((r for r in self.rows if r['family']=='EV' and r['case_id'] in self.ids),key=lambda r:r['case_id'])
        records=self._dispatch.native(self.answer,rows)
        RunStore.immutable_json(OUT/'predictions_before_grading.json',records)
        self.grade(records)
        RunStore.immutable_json(OUT/'scored_records.json',records)
        pick=lambda rs,c:[r for r in rs if (r['case_id'] in self.current)==c]
        gate=_head_admission('EV',metrics(pick(self.parents,True)),metrics(pick(records,True)),
            metrics(pick(self.parents,False)),metrics(pick(records,False)),contract=self.cfg['admission_contract'])
        pm,cm=metrics(self.parents)['EV'],metrics(records)['EV']
        old={r['case_id']:r for r in self.parents}
        both=[(old[r['case_id']],r) for r in records if old[r['case_id']]['parse_error'] is None and r['parse_error'] is None]
        errors=[]
        for rs in [self.parents,records]:
            total={k:0 for k in ['invalid_response','correct','missing','incorrect_value','extra_or_duplicate']}
            for r in rs:
                target=read(ROOT/self.cfg['grading_directory']/f"{r['case_id']}.json")['targets']['EV']
                fb=native_claim_feedback(r,target)
                for k in total:total[k]+=int(fb.get(k,0))
            errors.append(total)
        result={'at':now(),'state':'completed','original_parent_metrics':pm,'EC_context_metrics':cm,
            'gain_pp':{k:100*(cm[k]-pm[k]) for k in ['f1','full_output_f1']},
            'both_parseable_pair_net_contribution_pp':{k:100*sum(b['score'][k]-a['score'][k] for a,b in both)/32 for k in ['f1','full_output_f1']},
            'original_pilot_cohort_EV_gate':gate,'parent_errors':errors[0],'EC_context_errors':errors[1],
            'new_teacher_calls':0,'actual_new_EV_generations':len(self.native),
            'fresh_EC_generations':0,'frozen_same_bank_EC_forecasts_used':32,
            'actor_phase_elapsed_seconds':time.monotonic()-self.started,
            'context_encoding':'native_asset_id_to_citation_ref',
            'decoded_condition_semantic_identity_verified_in_every_request':True,
            'formal_method_changed':False,'no_automatic_training_or_paper_adoption':True}
        RunStore.immutable_json(OUT/'terminal.json',result)
        self.progress('terminal',state='completed')
        print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    runner=None
    try:
        with (ROOT/'artifacts/openexempt_training.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            runner=Diagnostic();runner.run()
    except BaseException as exc:
        if OUT.exists() and not (OUT/'failure.json').exists():
            RunStore.immutable_json(OUT/'failure.json',{'at':now(),'error':repr(exc),
                'traceback':traceback.format_exc(),'actual_new_native_calls':len(runner.native) if runner else None,
                'failed_usage_unknown_not_zero':True,'no_fallback_or_quality_retry':True})
        raise
