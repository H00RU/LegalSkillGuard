"""Current pinned XGrammar membership/mask regression; no model generation."""
from collections import Counter
from datetime import datetime,timezone
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sqlite3

import xgrammar as xgr

from legal_skill_guard.rr.source_program import program_schema,source_unit_schema
from legal_skill_guard.rr.source_structure import inspect_source


def field_schema(value):
    return {'type':'object','additionalProperties':False,'required':['predicate_source'],
            'properties':{'predicate_source':value}}


def main():
    root=Path(__file__).resolve().parents[2]
    sources={s['key']:s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    info=xgr.TokenizerInfo([bytes([i]) for i in range(256)]+[b''],vocab_size=257,stop_token_ids=[256])
    compiler=xgr.GrammarCompiler(info,max_threads=1,cache_enabled=False)
    checked={};groups=[];probe_count=0;errors=[]
    for source in sources.values():
        structure=inspect_source(source);all_ids={c.id for c in structure.ledger.clauses}
        role_sets={'all':all_ids,**{role:{k for k,v in structure.roles.items() if v['role']==role}
                                  for role in ('rule','fact')}}
        for role,ids in role_sets.items():
            if not ids:continue
            key=hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest()
            if key not in checked:
                schema=field_schema(source_unit_schema(ids))
                compiled=compiler.compile_json_schema(json.dumps(schema),any_whitespace=True)
                probes={f's{i}' for i in range(max(int(x[1:]) for x in all_ids)+12)}|{
                    's0\n','s1\n','s154\n','s0\r','\ns0','s00','s01','s-1','s0.0','foreign'}
                bad=[]
                for value in sorted(probes):
                    accepted=xgr.GrammarMatcher(compiled).accept_string(json.dumps({'predicate_source':value}))
                    if accepted!=(value in ids):bad.append({'value':value,'accepted':accepted})
                checked[key]={'ids':sorted(ids),'schema':schema,'probes':len(probes),'membership_errors':bad}
                probe_count+=len(probes);errors.extend(bad)
            groups.append({'source':source['key'],'role':role,'proof':key})
    fixture=json.loads((root/'tests/fixtures/rr_actual_method_c2_enum.json').read_text())['records']
    complete_wire=[];old_field=None
    with sqlite3.connect('file:'+str(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        for item in fixture:
            original=json.loads(db.execute('select result from calls where id=?',(item['call_id'],)).fetchone()[0])
            path=Path(original['artifact_directory']);wire=json.loads((path/'wire_request.json').read_text())
            payload=json.loads(base64.b64decode(wire['body_b64']));old=payload['response_format']['json_schema']['schema']
            new=program_schema(sources[item['source']]);results={}
            for label,schema in [('original',old),('repaired',new)]:
                ctx=compiler.compile_json_schema(json.dumps(schema),any_whitespace=True)
                results[label]=xgr.GrammarMatcher(ctx).accept_string(item['raw_content'])
            complete_wire.append({'call_id':item['call_id'],'raw_content_sha256':hashlib.sha256(item['raw_content'].encode()).hexdigest(),
                                  'wire_sha256':wire['body_sha256'],'grammar_acceptance':results})
            if item['source'].startswith('RuleArena_Airline:'):
                old_field=old['properties']['observations']['items']['properties']['predicate_source']
    # Token masks use the actual pinned model tokenizer, without loading weights.
    from transformers import AutoTokenizer
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer=AutoTokenizer.from_pretrained(cfg['model_root'],local_files_only=True)
    vocab=json.loads((Path(cfg['model_root'])/'config.json').read_text())['vocab_size']
    actual_info=xgr.TokenizerInfo.from_huggingface(tokenizer,vocab_size=vocab)
    actual_compiler=xgr.GrammarCompiler(actual_info,max_threads=1,cache_enabled=False)
    mask_results=[]
    for label,field in [('original',old_field),('repaired',source_unit_schema(old_field['enum']))]:
        ctx=actual_compiler.compile_json_schema(json.dumps(field_schema(field)),any_whitespace=True)
        for value in ['s0','s154','s157','s154\n']:
            tokens=tokenizer.encode(json.dumps({'predicate_source':value}),add_special_tokens=False)
            matcher=xgr.GrammarMatcher(ctx);mask=xgr.allocate_token_bitmask(1,actual_info.vocab_size);first=None
            for index,token in enumerate(tokens):
                matcher.fill_next_token_bitmask(mask)
                allowed=bool((int(mask[0,token//32].item())>>(token%32))&1)
                accepted=matcher.accept_token(token)
                if not allowed or not accepted:
                    first={'index':index,'token_id':token,'mask_allowed':allowed,'matcher_accepted':accepted};break
            mask_results.append({'variant':label,'value':value,'all_tokens_accepted':first is None,'first_rejection':first})
    repetition=json.loads((root/'tests/fixtures/rr_actual_method_c2_repetition.json').read_text())
    longest=max(re.findall(r'"name"\s*:\s*"([^"\\]*)"',repetition['raw_content']),key=len)
    symbol=program_schema(sources[repetition['source']])['$defs']['binding']['anyOf'][0]['properties']['name']
    name_masks=[]
    for label,field in [('original',{'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_]*$'}),('repaired',symbol)]:
        schema={'type':'object','additionalProperties':False,'required':['name'],'properties':{'name':field}}
        ctx=actual_compiler.compile_json_schema(json.dumps(schema),any_whitespace=True)
        for value in ['n0','n'*64,'n'*65,longest]:
            tokens=tokenizer.encode(json.dumps({'name':value}),add_special_tokens=False)
            matcher=xgr.GrammarMatcher(ctx);mask=xgr.allocate_token_bitmask(1,actual_info.vocab_size);first=None
            for index,token in enumerate(tokens):
                matcher.fill_next_token_bitmask(mask)
                allowed=bool((int(mask[0,token//32].item())>>(token%32))&1)
                accepted=matcher.accept_token(token)
                if not allowed or not accepted:
                    first={'index':index,'token_id':token,'mask_allowed':allowed,'matcher_accepted':accepted};break
            name_masks.append({'variant':label,'characters':len(value),'value_sha256':hashlib.sha256(value.encode()).hexdigest(),
                'all_tokens_accepted':first is None,'first_rejection':first})
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),'xgrammar_version':importlib.metadata.version('xgrammar'),
            'scope':'all128 current role sets after actual OE field-boundary repair, two original paid wires and actual Qwen3 token masks; CPU only',
            'source_count':len(sources),'role_groups':len(groups),'distinct_sets':len(checked),'membership_probes':probe_count,
            'membership_errors':errors,'proofs':checked,'groups':groups,'complete_real_wire_replays':complete_wire,
            'actual_token_masks':mask_results,'actual_identifier_token_masks':name_masks,
            'model_weights_loaded':False,'new_model_calls':0,
            'service_environment_modified':False,'old_outputs_modified':False,
            'related_upstream_report':'https://github.com/mlc-ai/xgrammar/issues/618',
            'upstream_note':'Related large-alternation/state-merging defect; local evidence, not version attribution, establishes this installed failure.'}
    out=root/'reports/rr_method_runtime_20261107/source_id_grammar_verification_v3.json'
    out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'proofs','groups'}},ensure_ascii=False))
    assert not errors
    assert complete_wire[0]['grammar_acceptance']=={'original':True,'repaired':False}
    assert complete_wire[1]['grammar_acceptance']=={'original':True,'repaired':True}
    assert all(item['all_tokens_accepted']==(item['value'] in old_field['enum'])
               for item in mask_results if item['variant']=='repaired')
    assert all(item['all_tokens_accepted']==(item['characters']<=64)
               for item in name_masks if item['variant']=='repaired')


if __name__=='__main__':main()
