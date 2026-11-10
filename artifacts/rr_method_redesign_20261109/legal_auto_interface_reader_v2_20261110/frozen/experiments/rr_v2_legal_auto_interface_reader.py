"""Use the actual automatically acquired ordinary-cache API on three fixed TRAIN cases."""
import argparse,hashlib,json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_predicate_skills import CASES,validate_case,validate,run
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
PARENT=BASE/'legal_auto_interface_cache_v1_20261110'
RUN='legal_auto_interface_reader_v2_20261110';STAGE=BASE/RUN
ORDINALS=[81,86,72]


def read(p):return json.loads(p.read_text())


def prepare():
    parent=read(PARENT/'seal.json');source=read(PARENT/'source.json')
    assert source['status']=='API_and_code_captured_not_yet_source_semantically_accepted'
    interface=source['value']['interface'];api={p['name']:p for p in interface}
    adaptation=read(PARENT/'literal_programme_adaptation.json')
    assert adaptation['status']=='source_structure_passed_not_semantic_certificate'
    validate(adaptation['program'],[p['rules'] for p in parent['source_policies']])
    public={r['key']:r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    material=[]
    for n in ORDINALS:
        r=public[parent['sources']['train'][n-1]]
        material.append({'ordinal':n,'facts':r['public']['facts'],'query':r['public']['query']})
    system=(
        'Read the three supplied original TRAIN fact texts and questions into the ordinary policy cache interface below. '
        'Return cases in the specified original ordinal order. The predicate names/roles/meanings are the actual cache model output, not a hand-written fixed legal API. '
        'Extract only assertions explicitly supported by the FACTS. Do not perform legal inference, guess missing facts, use the question as evidence for a legal assertion, or supply a final answer. '
        'An explicit statement that an individual qualifies under a particular section may be represented by the matching interface proposition; infer no composite qualification from an ordinary kinship fact alone. '
        'Respect claimant/subject order, polarity and year. Every nonneutral fact quote must be a nonempty exact substring of its own facts. '
        'The neutral case_subject_year relation may use names and year explicitly present in facts OR question and may quote that public text. '
        'Query predicate/arguments express what was asked, not an answer. Null projects a person not asked for, not a guessed person. Policy output amounts are strings. '
        'Do not invent legal predicates absent from the supplied interface. Missing evidence is unresolved/omitted, never an explicit false. No code, tools, browsing or outside materials.')
    user=json.dumps({'interface':interface,'cases':material,'expected_ordinals':ORDINALS},ensure_ascii=False)
    protocol=ROOT/'reports/method_redesign_20261109/legal_auto_interface_reader_protocol.md'
    paths=['experiments/rr_v2_legal_auto_interface_reader.py','legal_skill_guard/rr/ordinary_rule_literal.py',
        'legal_skill_guard/rr/legal_predicate_skills.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    s={'run_id':RUN,'config':parent['config'],'sources':parent['sources'],'source_ids':[parent['sources']['train'][n-1] for n in ORDINALS],
        'interface':interface,'code':source['value']['code'],'program':adaptation['program'],'adaptation':adaptation['adaptation'],
        'source_policies':parent['source_policies'],'material':material,
        'parent_response_sha256':hashlib.sha256((PARENT/'source.json').read_bytes()).hexdigest(),
        'schema':CASES,'messages':[{'role':'system','content':system},{'role':'user','content':user}],
        'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(parent['config'])},
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'thinking':False,
        'source_bodies_or_native_labels_in_reader_prompt':False,'no_63_c5_case_deliberately_used':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'new_model_calls':0,'native_ordinals':ORDINALS}));return
    out=STAGE/'execution_closed_before_grading.json'
    if out.exists():print(json.dumps({'existing':str(out),'no_redispatch':True}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Does the independently source-acquired ordinary cache API support actual Qwen/OFF factual binding and source-programme execution on the same three existing151/152 TRAIN cases, without a manually copied legal API or target answers? Native outcomes are recorded before reusing already cached labels.')
    client=MethodExecutor(l,STAGE,s['config']['executor']);client.readiness()
    w=client.generate(RUN+':reader',source=s['source_ids'][0],purpose='method_primitive_observation',messages=s['messages'],thinking=False,schema=s['schema'])
    result={'physical_response':w,'cases':[],'goal_complete':False,'new_native_labels_opened':False,'new_oracle_views':0}
    try:
        cases=json.loads(w['content'])['cases']
        if [c['ordinal'] for c in cases]!=ORDINALS:raise ValueError('Changed or missing original case ordinals')
        api={p['name']:p for p in s['interface']}
        for c,material in zip(cases,s['material']):
            row={'ordinal':c['ordinal'],'raw_case':c}
            try:
                validate_case(c,material['facts']+' '+material['query'],api)
                for fact in c['facts']:
                    if fact['atom']['predicate']!='case_subject_year' and fact['quote'] not in material['facts']:
                        raise ValueError('A substantive factual assertion is grounded only in the question')
                output=run(s['program'],c)
                row.update(status='executed_pending_independent_semantic_review',output=output)
            except Exception as exc:row.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
            result['cases'].append(row)
    except Exception as exc:result.update(status='reader_rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(out,result)
    print(json.dumps({'cases':[{'ordinal':r['ordinal'],'status':r['status'],'answer':r.get('output',{}).get('answer'),'error':r.get('error')} for r in result['cases']],
        'native_labels_opened':False},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','generate']);main(p.parse_args().action)
