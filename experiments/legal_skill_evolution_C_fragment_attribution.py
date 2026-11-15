"""Offline attribution on already-paid C fragment observations.

No client, new source, native label change or candidate selection. The no-read
and no-fragment interventions are never stored as actual observations.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_C_fragment_update as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations


def without(library, observation, *, remove_answers):
    visible=observation['visible_inputs']
    encoded=encode_source_observations(observation['context']['id'],
        source_text=visible['source_text'],units=visible['units'],
        source_output={'statements':[],'complete':False,'unresolved':[]},
        operations=visible['operations'],queries=visible['queries'],
        answers=[]if remove_answers else visible['answers'],scope=visible['scope'],
        query_scopes=visible['query_scopes'],
        complete_source_absence_choices=visible.get('complete_source_absence_choices'),
        query_aliases=visible.get('query_aliases'))
    encoded['counterfactual_only']=True
    return encoded


def run():
    protocol=current.protocol()
    freeze=current.read(current.OUT/'C/selected_before_reuse.json')
    library=freeze['library'];recommended=current.compile_proposals()['C']
    rows=[];pending=[]
    for sid in protocol['acquisition_sources']+protocol['fixed_reuse_sources']:
        path=current.OUT/'C/observations'/(digest(sid)+'.json')
        if not path.exists():pending.append(sid);continue
        observation=current.read(path)
        row={'source':sid,
            'phase':'acquisition'if sid in protocol['acquisition_sources']else'fixed_reuse',
            'C':current.assess(library,observation,sid),
            'NoFit':current.assess(recommended,observation,sid),
            'NoFragment':current.assess(library,without(library,observation,remove_answers=False),sid),
            'NoConcept':current.assess(library,without(library,observation,remove_answers=True),sid),
            'actual_fragment_count':len(observation.get('fragment_execution',{}).get('actual_fragments',{}).get('fragments',[])),
            'new_model_requests':0}
        immutable_json(current.OUT/'C/attribution_rows'/(digest(sid)+'.json'),row)
        rows.append(row)
        print(json.dumps({'source':sid,'phase':row['phase'],
            'scores':{name:[row[name]['native_correct'],row[name]['hard_source_pass'],row[name]['unresolved']]
                for name in ('C','NoFit','NoFragment','NoConcept')}}),flush=True)
    # Partial captures have distinct names; an in-progress result cannot later
    # be silently overwritten by a completed attribution receipt.
    name='attribution_complete.json'if not pending else'partial_attribution_'+digest([r['source']for r in rows])+'.json'
    immutable_json(current.OUT/'C'/name,{'rows':rows,'pending_sources':pending,
        'frozen_library_sha256':digest(library),'new_model_requests':0,
        'interventions_are_not_actual_observations':True,'goal_complete':False})


if __name__=='__main__':run()
