"""One source-only ordinary-Python executor control using an existing contract."""
import argparse
from copy import deepcopy
import hashlib,json
from pathlib import Path

from experiments.rr_v2_legal_scope_replay import adapted_module
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.python_scalar_module import compile_function
from legal_skill_guard.rr.semantic_contracts import compare_modules
from legal_skill_guard.rr.source_obligations import compile_module,verify,bind_and_assess

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_plain_python_v1_20261110'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
OLD=ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109'


def read(path):return json.loads(path.read_text())


def prepare():
    old=read(OLD/'seal.json');raw=read(OLD/'teacher_sara63_basic_deduction.json')['module']
    target=next(t for t in old['targets'] if t['id']=='sara63_basic_deduction')
    signature={r['name']:r['type'] for r in raw['inputs']}
    header='def basic_standard_deduction('+', '.join(n+': '+('int' if t=='integer' else 'bool') for n,t in signature.items())+') -> int:'
    system=('Write one ordinary pure Python function implementing the requested legal calculation from the supplied simplified source. '
        'Use the supplied source-learned input contract exactly. These referenced legal classifications are caller-provided inputs; do not guess them. '
        'All inputs are explicitly provided at call time; no defaults. Preserve the requested distinction between basic and additional deduction. '
        'Use integer arithmetic, assignments, if/elif/else, return, min/max; no imports, I/O, loops, decorators, project DSL or JSON. '
        'Unknown caller inputs will be handled symbolically outside the function; do not replace them by false or zero. '
        'Return only the complete Python function; no explanation. The original executor thinking/sampling settings are unchanged.')
    material={'policy':target['rules'],'requested_function':target['target'],
              'shared_source_learned_input_roles':raw['inputs'],'shared_input_domain':raw['domain'],
              'function_header':header}
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_plain_python.py','legal_skill_guard/rr/python_scalar_module.py',
        'legal_skill_guard/rr/semantic_contracts.py','legal_skill_guard/rr/source_obligations.py',
        'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
    protocol=ROOT/'reports/method_redesign_20261109/legal_plain_python_protocol.md'
    seal={'run_id':RUN,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
          'config':old['config'],'sources':old['sources'],'source':target['source'],'source_TRAIN_ordinal':8,
          'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(material,ensure_ascii=False)}],
          'signature':signature,'policy':target['rules'],'teacher_reference':adapted_module(raw),
          'teacher_reference_NOT_sent_to_executor':True,'cases_queries_labels_NOT_sent':True,
          'response_schema':None,'shared_contract_acquisition_cost_not_free':True,
          'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal)
    reference=seal['teacher_reference']
    plain=header+'\n    return '+reference['expression']+'\n'
    compiled=compile_function(plain,signature)
    check=compare_modules(compiled['expression'],reference['expression'],signature,reference['domain'])
    assert check['equivalent_over_supplied_domain']
    immutable_json(STAGE/'offline_teacher_roundtrip.json',{'check':check,'model_call':False,
        'purpose':'Verify pure Python transport/control-flow conversion before the single real request.'})
    return seal


def generate(seal):
    path=STAGE/'executor.json'
    if path.exists():print(json.dumps({'existing':str(path)}));return
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=seal['binding'],sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
        question='Can Qwen, given the existing source-learned scalar contract but no reference program or cases, produce a complete ordinary Python63 function? One raw no-schema request, source-law obligations and full-domain reference comparison; not two-contribution efficacy.')
    executor=MethodExecutor(ledger,STAGE,seal['config']['executor']);executor.readiness()
    wire=executor.generate(RUN+':source63',source=seal['source'],purpose='method_train_synthesis',
        messages=seal['messages'],thinking=False,schema=None)
    result={'physical_response':wire,'ordinary_program_is_actual_executor_output':True,
            'source_role_acquisition_not_tested':True,'new_method_contribution_claim':False,'goal_complete':False}
    (STAGE/'raw_program.txt').write_text(wire['content'])
    try:
        compiled=compile_function(wire['content'],seal['signature'])
        value=deepcopy(seal['teacher_reference']);value['expression']=compiled['expression']
        module=compile_module(value,seal['policy']);checks=verify(module)
        comparison=compare_modules(compiled['expression'],seal['teacher_reference']['expression'],
                                   seal['signature'],seal['teacher_reference']['domain'])
        binding={k:None for k in seal['signature']}
        binding.update(is_2018_through_2025_taxable_year=True,is_joint_return=True,is_c5_dependent=False,
            is_married_filing_separately_with_either_spouse_itemizing=False,
            is_nonresident_alien_individual=False,is_estate_trust_common_trust_fund_or_partnership=False)
        control=bind_and_assess(module,binding,24000)
        result.update(compiled=compiled,source_obligations=checks,reference_comparison=comparison,
            actual_execution_software_control_not_extra_native_case=control,
            validation={'status':'compiled_source_contract_control',
                        'source_fidelity_not_implied_by_type_or_self_agreement':True})
    except Exception as exc:
        result['validation']={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
    immutable_json(path,result)
    print(json.dumps({k:v for k,v in result.items() if k!='physical_response'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','generate']);action=p.parse_args().action
    seal=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'new_calls':0,'response_schema':None}))
    else:generate(seal)
