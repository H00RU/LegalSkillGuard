"""Verify actual finite provenance limits at byte and serving-token levels."""
from datetime import datetime,timezone
import json
from pathlib import Path
import socket

import xgrammar as xgr
from transformers import AutoTokenizer

from legal_skill_guard.rr.source_program import program_schema


def main():
    def denied(*a,**k):raise AssertionError('No network or model call')
    socket.socket.connect=denied;socket.create_connection=denied
    root=Path(__file__).resolve().parents[2]
    fixture=json.loads((root/'tests/fixtures/rr_actual_ast_scope_v1.json').read_text())
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==fixture['source'])
    schema=program_schema(source);clauses=schema['properties']['clauses']['items']['properties']['sources']
    evidence=schema['$defs']['binding']['anyOf'][0]['properties']['sources']
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer=AutoTokenizer.from_pretrained(cfg['model_root'],local_files_only=True)
    size=json.loads((Path(cfg['model_root'])/'config.json').read_text())['vocab_size']
    info=xgr.TokenizerInfo.from_huggingface(tokenizer,vocab_size=size)
    byte_info=xgr.TokenizerInfo([bytes([i]) for i in range(256)]+[b''],vocab_size=257,stop_token_ids=[256])
    compilers=[xgr.GrammarCompiler(i,max_threads=1,cache_enabled=False) for i in (byte_info,info)]
    cases=[('clause_sources_at_bound',clauses,['s1']*clauses['maxItems'],True),
        ('actual_loop_beyond_rule_domain',clauses,['s1']*(clauses['maxItems']+1),False),
        ('clause_empty_remains_allowed_by_existing_engine',clauses,[],True),
        ('binding_evidence_empty_rejected',evidence,[],False),
        ('binding_evidence_beyond_unit_domain',evidence,['s1']*(evidence['maxItems']+1),False)]
    checks=[]
    for label,current,value,expected in cases:
        spec=json.dumps(current);text=json.dumps(value)
        grammars=[c.compile_json_schema(spec,any_whitespace=True) for c in compilers]
        accepted=xgr.GrammarMatcher(grammars[0]).accept_string(text)
        matcher=xgr.GrammarMatcher(grammars[1]);mask=xgr.allocate_token_bitmask(1,info.vocab_size);first=None
        for index,token in enumerate(tokenizer.encode(text,add_special_tokens=False)):
            matcher.fill_next_token_bitmask(mask)
            allowed=bool((int(mask[0,token//32].item())>>(token%32))&1)
            if not allowed or not matcher.accept_token(token):first=index;break
        row={'case':label,'expected':expected,'byte_accepted':accepted,'Qwen_tokens_accepted':first is None,'first_rejection':first}
        assert accepted==expected and (first is None)==expected,row
        checks.append(row)
    receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,
        'max_clause_source_units':clauses['maxItems'],'max_binding_source_units':evidence['maxItems'],
        'uniqueness_enforced_by_existing_engine_not_claimed_as_backend_feature':True,
        'network_blocked':True,'new_model_calls':0,'new_oracle_views':0,'does_not_validate_rule_semantics':True}
    (root/'reports/rr_method_runtime_20261107/provenance_bounds_backend_v1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'all_passed':True,'new_model_calls':0}))


if __name__=='__main__':main()
