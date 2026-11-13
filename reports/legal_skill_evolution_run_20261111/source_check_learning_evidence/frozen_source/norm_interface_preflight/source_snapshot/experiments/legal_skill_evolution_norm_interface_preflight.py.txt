"""One existing-TRAIN preflight of an effect-level typed source interface.

Shared engineering only: no learned-method result, no new source or evaluation.
"""
import fcntl
import json
from pathlib import Path

import jsonschema
from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans,record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.source_term_interface import term_schema,validate_value
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

DEST=OUT/'norm_interface_preflight'


def run():
    old=read(OUT/'protocol.json');bundle=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json')
    source=next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key'].startswith('ContractNLI:8af247'))
    pub=source['views'][0]['public'];units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
    typed=term_schema(bundle['spec'],'Norm')
    host=record_schema({'complete':{'type':'boolean'},'unresolved':{'type':'array','items':{'type':'string'}},
        'statements':{'type':'array','items':record_schema({'term':{'$ref':'#/$defs/Norm'},
            'support_ids':{'type':'array','minItems':1,'uniqueItems':True,'items':{'type':'integer','enum':[u['id'] for u in units]}}})}})
    host['$defs']=typed['$defs'];wire,_=decoder_schema(host)
    prompt=[{'role':'system','content':
        'Read the CURRENT complete source and emit its operative return/destruction and retention norms using ONLY the supplied acquired constructors. '
        'Each effect has its own actor, information, trigger and condition. Do not force a duty bearer and the beneficiary of an exception/permission into one shared actor. '
        'Preserve source limits, alternatives, exceptions, ownership and conditions. A title, recital or continuing confidentiality is not a new disposal/retention norm. '
        'Do not invent missing legal facts, use task answers, or turn uncertainty into no-exception. Use unresolved for source effects the acquired types cannot faithfully represent. '
        'Constructor signatures and meanings are learned assets, not facts about this contract. Each term is an object with constructor and ordered arguments; text leaves remain source-grounded text. '
        'Select actual current unit IDs as support. Strict type validity alone is not semantic verification. Return the response schema exactly.'},
        {'role':'user','content':json.dumps({'acquired_constructors':bundle['spec']['constructors'],
            'current_source_units':[{'id':u['id'],'text':u['text']} for u in units]},ensure_ascii=False)}]
    p={'run_id':RUN+':norm_interface_preflight','source':source['key'],'source_public_sha256':digest(pub),
        'executor_profile':old['executor_profile'],'schema_sha256':digest(host),'messages_sha256':digest(prompt),
        'constructor_spec_sha256':digest(bundle['spec']['constructors']),
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in [Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/source_term_interface.py']},
        'existing_TRAIN_shared_interface_not_method_gain':True,'same_goal':True,'goal_complete':False,
        'no_current_validation_source_or_label':True,'no_full_training_DEV_TEST_or_paper':True}
    immutable_json(DEST/'protocol.json',p);immutable_json(DEST/'host_schema.json',host)
    for name in p['source_sha256']:
        src=ROOT/name;dst=DEST/'source_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':old['train_sources']+[source['key']],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,DEST,old['executor_profile']);client.readiness()
    r=client.generate(p['run_id']+':one',source=source['key'],purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
    immutable_json(DEST/'raw_result.json',r)
    if r['finish_reason']!='stop':raise ValueError('Incomplete; preserved without implicit retry')
    value=json.loads(r['content']);jsonschema.validate(value,host)
    canonical={**value,'statements':[{'term':validate_value(bundle['spec'],'Norm',s['term']),
        'support_ids':s['support_ids']} for s in value['statements']]}
    result=source_record(bundle,source,{'source_output':canonical,'wire_result':r,
        'deterministic_object_to_executable_term_only':True})
    immutable_json(DEST/'result.json',result)
    print(json.dumps({'source':source['key'],'typed_roots':len(canonical['statements']),
        'core':sum(v['core_executed'] for v in result['views']),
        'native_correct':sum(bool(v['score'] and v['score']['correct']) for v in result['views']),
        'source_semantic_review_pending':True,'new_physical':1}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
