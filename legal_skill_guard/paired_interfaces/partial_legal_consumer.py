"""Completion-invariant execution of the pinned MAUD covenant consumer.

The frozen program is unchanged. Its covenant query is existential: an
explicit COVID exception attached to the requested covenant entails Yes in
every complete graph extension retaining that witness. Unknown fields are
neither filled nor removed. Other partial queries remain unsupported.

This certifies the fixed program's result under a declared graph-extension
semantics, not the source truth, a correct benchmark label or legal advice.
"""
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.legal_consumers import maud as frozen_maud
from legal_skill_guard.skill_evolution.objects import digest

BASE_SHA256='24067f4a282dfe7c5b040c85bbfa19c8f109eb31d4a2ea2a354a5bf8978aebc2'
PROTOCOL='fixed-MAUD-completion-invariant-execution-v1'
COVID=frozenset(('pandemic','epidemic','covid_19'))


def base_binding():
    path=Path(__file__).with_name('legal_consumers.py')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=BASE_SHA256:
        raise ValueError('The completion proof binds a different frozen MAUD source')
    return BASE_SHA256


def shape_valid(graph):
    if (not isinstance(graph,dict) or type(graph.get('scope_complete')) is not bool
            or not isinstance(graph.get('unresolved'),list)
            or not isinstance(graph.get('nodes'),list) or not isinstance(graph.get('relations'),list)):
        return False
    nodes=graph['nodes'];ids=[n.get('id') for n in nodes if isinstance(n,dict)]
    if len(ids)!=len(nodes) or any(not isinstance(n,str) or not n for n in ids) or len(ids)!=len(set(ids)):
        return False
    if any(not isinstance(n.get('kind'),str) or not isinstance(n.get('concept'),str) for n in nodes):return False
    for edge in graph['relations']:
        if (not isinstance(edge,dict) or not isinstance(edge.get('predicate'),str)
                or not isinstance(edge.get('arguments'),list)
                or any(not isinstance(a,str) or a not in ids for a in edge['arguments'])
                or edge.get('status') not in ('stated','negated','not_stated','unknown','unread')):
            return False
    return True


def contradictory_known_facts(graph):
    states={}
    for edge in graph['relations']:
        key=(edge['predicate'],tuple(edge['arguments']),json.dumps(edge.get('value'),sort_keys=True))
        states.setdefault(key,set()).add(edge['status'])
    return any({'stated','negated'}<=values for values in states.values())


def maud(graph,task):
    """Preserve every defined base result; extend only a proved positive case."""
    binding=base_binding()
    if not shape_valid(graph):
        return {'handled':False,'answer':None,'reason':'Malformed graph cannot justify completion-invariant execution'}
    original=frozen_maud(graph,task)
    if original['handled']:
        return {**original,'partial_F_execution':{'protocol':PROTOCOL,'base_sha256':binding,
            'path':'unchanged_defined_base','unknown_fields_or_scope_changed':False}}
    wanted=('ordinary_course_covenant' if task.startswith('Ordinary Course Covenant') else
            'negative_interim_covenant' if task.startswith('Negative Interim Covenant') else None)
    if wanted is None or contradictory_known_facts(graph):
        return {**original,'partial_F_execution':{'protocol':PROTOCOL,'base_sha256':binding,
            'path':'no_supported_completion_certificate','unknown_fields_or_scope_changed':False}}
    nodes={n['id']:n for n in graph['nodes']}
    witnesses=[]
    for i,edge in enumerate(graph['relations']):
        args=edge['arguments']
        if edge['predicate']!='exception_for' or edge['status']!='stated' or len(args)<2 or edge.get('value') is False:
            continue
        exception=nodes[args[0]]
        if exception['kind']!='exception' or exception['concept'] not in COVID:continue
        for target in args[1:]:
            if nodes[target]['concept']!=wanted:continue
            # A witness with an explicitly uncertain competing spelling is
            # conservatively refused, rather than resolving that uncertainty.
            competing=any(e['predicate']=='exception_for' and e['status']!='stated'
                and e['arguments'] and e['arguments'][0]==args[0] and target in e['arguments'][1:]
                for e in graph['relations'])
            if not competing:witnesses.append((args[0],target,i))
    if not witnesses:
        return {**original,'partial_F_execution':{'protocol':PROTOCOL,'base_sha256':binding,
            'path':'no_supported_completion_certificate','unknown_fields_or_scope_changed':False}}
    exception,target,index=min(witnesses)
    return {'handled':True,'answer':'Yes','used_nodes':[exception],
        'partial_F_execution':{'protocol':PROTOCOL,'base_sha256':binding,
            'path':'completion_invariant_positive_witness','input_graph_sha256':digest(graph),
            'witness_exception':exception,'witness_covenant':target,'witness_relation_index':index,
            'completion_class':'all well-formed complete extensions preserving known node tags and stated relations',
            'known_fact_consistency_checked':True,'unknown_fields_or_scope_changed':False,
            'native_answer_label_or_reference_used':False,'factual_or_benchmark_truth_certified':False,
            'shared_execution_improvement_not_learned_interface_evidence':True}}
