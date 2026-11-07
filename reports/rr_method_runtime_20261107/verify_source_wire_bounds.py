"""Pinned-backend checks of the actual recursive wire failure; CPU only."""
from datetime import datetime,timezone
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import socket

import xgrammar as xgr

from legal_skill_guard.rr.source_program import program_schema
from legal_skill_guard.rr.strict_contract import EXPRESSION_DEPTH


def main():
    def denied(*args,**kwargs):raise AssertionError('No network in backend regression')
    socket.socket.connect=denied;socket.create_connection=denied
    root=Path(__file__).resolve().parents[2]
    fixture=json.loads((root/'tests/fixtures/rr_actual_method_c3_depth.json').read_text())
    sources=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
    source=next(s for s in sources if s['key']==fixture['source'])
    with sqlite3.connect('file:'+str(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        original=json.loads(db.execute('select result from calls where id=?',(fixture['call_id'],)).fetchone()[0])
    wire=json.loads((Path(original['artifact_directory'])/'wire_request.json').read_text())
    old=json.loads(base64.b64decode(wire['body_b64']))['response_format']['json_schema']['schema']
    new=program_schema(source)
    info=xgr.TokenizerInfo([bytes([i]) for i in range(256)]+[b''],vocab_size=257,stop_token_ids=[256])
    compiler=xgr.GrammarCompiler(info,max_threads=1,cache_enabled=False)
    checks=[]
    for name in ('expr','bool_expr','connector'):
        ctx=compiler.compile_json_schema(json.dumps({'$ref':'#/$defs/'+name,'$defs':new['$defs']}),any_whitespace=True)
        for depth in (0,1,EXPRESSION_DEPTH,EXPRESSION_DEPTH+1):
            value={'slot':'witnesses'} if name=='connector' else {'var':'guard'}
            for _ in range(depth):
                value={'op':'project_exists','inputs':[value],'params':{}} if name=='connector' else {'op':'not','args':[value]}
            accepted=xgr.GrammarMatcher(ctx).accept_string(json.dumps(value))
            checks.append({'kind':name,'depth':depth,'accepted':accepted,'expected':depth<=EXPRESSION_DEPTH})
    raw=fixture['raw_content'];start=raw.index('"graph":')+len('"graph":');graph_prefix=raw[start:].lstrip()
    actual=[]
    for label,schema in (('original',old),('repaired',new)):
        ctx=compiler.compile_json_schema(json.dumps({'$ref':'#/$defs/connector','$defs':schema['$defs']}),any_whitespace=True)
        accepted=xgr.GrammarMatcher(ctx).accept_string(graph_prefix)
        actual.append({'contract':label,'accepts_actual_unclosed_graph_prefix':accepted})
    from transformers import AutoTokenizer
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer=AutoTokenizer.from_pretrained(cfg['model_root'],local_files_only=True)
    vocab=json.loads((Path(cfg['model_root'])/'config.json').read_text())['vocab_size']
    actual_info=xgr.TokenizerInfo.from_huggingface(tokenizer,vocab_size=vocab)
    actual_compiler=xgr.GrammarCompiler(actual_info,max_threads=1,cache_enabled=False)
    masks=[]
    for name in ('expr','bool_expr','connector'):
        ctx=actual_compiler.compile_json_schema(json.dumps({'$ref':'#/$defs/'+name,'$defs':new['$defs']}),any_whitespace=True)
        for depth in (EXPRESSION_DEPTH,EXPRESSION_DEPTH+1):
            value={'slot':'witnesses'} if name=='connector' else {'var':'guard'}
            for _ in range(depth):
                value={'op':'project_exists','inputs':[value],'params':{}} if name=='connector' else {'op':'not','args':[value]}
            matcher=xgr.GrammarMatcher(ctx);mask=xgr.allocate_token_bitmask(1,actual_info.vocab_size);first=None
            for index,token in enumerate(tokenizer.encode(json.dumps(value),add_special_tokens=False)):
                matcher.fill_next_token_bitmask(mask)
                allowed=bool((int(mask[0,token//32].item())>>(token%32))&1)
                accepted=matcher.accept_token(token)
                if not allowed or not accepted:
                    first={'index':index,'token_id':token,'mask_allowed':allowed,'matcher_accepted':accepted};break
            masks.append({'kind':name,'depth':depth,'all_tokens_accepted':first is None,'first_rejection':first})
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),
        'xgrammar_version':importlib.metadata.version('xgrammar'),
        'actual_call_id':fixture['call_id'],'raw_content_sha256':fixture['raw_content_sha256'],
        'raw_graph_prefix_sha256':hashlib.sha256(graph_prefix.encode()).hexdigest(),
        'old_wire_body_sha256':wire['body_sha256'],'actual_prefix_checks':actual,
        'byte_grammar_checks':checks,'actual_Qwen3_token_masks':masks,
        'depth_limit':EXPRESSION_DEPTH,'model_weights_loaded':False,'new_model_calls':0,
        'network_blocked':True,'old_outputs_modified':False,
        'interpretation':'Grammar/type boundary regression, not benchmark execution, factual truth, or A/B semantic success.'}
    out=root/'reports/rr_method_runtime_20261107/source_wire_bounds_backend_v1.json'
    out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    assert all(c['accepted']==c['expected'] for c in checks)
    assert actual==[{'contract':'original','accepts_actual_unclosed_graph_prefix':True},
                    {'contract':'repaired','accepts_actual_unclosed_graph_prefix':False}]
    assert all(m['all_tokens_accepted']==(m['depth']<=EXPRESSION_DEPTH) for m in masks)


if __name__=='__main__':main()
