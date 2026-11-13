"""Reuse the actually successful constructor-expression source frontend."""
import fcntl
import json
from pathlib import Path
import jsonschema

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import material_public,constructors
from legal_skill_guard.skill_evolution.scoped_reader import decode_expression
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

DEST=OUT/'expression_interface_preflight'


def run():
    original=read(OUT/'protocol.json');bundle=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json')
    previous=ROOT/'artifacts/legal_skill_evolution_semantic_operations_v2_20261113/calls/34bb3064ca5c6f0136440e260dd68367722997524c9772718f1ba0e9d09b50ba/request.json'
    old=read(previous);prompt=old['payload']['messages'];assets=json.loads(prompt[1]['content'])
    source=next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key'].startswith('ContractNLI:8af247'))
    pub=source['views'][0]['public'];units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
    before=dict(assets);assets['current_source_units']=[{'id':u['id'],'text':u['text']} for u in units]
    assert all(assets[k]==before[k] for k in assets if k!='current_source_units')
    prompt=[prompt[0],{**prompt[1],'content':json.dumps(assets,ensure_ascii=False,separators=(',',':'))}]
    host=old['payload']['response_format']['json_schema']['schema'];wire,_=decoder_schema(host)
    p={'run_id':RUN+':expression_interface_preflight','source':source['key'],
        'successful_reference_request':str(previous.relative_to(ROOT)),'successful_reference_sha256':sha(previous),
        'profile':original['executor_profile'],'messages_sha256':digest(prompt),'wire_schema_sha256':digest(wire),
        'original_acquired_assets_unchanged':True,'current_source_words_and_IDs_preserved':True,
        'metadata_offsets_omitted_from_neural_display_only':True,'compact_JSON_preserves_all_string_values':True,
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in [Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/scoped_reader.py']},
        'same_goal':True,'goal_complete':False,'existing_TRAIN_shared_interface_not_method_gain':True,
        'not_single_factor_comparison_to_object_prompt':True,'no_new_validation_or_TEST':True}
    immutable_json(DEST/'protocol.json',p)
    for name in p['source_sha256']:
        q=ROOT/name;target=DEST/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(q.read_bytes())
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':original['train_sources']+[source['key']],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,DEST,original['executor_profile']);client.readiness()
    count=client.tokenize(prompt,thinking=False)['count']
    immutable_json(DEST/'tokenization.json',{'input_tokens':count,'reserved_output':original['executor_profile']['max_tokens'],
        'context':original['executor_profile']['context_tokens'],'no_generation_request_yet':True})
    if count+original['executor_profile']['max_tokens']>original['executor_profile']['context_tokens']:
        raise ValueError('Complete shared assets plus source exceed fixed context, no truncation or dispatch')
    r=client.generate(p['run_id']+':one',source=source['key'],purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
    immutable_json(DEST/'raw_result.json',r)
    if r['finish_reason']!='stop':raise ValueError('Incomplete preserved; no unchanged retry')
    value=json.loads(r['content']);jsonschema.validate(value,host);index={u['id']:u for u in units};statements=[]
    for row in value['statements']:
        if len(set(row['support_ids']))!=len(row['support_ids']) or not set(row['support_ids'])<=set(index):
            raise ValueError('Strict current source evidence identities required')
        evidence=' '.join(index[i]['text'] for i in row['support_ids'])
        term=decode_expression(row['expression'],constructors(bundle['spec']),evidence)
        statements.append({'term':term,'support_ids':row['support_ids']})
    canonical={'statements':statements,'complete':not value['unresolved'],'unresolved':value['unresolved']}
    result=source_record(bundle,source,{'source_output':canonical,'raw_result':r,
        'existing_expression_parser_and_host_checks_reused':True,'model_reported_unresolved_only':True})
    immutable_json(DEST/'result.json',result)
    print(json.dumps({'source':source['key'],'typed_roots':len(statements),
        'core':sum(v['core_executed'] for v in result['views']),
        'correct':sum(bool(v['score'] and v['score']['correct']) for v in result['views']),
        'source_semantic_review_pending':True,'tokens':r['usage'],'seconds':r['elapsed_seconds']}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
