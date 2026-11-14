"""One TRAIN-only interface diagnostic; no native scores or learned-G update."""
from copy import deepcopy
import fcntl
import hashlib
import json
import re

from experiments import legal_skill_evolution_field_binding_acquisition as parent
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.unit_evidence import context_batches,answer_schema,decode_answers

ROOT=parent.ROOT
RUN='legal_skill_evolution_field_scope_probe_20261114'
OUT=ROOT/'artifacts'/RUN


def run():
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        previous=parent.read(parent.OUT/'protocol.json')
        sources=parent.read(parent.prior.PUBLIC)
        source=next(s for s in sources if s['key'].startswith('ContractNLI:e82b'))
        key=source['key'];text=source['views'][0]['public']['source_text']
        row=parent.read(parent.OUT/'acquisition/ConstraintAcquire'/parent.name_for(key))
        original_units=row['observation']['visible_inputs']['units']
        original_ops={o['name']:o for o in row['observation']['visible_inputs']['operations']}
        # A real contiguous subclause, keeping the complete original source
        # and all original units available as context. No words are synthesized.
        match=re.search(r'3\.1\.1\s+only[\s\S]*?(?=3\.1\.2)',text)
        assert match is not None
        fragment=text[match.start():match.end()]
        assert 'employees of the receiving Party' in fragment
        unit_id=max(u['id'] for u in original_units)+1
        units=deepcopy(original_units)+[{'id':unit_id,'text':fragment}]
        ordered=[u['id'] for u in original_units]
        definitions=[('disclosure_effect_v2',unit_id),('recipient_employees_v2',unit_id),
                     ('destroy_trigger_v2',45),('destroy_material_scope_v2',45)]
        operations=[];queries=[]
        for name,focus in definitions:
            op=deepcopy(original_ops[name])
            question=op['question'].replace('整个供应窗口','目标条款及关联上下文').replace('供应披露窗口','目标披露条款').replace('供应窗口','目标条款及关联上下文')
            op['question']=('The LAST source unit is the target clause. Other units are current-source context. '
                'Read this field of that target and its actual conditions/references; do not aggregate separate norms. '
                +question)
            operations.append(op)
            queries.append({'id':'target_'+name,'operation':name,
                'unit_ids':[i for i in ordered if i!=focus]+[focus]})
        # These are source-field checks, never a benchmark answer or a new case.
        assert all({u['id'] for u in original_units}<=set(q['unit_ids']) for q in queries)
        assert all(op['choices']==original_ops[op['name']]['choices'] for op in operations)
        proof={'source':key,'original_source_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'all_original_units_retained':True,'focus_fragment':{'unit_id':unit_id,'start':match.start(),
            'end':match.end(),'text':fragment},'new_source_count':0,'native_labels_loaded':False,
            'no_native_score_or_fit':True,'purpose':'Test explicit source-clause focus versus current mixed-window field reading.',
            'decision':'If concrete fields remain wrong, do not scale the same fine-question path; use the authorized program-concept route.',
            'operations':operations,'queries':queries,'executor_profile':previous['executor_profile'],
            'source_code_sha256':hashlib.sha256(__file__.encode()).hexdigest()}
        proof['source_code_sha256']=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest()
        immutable_json(OUT/'protocol.json',proof)
        ledger=EvolutionLedger(parent.prior.LEDGER,run_id=RUN,
            sources={'train':[key],'dev':[],'test':[]},binding=digest(proof))
        before=parent.rows();assert not any(r[6]=='reserved' for r in before)
        immutable_json(OUT/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in before})
        client=FrozenExecutor(ledger,OUT,previous['executor_profile'])
        checks=[]
        batches=list(context_batches(client,operations,queries,units,scope='focus_last',checks=checks))
        # The frozen context preflight, rather than truncation, determines the
        # actual number of physical requests for this fixed four-field payload.
        results=[];answers=[]
        for batch,prompt,check in batches:
            wire,_=decoder_schema(answer_schema(operations,batch))
            result=client.generate(RUN+':fields:'+digest(prompt),source=key,purpose='skill_replay',
                messages=prompt,thinking=False,schema=wire)
            immutable_json(OUT/'responses'/(digest(prompt)+'.json'),result)
            assert result['finish_reason']=='stop'
            raw,grounded=decode_answers(operations,batch,units,result['content'],scope='focus_last')
            answers.extend(grounded);results.append(result)
        original={a['operation']:a for a in row['observation']['visible_inputs']['answers']}
        pairs=[{'operation':a['operation'],'previous_choice':original[a['operation']]['choice'],
                'focused_actual_answer':a} for a in answers]
        after=parent.rows();old={r[0]:digest(r) for r in before}
        assert all(digest(r)==old[r[0]] for r in after if r[0] in old)
        immutable_json(OUT/'result.json',{'source':key,'actual_answers':pairs,
            'new_physical_requests':sum(not x.get('cache_hit') for x in results),
            'native_labels_or_scores_used':False,'not_a_core_method_or_generalization_success':True,
            'all_original_units_retained':True,'old_rows_unchanged':len(old),'goal_complete':False})
        print(json.dumps(parent.read(OUT/'result.json'),ensure_ascii=False),flush=True)


if __name__=='__main__':run()
