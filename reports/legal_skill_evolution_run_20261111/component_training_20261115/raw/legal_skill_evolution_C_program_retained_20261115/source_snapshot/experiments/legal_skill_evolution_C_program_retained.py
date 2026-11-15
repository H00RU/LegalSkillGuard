"""Preserve working learned reads/channels while installing program concepts.

One actual revision repair, no new teacher. Demonstration-only changes are
rolled back equally for both arms; meanings and choices are byte-identical.
The C source-program update owns disclosure, while the unchanged acquired
disposal/retention conversion is retained instead of an incomplete rewrite.
"""
from copy import deepcopy
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import time

from experiments import legal_skill_evolution_C_program_concepts as acquisition
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations

ROOT=acquisition.ROOT
RUN='legal_skill_evolution_C_program_retained_20261115'
OUT=ROOT/'artifacts'/RUN
RETAINED={'disposal_action','disposal_material_scope','disposal_trigger','retention_effect'}


def read(path):return json.loads(path.read_text())


def prepare():
    p=acquisition.protocol();libraries=acquisition.compile_proposals();changes={}
    for arm,library in libraries.items():
        prior=acquisition.previous.compile_proposals()[arm];old={o['name']:o for o in prior['operations']};changes[arm]=[]
        for i,operation in enumerate(library['operations']):
            historical=old.get(operation['name'])
            if historical and operation!=historical and {k:v for k,v in operation.items()if k!='examples'}=={k:v for k,v in historical.items()if k!='examples'}:
                assert library['operation_scopes'][operation['name']]==prior['operation_scopes'][operation['name']]
                library['operations'][i]=deepcopy(historical)
                changes[arm].append({'operation':operation['name'],'new_sha256':digest(operation),
                    'retained_sha256':digest(historical),'question_choices_scope_exactly_equal':True})
        if arm=='C':
            library['retained_fragment_library']=prior
        immutable_json(OUT/arm/'candidate.json',library)
    immutable_json(OUT/'operation_versions.json',{'arms':changes,'new_teacher_requests':0,
        'new_source_program_and_G_candidates_unchanged':True,'restored_channels':sorted(RETAINED)})
    p=deepcopy(p);p.update(run_id=RUN,generation_run=acquisition.RUN,
        ledger_before=acquisition.previous.base.lineage.ledger_snapshot(),
        actual_repair='Retain previously validated demonstrations where semantics unchanged; preserve acquired non-disclosure conversion; no old normative outputs supplied')
    files=[Path(__file__),Path(acquisition.__file__),Path(acquisition.previous.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [OUT/a/'candidate.json'for a in ('C','FreeTeacher')]+[OUT/'operation_versions.json']
    files += [acquisition.OUT/n for n in ('protocol.json','raw_source_bank.json','TRAIN_grading.json','common_spec.json','C/teacher.json','FreeTeacher/teacher.json')]
    core=acquisition.previous.base.history.previous.update.train.previous.old.previous.prior.prior
    files.append(Path(core.__file__))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'operation_versions':{a:len(v)for a,v in changes.items()},'new_teacher_requests':0}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p


def convert(library,raw):
    value=acquisition.program_concepts(library,raw)
    if'retained_fragment_library'not in library:return value
    old=acquisition.previous.fragments(library['retained_fragment_library'],raw)
    old_fragments=old['fragment_execution']['actual_fragments']['fragments']
    current=value['source_concept_execution']['program_output'];v=value['visible_inputs']
    by_query={q['id']:q for q in v['queries']}
    def unaffected(fragment):
        return bool(fragment['query_ids'])and all(by_query[q]['operation']in RETAINED for q in fragment['query_ids'])
    kept_new=[fragment for fragment in current['fragments']if not unaffected(fragment)]
    kept_old=[fragment for fragment in old_fragments if unaffected(fragment)]
    combined=kept_new+kept_old
    encoded=encode_source_observations(raw['context']['id'],source_text=v['source_text'],units=v['units'],
        source_output={'statements':[{'term':r['term'],'support_ids':r['support_ids']}for r in combined],
            'complete':False,'unresolved':current['unresolved']},
        operations=v['operations'],queries=v['queries'],answers=v['answers'],scope=v['scope'],
        query_scopes=v['query_scopes'],complete_source_absence_choices=v.get('complete_source_absence_choices'),query_aliases=v.get('query_aliases'))
    encoded['source_concept_execution']=deepcopy(value['source_concept_execution'])
    encoded['source_concept_execution']['composed_fragments']={'new_disclosure_fragments':kept_new,
        'retained_other_fragments':kept_old,'retained_program_sha256':digest(library['retained_fragment_library']['fragment_program']),
        'no_old_normative_outputs_used':True}
    return acquisition.typed(encoded,library['spec'])


def run():
    p=protocol();bank=read(acquisition.OUT/'raw_source_bank.json');libraries={a:read(OUT/a/'candidate.json')for a in ('C','FreeTeacher')}
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);results=[]
    for arm,library in libraries.items():
        folder=OUT/arm
        def observation(sid):
            target=folder/'observations'/(digest(sid)+'.json')
            if target.exists():return read(target)
            histories=[]
            for origin in (acquisition.previous.OUT/arm/'observations',acquisition.OUT/arm/'raw_observations'):
                path=origin/target.name
                if path.exists():histories.append(read(path))
            item=bank[sid]
            raw=observe(client,RUN+':'+arm+':'+digest(sid),sid,library,
                source_text=item['source']['views'][0]['public']['source_text'],units=item['units'],source_output=item['empty_upstream'],previous_observations=histories,
                save_event=lambda event:immutable_json(folder/'read_events'/(digest(event['call_id'])+'.json'),event))
            immutable_json(folder/'raw_observations'/target.name,raw);value=convert(library,raw);immutable_json(target,value);return value
        observations={s:observation(s)for s in p['acquisition_sources']}
        nofit=[acquisition.assess(library,observations[s],s)for s in p['acquisition_sources']]
        if'language'in library:
            ids=[r['id']for r in library['language']['rules']];recommended=library['selected_rule_ids'];costs={r['id']:r['cost']for r in library['language']['rules']}
            candidates=[recommended,[],ids]+[sorted(set(recommended)^{i})for i in ids]
            best=None;seen=set();trials=[];start=time.monotonic()
            for selection in candidates:
                key=tuple(sorted(selection))
                if key in seen:continue
                if trials and time.monotonic()-start>=p['fitting_wall_time_seconds']:break
                seen.add(key);candidate=deepcopy(library);candidate['selected_rule_ids']=list(key)
                rows=[acquisition.assess(candidate,observations[s],s)for s in p['acquisition_sources']]
                valid=all(r['hard_source_pass']for r in rows);rank=(-sum(r['native_correct']for r in rows),sum(costs[i]for i in key),len(key),key)
                trials.append({'rule_ids':list(key),'rows':rows,'hard_source_pass':valid})
                if valid and(best is None or rank<best[0]):best=(rank,candidate)
            immutable_json(folder/'fit_receipt.json',{'trials':trials,'optimization_complete':False,'new_model_requests':0})
            if best is None:
                immutable_json(folder/'unresolved.json',{'reason':'No source-valid retained-component candidate'});continue
            library=best[1]
        immutable_json(folder/'selected_before_reuse.json',{'library':library,'acquisition_only':True})
        acquisition_rows=[acquisition.assess(library,observations[s],s)for s in p['acquisition_sources']]
        reuse=[acquisition.assess(library,observation(s),s)for s in p['fixed_reuse_sources']]
        result={'arm':arm,'acquisition':acquisition_rows,'fixed_reuse':reuse,'NoFit_acquisition':nofit,'goal_complete':False}
        immutable_json(folder/'result.json',result);results.append(result)
        print(json.dumps({'arm':arm,'acquisition':[(r['native_correct'],r['hard_source_pass'],r['unresolved'])for r in acquisition_rows],
            'reuse':[(r['native_correct'],r['hard_source_pass'],r['unresolved'])for r in reuse]}),flush=True)
    immutable_json(OUT/'result.json',{'arms':results,'goal_complete':False,'new_DEV_TEST':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'execute':run}[args.phase]()
