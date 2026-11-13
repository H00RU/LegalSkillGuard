"""Remove proven-incompatible clause-role code from a source-only frontend."""
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
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,material_public
from legal_skill_guard.skill_evolution.scoped_reader import decode_expression,expression_text
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

DEST=OUT/'slim_expression_preflight'


def run():
    config=read(OUT/'protocol.json');bundle=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json')
    common=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/revision/common_input.json')
    reference=common['original_TRAIN'][0]
    example=next(s for s in reference['actual_source_output']['statements'] if s['term'][0]=='disposal_obligation')
    by_id={u['id']:u for u in reference['source_units']}
    source=next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key'].startswith('ContractNLI:8af247'))
    pub=source['views'][0]['public'];units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
    prior_request=ROOT/'artifacts/legal_skill_evolution_semantic_operations_v2_20261113/calls/34bb3064ca5c6f0136440e260dd68367722997524c9772718f1ba0e9d09b50ba/request.json'
    host=read(prior_request)['payload']['response_format']['json_schema']['schema'];wire,_=decoder_schema(host)
    body={'constructors':bundle['spec']['constructors'],
        'actual_other_TRAIN_syntax_example_not_current_facts':{'source':reference['source'],
            'source_units':[{'id':i,'text':by_id[i]['text']} for i in example['support_ids']],
            'answer':{'statements':[{'expression':expression_text(example['term']),'support_ids':example['support_ids']}],
                'unresolved':['This syntax example is partial; it does not certify complete source semantics.']}},
        'current_source_units':[{'id':u['id'],'text':u['text']} for u in units]}
    prompt=[{'role':'system','content':
        'Read the CURRENT complete source and emit its actual source-supported Norm/Definition interpretations using only the supplied acquired constructors. '
        'Output ordinary callable constructor expressions NAME(arg1,arg2), NAME() for zero arguments, and quoted text leaves. Do not invent constructor names or use informal operation-choice labels as constructors. '
        'Each distinct source effect has its own actor, information, trigger, condition and exception. Preserve limits and alternatives; do not merge duty bearers with exception beneficiaries. '
        'A mention, heading or continuing confidentiality is not a new disposal/retention duty or permission. Unknown or unrepresentable source details stay unresolved; no default no-exception or unsupported trigger. '
        'Do not enumerate constructor combinations. Return each actually supported effect once, and only cite its actual current source-unit IDs. '
        'The other-TRAIN example teaches syntax only, never current facts. Do not copy its source conclusions or IDs. No downstream task questions or answers are supplied. '
        'Return {"statements":[{"expression":"a callable acquired constructor expression","support_ids":[current IDs]}],"unresolved":[unresolved source details]}. '
        'After JSON decoding the expression uses ordinary string delimiters, not another layer of escaping. Strict host arity, type and provenance checks remain.'},
        {'role':'user','content':json.dumps(body,ensure_ascii=False,separators=(',',':'))}]
    p={'run_id':RUN+':slim_expression_preflight','source':source['key'],'profile':config['executor_profile'],
        'messages_sha256':digest(prompt),'wire_sha256':digest(wire),'constructor_spec_sha256':digest(bundle['spec']['constructors']),
        'removed_incompatible_assets':['single-actor-per-clause G','closed operation-choice labels','consumer/native label code'],
        'retained':['same current source words/IDs','same acquired constructors','existing strict expression parser','one actual other-TRAIN syntax example'],
        'reason':'Prior complete reply copied stale triggers and used an operation-choice name as an unacquired constructor. These assets are not a semantically compatible source interface.',
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in [Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/scoped_reader.py']},
        'same_goal':True,'goal_complete':False,'shared_engineering_not_method_gain':True,
        'no_new_source_or_validation_or_TEST':True}
    immutable_json(DEST/'protocol.json',p)
    for name in p['source_sha256']:
        q=ROOT/name;target=DEST/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(q.read_bytes())
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':config['train_sources']+[source['key']],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,DEST,config['executor_profile']);client.readiness()
    r=client.generate(p['run_id']+':one',source=source['key'],purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
    immutable_json(DEST/'raw_result.json',r)
    if r['finish_reason']!='stop':raise ValueError('Incomplete; no unchanged retry')
    value=json.loads(r['content']);jsonschema.validate(value,host);index={u['id']:u for u in units};rows=[]
    for item in value['statements']:
        ids=item['support_ids']
        if len(set(ids))!=len(ids) or not set(ids)<=set(index):raise ValueError('Invalid source support')
        term=decode_expression(item['expression'],constructors(bundle['spec']),' '.join(index[i]['text'] for i in ids))
        rows.append({'term':term,'support_ids':ids})
    result=source_record(bundle,source,{'source_output':{'statements':rows,'complete':not value['unresolved'],
        'unresolved':value['unresolved']},'raw_result':r,'source_semantics_certified':False})
    immutable_json(DEST/'result.json',result)
    print(json.dumps({'source':source['key'],'typed_roots':len(rows),
        'core':sum(v['core_executed'] for v in result['views']),
        'correct':sum(bool(v['score'] and v['score']['correct']) for v in result['views']),
        'tokens':r['usage'],'seconds':r['elapsed_seconds'],'source_semantic_review_pending':True}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
