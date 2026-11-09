"""One execution-feedback repair of actual ordinary Python, without law edits."""
import argparse,hashlib,json
from pathlib import Path

from experiments.rr_v2_legal_annual_python_control import ROOT,admitted,read
from experiments.rr_v2_legal_annual_scope import probes
from legal_skill_guard.rr.ordinary_python_cache import execute,validate
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger

RUN='legal_annual_python_repair_v1_20261110'
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/RUN
PREVIOUS=BASE/'legal_annual_python_control_v1_20261110'
QUERY='component3306_b_1'


def checks(code):
    validate(code);rows=[]
    for p in probes():
        try:actual=execute(code,admitted(p['payments'],p['qualifications']),QUERY);passed=type(actual) is int and actual==p['expected'];error=None
        except Exception as exc:actual=None;passed=False;error=type(exc).__name__+': '+str(exc)
        rows.append({'name':p['name'],'expected':p['expected'],'actual':actual,'passed':passed,'error':error})
    return {'rows':rows,'all_passed':all(r['passed'] for r in rows),'source_contract_probes_not_native_examples':True}


def prepare():
    old=read(PREVIOUS/'seal.json');before=read(PREVIOUS/'source.json');bad=before['physical_response']['content'].strip()
    errors=checks(bad);assert not errors['all_passed']
    assert any('TypeError' in str(r['error']) for r in errors['rows'])
    immutable_json(PREVIOUS/'ordinary_execution_diagnostic.json',{
        'old_style_rejection_preserved':True,'bounded_ordinary_Python_with_lambda_helpers_supported':True,
        'query_object_was_underspecified_in_previous_model_prompt':True,
        'explicit_component_dispatch_string':QUERY,'actual_unmodified_programme_still_fails':True,
        'source_checks':errors,'dictionary_keys_iterated_instead_of_group_values':True,
        'no_raw_programme_semantic_adapter_or_manual_repair_admitted':True,'new_model_calls':0})
    system=('Repair your previous ordinary Python cache using the actual execution failure below. The original source and source-contract feedback remain authoritative. '
        'Return a complete executable Python programme defining law_cache(facts, query). Ordinary top-level helper functions and an entry lambda are supported, in addition to a normal def. '
        'facts is a list of admitted payment row dicts. The caller passes query EXACTLY as the string component3306_b_1; the previous prompt had not specified its representation. '
        'The previous helper returns a dict mapping key tuples to lists of rows, while its consumer iterates the dict as if it were lists of rows; dictionary iteration yields keys, causing TypeError. Correct the programme, not the source rule or the expected financial values. '
        'Preserve the statute\'s grouping/amount semantics; do not use any native case answer. No imports/classes/decorators/annotations/defaults/files/network/dynamic calls. '
        'Allowed builtins: set,frozenset,list,dict,tuple,str,int,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance. Collection get/items/keys/values/append/setdefault etc are available. '
        'Return only the full code, no JSON, explanation or test invocation.')
    feedback={'execution_feedback':errors,'return_contract':'one integer total; query is the registered component string; empty input total0',
        'instruction':'This was a rejected programme, not an example to copy unchanged. Return a corrected executable version.'}
    messages=[{'role':'system','content':system},old['messages'][1],{'role':'assistant','content':bad},
              {'role':'user','content':json.dumps(feedback,ensure_ascii=False)}]
    protocol=ROOT/'reports/method_redesign_20261109/legal_annual_python_repair_protocol.md'
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
      'experiments/rr_v2_legal_annual_python_repair.py','legal_skill_guard/rr/ordinary_python_cache.py',
      'tests/test_rr_ordinary_python_cache.py','experiments/rr_v2_legal_annual_python_control.py',
      'experiments/rr_v2_legal_annual_scope.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
    s={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source':old['source'],'messages':messages,
       'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
       'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
       'source_law_native_case_or_labels_changed':False,'old_programme_unchanged':True,
       'source_counterexample_feedback_shared_from_v3':True,
       'specific_changes':['execute ordinary lambda/helper style','explicit component-string call contract','actual TypeError feedback as chat turn'],
       'offline':{'actual_bad_programme_replayed_and_rejected':True,'ordinary_Python_runner_regressions':9},'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'offline':s['offline'],'new_calls':0}));return
    path=STAGE/'source.json'
    if path.exists():print(json.dumps({'existing':str(path)}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
      question='Repair one actual dictionary-iteration failure in an ordinary source Python baseline after making the previously unspecified call representation explicit. No law/source/native-answer repair or unchanged retry.')
    e=MethodExecutor(l,STAGE,s['config']['executor']);e.readiness()
    w=e.generate(RUN+':source',source=s['source'],purpose='method_train_synthesis',messages=s['messages'],thinking=False,schema=None)
    r={'physical_response':w,'goal_complete':False}
    try:
        code=w['content'].strip()
        if code.startswith('```'):
            lines=code.splitlines()
            if lines[0] not in ['```','```python'] or lines[-1]!='```':raise ValueError('Incomplete outer fence')
            code='\n'.join(lines[1:-1])
        r.update(code=code,source_checks=checks(code),status='ordinary_source_code_checked')
    except Exception as exc:r.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(path,r)
    print(json.dumps({k:v for k,v in r.items() if k!='physical_response'},ensure_ascii=False,indent=2))


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','source']);main(p.parse_args().action)
