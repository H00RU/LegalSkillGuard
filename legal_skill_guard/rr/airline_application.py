"""Apply actually learned Airline rules without regenerating their definitions.

Only byte-identical statutes and rule contexts may use this path. Prior facts,
case calculations and query are discarded. Untranslated source stays unknown.
"""
from copy import deepcopy
import json
import re

from .compiler_templates import validate_template
from .coverage import Unsupported,digest
from .pal_frontend import parse_pal,render_pal,pal_runtime_contract
from .scoped_program import expression_reads
from .source_program import compile_source,source_theory
from .source_structure import inspect_source
from .strict_contract import obj
from .wire_validation import validate_wire

FIELDS=('bindings','observations','rule_residuals','nodes','scopes','clauses')


def _units(structure,role):
    return [(c.id,c.context,structure.ledger.text[c.start:c.end]) for c in structure.ledger.clauses if structure.roles[c.id]['role']==role]


def _flight(structure):
    found=[]
    for sid,_,text in _units(structure,'fact'):
        match=re.match(r'^([^\n]+?) is (?:a|an) .+? passenger flying\b',text)
        if match:found.append((sid,match[1]))
    return found[0] if len(found)==1 else None


def matching_application(source,library):
    if source['dataset']!='RuleArena_Airline':return None
    current=inspect_source(source);flight=_flight(current)
    if not flight:return None
    item_sources=[sid for sid,_,text in _units(current,'fact') if re.match(r'^[0-9]+\.\s+',text)]
    if not item_sources:return None
    for item in (library or {}).get('compiler_templates',[]):
        if item['source']['key']==source['key']:raise ValueError('A compiler template cannot provide its own current application')
        if (item['language']!='source_annotated_python_v1' or item['source']['dataset']!=source['dataset'] or
                item['source']['public']['rules']!=source['public']['rules']):continue
        previous=validate_template(item);old=previous['program'];prior=previous['structure'];old_flight=_flight(prior)
        if not old_flight or _units(prior,'rule')!=_units(current,'rule'):continue
        fact_bindings={b['name'] for b in old['bindings'] if any(prior.roles[s]['role']=='fact' for s in b['sources'])}
        local_names={n['name'] for n in old['nodes']}
        definitions={n['name']:expression_reads(n['body']) for n in old['nodes'] if n['kind']=='expression'}
        definitions.update({s['name']:expression_reads(s['condition']) for s in old['scopes']})
        definitions.update({c['name']:expression_reads(c['value'])|expression_reads(c['otherwise']) for c in old['clauses']})
        def reads(name):
            result=set();pending=list(definitions[name])
            while pending:
                value=pending.pop()
                if value in result:continue
                result.add(value);pending.extend(definitions.get(value,()))
            return result
        if any(reads(s['name'])&(fact_bindings|local_names) for s in old['scopes']):continue
        case_clauses=[c for c in old['clauses'] if reads(c['name'])&(fact_bindings|local_names)]
        removed={c['name'] for c in case_clauses}
        base=deepcopy(old);base.pop('query');base['nodes']=[]
        base['bindings']=[b for b in base['bindings'] if b['name'] not in fact_bindings]
        base['clauses']=[c for c in base['clauses'] if c['name'] not in removed]
        groups={};valid=True
        for observation in base['observations']:
            original=(observation['entity_source'],observation['entity'])
            if original==old_flight:
                observation['entity_source'],observation['entity']=flight
            else:
                if original[0] not in {sid for sid,_,text in _units(prior,'fact') if re.match(r'^[0-9]+\.\s+',text)}:
                    valid=False;break
                groups.setdefault(original,[]).append(observation['name'])
        if not valid:continue
        witnesses=[{'parameter':'w'+str(i),'old_source':key[0],'old_entity':key[1],'observations':names}
            for i,(key,names) in enumerate(groups.items())]
        example={field:deepcopy(old[field]) for field in FIELDS}
        example.update(bindings=[b for b in example['bindings'] if b['name'] in fact_bindings],
            observations=[],rule_residuals=[],scopes=[],clauses=deepcopy(case_clauses),query=deepcopy(old['query']))
        unknown={r.source for r in source_theory(previous).residuals if r.unknown_scope}
        unknown.update(s for c in case_clauses for s in c['sources'])
        return {'kind':'airline_case_program','template':item,'program':base,'case_clauses':case_clauses,
            'case_example':example,'witnesses':witnesses,'item_sources':item_sources,
            'untranslated_units':sorted(unknown),'flight':flight,'old_flight':old_flight,
            'patterns':(library or {}).get('patterns',[])}
    return None


