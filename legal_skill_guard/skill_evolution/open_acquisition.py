"""Executable concept updates and global source-rule composition learning.

The teacher proposes source operations, executable query planning and relational
rule candidates. A deterministic finite learner selects G using accumulated
lawful source constraints. Every new reading still comes from the real frozen
executor. This module supplies no domain rule or answer and starts no queue.
"""
from copy import deepcopy

from .objects import digest
from .relational_learning import execute_composition, fit_composition
from .relational_rules import validate_language
from .semantic_execution import (answer_schema, decode_answers, focused_messages,
                                 operation_groups)
from .semantic_operations import prepare_queries, validate_operations
from .source_composition import render_composition, validate_renderers
from .source_effect_update import function_update
from .source_observations import encode_source_observations, signatures


def compile_update(previous, proposal, training_texts):
    """Compile a concrete learned update without editing any previous artifact."""
    validate_operations(proposal['operations'],training_texts)
    language=deepcopy(proposal['language']);validate_language(language)
    base=signatures()
    for name,signature in base.items():
        if language['signatures'].get(name)!=signature:
            raise ValueError('Learned compositions must preserve their complete source interface')
    for name,signature in language['signatures'].items():
        if signature['kind']=='observed' and name not in base:
            raise ValueError('A new observation needs an executable reader, not a supplied factual predicate')
    if proposal['scope'] not in ('focus_last','window'):
        raise ValueError('Explicit learned reading scope required')
    validate_renderers(language,proposal['renderers'])
    planner=function_update(previous['planner_program'],proposal['planner_functions'])
    old_ops={op['name']:op for op in previous['operations']}
    changed=[op['name'] for op in proposal['operations'] if op['name'] not in old_ops or op!=old_ops[op['name']]]
    removed=sorted(set(old_ops)-{op['name'] for op in proposal['operations']})
    library={
        'operations':deepcopy(proposal['operations']),'planner_program':planner,
        'language':language,'renderers':deepcopy(proposal['renderers']),
        'scope':proposal['scope'],'spec':deepcopy(previous['spec']),
        'selected_rule_ids':None,
        'update':{'previous_library_sha256':digest(previous),'proposal_sha256':digest(proposal),
            'changed_operation_names':changed,'rationale':proposal['rationale'],
            'removed_operation_names':removed,
            'new_model_requests_during_compilation':0,
            'current_source_or_generalization_certified':False}}
    return library


def _read_identity(operations,query,units,scope):
    by_op={o['name']:o for o in operations};by_unit={u['id']:u for u in units}
    return digest({'operation':by_op[query['operation']],'query':query,
        'units':[by_unit[i] for i in query['unit_ids']],'scope':scope})


def observe(client,prefix,source_id,library,*,source_text,units,source_output,
            previous_observation=None,save_event=None):
    """Run actual new concepts; reuse only identical current-source observations.

    Previously answered unknown is terminal for an unchanged operation/window.
    A changed meaning/planner window is a new query with a recorded identity.
    The caller separately supplies the preserved actual upstream source output.
    """
    from .runtime import decoder_schema
    queries=prepare_queries(library['planner_program'],library['operations'],source_text,units)
    scope=library['scope'];reusable={}
    if previous_observation:
        previous=previous_observation['visible_inputs']
        if previous['source_text']!=source_text or previous['units']!=units:
            raise ValueError('Cannot reuse readings from different current material')
        by_id={a['id']:a for a in previous['answers']}
        for q in previous['queries']:
            if q['id'] in by_id:
                reusable[_read_identity(previous['operations'],q,units,previous['scope'])]=by_id[q['id']]
    answers={};pending=[];reused=[];events=[]
    for q in queries:
        key=_read_identity(library['operations'],q,units,scope)
        if key in reusable:
            answers[q['id']]=deepcopy(reusable[key]);reused.append(q['id'])
        else:pending.append(q)
    for batch in operation_groups(pending):
        prompt=focused_messages(library['operations'],batch,units,scope=scope)
        wire,_=decoder_schema(answer_schema(library['operations'],batch))
        call_id=prefix+':concept:'+digest(prompt)
        result=client.generate(call_id,source=source_id,purpose='skill_replay',
            messages=prompt,thinking=False,schema=wire)
        event={'call_id':call_id,'query_ids':[q['id'] for q in batch],'result':result,
            'scope':scope,'library_sha256':digest(library)}
        # Save even truncated/type-invalid responses before raising. The common
        # client has already reserved/settled their physical request in ledger.
        if save_event:save_event(event)
        events.append(event)
        if result['finish_reason']!='stop':raise ValueError('Incomplete concept read; no hidden retry')
        _,grounded=decode_answers(library['operations'],batch,units,result['content'])
        answers.update({a['id']:a for a in grounded})
    encoded=encode_source_observations(source_id,source_text=source_text,units=units,
        source_output=source_output,operations=library['operations'],queries=queries,
        answers=[answers[q['id']] for q in queries],scope=scope)
    encoded['execution']={'events':events,'reused_query_ids':reused,
        'planned_queries':len(queries),'new_logical_queries':len(pending),
        'new_physical_requests':sum(not e['result'].get('cache_hit',False) for e in events),
        'no_unchanged_unknown_retried':True}
    return encoded


def fit(library,observations,*,timeout_seconds=30):
    """Supervision is attached to context constraints, never observation facts."""
    result=fit_composition(library['language'],[o['context'] for o in observations],
                           timeout_seconds=timeout_seconds)
    updated=deepcopy(library)
    updated['selected_rule_ids']=result['selected_rule_ids']
    updated['fit']={'result':result,'training_context_sha256':[digest(o['context']) for o in observations],
        'new_model_requests':0}
    return updated,result


def execute(library,observation,*,timeout_seconds=30):
    if library['selected_rule_ids'] is None:raise ValueError('No successfully learned G to execute')
    result=execute_composition(library['language'],library['selected_rule_ids'],
                               observation['context'],timeout_seconds=timeout_seconds)
    output=render_composition(library['language'],library['renderers'],observation,result,library['spec'])
    return {'composition':result,'source_output':output,'library_sha256':digest(library),
        'observation_sha256':observation['visible_inputs_sha256'],'new_model_requests':0}
