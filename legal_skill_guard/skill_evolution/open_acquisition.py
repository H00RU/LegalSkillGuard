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
from .semantic_execution import operation_groups
from .unit_evidence import answer_schema, decode_answers, context_batches, TRANSPORT
from .semantic_operations import prepare_queries, validate_operations
from .source_composition import render_composition, validate_renderers
from .scoped_grammar import constructors
from .source_effect_update import function_update
from .source_observations import encode_source_observations, signatures
from .joint_library_updates import library_candidates


def compile_update(previous, proposal, training_texts, *, semantic_update=None):
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
    spec=deepcopy(previous['spec'])
    if semantic_update is not None:
        # The preserved59-constructor seed is a starting asset, not a permanent
        # output-language ceiling. The teacher supplies actual new meanings and
        # their pure consumer code; the original benchmark scorer stays fixed.
        spec['constructors'].extend(deepcopy(semantic_update['constructors']))
        spec['decision_program']=function_update(spec['decision_program'],semantic_update['decision_functions'])
        constructors(spec)
    library={
        'operations':deepcopy(proposal['operations']),'planner_program':planner,
        'language':language,'renderers':deepcopy(proposal['renderers']),
        'scope':proposal['scope'],'spec':spec,
        'selected_rule_ids':None,
        'update':{'previous_library_sha256':digest(previous),'proposal_sha256':digest(proposal),
            'changed_operation_names':changed,'rationale':proposal['rationale'],
            'removed_operation_names':removed,
            'semantic_update_sha256':digest(semantic_update) if semantic_update is not None else None,
            'new_model_requests_during_compilation':0,
            'current_source_or_generalization_certified':False}}
    return library


def _read_identity(operations,query,units,scope):
    by_op={o['name']:o for o in operations};by_unit={u['id']:u for u in units}
    return digest({'operation':by_op[query['operation']],'window':query['unit_ids'],
        'units':[by_unit[i] for i in query['unit_ids']],'scope':scope})


def update_candidates(library, bundles, observation, training_texts, *, use_updates=True):
    """Construct actual φ/G edits before normal observe→fit→execute.

    The -U arm supplies the same observations/history and disables this call's
    learned candidate construction and prior. Ordinary teacher proposals remain
    available to both arms. A returned candidate has no new semantic certificate
    and must pass the normal current-source reads and composition learning.
    """
    return library_candidates(library,bundles,observation,training_texts,enabled=use_updates)


def observe(client,prefix,source_id,library,*,source_text,units,source_output,
            previous_observation=None,previous_observations=(),save_event=None):
    """Run actual new concepts; reuse only identical current-source observations.

    Previously answered unknown is terminal for an unchanged operation/window.
    A changed meaning/planner window is a new query with a recorded identity.
    The caller separately supplies the preserved actual upstream source output.
    """
    from .runtime import decoder_schema
    scope=library['scope'];reusable={};operation_scopes=library.get('operation_scopes')
    if operation_scopes is not None:
        if set(operation_scopes)!={o['name'] for o in library['operations']} or any(v not in ('focus_last','window') for v in operation_scopes.values()):
            raise ValueError('Every acquired operation needs its explicit actual reading scope')
    def current_scope(query):
        return operation_scopes[query['operation']] if operation_scopes is not None else scope
    histories=([previous_observation] if previous_observation is not None else [])+list(previous_observations)
    for historical in histories:
        previous=historical['visible_inputs']
        if previous['source_text']!=source_text or previous['units']!=units:
            raise ValueError('Cannot reuse readings from different current material')
        by_id={a['id']:a for a in previous['answers']}
        for q in previous['queries']:
            if q['id'] in by_id:
                actual_scope=previous.get('query_scopes',{}).get(q['id'],previous['scope'])
                identity=_read_identity(previous['operations'],q,units,actual_scope)
                value=by_id[q['id']]
                if identity in reusable and any(reusable[identity][k]!=value[k] for k in ('choice','evidence')):
                    raise ValueError('Conflicting actual prior readings require explicit diagnosis, not label-based selection')
                reusable.setdefault(identity,value)
    answers={};reused=[];events=[];queries=[];by_id={};by_content={};rounds=[];new_logical=0;batch_checks=[]
    while True:
        # A learned semantic scout may locate operative clauses first, then
        # request their roles/qualifiers using actual returned judgments. The
        # host supplies no legal routing or classifier outcomes.
        plan=prepare_queries(library['planner_program'],library['operations'],source_text,units,
            answers=[answers[q['id']] for q in queries],source_output=source_output)
        pending=[];added=[]
        for q in plan:
            key=_read_identity(library['operations'],q,units,current_scope(q))
            if q['id'] in by_id:
                if q!=by_id[q['id']]:raise ValueError('A frozen planner changed the meaning/window of an issued query ID')
                continue
            if key in by_content:
                raise ValueError('Query ID churn would repeat an already issued source question')
            by_id[q['id']]=q;by_content[key]=q['id'];queries.append(q);added.append(q['id'])
            if key in reusable:
                answers[q['id']]={**deepcopy(reusable[key]),'id':q['id']};reused.append(q['id'])
            else:pending.append(q)
        if not added:break
        rounds.append(added);new_logical+=len(pending)
        prepared=[]
        for group in operation_groups(pending):
            batch_scope=current_scope(group[0])
            if any(current_scope(q)!=batch_scope for q in group):raise ValueError('Mixed actual query scopes in one operation batch')
            prepared.extend((batch,prompt,check,batch_scope) for batch,prompt,check in context_batches(
                client,library['operations'],group,units,scope=batch_scope,checks=batch_checks))
        for batch,prompt,check,batch_scope in prepared:
            wire,_=decoder_schema(answer_schema(library['operations'],batch))
            call_id=prefix+':concept:'+digest(prompt)
            result=client.generate(call_id,source=source_id,purpose='skill_replay',
                messages=prompt,thinking=False,schema=wire)
            event={'call_id':call_id,'query_ids':[q['id'] for q in batch],'result':result,
                'scope':batch_scope,'library_sha256':digest(library),'evidence_transport':TRANSPORT,
                'context_preflight':check}
            # Preserve even truncated/type-invalid responses before raising.
            if save_event:save_event(event)
            events.append(event)
            if result['finish_reason']!='stop':raise ValueError('Incomplete concept read; no hidden retry')
            _,grounded=decode_answers(library['operations'],batch,units,result['content'],scope=batch_scope,
                complete_source_absence_choices=library.get('complete_source_absence_choices'))
            answers.update({a['id']:a for a in grounded})
    encoded=encode_source_observations(source_id,source_text=source_text,units=units,
        source_output=source_output,operations=library['operations'],queries=queries,
        answers=[answers[q['id']] for q in queries],scope=scope,
        query_scopes={q['id']:current_scope(q) for q in queries},
        complete_source_absence_choices=library.get('complete_source_absence_choices'))
    encoded['execution']={'events':events,'reused_query_ids':reused,
        'reuse_history_inputs_sha256':[digest(o['visible_inputs']) for o in histories],
        'planned_queries':len(queries),'new_logical_queries':new_logical,'planning_rounds':rounds,
        'context_batch_checks':batch_checks,
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
