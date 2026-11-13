"""Finite original-TRAIN acquisition and induction of source influence links.

Source links are learned supervision, not facts inferred from native answers.
No original reuse parent, DEV/TEST, new full study, or old run is dispatched.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.legal_skill_evolution_focused_reader import material
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,occurrences

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_skill_evolution_scope_learning_20261113'
KINDS=['principal_disposal','substitute_disposal','retention_permission','retention_prohibition',
       'linked_qualification','followup_disposal','other','unresolved']
RELATIONS=['qualifies','substitutes','inherits_trigger','information_antecedent','followup_of']


def prepare():
    prior,p,ledger,public,b=material();out=ROOT/'artifacts'/RUN/'execution'
    with ledger.transaction() as db:
        rows=[list(r) for r in db.execute('select * from calls order by id')]
    assert not any(r[6]=='reserved' for r in rows)
    sources={};foci={};examples=[]
    for key in p['teacher_sources']:
        pub=public[key]['views'][0]['public']
        units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
        sources[key]=units;foci[key]=set()
    for op in b['LearnedOperations']['operations']:
        for e in op['examples']:
            key=e['source'];text=public[key]['views'][0]['public']['source_text']
            hits=occurrences(text,e['quote']);assert len(hits)==1
            start,end=hits[0];ids=[u['id'] for u in sources[key] if u['start']<end and u['end']>start]
            assert ids
            foci[key].add(ids[-1]);examples.append({'source':key,'operation':op['name'],
                'choice':e['choice'],'quote':e['quote'],'quote_unit_ids':ids,'focus_unit_id':ids[-1]})
    foci={k:sorted(v) for k,v in foci.items()}
    material_data={'sources':sources,'review_focus_units':foci,'existing_acquired_examples':examples}
    sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
    protocol={'same_goal':True,'goal_complete':False,'sources':p['teacher_sources'],
        'excluded_reuse_parents':p['reuse_sources'],'no_reuse_material_read':True,
        'data_input_sha256':digest(material_data),'source_sha256':{str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))},
        'executor_profile':p['executor_profile'],'teacher_profile':p['teacher_profile'],
        'learning_object':'Conditional set-valued influence relations between acquired source units; not a new law vocabulary or source-ID rule cache.',
        'update_algorithm':'Minimum consistent DNF over shared source-structural features; finite set cover reused from binding_learning. Unknown annotations excluded from negative supervision. Apply links as a graph, not a single nearest target.',
        'comparison':'Same acquired unit kinds/annotations: nearest eligible anchor, all eligible anchors in the explicit current paragraph, and operation-specific structural DNF. Leave one acquisition parent out; no native-label objective. Same-information controls receive all acquired annotations and features.',
        'decision':'If paragraph/reference matching or ordinary conditional relation induction gives the same links/updates, record absorption and do not dispatch downstream comparisons just to populate cells. Quote inclusion alone does not certify semantic sufficiency.',
        'workload':'One shared teacher source-link acquisition, offline induction and exact controls. No independent-acquisition advantage claimed for shared data; no execution-model call authorized by this runner.',
        'no_new_mechanical_call_cap':True,'teacher_artifact_is_acquired_supervision_not_independent_legal_gold':True}
    immutable_json(out/'protocol.json',protocol);immutable_json(out/'input.json',material_data)
    if not (out/'ledger_before.json').exists():immutable_json(out/'ledger_before.json',{'rows':rows})
    snap=out/'source_snapshot'/Path(__file__).relative_to(ROOT);snap.parent.mkdir(parents=True,exist_ok=True)
    if snap.exists():assert snap.read_bytes()==Path(__file__).read_bytes()
    else:snap.write_bytes(Path(__file__).read_bytes())
    bound=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['teacher_sources'],'dev':[],'test':[]},binding=digest(protocol))
    return out,p,bound,public,material_data,protocol


def schema(keys):
    link=record_schema({'relation':{'type':'string','enum':RELATIONS},
        'target_unit_ids':{'type':'array','items':{'type':'integer','minimum':0}},
        'quote':{'type':'string','minLength':1}})
    unit=record_schema({'source':{'type':'string','enum':keys},'unit_id':{'type':'integer','minimum':0},
        'effects':{'type':'array','items':{'type':'string','enum':KINDS}},
        'target_scope_complete':{'type':'boolean'},'links':{'type':'array','items':link},
        'explanation':{'type':'string'}})
    return record_schema({'units':{'type':'array','items':unit}})


SYSTEM='''Acquire source influence supervision from only the supplied original TRAIN.
Do not produce answers to downstream hypotheses, repair programs, invent laws,
or use source names as rules. Full source units and existing acquired quote
examples are supplied. These examples are fallible local judgments, not complete
legal gold. Review exactly the listed focus units in each source.

For each focus unit, identify all its actual effects; multiple kinds can coexist.
Identify explicit relations to OTHER reviewed focus units of the SAME source.
qualifies: a condition/exception/retention allowance changes the applicability
or scope of the targeted disposal effect. An exception to a duty does NOT by
itself create an opposite permission. substitutes: an alternative performance
replaces the targeted principal action. inherits_trigger: a linked effect uses
the targeted effect's trigger. information_antecedent: a reference such as
foregoing obtains its information object from the target. followup_of: a later
performance follows the target's retention or process. A relation can have
MULTIPLE target units; never force the nearest unit when the actual reference
covers a paragraph or several performances. Do not add a link merely because
two units are adjacent or share vocabulary. List only source-supported links.
Each link needs an exact quote from the current focus unit; target IDs preserve
all identified targets. Do not create self-links. Report unresolved instead of
inventing a missing relation. Set target_scope_complete only if the actual
scope of ALL relevant relations to reviewed units has been determined; this
flag will make omitted target pairs negative supervision. Uncertainty must
remain incomplete. This is acquisition, not formal proof of legal semantics.
'''


def acquire():
    out,p,ledger,public,data,protocol=prepare();dst=out/'teacher.json'
    teacher=FrozenTeacher(ledger,out,p['teacher_profile'])
    result=teacher.propose(RUN+':teacher:'+digest(protocol),source_ids=p['teacher_sources'],
        system_prompt=SYSTEM,user_prompt=json.dumps(data,ensure_ascii=False),output_schema=schema(p['teacher_sources']))
    immutable_json(dst,result)
    value=result['value'];jsonschema.validate(value,schema(p['teacher_sources']))
    actual={(r['source'],r['unit_id']) for r in value['units']}
    expected={(s,u) for s,ids in data['review_focus_units'].items() for u in ids}
    assert len(actual)==len(value['units']) and actual==expected
    for r in value['units']:
        unit=next(u for u in data['sources'][r['source']] if u['id']==r['unit_id'])
        assert len(set(r['effects']))==len(r['effects']) and r['effects']
        for link in r['links']:
            ids=link['target_unit_ids'];assert ids and len(set(ids))==len(ids)
            assert set(ids)<=set(data['review_focus_units'][r['source']])-{r['unit_id']}
            assert occurrences(unit['text'],link['quote'])
    immutable_json(out/'validated.json',{'value':value,'source_grounding_only_not_semantic_certification':True,
        'all_acquisition_parents':p['teacher_sources'],'new_native_DEV_TEST_labels_used':False})
    print(json.dumps({'units':len(value['units']),'links':sum(len(r['links']) for r in value['units']),
        'complete_scope_rows':sum(r['target_scope_complete'] for r in value['units']),
        'elapsed_seconds':result['elapsed_seconds'],'goal_complete':False}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','acquire']);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_scope_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.stage=='prepare':print(prepare()[0])
        else:acquire()
