"""One same-source native ability pair; never counted as A/B mechanism success."""
from datetime import datetime,timezone
import json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.strict_contract import obj

ROOT=Path(__file__).resolve().parents[1]
RUN='efficacy_native_control_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_efficacy_20261109'/RUN


def main():
    old=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109/seal.json').read_text())
    source_id=old['sources']['train'][6]
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==source_id)
    messages=[{'role':'system','content':'Solve the supplied airline fee task from its public rules and current facts. Return the requested nonnegative integer total answer and a concise calculation with the ticket/base fare and each item fee. Cite the supplied policy text supporting those amounts. No tools, external sources or grading information are available.'},
        {'role':'user','content':json.dumps(source['public'],ensure_ascii=False)}]
    schema=obj({'answer':{'type':'integer','minimum':0},'calculation':{'type':'string'}})
    files=science_files(ROOT);binding={'code_hash':digest(files),'config_hash':digest(old['config'])}
    protocol=(ROOT/'reports/method_efficacy_20261109/protocol.md').read_text()
    immutable_json(STAGE/'seal.json',{'run_id':RUN,'files':files,'binding':binding,'source':source,
        'messages':messages,'schema':schema,'config':old['config'],'protocol_hash':digest(protocol),'TEST_authorized':False})
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=binding,
        sources=old['sources'],authorization_hash=digest(protocol),
        question='Same TRAIN7 native ability pair after both constrained static translators failed; not an A/B core success.')
    executor=MethodExecutor(ledger,STAGE,old['config']['executor']);teacher=MethodTeacher(ledger,STAGE,old['config']['teacher'])
    for role in ('executor','teacher'):
        path=STAGE/(role+'.json')
        if path.exists():continue
        if role=='executor':
            wire=executor.generate(RUN+':executor:0',source=source_id,purpose='method_train_synthesis',
                messages=messages,schema=schema,thinking=False)
            value=json.loads(wire['content'])
        else:
            wire=teacher.summarize(RUN+':teacher:0',source_ids=[source_id],system_prompt=messages[0]['content'],
                user_prompt=messages[1]['content'],output_schema=schema)
            value=wire['value']
        result={'captured_utc':datetime.now(timezone.utc).isoformat(),'role':role,'source':source_id,
            'response':value,'physical_response':wire,'counts_as_core_method_success':False,
            'labels_not_in_prompt':True,'original_frozen_libraries_not_updated':True}
        immutable_json(path,result)
        print(json.dumps({'role':role,'response':value},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
