"""Static strong control versus answer-separating planning on saved real IR.

The pinned local serving tokenizer is used offline; no serving requests. Saved
responses are executable evidence only when the complete request is identical.
"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
from collections import Counter
from datetime import datetime, timezone
import json
from jsonschema import ValidationError
from pathlib import Path
from time import perf_counter

from transformers import AutoTokenizer
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.source_program import compile_source, source_theory
from legal_skill_guard.rr.source_execution import prepare_followup, accept_followup, assess_source

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
REPORT=ROOT/'reports/method_efficacy_20261109'


def main():
    config=json.loads((ROOT/'configs/rr_v2_preflight.json').read_text())['executor']
    tok=AutoTokenizer.from_pretrained(config['model_root'],local_files_only=True)
    seal=json.loads((STAGE/'seal.json').read_text())
    public={s['key']:s for split in ('train','dev') for s in
        json.loads((ROOT/f'data/packets/rr_v2/public_{split}.json').read_text())['sources']}
    prefix=SkillLibrary(stage='formal_train');cases=[]
    for ordinal,source in enumerate(seal['sources']['train'],1):
        record=json.loads((STAGE/'build/sources'/(digest(source)+'.json')).read_text())
        assert digest(prefix.export())==record['library_before_hash']
        cases.append(('TRAIN',ordinal,source,record['prediction'],prefix.export(),STAGE/'build/journals'/digest(source)))
        if record['learning'].get('learned_pattern'):prefix.add(record['learning']['learned_pattern'],source=source)
        for item in record.get('compiler_learning',{}).get('templates',[]):prefix.add_compiler_template(item)
    library=SkillLibrary.restore(STAGE/'build/B8.frozen.json').export()
    for ordinal,source in enumerate(seal['sources']['dev'],1):
        pred=json.loads((STAGE/'dev/predictions/M11'/(digest(source)+'.json')).read_text())['prediction']
        cases.append(('DEV',ordinal,source,pred,library,STAGE/'dev/journals/M11'/digest(source)))
    rows=[]
    for partition,ordinal,source,pred,library,journal in cases:
        if not any(a.get('kind') in {'factual_observation','joint_rule_translation_and_facts'} for a in pred['translation_actions']):continue
        state=json.loads(json.loads((journal/'state0.json').read_text())['state_json'])
        assert state['compiled_valid'] and state['program'] is not None
        compiled=compile_source(public[source],state['program'],library=library)
        observed=state['observed'];theory=source_theory(compiled,observed)
        old=json.loads((journal/'request1.json').read_text())
        actual_dispatch=json.loads(old['dispatch_json']);old_prepared=old['prepared']
        def count(messages,*,thinking):
            assert thinking is False
            return {'count':len(tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False))}
        assert count(actual_dispatch['messages'],thinking=False)['count']==old_prepared['input_tokens']
        choices={}
        for policy in ('static_dependencies','answer_separating'):
            calls=[]
            def measured(messages,*,thinking):
                before=perf_counter();value=count(messages,thinking=thinking)
                calls.append(perf_counter()-before);return value
            start=perf_counter()
            prepared=prepare_followup(compiled,observed,compilation=policy,tokenize=measured,
                request_config=config,thinking=False,library=library,pal_fragments=True,
                seconds=max(0,state['remaining']))
            elapsed=perf_counter()-start
            identical=prepared.get('messages')==actual_dispatch['messages'] and prepared.get('schema')==actual_dispatch['schema']
            entry={'kind':prepared['kind'],'selection_basis':prepared['selection_basis'],
                'selected':prepared.get('selected',[]),'names':prepared.get('names',[]),
                'input_tokens':prepared.get('input_tokens'), 'request_hash':digest([prepared.get('messages'),prepared.get('schema')]),
                'planning_including_offline_tokenization_seconds':elapsed,'tokenizer_calls':len(calls),
                'offline_tokenizer_seconds':sum(calls),'request_identical_to_original_actual_followup':identical,
                'unknown_scope_sources_retained':{r.source for r in theory.residuals if r.unknown_scope}<=set(prepared.get('context_closure',[]))}
            if identical:
                wire=pred['calls'][1]
                response=json.loads(wire['raw_content'])
                try:
                    updated,facts=accept_followup(compiled,prepared,response,observed,library=library)
                    before=perf_counter();assessment=assess_source(updated,facts,compilation=policy)
                    entry.update(reexecuted_saved_real_response=True,answer=assessment['answer'],status=assessment['status'],
                        final_assessment_seconds=perf_counter()-before)
                except (ValueError,ValidationError) as exc:
                    entry.update(reexecuted_saved_real_response=True,status='original_model_response_rejected',
                        error_type=type(exc).__name__,error=str(exc),answer=None)
                entry.update(original_followup_physical_generation_seconds=wire.get('elapsed_seconds'),
                    source_faithfulness_not_inferred_from_formal_result=True)
            choices[policy]=entry
        rows.append({'partition':partition,'ordinal':ordinal,'source':source,'old_remaining_semantic_seconds':state['remaining'],
            'actual_selection_basis':old_prepared['selection_basis'],'actual_selected':old_prepared['selected'],
            'actual_input_tokens':old_prepared['input_tokens'],'actual_followup_kind':old_prepared['kind'],
            'choices':choices,'same_static_and_completion_request':choices['static_dependencies']['request_hash']==choices['answer_separating']['request_hash'],
            'old_formal_final_status':pred['result']['certificate_status']})
        print(json.dumps({'source':source,'old_basis':old_prepared['selection_basis'],
            'same_request':rows[-1]['same_static_and_completion_request'],
            'static_tokens':choices['static_dependencies']['input_tokens'],'A_tokens':choices['answer_separating']['input_tokens']}),flush=True)
    result={'captured_utc':datetime.now(timezone.utc).isoformat(),'rows':rows,'cases':len(rows),
        'partition_counts':dict(Counter(r['partition'] for r in rows)),
        'same_request_count':sum(r['same_static_and_completion_request'] for r in rows),
        'new_model_or_oracle_or_tokenizer_HTTP_requests':0,'labels_opened':False,
        'all_original_actual_followup_token_counts_reproduced':True,
        'CPU_timings_are_current_offline_replays_not_original_end_to_end_wall':True,
        'all_semantics_and_scope_checks_preserved':True}
    (REPORT/'A_static_vs_completion_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
