"""Revise a measured unsafe critic into explicit probe/outcome programs."""
import argparse
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.refutation_learning import BANK,validate_bank,instantiate,messages,fit
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.source_evidence_codec import schema,decode
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION,pack

FOLDER=OUT/'atomic_revision'
SYSTEM='''Revise the measured source-check skill, using only the same original4
TRAIN and actual check outcomes. The previous whole-category critic rejects two
confirmed acceptable interpretations and misses two false ones. Five other
checks target operations with no rejection supervision here. Do not call that
nontrivial test selection or generalization. No validation material is supplied.

The representation has changed: each question_template is now an ATOMIC SOURCE
PROBE, not necessarily another full-candidate entailment judgment. A check also
learns exclusion_on, either supported or refuted. Only that observed outcome
excludes its explicitly targeted candidate_choices. Unknown never excludes and
no outcome automatically supplies a replacement interpretation. The system
will learn a subset from actual frozen8B probe results, not your predicted truth.

Target ONLY disposal_retention_clause_role and its actually supplied choices.
Learn a small complementary, possibly overlapping test bank (at most6), able to
retain supported alternatives and reject real source-refuted readings. Do not
generate synonym samples or a test per unrelated field. Use the supplied real
mis-refutations/misses to change the actual question, evidence-reading plan or
candidate applicability. Preserve nonexclusive labels and incomplete context.

For example, the computational distinction is a probe asking whether the focus
expressly states a new permission, obligation, continuing condition or linked
follow-up, rather than re-asking the six-way class in longer language. You must
decide the actual probes and outcome mapping from source feedback. A probe can
ask whether something is explicitly present in the complete focus, but generic
absence from an incomplete context is not contradiction. Do not encode TRAIN
truth values, companies, source IDs, unit positions, quotation fragments or regex
choice replacements. Keep questions concise and interpretable by frozen8B.

window_program is pure Python apply(inputs,premises) returning only {unit_ids:[
current IDs]}. Inputs are source_spans, query(id,operation,unit_ids),
candidate_choice,focus_unit_id. Retain the actual focus; acquire governing
clauses/antecedents/definitions as needed, but do not attribute their own effects
to focus. Common helpers/recursion are allowed, no imports/introspection/tools.
Question templates may be constant source probes or use {candidate_meaning},
{candidate_name},{operation_question}. No other interpolation fields. Supported
and refuted refer to your PROBE, not automatically the original candidate.

The old442 IR already contains return/destroy alternatives. Do not invent a
missing whole return duty. Use only supplied explicit source review, not native
score as local truth. This is one specific representation repair, not a new
research direction, a new claim about oldM1, or permission for unlimited retries.
'''+INSTRUCTION


def prepare():
    p0=read(OUT/'protocol.json');data=read(OUT/'input.json')
    role=[o for o in data['operations'] if o['name']=='disposal_retention_clause_role']
    current={**data,'operations':role,'previous_bank':read(OUT/'validated_bank.json'),
        'actual_previous_calibration':read(OUT/'calibration/completed.json'),
        'representation_change':'Atomic probe proposition plus acquired exclusion_on mapping; explicit focus text displayed with unchanged source evidence.'}
    paths=[Path(__file__).resolve()]+[ROOT/'legal_skill_guard/skill_evolution'/n for n in
        ['refutation_learning.py','refutation_reader.py']]+[ROOT/'tests'/n for n in
        ['test_skill_evolution_refutation_learning.py','test_skill_evolution_refutation_reader.py']]
    p={'run_id':RUN+':atomic_revision','same_goal':True,'goal_complete':False,
        'train_sources':p0['train_sources'],'validation_sources':p0['validation_sources'],
        'executor_profile':p0['executor_profile'],'teacher_profile':p0['teacher_profile'],
        'system':SYSTEM,'input_sha256':digest(current),'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
        'previous_results_preserved':True,'representation_version':'atomic_probe_v2',
        'one_measured_revision_workload':True,'no_validation_adaptation':True,
        'no_new_full_training_DEV_TEST_or_paper':True}
    immutable_json(FOLDER/'protocol.json',p);immutable_json(FOLDER/'input.json',current)
    for q in paths:
        dst=FOLDER/'source_snapshot'/q.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==q.read_bytes()
        else:dst.write_bytes(q.read_bytes())
    for name,h in p['source_sha256'].items():assert sha(ROOT/name)==h
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,current,ledger


