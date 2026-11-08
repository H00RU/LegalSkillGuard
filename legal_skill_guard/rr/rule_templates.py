"""Instantiate a learned program only for byte-identical supplied statutes.

This reuses code, never a previous answer or factual observation. The executor
supplies the new case's entity binding and executable native query. All facts
start unknown, and the normal completion/refinement checks still apply.
"""
from copy import deepcopy
import json
import re

from .compiler_templates import validate_template
from .coverage import Unsupported,digest
from .source_program import compile_source
from .source_structure import inspect_source,explicit_query_target
from .scoped_program import expression_reads
from .strict_contract import obj
from .wire_validation import validate_wire


def matching_rule_template(source,library):
    if source['dataset']=='RuleArena_Airline':
        from .airline_application import matching_application
        return matching_application(source,library)
    if source['dataset']!='SARA_v2_Binary':return None
    current=inspect_source(source)
    def rules(structure):
        return [(c.id,c.context,structure.ledger.text[c.start:c.end]) for c in structure.ledger.clauses
            if structure.roles[c.id]['role']=='rule']
    facts=[c.id for c in current.ledger.clauses if current.roles[c.id]['role']=='fact']
    if len(facts)!=1:return None
    for item in (library or {}).get('compiler_templates',[]):
        if item['source']['key']==source['key']:raise ValueError('A rule template cannot provide its own current program')
        if (item['language']!='source_annotated_python_v1' or item['source']['dataset']!=source['dataset'] or
            item['source']['public']['rules']!=source['public']['rules']):continue
        previous=validate_template(item);program=previous['program']
        # This actual path handles the learned Boolean statute program. A
        # source-specific numeric/witness binding requires fresh compilation.
        if program['bindings'] or any(c['otherwise'] is not False for c in program['clauses']) or rules(previous['structure'])!=rules(current):continue
        oldfacts={o['entity_source'] for o in program['observations']}
        if len(oldfacts)!=1:continue
        return {'template':item,'program':deepcopy(program),'fact_source':facts[0],
            'entities':sorted({o['entity'] for o in program['observations']})}
    return None


def target_clauses(source,program):
    target=explicit_query_target(source)
    if not target:return []
    structure=inspect_source(source);wanted=set(target['unit_ids'])
    return [c for c in program['clauses'] if wanted&structure.ledger.closure(set(c['sources']))]


def instance_request(source,match,*,feedback=None):
    if match.get('kind')=='airline_case_program':
        from .airline_application import application_request
        return application_request(source,match,feedback=feedback)
    program=match['program'];entities=match['entities'];structure=inspect_source(source)
    role_hints={}
    for employer in entities:
        for employee in entities:
            if employer!=employee and re.search(r'\b'+re.escape(employer)+r'\s+(?:has\s+)?employed\s+'+re.escape(employee)+r'\b',match['template']['source']['public']['facts']):
                role_hints[employer]='employer/payer';role_hints[employee]='employee performing the services'
    role_predicates={entity:role_hints.get(entity,[o['predicate'] for o in program['observations'] if o['entity']==entity]) for entity in entities}
    choices=target_clauses(source,program)
    if not choices:raise Unsupported('The learned program has no source-linked output for this requested section')
    # Lexical mentions only; no inferred participant, date, law or truth value.
    dates=[m.span() for m in re.finditer(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+[0-9]',source['public']['facts'])]
    mentions=sorted({m[0] for m in re.finditer(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',source['public']['facts'])
        if not any(start<=m.start()<end for start,end in dates)})
    if not mentions:raise Unsupported('No explicit current entity mentions for this learned-template instance')
    schema=obj({'entity_bindings':obj({name:{'type':'string','enum':mentions} for name in entities}),
        'rule_outputs':{'type':'array','items':{'type':'string','enum':[c['name'] for c in choices]},'minItems':1,'maxItems':len(choices)},
        'combine':{'type':'string','enum':['any','all']},'negated':{'type':'boolean'}})
    system=('The exact CURRENT statutes already have a learned, checked source program. Do not regenerate its rules. '
        'Return entity_bindings, rule_outputs, combine and negated. Bind every old case entity to its actual CURRENT factual entity '
        'according to the listed predicate roles, never to a source ID or a guessed absent entity. '
        'No previous factual truth or answer is reused. The supplied rule outputs compute their current values later. '
        'Choose the named guarded rule outputs for the requested section. Use combine=any for alternatives, all for conjunction. '
        'For an ordinary positive applies claim set negated=false; set true only when the CURRENT question negates that claim. '
        'The compiler builds the native query from these choices. Do not output code, predicate text in an entity field, '
        'factual truth values or a native answer.')
    payload={'learned_template_hash':match['template']['template_hash'],
        'same_statute_bytes_and_rule_contexts':True,'training_parameter_roles':role_predicates,'CURRENT_entity_mentions':mentions,
        'available_requested_rule_outputs':[{'name':c['name'],'sources':c['sources'],'expression':c['value']} for c in choices],
        'CURRENT_facts':source['public']['facts'],'CURRENT_query':source['public']['query'],
        'CURRENT_target':explicit_query_target(source),'source_only_feedback':feedback}
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],schema


def instantiate_rule_template(source,match,value,*,library=None):
    if match.get('kind')=='airline_case_program':
        from .airline_application import instantiate_application
        return instantiate_application(source,match,value,library=library)
    _,schema=instance_request(source,match);validate_wire(value,schema)
    program=deepcopy(match['program']);structure=inspect_source(source)
    facts=next(structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses if c.id==match['fact_source'])
    for original,current in value['entity_bindings'].items():
        if not current or current not in facts:raise Unsupported('A bound entity needs its exact current fact quote')
    for observation in program['observations']:
        observation['entity']=value['entity_bindings'][observation['entity']]
        observation['entity_source']=match['fact_source']
    if len(value['rule_outputs'])!=len(set(value['rule_outputs'])):raise Unsupported('Rule output selection is a set, not repeated filler')
    terms=[{'var':name} for name in value['rule_outputs']]
    condition=terms[0] if len(terms)==1 else {'op':'or' if value['combine']=='any' else 'and','args':terms}
    if value['negated']:condition={'op':'not','args':[condition]}
    program['query']={'op':'if','args':[condition,'Entailment','Contradiction']}
    choices={c['name'] for c in target_clauses(source,program)}
    reads=expression_reads(program['query'])
    if not reads or not reads<=choices:raise Unsupported('The current query must read only the requested guarded rule outputs')
    compiled=compile_source(source,program,library=library)
    audit={'template_hash':match['template']['template_hash'],'training_source':match['template']['source']['key'],
        'current_source':source['key'],'statute_hash':digest(source['public']['rules']),
        'entity_bindings':value['entity_bindings'],'current_query_selection':{k:value[k] for k in ('rule_outputs','combine','negated')},
        'all_rule_expressions_and_scope_definitions_reused_unchanged':True,
        'old_factual_values_or_answer_reused':False,'current_executor_authored_full_statute':False}
    return program,compiled,audit
