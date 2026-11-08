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
from .source_program import compile_source,source_theory,source_unit_schema
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


def literal_case_bindings(structure):
    """Read explicit literal fields in the original Airline input format.

    Dimension positions use the actual earlier teacher's input convention,
    checked exactly before reuse. No fee, rule, geography or truth is inferred.
    """
    bindings=[];names=set();traveler=None;ticket_owner=None
    def add(name,value,sid):
        if name in names:raise Unsupported('Duplicate original case literal field '+name)
        names.add(name);bindings.append({'name':name,'sources':[sid],
            'type':'integer' if type(value) is int else 'scalar','value':value})
    for sid,_,text in _units(structure,'fact'):
        profile=re.fullmatch(r'(.+?) is (?:a|an) (.+?) Class passenger flying from (.+?) to (.+?) with the following items:',text)
        item=re.fullmatch(r'([0-9]+)\. .+?: ([0-9]+) x ([0-9]+) x ([0-9]+) inches, ([0-9]+) lbs;',text)
        ticket=re.fullmatch(r"(.+?)'s flight ticket is \$([0-9]+)\.",text)
        if profile:
            traveler=profile[1]
            for name,value in zip(('traveler','cabin','origin','destination'),profile.groups()):add(name,value,sid)
        elif item:
            for name,value in zip(('length','width','height','weight'),item.groups()[1:]):add('bag'+item[1]+'_'+name,int(value),sid)
        elif ticket:ticket_owner=ticket[1];add('ticket_price',int(ticket[2]),sid)
        else:raise Unsupported('Unrecognized original Airline literal source '+sid)
    if traveler is None or ticket_owner!=traveler:raise Unsupported('Current passenger and explicit ticket owner must agree')
    return bindings


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
        groups={};valid=True;retained=[];item_observations=[]
        for observation in base['observations']:
            original=(observation['entity_source'],observation['entity'])
            if original==old_flight:
                observation['entity_source'],observation['entity']=flight
                retained.append(observation)
            else:
                if original[0] not in {sid for sid,_,text in _units(prior,'fact') if re.match(r'^[0-9]+\.\s+',text)}:
                    valid=False;break
                groups.setdefault(original,[]).append(observation['name'])
                item_observations.append(observation)
        if not valid:continue
        if len(groups)!=1:continue
        base['observations']=retained
        previous_inputs=literal_case_bindings(prior)
        if {b['name']:b for b in previous_inputs}!={b['name']:b for b in old['bindings'] if b['name'] in fact_bindings}:continue
        base['bindings'].extend(literal_case_bindings(current))
        example={field:deepcopy(old[field]) for field in FIELDS}
        example.update(bindings=[],observations=[],rule_residuals=[],scopes=[],clauses=deepcopy(case_clauses),query=deepcopy(old['query']))
        unknown={r.source for r in source_theory(previous).residuals if r.unknown_scope}
        unknown.update(s for c in case_clauses for s in c['sources'])
        return {'kind':'airline_case_program','template':item,'program':base,'case_clauses':case_clauses,
            'case_example':example,'item_observations':item_observations,'item_sources':item_sources,
            'previous_input_bindings':previous_inputs,
            'untranslated_units':sorted(unknown),'flight':flight,'old_flight':old_flight,
            'patterns':(library or {}).get('patterns',[])}
    return None


def application_schema(match):
    # The pinned nested-enum grammar admits forbidden near-prefix IDs. The
    # existing finite-ID trie denotes the identical whitelist exactly.
    return obj({'current_item_source':source_unit_schema(match['item_sources']),
        'program_lines':{'type':'array','items':{'type':'string'},'minItems':1}})


def complete_case_example(match):
    """Render the actual earlier query with associative exact sums flattened."""
    example=deepcopy(match['case_example'])
    def terms(expression):
        if isinstance(expression,dict) and expression.get('op')=='add':
            return [term for arg in expression['args'] for term in terms(arg)]
        return [expression]
    if isinstance(example['query'],dict) and example['query'].get('op')=='add':
        example['query']={'op':'add','args':terms(example['query'])}
    return render_pal(example).splitlines()


