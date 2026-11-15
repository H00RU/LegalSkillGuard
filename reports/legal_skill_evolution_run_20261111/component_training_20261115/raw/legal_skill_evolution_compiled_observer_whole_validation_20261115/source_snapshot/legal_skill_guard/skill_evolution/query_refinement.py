"""Select actual acquired reads by their possible effect on the current program.

The finite choice branches are counterfactuals, never source observations. Only
the returned request may be passed to the normal evidence-checked model reader.
The objective can be lawful TRAIN accuracy or unlabeled execution coverage; its
identity is recorded and cannot be changed after seeing future labels.
"""
from copy import deepcopy
import math

from .objects import digest
from .open_acquisition import _read_identity
from .source_observations import encode_source_observations


def select_query(library, observation, objective, *, objective_name, query_ids):
    """Choose one unissued full-window read with a strictly useful choice branch.

This is an optimistic finite acquisition decision, not an expected value or a
claim that the model will return the helpful branch. The acquired G/consumer,
operation meanings and choices are fixed. No source-specific rule is supplied.
Unchanged unknowns and previously issued reads are terminal for this selector.
"""
    if objective_name not in ('lawful_TRAIN_native_correct', 'unlabeled_core_coverage'):
        raise ValueError('Declare the actual training or unlabeled objective')
    if (set(query_ids)!={op['name'] for op in library['operations']}
            or any(not isinstance(q,str) or not q for q in query_ids.values())
            or len(set(query_ids.values()))!=len(query_ids)):
        raise ValueError('Use the distinct actual acquired query IDs for every operation')
    visible=observation['visible_inputs'];units=visible['units']
    if not units:raise ValueError('A complete current source window is required')
    def score(encoded):
        value=objective(encoded)
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('The frozen objective must return a finite number')
        return value
    baseline=score(observation)
    scopes=library.get('operation_scopes',{})
    seen={_read_identity(visible['operations'],q,units,
            visible.get('query_scopes',{}).get(q['id'],visible['scope']))
          for q in visible['queries']}
    evaluations=[]
    for op in sorted(library['operations'],key=lambda op:op['name']):
        scope=scopes.get(op['name'],library['scope'])
        query={'id':query_ids[op['name']],
               'operation':op['name'],'unit_ids':[u['id'] for u in units]}
        identity=_read_identity(library['operations'],query,units,scope)
        if identity in seen:continue
        choices=[]
        for choice in op['choices']:
            # Actual current quotes are used only to make a typed conditional
            # branch executable. These are NOT purported model judgments.
            evidence=[{'unit_id':u['id'],'quote':u['text']} for u in
                      (units if scope=='window' else units[-1:])]
            answer={'id':query['id'],'choice':choice['name'],'evidence':evidence}
            query_scopes={q['id']:visible.get('query_scopes',{}).get(q['id'],visible['scope'])
                          for q in visible['queries']}
            query_scopes[query['id']]=scope
            hypothetical=encode_source_observations(observation['context']['id'],
                source_text=visible['source_text'],units=units,source_output=visible['source_output'],
                operations=library['operations'],queries=[*visible['queries'],query],
                answers=[*visible['answers'],answer],scope=library['scope'],query_scopes=query_scopes,
                complete_source_absence_choices=library.get('complete_source_absence_choices'))
            # Partial structural source constraints remain actual constraints.
            for field in ('required','forbidden'):
                hypothetical['context'][field]=deepcopy(observation['context'][field])
            hypothetical['execution']=deepcopy(observation.get('execution',{}))
            hypothetical['counterfactual_only']=True
            choices.append({'choice':choice['name'],'counterfactual_objective':score(hypothetical)})
        upper=max(c['counterfactual_objective'] for c in choices)
        evaluations.append({'query':query,'reading_identity':identity,'scope':scope,
            'choice_branches':choices,'optimistic_gain':upper-baseline,
            'counterfactuals_are_not_actual_readings':True})
    useful=sorted([e for e in evaluations if e['optimistic_gain']>0],
                  key=lambda e:(-e['optimistic_gain'],len(e['query']['unit_ids']),e['query']['operation']))
    return {'status':'request_selected' if useful else 'no_useful_current_operation',
        'query':deepcopy(useful[0]['query']) if useful else None,
        'objective':objective_name,'baseline_objective':baseline,'candidates':evaluations,
        'library_sha256':digest(library),'observation_sha256':digest(visible),
        'actual_source_semantics_certified':False,'representation_insufficiency_certified':False,
        'selection_uses_native_labels':objective_name=='lawful_TRAIN_native_correct',
        'new_model_requests':0}
