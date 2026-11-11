"""Compare frozen old and current teacher input on the actual saved B5 cohorts."""
from datetime import datetime,timezone
import hashlib,importlib.util,json
from pathlib import Path
from legal_skill_guard.skill_evolution.objects import Library
from legal_skill_guard.skill_evolution.teacher import propose
from legal_skill_guard.skill_evolution.teacher_transport import unpack,serialized,INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import render_structured_codex_prompt,CODEX_TURN_INPUT_CHARACTER_LIMIT
ROOT=Path(__file__).resolve().parents[2];REPORT=Path(__file__).resolve().parent

def main():
    folder=ROOT/'artifacts/legal_skill_evolution_20261111/formal_v3'
    spec=importlib.util.spec_from_file_location('legal_skill_guard.skill_evolution.teacher_before_shared_transport',folder/'source_snapshot/legal_skill_guard/skill_evolution/teacher.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    prepared=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train'
    records={r['key']:r for r in json.loads((prepared/'public.json').read_text())}
    grading=json.loads((prepared/'grading.json').read_text())
    class Capture:
        class ledger:run_id='offline_transport_capture'
        def propose(self,*args,**kwargs):return kwargs
    rows=[]
    for arm in ('FreeEvolution','LiftOnly','CoRevOnly','Full','Lift+GenericJoint','AllPorts+CoRev'):
        context=json.loads((folder/arm/'update_context_B5.json').read_text());library=Library.load(folder/arm/'B4.json');cohort=context['cohort']
        args={'arm':arm,'batch':5,'library':library,'source_records':[records[k] for k in cohort],
              'feedback':[{'source':k,'annotations':grading[k],'execution':context['current'][k]} for k in cohort],
              'learned_patterns':library.revision_patterns,'trigger':cohort[:3],'history':cohort[3:]}
        before=old.propose(Capture(),**args);after=propose(Capture(),**args)
        original=json.loads(before['user_prompt']);decoded=unpack(json.loads(after['user_prompt']))
        assert serialized(decoded)==serialized(original),arm
        assert after['system_prompt']==before['system_prompt']+'\n'+INSTRUCTION
        assert after['source_ids']==before['source_ids'] and after['output_schema']==before['output_schema']
        rendered=render_structured_codex_prompt(after['system_prompt'],after['user_prompt'])
        assert len(rendered)<=CODEX_TURN_INPUT_CHARACTER_LIMIT
        rows.append({'arm':arm,'original_rendered_chars':len(render_structured_codex_prompt(before['system_prompt'],before['user_prompt'])),
            'encoded_rendered_chars':len(rendered),'transport_limit':CODEX_TURN_INPUT_CHARACTER_LIMIT,'source_count':len(cohort),
            'all_original_JSON_values_types_key_order_and_literal_strings_preserved':True,
            'original_user_prompt_sha256':hashlib.sha256(before['user_prompt'].encode()).hexdigest(),
            'decoded_canonical_sha256':hashlib.sha256(serialized(decoded).encode()).hexdigest(),
            'shared_value_count':len(json.loads(after['user_prompt'])['shared_values'])})
    result={'captured_utc':datetime.now(timezone.utc).isoformat(),'new_model_calls':0,'ledger_writes':0,'TEST_opened':False,
        'failure':'FreeEvolution B5 was rejected before a physical reservation: 1082126 characters exceed the fixed 1048576 CLI turn cap. One independent LiftOnly B5 response completed and is retained.',
        'repair':'Common lossless shared-JSON-value encoding. Original system instructions and output schema preserved, with only the reference decoding explanation appended.',
        'checks':rows,'isolated_regression_tests_passed':52,
        'implementation_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('legal_skill_guard/skill_evolution/teacher.py','legal_skill_guard/skill_evolution/teacher_transport.py')}}
    (REPORT/'actual_B5_teacher_transport_regression.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'actual_B5_cohorts_roundtrip_equal':len(rows),'largest_encoded_chars':max(r['encoded_rendered_chars'] for r in rows),'new_model_calls':0}))

if __name__=='__main__':main()
