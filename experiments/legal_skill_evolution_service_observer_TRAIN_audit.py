"""Check frozen service programs on all original 24 SARA TRAIN sources.

Zero model requests, no reselection/update. Positive service cases and absent
service scans are reported separately; neither counts as a whole-case verdict.
"""
from copy import deepcopy
import json
from types import SimpleNamespace

from experiments import legal_skill_evolution_service_observer_validate as validation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.observation_component_library import component_value
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.sara_statute_kernel import literal_date,prepare_case

ROOT=validation.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_service_observer_TRAIN_audit_20261115'


def reference(sid):
    # Source-only finite annotations; no native labels or query-derived dates.
    rows={
        '815f377b':[('Bob','Alice','2011-01-02','2019-10-10',None)],
        '982d5316':[('Alice',None,None,None,None)],
        'd5e1138c':[('Bob','Alice',None,None,'agricultural labor')],
        '6939feda':[('Bob','Alice','2017-02-01','2017-09-02','domestic service'),
            ('Alice','Bob','2017-04-01','2018-09-02',None)],
        '250fc5e7':[('Alice','Johns Hopkins University',None,None,None)],
        'bb6b0bc1':[('Bob','Alice','2017-02-01','2017-09-02','domestic service')],
        'ed3f34d3':[('Bob','Alice','2017-02-01','2017-09-02','domestic service')],
        'd9d6b236':[(w,'Alice','2017-02-01','2017-09-02','agricultural labor')for w in ('Bob','Charlie','Dan')]+
            [('Alice','Bob','2017-04-01','2018-09-02',None)],
        '3e22604a':[('Bob','Alice','2017-02-01','2017-09-02',None)]}
    return rows.get(sid.split(':')[1][:8],[])


def check(part,expected):
    if not part['complete']or part['reasons']:
        return {'usable':False,'errors':[],'status':'explicit_unresolved'}
    facts=deepcopy(part['facts'])
    for f in facts:
        if f['predicate']in ('start_','end_'):f['arguments'][1]=literal_date(f['arguments'][1])
    def values(p,e):return [r['arguments'][1]for r in facts if r['predicate']==p and r['arguments'][0]==e]
    events=[f['arguments'][0]for f in facts if f['predicate']=='service_']
    errors=[]
    if len(events)!=len(expected):errors.append('Complete scan has wrong count of source service events')
    for worker,employer,start,end,kind in expected:
        found=[e for e in events if values('agent_',e)==[worker]and values('patient_',e)==([employer]if employer else [])]
        if len(found)!=1:errors.append('Missing, invented or reversed source role: '+worker);continue
        e=found[0]
        if values('start_',e)!=([start]if start else [])or values('end_',e)!=([end]if end else []):errors.append('Service period not source-faithful: '+worker)
        kinds=values('purpose_',e)
        if kind is not None and kinds!=[kind]:errors.append('Source service kind missing or changed: '+worker)
        if kind is None and any(k in ('agricultural labor','domestic service')for k in kinds):errors.append('Unstated restricted service kind')
    return {'usable':not errors,'errors':errors,'status':'passed_partial_source_checks'if not errors else 'known_source_violation'}


def run():
    p=validation.setup();public,kernels=validation.acquired.data()
    selected=validation.train.read(validation.OUT/'selected_before_reuse.json')['selected']
    assert len(public)==24 and all(s['split']=='train'for s in public.values())
    # References and selected versions are frozen before examining audit outputs.
    immutable_json(OUT/'protocol.json',{'original_TRAIN_sources':list(public),'selected':selected,
        'source_annotations':{s:reference(s)for s in public},'no_reselection':True,
        'public_content_sha256':{s:digest(v)for s,v in public.items()},'new_model_calls':0,
        'prior_B8_exposure_not_a_blind_split':True,'DEV_TEST_loaded':False})
    rows=[];client=SimpleNamespace(artifacts=OUT,ledger=SimpleNamespace(run_id=OUT.name))
    for arm in validation.train.ARMS:
        base=validation.train.read(validation.acquired.BASE/'libraries'/(arm+'.json'))
        old=next(c for c in base['components']if c['id']==validation.acquired.COMPONENT)
        proposals=validation.train.read(validation.acquired.OUT/arm/'teacher.json')['value']['candidates']
        for index,proposal in enumerate(proposals):
            component={**old,**{k:v for k,v in proposal.items()if k!='rationale'},'facts_only':True}
            for sid,source in public.items():
                row={'arm':arm,'candidate':index,'selected_before_audit':selected[arm]['candidate']==index,
                    'source':sid,'positive_service_source':bool(reference(sid)),'not_a_whole_case_result':True}
                try:
                    pub=source['views'][0]['public']
                    observation,receipt=validation.train.actor.read_component(client,p,sid,component,kernels[sid],pub,purpose='skill_actor')
                    parts=[component_value(base,component,kernels[sid],pub,v)for v in observation[validation.acquired.COMPONENT]['views']]
                    for part in parts:
                        prepare_case(kernels[sid],{'facts':part['facts'],'negative_givens':part['negative_givens'],'extraction_status':'unread'})
                    checks=[check(part,reference(sid))for part in parts]
                    row.update(observation=observation,receipt=receipt,converted=parts,checks=checks,
                        usable=all(c['usable']for c in checks),source_errors=sum(len(c['errors'])for c in checks))
                except Exception as error:row.update(error=type(error).__name__+': '+str(error),usable=False)
                immutable_json(OUT/'rows'/arm/str(index)/(digest(sid)+'.json'),row);rows.append(row)
    summary=[]
    for arm in validation.train.ARMS:
        for index in range(2):
            own=[r for r in rows if r['arm']==arm and r['candidate']==index]
            summary.append({'arm':arm,'candidate':index,'selected_before_audit':selected[arm]['candidate']==index,
                'positive_service_sources':sum(r['positive_service_source']for r in own),
                'positive_source_usable':sum(r['positive_service_source']and r['usable']for r in own),
                'no_service_sources':sum(not r['positive_service_source']for r in own),
                'no_service_scan_usable':sum(not r['positive_service_source']and r['usable']for r in own),
                'known_source_errors':sum(r.get('source_errors',0)for r in own),
                'runtime_or_type_errors':sum('error'in r for r in own)})
    immutable_json(OUT/'result.json',{'rows':rows,'summary':summary,'new_model_calls':0,
        'all_original24_TRAIN_only':True,'DEV_TEST_loaded':False,'candidate_selection_unchanged':True,
        'not_new_independent_sources_or_a_core_method_gain':True,'goal_complete':False})
    print(json.dumps(summary),flush=True)


if __name__=='__main__':run()
