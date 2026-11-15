"""Repair C's demonstrated whole-frame bias using acquired typed fragments.

Existing term nodes/term_argument already support this factorization. No new
legal runtime or constructor is introduced. Source fragments must be grounded
in real concept answers and may contain no Norm node. G alone emits norms.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import time

from experiments import legal_skill_evolution_C_direct_acquisition as base
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION,validate_operations
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations,signatures
from legal_skill_guard.skill_evolution.source_composition import validate_renderers,validate_template_constructors
from legal_skill_guard.skill_evolution.relational_rules import validate_language
from legal_skill_guard.skill_evolution.scoped_grammar import material_public,constructors,term_sort
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,execute_json,validate_procedure
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs,INSTRUCTION,PROGRAM_INSTRUCTION

ROOT=base.ROOT
GENERATION=ROOT/'artifacts/legal_skill_evolution_C_fragment_update_20261115'
RUN='legal_skill_evolution_C_fragment_runtime_20261115'
OUT=ROOT/'artifacts'/RUN
SCHEMA=record_schema({**base.SCHEMA['properties'],'fragment_program':{'type':'string'}})
SYSTEM=base.SYSTEM+'''

This is a concrete repair, not a new research direction. Raw C achieved 8/8
native acquisition but missed the positively reviewed affiliate permission.
Generic guard relaxation recovered that TRAIN source check. Frozen reuse then
scored 0/8: the acquired G/renderers enumerate complete action/trigger/exception
frames and cannot recombine their parts. Audits find a category present but the
planner sometimes never reads the separate retention clause. The independent
ordinary teacher scored 7/8 reuse, including one source-invalid disposal scope.
All negative results and costs are retained. Those four parents are now lawful
acquisition/development data, NOT claimed held-out. Two further original TRAIN
parents are fixed in a stored manifest before you receive this task, omitted
from your input, and cannot affect candidate selection.

Repair concrete compositional coverage, rather than adding one special rule per
old case. Use existing typed term nodes and term_argument; no consumer change.
C additionally returns fragment_program: pure apply(inputs,premises), inputs
are the SAME raw source_text,source_spans,empty source_output, and ACTUAL
semantic_answers. Return {fragments:[{term:<existing typed term>,support_ids:
[current unit IDs],query_ids:[actual definite answer IDs]}],unresolved:[string]}.
Fragments may be Action,Trigger,ExceptionSet,Condition,Entity etc, but NO node
anywhere may have sort Norm. Every fragment needs actual non-unknown query IDs
and its support must be contained in their actual evidence units. No invented
meaning, guessed unknown, source-ID/name dispatch or source-specific constants.
The program can mechanically map acquired concept choices to typed fragments;
it must not produce a whole norm or hide a normative source parser. All inputs
and actual quotes are retained. Learned fragment mappings are learned content,
not a host legal rule or automatically a novel contribution.

The host places these non-Norm fragments into source_output for the existing
encoder: legacy_root,term_constructor,term_child,root_support give their REAL
typed identities. These are concept-grounded fragments, never old whole norms.
G must assemble source norms from current Action/Trigger/Exception etc nodes
with term_argument and match source-unit ownership. This can combine pieces
not jointly seen before. All whole-source absence markers still require actual
complete-source absence reads. Do not use keep_root. Existing scalar/unit/query
interfaces remain. Ensure all renderer positions are used and types match.
No undeclared legal constructor, default missing exception or category-absence
claim. Read a separate exception when needed; unknowns remain unresolved.

Both arms have equal raw text, lawful supervision, source reviews, code capacity
and budgets, and independently revise their own complete prior proposal.
FreeTeacher may adopt the SAME fragment/G architecture, factor its strongest
ordinary pure program, or change its read operations/planner; it is not forced
to preserve a failing baseline. Return fragment_program='' if unused. If using
fragments it must use relational composition (free_composition_program='').
Programs are pure top-level Python; helper functions are allowed, no imports,
nested functions, reflection or IO. Use supported builtins; repr is supported.
Keep programs compact and executable. This is one focused architecture repair,
not a request to fit labels by changing legal meaning. Source output is still
raw/empty before ACTUAL reading. Nothing is supplied as a desired current norm.
'''


def read(path):return json.loads(path.read_text())


def prepare_runtime():
    import sqlite3
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')as db:
        assert not db.execute("select id from calls where status='reserved'").fetchall()
    p=read(GENERATION/'protocol.json')
    names=['common_task.json','raw_source_bank.json','TRAIN_grading.json','common_spec.json','source_selection.json']
    names += [arm+'/'+name for arm in ('C','FreeTeacher')for name in ('teacher_task.json','teacher.json')]
    for relative in names:
        target=OUT/relative;target.parent.mkdir(parents=True,exist_ok=True);payload=(GENERATION/relative).read_bytes()
        if target.exists():assert target.read_bytes()==payload
        else:target.write_bytes(payload)
    p.update(run_id=RUN,generation_run=p['run_id'],ledger_before=base.lineage.ledger_snapshot(),
        runtime_change='Shared pure dict.setdefault support preserving unresolved field protection; fragments restricted to proper semantic parts, excluding Norm/Description/Definition; teacher responses byte-identical')
    files=[Path(__file__),Path(base.__file__),Path(base.history.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))+[OUT/n for n in names]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'runtime_prepared':RUN,'new_teacher_calls':0}),flush=True)


def prepare():
    old=read(base.OUT/'protocol.json');public,grading=base.history.bank()
    acquisition=old['acquisition_sources']+old['fixed_reuse_sources']
    # Deterministic original bank insertion order; no labels or source contents
    # participate in choosing the next two parents.
    reuse=[sid for sid in public if sid not in acquisition][:2]
    immutable_json(OUT/'source_selection.json',{'acquisition_sources':acquisition,'fixed_reuse_sources':reuse,
        'selection':'first two remaining original TRAIN bank entries in preserved insertion order',
        'labels_or_source_contents_used_for_selection':False,'prior_B8_exposure_disclosed':True})
    bank={};sources=[]
    for sid in acquisition+reuse:
        source=public[sid];text=source['views'][0]['public']['source_text']
        units,_=execution_source_units(text,source_spans(material_public(source['views'][0]['public'])))
        bank[sid]={'source':source,'units':units,'empty_upstream':{'statements':[],'complete':False,'unresolved':[]}}
        if sid in acquisition:sources.append({'source':sid,'source_text':text,'units':units,
            'native_TRAIN_supervision':grading[sid],'native_hypotheses':[{'id':v['id'],'question':v['public']['question']}for v in source['views']]})
    task={'common_output_spec':read(base.OUT/'common_spec.json'),'observed_signatures':signatures(),
        'acquisition_sources':sources,'source_feedback':read(base.OUT/'teacher_task.json')['source_feedback'],
        'shared_partial_disposal_feedback':read(base.history.OUT/'teacher_task.json')['shared_partial_reviews'],
        'actual_shared_diagnosis':'Whole-frame G cannot recombine return/destroy, trigger and separate retention; planner missed independent retention units. Preserve source qualifiers and complete-material scope.'}
    from legal_skill_guard.skill_evolution.span_compiler import CALLS,METHODS
    task['supported_pure_builtins']=sorted(CALLS);task['supported_pure_methods']=sorted(METHODS)
    for name in ('relational_rules.py','source_composition.py','source_observations.py'):
        task[name]=(ROOT/'legal_skill_guard/skill_evolution'/name).read_text()
    immutable_json(OUT/'common_task.json',task);immutable_json(OUT/'raw_source_bank.json',bank)
    immutable_json(OUT/'TRAIN_grading.json',{s:grading[s]for s in bank})
    immutable_json(OUT/'common_spec.json',task['common_output_spec'])
    for arm in ('C','FreeTeacher'):
        own={'previous_own_proposal':read(base.OUT/arm/'teacher.json')['value'],'actual_own_readings':[]}
        origins=[base.OUT/arm/'observations']
        if arm=='C':origins.append(ROOT/'artifacts/legal_skill_evolution_C_guard_learning_20261115/observations')
        for sid in acquisition:
            paths=[folder/(digest(sid)+'.json')for folder in origins];path=next(p for p in paths if p.exists())
            obs=read(path);own['actual_own_readings'].append({'source':sid,'visible_inputs':obs['visible_inputs']})
        immutable_json(OUT/arm/'teacher_task.json',{**task,**own})
    p={k:deepcopy(old[k])for k in ('sources','executor_profile','teacher_profile')}
    p.update(run_id=RUN,acquisition_sources=acquisition,fixed_reuse_sources=reuse,
        same_goal=True,goal_complete=False,full_training_DEV_TEST=False,
        fitting_wall_time_seconds=120,ledger_before=base.lineage.ledger_snapshot())
    files=[Path(__file__),Path(base.__file__),Path(base.history.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files+=[OUT/n for n in ('common_task.json','raw_source_bank.json','TRAIN_grading.json','common_spec.json','source_selection.json','C/teacher_task.json','FreeTeacher/teacher_task.json')]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'acquisition':acquisition,'reuse':reuse,
        'teacher_task_chars':{a:len(json.dumps(pack_programs(read(OUT/a/'teacher_task.json'))))for a in ('C','FreeTeacher')}}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    return p


def ledger(p):return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
    sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)


def acquire():
    p=protocol();client=FrozenTeacher(ledger(p),OUT,p['teacher_profile'])
    def one(arm):
        if(OUT/arm/'teacher.json').exists():return
        result=client.propose(RUN+':'+arm+':fragment_update',source_ids=p['acquisition_sources'],
            system_prompt=SYSTEM+'\nYour arm: '+arm+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(read(OUT/arm/'teacher_task.json')),ensure_ascii=False,separators=(',',':')),output_schema=SCHEMA)
        immutable_json(OUT/arm/'teacher.json',result);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,a)for a in ('C','FreeTeacher')]
        for job in jobs:job.result()


def compile_proposals():
    p=protocol();bank=read(OUT/'raw_source_bank.json');spec=read(OUT/'common_spec.json');libraries={}
    for arm in ('C','FreeTeacher'):
        v=read(OUT/arm/'teacher.json')['value'];ops=v['operations'];validate_operations(ops,{s:bank[s]['source']['views'][0]['public']['source_text']for s in p['acquisition_sources']})
        scopes=json.loads(v['operation_scopes_json']);assert set(scopes)=={o['name']for o in ops}
        assert all(s in ('window','focus_last')for s in scopes.values());validate_procedure(v['planner_program'],allow_helpers=True)
        lib={'operations':ops,'operation_scopes':scopes,'scope':'window','planner_program':v['planner_program'],
            'spec':spec,'complete_source_absence_choices':json.loads(v['complete_source_absence_choices_json'])}
        if v['fragment_program']:
            validate_procedure(v['fragment_program'],allow_helpers=True);lib['fragment_program']=v['fragment_program']
        if v['free_composition_program']:
            assert arm=='FreeTeacher'and not v['fragment_program'];validate_procedure(v['free_composition_program'],allow_helpers=True)
            lib['composition_program']=v['free_composition_program']
        else:
            lang=json.loads(v['language_json']);assert not set(lang['signatures'])&set(signatures())
            assert 'keep_root'not in lang['signatures'];lang['signatures']={**signatures(),**lang['signatures']}
            for sort,values in [('operation',[o['name']for o in ops]),('choice',[c['name']for o in ops for c in o['choices']])]:
                lang['constants'][sort]=list(dict.fromkeys(lang['constants'].get(sort,[])+values))
            # Constructor names are the shared public typed vocabulary. This
            # restores a missing declaration, not a rule or source fact.
            lang['constants']['constructor']=list(dict.fromkeys(lang['constants'].get('constructor',[])+list(constructors(spec))))
            renderers=json.loads(v['renderers_json']);validate_language(lang);validate_renderers(lang,renderers);validate_template_constructors(renderers,spec)
            assert set(v['recommended_rule_ids'])<={r['id']for r in lang['rules']}
            lib.update(language=lang,renderers=renderers,selected_rule_ids=v['recommended_rule_ids'])
        libraries[arm]=lib
    return libraries


def fragments(library,obs):
    if'fragment_program'not in library:return obs
    v=obs['visible_inputs'];inputs={'source_text':v['source_text'],'source_spans':v['units'],
        'source_output':v['source_output'],'semantic_answers':v['answers']}
    value=execute_json(library['fragment_program'],inputs,{},allow_helpers=True)
    assert set(value)=={'fragments','unresolved'}and isinstance(value['fragments'],list)
    schema=constructors(library['spec']);answers={a['id']:a for a in v['answers']};rows=[]
    def no_norm(term):
        if isinstance(term,list):
            assert schema[term[0]]['sort'] in {'Participant','Information','Action','Trigger','Condition','Exception','ExceptionSet'},'A fragment must be a proper semantic part, never a whole norm or answer-bearing description/definition'
            for child in term[1:]:no_norm(child)
    for row in value['fragments']:
        assert set(row)=={'term','support_ids','query_ids'}
        term_sort(row['term'],schema);no_norm(row['term']);assert row['query_ids']and row['support_ids']
        assert all(q in answers and answers[q]['choice']!='unknown'for q in row['query_ids'])
        supports={w['unit_id']for q in row['query_ids']for w in answers[q]['evidence']}
        assert set(row['support_ids'])<=supports
        rows.append({'term':row['term'],'support_ids':row['support_ids']})
    encoded=encode_source_observations(obs['context']['id'],source_text=v['source_text'],units=v['units'],
        source_output={'statements':rows,'complete':False,'unresolved':value['unresolved']},
        operations=v['operations'],queries=v['queries'],answers=v['answers'],scope=v['scope'],
        query_scopes=v['query_scopes'],complete_source_absence_choices=v.get('complete_source_absence_choices'))
    encoded['fragment_execution']={'program_sha256':digest(library['fragment_program']),'actual_fragments':value,
        'no_norm_nodes':True,'original_observation_sha256':digest(obs),'new_model_calls':0}
    return encoded


def assess(library,obs,sid):
    bank=read(OUT/'raw_source_bank.json');source=bank[sid]['source'];grading=read(OUT/'TRAIN_grading.json')[sid]
    core=base.history.previous.update.train.previous.old.previous.prior.prior
    output=core.evaluate_source(library,obs,source,None)['execution']['source_output']
    from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
    prior=read(base.history.OUT/'teacher_task.json')['shared_partial_reviews']
    check=with_disposal_review(core.checker(library,source,grading),sid,prior.get('shared_reviewed_source_scope_checks')or[],
        library['spec']['decision_program'],authorization_review=prior.get('shared_branch_authorization_review'))
    feedback=check(output);frame=base.history.frame_review(sid,output)
    return {'source':sid,'feedback':feedback,'frame_review':frame,'source_output':output,
        'hard_source_pass':feedback.get('source_review_passed',True)and not frame['failures'],
        'native_correct':sum(bool(v['score']and v['score']['correct'])for v in feedback['views']),
        'native_total':len(feedback['views']),'unresolved':sum(not v['core_executed']for v in feedback['views'])}


def execute():
    p=protocol();libraries=compile_proposals();bank=read(OUT/'raw_source_bank.json');client=FrozenExecutor(ledger(p),OUT,p['executor_profile']);results=[]
    for arm,library in libraries.items():
        folder=OUT/arm
        def observation(sid):
            target=folder/'observations'/(digest(sid)+'.json')
            if target.exists():return read(target)
            prior=[]
            for origin in (base.OUT/arm/'observations',ROOT/'artifacts/legal_skill_evolution_C_guard_learning_20261115/observations'if arm=='C'else base.OUT/arm/'observations'):
                path=origin/target.name
                if path.exists()and not any(digest(read(path))==digest(o)for o in prior):prior.append(read(path))
            item=bank[sid]
            obs=observe(client,RUN+':'+arm+':'+digest(sid),sid,library,source_text=item['source']['views'][0]['public']['source_text'],
                units=item['units'],source_output=item['empty_upstream'],previous_observations=prior,
                save_event=lambda event:immutable_json(folder/'read_events'/(digest(event['call_id'])+'.json'),event))
            encoded=fragments(library,obs);immutable_json(folder/'raw_observations'/target.name,obs);immutable_json(target,encoded);return encoded
        observations={s:observation(s)for s in p['acquisition_sources']}
        nofit=[assess(library,observations[s],s)for s in p['acquisition_sources']]
        if'language'in library:
            recommended=library['selected_rule_ids'];names=[r['id']for r in library['language']['rules']]
            costs={r['id']:r['cost']for r in library['language']['rules']};candidates=[recommended,[],names]
            candidates += [sorted(set(recommended)^{name})for name in names]
            best=None;seen=set();trials=[];start=time.monotonic()
            for ids in candidates:
                key=tuple(sorted(ids))
                if key in seen:continue
                if trials and time.monotonic()-start>=p['fitting_wall_time_seconds']:break
                seen.add(key);candidate=deepcopy(library);candidate['selected_rule_ids']=list(key)
                rows=[assess(candidate,observations[s],s)for s in p['acquisition_sources']]
                rank=(-sum(r['native_correct']for r in rows),sum(costs[i]for i in key),len(key),key)
                valid=all(r['hard_source_pass']for r in rows);trials.append({'rule_ids':list(key),'rows':rows,'hard_source_pass':valid})
                if valid and(best is None or rank<best[0]):best=(rank,candidate)
            immutable_json(folder/'fit_receipt.json',{'trials':trials,'optimization_complete':False,'new_model_calls':0})
            if best is None:
                immutable_json(folder/'unresolved.json',{'reason':'No source-valid acquired hypothesis','paid_reads_preserved':True});continue
            library=best[1]
        immutable_json(folder/'selected_before_reuse.json',{'library':library,'acquisition_only':True})
        acquisition=[assess(library,observations[s],s)for s in p['acquisition_sources']]
        reuse=[assess(library,observation(s),s)for s in p['fixed_reuse_sources']]
        result={'arm':arm,'acquisition':acquisition,'fixed_reuse':reuse,'NoFit_acquisition':nofit,'goal_complete':False}
        immutable_json(folder/'result.json',result);results.append(result)
        print(json.dumps({'arm':arm,'acquisition':[(r['native_correct'],r['hard_source_pass'])for r in acquisition],
            'reuse':[(r['native_correct'],r['hard_source_pass'])for r in reuse]}),flush=True)
    immutable_json(OUT/'result.json',{'arms':results,'goal_complete':False,'new_DEV_TEST':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare_runtime','validate','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare_runtime':prepare_runtime,'validate':compile_proposals,'execute':execute}[args.phase]()