def acquire():
    p,data,ledger=prepare();teacher=FrozenTeacher(ledger,FOLDER,p['teacher_profile'])
    r=teacher.propose(p['run_id']+':teacher',source_ids=p['train_sources'],system_prompt=p['system'],
        user_prompt=json.dumps(pack(data),ensure_ascii=False),output_schema=BANK)
    immutable_json(FOLDER/'teacher.json',r);bank=validate_bank(r['value'],data['operations'])
    for t in bank['tests']:
        for c in data['training_cases']:instantiate(t,c,data['operations'][0],data['sources'][c['source']]['units'])
    immutable_json(FOLDER/'validated_bank.json',bank)
    print(json.dumps({'acquired_atomic_tests':len(bank['tests'])}),flush=True)


def generic(data):
    return {'name':'generic_source_judge','operation':data['operations'][0]['name'],
        'candidate_choices':[c['name'] for c in data['operations'][0]['choices']],
        'question_template':'Does the focused unit, interpreted with its actual context, support this candidate interpretation: {candidate_meaning}? A compatible alternative is not a refutation. Use unknown for missing context.',
        'exclusion_on':'refuted','window_program':"def apply(inputs,premises):\n    return {'unit_ids':[s['id'] for s in inputs['source_spans']]}\n"}


def calibrate():
    p,data,ledger=prepare();tests=read(FOLDER/'validated_bank.json')['tests']+[generic(data)]
    client=FrozenExecutor(ledger,FOLDER,p['executor_profile']);client.readiness();all_rows=[]
    for source in p['train_sources']:
        path=FOLDER/'calibration'/(source.replace(':','_')+'.json')
        if path.exists():all_rows+=read(path)['observations'];continue
        units=data['sources'][source]['units'];queries=[];ops=[];focus={};binding={};rows=[]
        for c in data['training_cases']:
            if c['source']!=source:continue
            for t in tests:
                item=instantiate(t,c,data['operations'][0],units)
                if item is None:
                    rows.append({'case':c['id'],'test':t['name'],'verdict':'inapplicable','exclude_candidate':False});continue
                op,q=item;ops.append(op);queries.append(q);focus[q['id']]=c['focus_unit_id'];binding[q['id']]={'case':c['id'],'test':t['name'],'exclusion_on':t['exclusion_on']}
        prompt=messages(ops,queries,units,focus);wire,_=decoder_schema(schema(ops,queries))
        r=client.generate(p['run_id']+':calibration:'+source,source=source,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
        if r['finish_reason']!='stop':raise ValueError('Incomplete; no unchanged retry')
        _,answers=decode(ops,queries,units,r['content'])
        rows += [{**binding[a['id']],'verdict':a['choice'],'answer':a,
                  'exclude_candidate':a['choice']==binding[a['id']]['exclusion_on']} for a in answers]
        immutable_json(path,{'source':source,'queries':queries,'operations':ops,'result':r,'observations':rows});all_rows+=rows
        print(json.dumps({'source':source,'probes':len(queries),'exclusions':sum(x['exclude_candidate'] for x in rows)}),flush=True)
    result=fit(tests,data['training_cases'],all_rows)
    immutable_json(FOLDER/'learned_policy.json',result)
    immutable_json(FOLDER/'calibration/completed.json',{'tests':tests,'observations':all_rows,'policy':result,
        'training_fit_not_reuse':True,'goal_complete':False})
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['acquire','calibrate']);args=a.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'acquire':acquire,'calibrate':calibrate}[args.stage]()