def application_request(source,match,*,feedback=None):
    structure=inspect_source(source);wanted=set(match['untranslated_units'])
    facts=[{'id':sid,'text':text} for sid,_,text in _units(structure,'fact')]
    missing=[{'id':sid,'text':text,'context':list(context)} for sid,context,text in _units(structure,'rule') if sid in wanted]
    system=('The CURRENT statutes are byte-identical to an actual earlier TRAIN learned rule library. '
        'Do not regenerate the known rule functions: the runtime reuses them with their real source scopes. '
        'Return current_item_source and program_lines. Select exactly one listed CURRENT item source for the fixed item observations; '
        'their existing names, predicate meanings and shared item are instantiated by the runtime without any truth assignment. '
        'program_lines is the Python line-list representation used by PAL: one source line per string, including explicit indentation and blank lines. '
        'All listed current literal input bindings and fixed observations are already declared: read them, never redeclare or overwrite them. '
        'Generate ONLY fresh CURRENT '
        'case calculations, any selected missing rule/scope translations, and query = the native total-cost expression. '
        'Call the listed learned rule outputs as NAME() or read NAME. Their definitions, source ownership and scopes are immutable. '
        'No previous fact value, case calculation or query is reused. The earlier case application is a real syntax example, never the current answer. '
        'The passenger name is already rebound from the explicit CURRENT passenger statement, without assigning geographic truth. '
        'Factual constants use variable = literal # sN. New rule functions use @rule("sN", otherwise=EXPLICIT) and one return expression. '
        'Use actual current dimensions, weights and checked-bag positions; do not copy earlier bag categories, fares or counts. '
        'Write totals using one flat add(a, b, c, ...) call or separate named subtotals; do not nest add repeatedly. '
        'sum(NUMERIC_LIST) adds exact numeric list elements without a fixed bag count. '
        'The earlier complete query has an earlier bag count and case: write the CURRENT complete total, including its ticket and all applicable baggage costs. '
        'Expressions and graphs have at most16 nested operations. '
        'Every unowned source unit and proper legal residual stays unknown until actually translated. '
        'Do not mark operative headings or thresholds True, guess factual truth, or return a native answer literal. '
        'The source/type/literal/guard/resource/completion checks are unchanged. No imports, loops, tools or arbitrary calls.')
    payload={'learned_template_hash':match['template']['template_hash'],
        'known_rule_library_code':render_pal(match['program'],include_query=False),
        'fixed_item_observations':[{k:o[k] for k in ('name','predicate','predicate_source')} for o in match['item_observations']],
        'current_item_sources':match['item_sources'],
        'earlier_TRAIN_case_application':{'source':match['template']['source']['key'],
            'public_facts':match['template']['source']['public']['prompt'],
            'current_item_source':match['item_observations'][0]['entity_source'],
            'known_input_bindings':match['previous_input_bindings'],
            'program_lines':complete_case_example(match)},
        'CURRENT':{'facts':facts,'untranslated_source_units':missing,
            'case_dependent_rules_to_translate':[{k:c[k] for k in ('name','sources')} for c in match['case_clauses']],
            'native_task':'include the current ticket price and all applicable baggage costs; return the exact integer total'},
        'runtime_contract':pal_runtime_contract(source,{'patterns':match['patterns']}),
        'source_only_feedback':feedback}
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],application_schema(match)


def instantiate_application(source,match,value,*,library=None):
    validate_wire(value,application_schema(match))
    program=deepcopy(match['program']);structure=inspect_source(source)
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    selected=value['current_item_source']
    for original in match['item_observations']:
        current=deepcopy(original);current.update(entity_source=selected,entity=units[selected]);program['observations'].append(current)
    code='\n'.join(value['program_lines'])
    functions=[r['name'] for field in ('scopes','clauses') for r in program[field]]
    fragment=parse_pal(code,external_functions=functions)
    # Real v19 output repeated the already supplied public constants. Removing
    # only byte-equivalent typed/source-owned literals is idempotent; different
    # values, owners, types, observations and rules remain protected errors.
    inputs={row['name']:row for row in program['bindings']}
    redundant=[row for row in fragment['bindings'] if row['name'] in inputs and digest(row)==digest(inputs[row['name']])]
    redundant_names={row['name'] for row in redundant}
    fragment['bindings']=[row for row in fragment['bindings'] if row['name'] not in redundant_names]
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
        'prior_facts_case_helpers_and_query_reused':False,'current_application_code_hash':digest(code),
        'passenger_rebound_from_exact_public_role':{'previous':match['old_flight'],'current':match['flight']},
        'current_item_observations':[o for o in program['observations'] if o['name'] in {x['name'] for x in match['item_observations']}],
        'current_literals_read_verbatim_from_public_input':True,'literal_input_convention_matches_actual_earlier_teacher':True,
        'identical_current_literal_redeclarations_removed':redundant,
        'unknown_source_units_before_current_application':match['untranslated_units'],
        'missing_rules_or_factual_truth_filled':False,'current_executor_authored_full_statute':False}
    return program,compiled,audit
