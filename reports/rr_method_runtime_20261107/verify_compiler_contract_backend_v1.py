"""Installed XGrammar/Qwen-token checks for typed declarations; no generation."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import socket

import xgrammar as xgr
from transformers import AutoTokenizer
from jsonschema import ValidationError

from legal_skill_guard.rr.source_code import compiler_response_schema, encode_compiler_program
from legal_skill_guard.rr.source_execution import prepare_followup
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.wire_validation import validate_wire


def ordered(value, schema, definitions):
    """Only serialization order changes; all values remain byte-equivalent JSON."""
    if '$ref' in schema:
        return ordered(value, definitions[schema['$ref'].split('/')[-1]], definitions)
    if 'anyOf' in schema:
        for arm in schema['anyOf']:
            try:validate_wire(value, {'$defs': definitions, **arm})
            except ValidationError:continue
            return ordered(value, arm, definitions)
    if isinstance(value, dict) and 'properties' in schema:
        return {key:ordered(value[key], child, definitions) for key, child in schema['properties'].items() if key in value}
    if isinstance(value, list):
        prefix=schema.get('prefixItems',[])
        return [ordered(item,prefix[i] if i<len(prefix) else schema.get('items',{}),definitions) for i,item in enumerate(value)]
    return value


def main():
    def denied(*a,**k):raise AssertionError('No network in backend contract checks')
    socket.socket.connect=denied;socket.create_connection=denied
    root=Path(__file__).resolve().parents[2]
    case=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    source=case['source'];program=encode_compiler_program(case['canonical_program'])
    schema=compiler_response_schema(source)
    program=ordered(program,schema,schema['$defs'])
    assert program==encode_compiler_program(case['canonical_program'])
    compiled=compile_source(source,case['canonical_program'])
    joint=prepare_followup(compiled,compilation='full',thinking=False,
        tokenize=lambda *a,**k:{'count':100},request_config={'context_tokens':32768,'max_tokens':8192})
    facts=[{'name':n,'value':None,'evidence':''} for n in joint['names']]
    cases=[('actual_paid_translation',schema,program,True),
        ('code_only_rejected',schema,{'code':'query = True'},False),
        ('internal_IR_rejected',schema,case['canonical_program'],False),
        ('side_answer_rejected',schema,{**program,'answer':'Entailment'},False),
        ('joint_translation_and_facts',joint['schema'],{'program':program,'factual_observations':facts},True),
        ('joint_code_only_rejected',joint['schema'],{'program':{'code':'query = True'},'factual_observations':facts},False)]
    for label,field,index,key,value in [
        ('Boolean_native_query','query',None,None,True),
        ('observation_bad_name','observations',0,'name','s10'),
        ('fact_source_is_rule','observations',0,'entity_source','s0'),
        ('rule_source_is_fact','observations',0,'predicate_source','s10'),
        ('scope_source_is_fact','scopes',0,'source','s10'),
        ('binding_full_task_id','bindings',0,'sources',[source['key']]),
    ]:
        wrong=deepcopy(program)
        if index is None:wrong[field]=value
        else:wrong[field][index][key]=value
        cases.append((label,schema,wrong,False))
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer=AutoTokenizer.from_pretrained(cfg['model_root'],local_files_only=True)
    size=json.loads((Path(cfg['model_root'])/'config.json').read_text())['vocab_size']
    info=xgr.TokenizerInfo.from_huggingface(tokenizer,vocab_size=size)
    byte_info=xgr.TokenizerInfo([bytes([i]) for i in range(256)]+[b''],vocab_size=257,stop_token_ids=[256])
    compilers=[xgr.GrammarCompiler(i,max_threads=1,cache_enabled=False) for i in (byte_info,info)]
    caches=[{},{}];checks=[]
    for label,current,value,expected in cases:
        text=json.dumps(value,ensure_ascii=False);schema_text=json.dumps(current,ensure_ascii=False)
        for compiler,cache in zip(compilers,caches):
            if schema_text not in cache:cache[schema_text]=compiler.compile_json_schema(schema_text,any_whitespace=True)
        accepted=xgr.GrammarMatcher(caches[0][schema_text]).accept_string(text)
        matcher=xgr.GrammarMatcher(caches[1][schema_text]);mask=xgr.allocate_token_bitmask(1,info.vocab_size)
        first=None
        for index,token in enumerate(tokenizer.encode(text,add_special_tokens=False)):
            matcher.fill_next_token_bitmask(mask)
            allowed=bool((int(mask[0,token//32].item())>>(token%32))&1)
            token_ok=matcher.accept_token(token)
            if not allowed or not token_ok:
                first={'index':index,'token_id':token,'mask_allowed':allowed,'matcher_accepted':token_ok};break
        check={'case':label,'expected':expected,'byte_accepted':accepted,
            'actual_Qwen_tokens_accepted':first is None,'first_rejection':first,
            'value_sha256':hashlib.sha256(text.encode()).hexdigest()}
        checks.append(check)
        assert accepted==expected and (first is None)==expected,check
    receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
        'xgrammar_version':importlib.metadata.version('xgrammar'),'network_blocked':True,
        'new_model_calls':0,'new_oracle_views':0,'model_weights_loaded':False,
        'interpretation':'Generation metadata/native-query syntax only; expression syntax, full source IR and semantic checks remain mandatory.'}
    (root/'reports/rr_method_runtime_20261107/compiler_contract_backend_v1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'all_passed':True,'new_model_calls':0}))


if __name__=='__main__':main()
