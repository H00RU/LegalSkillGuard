"""Two existing TRAIN source-field probes, no native question or answer input.

This is common-interface diagnosis, not a new contribution or method score.
It tests literal roles and scope structure after measured source-information
loss. No model/configuration search, new source, teacher, DEV or TEST.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_C_program_concepts as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages

ROOT=current.ROOT
RUN='legal_skill_evolution_source_field_schema_visible_20261115'
OUT=ROOT/'artifacts'/RUN
SYSTEM='''Extract literal rule-text fields from the supplied CURRENT source.
The complete source and its original unit IDs are provided. No downstream
question or target answer is supplied. Do not judge a legal claim, return a
native label, recall outside law or manufacture unstated facts.

Extract source clauses about disclosure/access, return/destruction, retention,
and their governing obligations or definitions. Keep the actual predicate,
modal cue and negation separate. A subsequent list item may inherit a subject
or modal from a preceding governing clause; cite that actual unit. A reference
to a defined recipient group must be resolved against its current definition,
including forward references. List the individual recipient kinds and who
owns them; affiliate employees are distinct from the recipient's own employees.
Do not merge a definition, NDA-signing obligation or foreign-hosting ban into
disclosure permission. Record the actual predicate instead.

For each field cite actual current evidence unit IDs. predicate_surface is a
SHORT verb phrase copied from source, not a whole clause. For each condition or
exception cite its actual units; do not invent a default condition. For retention
record the source's temporal/scope relation: after required return/destruction,
during ordinary use, confidentiality-duration only, or unresolved. Resolve
references such as 'this paragraph/Section 6' using the supplied text. Mere
confidentiality survival is not automatically permission to retain documents.

Unknown information remains null/unknown and is listed in unresolved_fields.
Empty results do not prove a category absent. This output contains source
observations, not executable Norms or conclusions. Do not add explanations.
'''


def read(path):return json.loads(path.read_text())


def schema(units):
    ids=[u['id']for u in units];anchor={'type':'integer','enum':ids}
    evidence={'type':'array','maxItems':len(ids),'uniqueItems':True,'items':anchor}
    role=record_schema({'kind':{'type':'string','enum':['employee','officer','director','agent','consultant',
        'professional_advisor','legal_advisor','financial_advisor','accountant','independent_contractor',
        'representative','affiliate','third_party','other','unknown']},
        'owner':{'type':'string','enum':['receiving_party','disclosing_party','receiving_party_affiliate',
            'disclosing_party_affiliate','both_parties','other','unknown']},
        'definition_unit_ids':evidence,'evidence_unit_ids':evidence})
    condition=record_schema({'kind':{'type':'string','enum':['need_to_know','confidentiality_bound',
        'purpose_limit','written_consent','required_by_law','service_scope','cross_reference','other','unknown']},
        'evidence_unit_ids':evidence})
    frame=record_schema({'clause_unit_id':anchor,'evidence_unit_ids':evidence,
        'predicate':{'type':'string','enum':['disclose','restrict_access','return','destroy','retain',
            'confidentiality_duty','define','sign_nda','foreign_hosting','other','unknown']},
        'predicate_surface':{'type':'string','maxLength':120},
        'modal':{'type':'string','enum':['may','shall','must','agrees','none','other','unknown']},
        'negative':{'type':['boolean','null']},'governing_unit_ids':evidence,
        'recipient_members':{'type':'array','maxItems':15,'items':role},
        'conditions':{'type':'array','maxItems':10,'items':condition},
        'exception_unit_ids':evidence,
        'retention_scope':{'type':'string','enum':['after_return_or_destruction','during_use',
            'confidentiality_duration_only','not_retention','unknown']},
        'unresolved_fields':{'type':'array','maxItems':12,'items':{'type':'string','enum':[
            'predicate','modal','negative','governing_scope','recipient_kind','recipient_owner',
            'recipient_definition','condition','exception','retention_scope']}}})
    return record_schema({'frames':{'type':'array','maxItems':len(ids),'items':frame},
        'unresolved_unit_ids':evidence})


def prepare():
    prior=current.read(current.OUT/'protocol.json');bank=current.read(current.OUT/'raw_source_bank.json')
    chosen=[next(s for s in bank if ':e671' in s),next(s for s in bank if ':442c' in s)]
    public={sid:{'source_text':bank[sid]['source']['views'][0]['public']['source_text'],'units':bank[sid]['units']}for sid in chosen}
    immutable_json(OUT/'source_only_inputs.json',public)
    p={k:prior[k]for k in ('sources','executor_profile')};p.update(run_id=RUN,probe_sources=chosen,
        no_native_questions_or_labels_in_model_input=True,common_interface_probe_not_C_success=True,
        model_visible_schema=True,
        prior_run='legal_skill_evolution_source_field_probe_20261115',
        change='Reuse common render_messages to expose unchanged host schema in prompt',
        teacher_requests=0,new_sources=0,new_DEV_TEST=False,
        ledger_before=current.previous.base.lineage.ledger_snapshot())
    files=[Path(__file__),OUT/'source_only_inputs.json']+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files};immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'probe_sources':chosen,'teacher_requests':0}),flush=True)


def run():
    p=read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    l=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(l,OUT,p['executor_profile']);bank=read(OUT/'source_only_inputs.json');rows=[]
    for sid in p['probe_sources']:
        target=OUT/'results'/(digest(sid)+'.json')
        if target.exists():rows.append(read(target));continue
        item=bank[sid];host=schema(item['units']);wire,checks=decoder_schema(host)
        prompt=render_messages(SYSTEM,item,host)
        tokens=client.tokenize(prompt,thinking=False)['count'];assert tokens+p['executor_profile']['max_tokens']<=p['executor_profile']['context_tokens']
        response=client.generate(RUN+':fields:'+digest(sid),source=sid,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
        row={'source':sid,'response':response,'input_tokens':tokens,'decoder_host_checks':checks,
            'typed_complete':False,'source_semantics_verified':False,'native_score':None,'not_method_contribution_evidence':True}
        if response['finish_reason']=='stop':
            try:
                value=json.loads(response['content']);jsonschema.validate(value,host)
                row.update(typed_complete=True,value=value)
            except (ValueError,jsonschema.ValidationError)as error:row['error']=str(error)
        else:row['error']='Incomplete source-field response; no implicit retry'
        immutable_json(target,row);rows.append(row)
        print(json.dumps({'source':sid,'typed_complete':row['typed_complete'],'frames':len(row.get('value',{}).get('frames',[])),
            'finish_reason':response['finish_reason'],'elapsed_seconds':response['elapsed_seconds']}),flush=True)
    immutable_json(OUT/'result.json',{'rows':rows,'common_interface_diagnostic_only':True,'goal_complete':False,'new_DEV_TEST':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'execute':run}[args.phase]()