def application_request(source,match,*,feedback=None):
    properties={w['parameter']:obj({'entity_source':{'type':'string','enum':match['item_sources']},
        'entity':{'type':'string','minLength':1}}) for w in match['witnesses']}
    schema=obj({'witness_bindings':obj(properties),'code':{'type':'string','minLength':1}})
    structure=inspect_source(source);wanted=set(match['untranslated_units'])
    facts=[{'id':sid,'text':text} for sid,_,text in _units(structure,'fact')]
    missing=[{'id':sid,'text':text,'context':list(context)} for sid,context,text in _units(structure,'rule') if sid in wanted]
    system=('The CURRENT statutes are byte-identical to an actual earlier TRAIN learned rule library. '
        'Do not regenerate the known rule functions: the runtime reuses them with their real source scopes. '
        'Return witness_bindings and a compact Python code string containing ONLY fresh CURRENT factual inputs, '
        'case calculations, any selected missing rule/scope translations, and query = the native total-cost expression. '
        'Call the listed learned rule outputs as NAME() or read NAME. Their definitions, source ownership and scopes are immutable. '
        'No previous fact value, case calculation or query is reused. The earlier case application is a real syntax example, never the current answer. '
        'Bind each witness parameter to one exact CURRENT item quote and its factual source ID; predicates in the same parameter retain their shared item. '
        'The passenger name is already rebound from the explicit CURRENT passenger statement, without assigning geographic truth. '
        'Factual constants use variable = literal # sN. New rule functions use @rule("sN", otherwise=EXPLICIT) and one return expression. '
        'Use actual current dimensions, weights and checked-bag positions; do not copy earlier bag categories, fares or counts. '
        'Factor long sums into named local helpers; expressions and graphs have at most16 nested operations. '
        'Every unowned source unit and proper legal residual stays unknown until actually translated. '
        'Do not mark operative headings or thresholds True, guess factual truth, or return a native answer literal. '
        'The source/type/literal/guard/resource/completion checks are unchanged. No imports, loops, tools or arbitrary calls.')
    payload={'learned_template_hash':match['template']['template_hash'],
        'known_rule_library_code':render_pal(match['program'],include_query=False),
        'witness_parameters':match['witnesses'],
        'earlier_TRAIN_case_application':{'source':match['template']['source']['key'],
            'public_facts':match['template']['source']['public']['prompt'],
            'code':render_pal(match['case_example'])},
        'CURRENT':{'facts':facts,'untranslated_source_units':missing,
            'case_dependent_rules_to_translate':[{k:c[k] for k in ('name','sources')} for c in match['case_clauses']],
            'native_task':'include the current ticket price and all applicable baggage costs; return the exact integer total'},
        'runtime_contract':pal_runtime_contract(source,{'patterns':match['patterns']}),
        'source_only_feedback':feedback}
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],schema


def instantiate_application(source,match,value,*,library=None):
    _,schema=application_request(source,match);validate_wire(value,schema)
    program=deepcopy(match['program']);structure=inspect_source(source)
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    by_name={o['name']:o for o in program['observations']}
    for parameter in match['witnesses']:
        witness=value['witness_bindings'][parameter['parameter']]
        if witness['entity'] not in units[witness['entity_source']]:raise Unsupported('A current witness needs its verbatim factual quote')
        for name in parameter['observations']:by_name[name].update(witness)
    functions=[r['name'] for field in ('scopes','clauses') for r in program[field]]
    fragment=parse_pal(value['code'],external_functions=functions)
    old_names={r['name'] for field in FIELDS for r in program[field]}
    if any(row['name'] in old_names for field in FIELDS for row in fragment[field]):
        raise Unsupported('A case application cannot overwrite learned rules, scopes or primitive meanings')
    for field in FIELDS:program[field].extend(fragment[field])
    program['query']=fragment['query']
    compiled=compile_source(source,program,library=library)
    audit={'template_hash':match['template']['template_hash'],'training_source':match['template']['source']['key'],
        'current_source':source['key'],'kind':'fresh_case_program_over_learned_unchanged_rules',
        'reused_rule_outputs':[c['name'] for c in match['program']['clauses']],
        'prior_case_rule_sources_removed':[c['sources'] for c in match['case_clauses']],
        'prior_facts_case_helpers_and_query_reused':False,'current_application_code_hash':digest(value['code']),
        'passenger_rebound_from_exact_public_role':{'previous':match['old_flight'],'current':match['flight']},
        'current_witness_bindings':value['witness_bindings'],'unknown_source_units_before_current_application':match['untranslated_units'],
        'missing_rules_or_factual_truth_filled':False,'current_executor_authored_full_statute':False}
    return program,compiled,audit
