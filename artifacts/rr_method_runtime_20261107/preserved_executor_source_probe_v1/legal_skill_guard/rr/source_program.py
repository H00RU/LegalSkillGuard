"""Source-linked compact translations, factual observations and method A.

The compiler supplies rule ASTs, never observation truth or a native answer.
Footprints come from those ASTs. Untranslated whole clauses retain TOP. Like
the original method, certificates are conditional on accepted NL translation
faithfulness; neither typing nor matching a TRAIN label proves that assumption.
"""
from __future__ import annotations

from dataclasses import replace
import json
import re

from .coverage import FiniteTheory,Residual,Unsupported,digest
from .grounding import expression_literal_audit
from .source_bindings import decode_source_bindings
from .scoped_program import compile_query,expression_reads
from .source_structure import inspect_source
from .strict_contract import obj,array,ref,interface_definitions
from .wire_validation import validate_wire
from .clause_scope import lower_clauses,required_scope_sources


OPERATORS=['if','not','xor','eq','ne','lt','le','sub','scale','divide_constant',
           'min','max','and','or','add','array','pair','object','concat']


def program_schema(source,library=None):
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema
    structure=inspect_source(source)
    unit={'enum':[c.id for c in structure.ledger.clauses]}
    string={'type':'string'}
    definitions=interface_definitions(unit['enum'])
    for binding in definitions['binding']['anyOf']:
        binding['properties'].pop('source')
        binding['properties']['sources']={**array(unit),'minItems':1}
    # Strict teacher objects need concrete property names. Only actually
    # available learned patterns can enter this compiler's invocation menu.
    graphs=definitions['connector']['anyOf']
    graphs[:]=[g for g in graphs if 'pattern' not in g.get('properties',{})]
    from .pattern_execution import graph_roles
    for item in (library or {}).get('patterns',[]):
        for variant,graph in enumerate(item['pattern']['graphs']):
            slots,columns=graph_roles(graph)
            graphs.append(obj({'pattern':{'enum':[item['pattern_hash']]},'variant':{'enum':[variant]},
                'slots':obj({s:string for s in sorted(slots)}),
                'columns':obj({c:string for c in sorted(columns)})}))
    definitions['expr']={'anyOf':[{'type':'integer'},{'type':'boolean'},string,
        {'type':'null'},
        obj({'var':string}),obj({'op':{'enum':OPERATORS},'args':array(ref('expr'))})]}
    definitions['node']={'anyOf':[
        obj({'name':string,'kind':{'enum':['expression']},'body':ref('expr')}),
        obj({'name':string,'kind':{'enum':['connector']},'body':obj({'graph':ref('connector'),
            'project':{'enum':['identity','amount_value','amount_values','entailment_label']}})})]}
    schema=obj({'bindings':array(ref('binding')),'observations':array(obj({
        'name':{'type':'string','pattern':'^b_[A-Za-z0-9_]+$'},'entity':string,'entity_source':unit,
        'predicate':string,'predicate_source':unit})),
        'rule_residuals':array(obj({'name':{'type':'string','pattern':'^b_[A-Za-z0-9_]+$'},
            'source':unit,'quote':string})),
        'nodes':array(ref('node')),
        'scopes':array(obj({'name':string,'source':unit,'condition':ref('expr')})),
        'clauses':array(obj({'name':string,'sources':array(unit),'value':ref('expr'),'otherwise':ref('expr')})),
        'query':ref('expr')})
    schema['$defs']=definitions
    def type_enums(node):
        if isinstance(node,dict):
            if 'enum' in node and 'type' not in node:
                values=node['enum']
                node['type']='integer' if all(type(v) is int for v in values) else 'string'
            for value in list(node.values()):type_enums(value)
        elif isinstance(node,list):
            for value in node:type_enums(value)
    type_enums(schema)
    return strict_output_schema(schema)


def compiler_prompt(source,library=None,previous_program=None):
    from .source_format import FORMAT_EXAMPLE
    structure=inspect_source(source)
    units=[{'id':c.id,**structure.roles[c.id],'text':structure.ledger.text[c.start:c.end],
            'context':list(c.context)} for c in structure.ledger.clauses]
    system=(
        'Compile the CURRENT public rule task into a compact, data-only local-definition DAG. '
        'Do not solve it or emit the native answer. No tools or grading information are available. '
        'bindings are only exact public literals/typed primitive inputs with sources:[UNIT_IDS] provenance. '
        'A relation assembled from multiple factual lines must cite all of those units; '
        'bindings use the plural sources array, never a singular source field. '
        'booleans in bindings require a literal true/false in that unit. '
        'Use observations for atomic FACTUAL predicates: entity must be an exact substring of a fact unit, '
        'predicate an exact substring of a rule unit. You do not provide their truth values. '
        'Observation and residual variable names MUST begin b_. Names carry no extra meaning: '
        'dates, years, quantifiers and comparisons must appear in the AST/typed inputs, never only in names. '
        'Reuse one observation for identical entity/predicate/source quotes; different names cannot add temporal context. '
        'Decompose legal applicability, arithmetic, thresholds, exceptions and conjunctions into nodes, '
        'never outsource the final claim, a complete legal rule or a numerical comparison to one observation. '
        'An observation can remain unknown when facts do not establish it; do not invent missing facts. '
        'For an unresolved legal/numerical SUBEXPRESSION use rule_residuals, with a Boolean b_ name, '
        'the rule source unit and an exact quote. It denotes both possible truth values and will NEVER '
        'be sent to the factual observer for resolution. A residual must be a proper, quoted subexpression '
        'inside an explicit clause value or source scope condition that reads it. This allows an external '
        'section reference or missing numeric comparison to remain unresolved without guessing its rule. '
        'Do not replace an entire untranslated clause or the final claim with one Boolean placeholder. '
        'nodes are local calculations with name/kind/body ONLY; they never discharge source coverage. '
        'Use scopes={name,source,condition} for each applicable source context or structural heading. '
        'A scope owns exactly ONE public rule unit; its condition must be executable Boolean IR, '
        'never a string quoting the policy. Only a structural, nonconditional title may use literal true. '
        'A scope with unknown legal applicability may read a quoted Boolean rule_residual. '
        'Use clauses={name,sources,value,otherwise} for actual translated rule outputs. '
        'sources owns the actual rule units translated by this clause, not every heading it cites. '
        'The engine derives inherited scopes from the supplied source context and physically executes '
        'each clause as if(all inherited scopes, value, otherwise). You cannot omit an inherited guard. '
        'Choose an explicit disabled value (false,0,empty array,or null as appropriate); no value is guessed. '
        'All explicit conditional prefaces listed in required_scope_sources must be scopes, not quoted metadata. '
        'Unused scope declarations and local calculations do not cover source units. '
        'Translate other supplied rules into clauses/scopes even when not selected by this query; '
        'leave genuinely untranslated units unowned so they remain unknown-scope residuals. '
        'Do not mark a whole unparsed rule covered by citing a numeric constant or an unrelated node. '
        'For expressions use {var:NAME} or {op:OP,args:[...]}; if=[Boolean,then,else]. '
        'add/sub/min/max/lt/le use exact numbers, scale=[literal multiplier,numeric], '
        'divide_constant=[numeric,nonzero literal denominator]. and/or/not use Booleans. '
        'array creates arrays; object takes pair operations, each pair=[string key,value expression]. '
        'The root query combines guarded CLAUSE outputs and public inputs into the native result; '
        'it must not read local helper or scope names directly to bypass their enclosing clauses. '
        'Use named definitions to avoid duplicating ASTs. Do not return a constant native result. '
        'Connector nodes use the seven supplied typed operators or explicit available learned calls. '
        'When a supplied learned graph matches the actual role and column obligations, invoke its '
        'pattern hash/variant with complete slots/columns bindings; copying its operators independently '
        'is not library use. Never add an irrelevant call just to report reuse. '
        'All consumption of one allowance bank belongs in one threaded graph; never clone it. '
        'No other functions or hidden execution are available. All branches must type check. '
        'For SARA use Entailment/Contradiction; ProofWriter uses True/False/Unknown; '
        'Airline returns the full numeric cost; OpenExempt returns EC/EV with verbatim supplied citations; '
        'ContractNLI uses Entailment/Contradiction/NotMentioned. Source identifiers are metadata, not operands. '
        'Do not invent laws, entity witnesses, dates or constants. '
        'A quoted determination-time policy is not an executable temporal comparison. '
        'Use actual date/year operations when supported, and keep unsupported subexpressions residual. '
        'If previous_candidate is supplied, preserve its valid factual primitive names and quotes where '
        'their meaning is unchanged. Rewrite its incomplete rule/scoping representation into this contract; '
        'the previous candidate is not a trusted source or a grading answer. '
        'format_only_example is an invented, unrelated task illustrating the complete syntax; '
        'its rules, source IDs, numbers and labels must not be copied into the CURRENT task.')
    return system,json.dumps({'dataset':source['dataset'],'source':source['key'],
        'public_task':source['public'],'units':units,'required_scope_sources':required_scope_sources(structure),
        'previous_candidate':previous_program,
        'format_only_example':FORMAT_EXAMPLE,
        'available_learned_patterns':(library or {}).get('patterns',[])},ensure_ascii=False)


def compile_source(source,program,*,library=None):
    validate_wire(program,program_schema(source,library))
    structure=inspect_source(source);ledger=structure.ledger
    units={c.id:ledger.text[c.start:c.end] for c in ledger.clauses}
    slots,binding_sources,binding_checks=decode_source_bindings(program['bindings'],units)
    specs={};by_fact={};holes={};by_rule={};observation_signatures=set()
    for observation in program['observations']:
        name=observation['name'];fs=observation['entity_source'];rs=observation['predicate_source']
        if name in slots or name in specs or not re.fullmatch(r'b_[A-Za-z0-9_]+',name):
            raise Unsupported('Factual observations need unique b_ names')
        if structure.roles[fs]['role']!='fact' or structure.roles[rs]['role']!='rule':
            raise Unsupported('Observations require a factual entity and a rule predicate, never a query label')
        for field,key in [('entity',fs),('predicate',rs)]:
            if not observation[field] or observation[field] not in units[key]:
                raise Unsupported('Observation '+field+' is not an exact source quote')
        signature=(fs,rs,observation['entity'],observation['predicate'])
        if signature in observation_signatures:
            raise Unsupported('Duplicate observation quotes cannot gain time or legal context from variable names')
        observation_signatures.add(signature)
        if re.search(r'\d|§|\b(?:shall|applies|applicable|entailment|contradiction|entitled|refer|subsection|section|half|more than|over|less than)\b',observation['predicate'],re.I):
            raise Unsupported('Compile legal effects and numerical comparisons into rule ASTs')
        specs[name]=observation;by_fact.setdefault(fs,[]).append(name)
    domains={name:(False,True) for name in specs}
    for hole in program['rule_residuals']:
        name=hole['name'];unit=hole['source'];quote=hole['quote']
        if name in slots or name in specs or name in holes or structure.roles[unit]['role']!='rule':
            raise Unsupported('Rule residuals need unique names and actual rule provenance')
        if not quote or quote not in units[unit] or quote.strip()==units[unit].strip():
            raise Unsupported('A rule residual must quote a proper subexpression, not a whole untranslated clause')
        holes[name]=hole;by_rule.setdefault(unit,[]).append(name);domains[name]=(False,True)
    lowered=lower_clauses(structure,program)
    nodes=lowered['nodes']
    query=compile_query(nodes,program['query'],slots,domains=domains,library=library,
                        boolean_nodes=lowered['scope_names'])
    by_name={n['name']:n for n in query.nodes}
    def reads_from(name):
        pending=[name];result=set()
        while pending:
            key=pending.pop()
            if key in result:continue
            result.add(key)
            if key in by_name:pending.extend(query.node_reads(by_name[key]))
        return result
    for name,hole in holes.items():
        owners=[s['name'] for s in program['scopes'] if s['source']==hole['source']]+\
            [c['name'] for c in program['clauses'] if hole['source'] in c['sources']]
        if not any(name in reads_from(owner) for owner in owners):
            raise Unsupported('A rule residual needs an explicit containing rule AST, not a guessed footprint')
    covered=lowered['covered']|{s for s in binding_sources if structure.roles[s]['role']=='fact'}
    dependencies=query.completion_dependencies()
    if not dependencies:
        raise Unsupported('Native answer literals are not a source-derived main program')
    reachable=set();pending=list(expression_reads(program['query']))
    while pending:
        name=pending.pop()
        if name in reachable:continue
        reachable.add(name)
        if name in by_name:pending.extend(query.node_reads(by_name[name]))
    text='\n'.join(units[s] for s in covered|binding_sources)
    checks=[expression_literal_audit(program['query'],text,source['dataset'])]
    for node in nodes:
        if node['kind']=='expression':
            checks.append({'node':node['name'],**expression_literal_audit(node['body'],text,
                source['dataset'],structural_keys=node['name'] not in reachable,allow_system_null=True)})
    checks+=binding_checks
    if not all(c['pass'] for c in checks):
        raise Unsupported('Public literal grounding failed: '+str([c for c in checks if not c['pass']]))
    return {'source':source,'program':program,'query':query,'structure':structure,
            'slots':slots,'observations':specs,'by_fact':by_fact,'covered':covered,
            'rule_residuals':holes,'by_rule':by_rule,'grounding':checks,'translation_hash':digest(program),
            'scope_bindings':lowered['scope_bindings'],'missing_scope_sources':lowered['missing_scope_sources'],
            'unused_scope_sources':lowered['unused_scope_sources']}


def source_theory(compiled,observed=None):
    observed=observed or {};specs=compiled['observations']
    if not set(observed)<=set(specs) or any(v is not None and type(v) is not bool for v in observed.values()):
        raise Unsupported('Primitive observation results are Boolean or unknown; no coerced values')
    structure=inspect_source(compiled['source']);ledger=structure.ledger
    facts=dict(compiled['slots']);domains={};residuals=[]
    for name in specs:
        if observed.get(name) is None:domains[name]=(False,True)
        else:facts[name]=observed[name]
    domains.update({name:(False,True) for name in compiled['rule_residuals']})
    for i,clause in enumerate(ledger.clauses):
        pending=tuple(n for n in compiled['by_fact'].get(clause.id,[]) if n in domains)+\
            tuple(compiled['by_rule'].get(clause.id,[]))
        represented=clause.id in compiled['covered'] or clause.id in compiled['by_fact'] or \
            structure.roles[clause.id]['role'] in {'instruction','heading','query'}
        if not represented:
            residuals.append(Residual(clause.id,pending,'unverified_llm',True))
        elif pending:
            residuals.append(Residual(clause.id,pending,'accepted_translation',False))
        else:ledger.clauses[i]=replace(clause,state='compiled')
    return FiniteTheory(ledger,facts,domains,compiled['query'],residuals,
        containment_assumptions=('accepted full-clause source-linked AST translation is faithful',
                                'accepted factual primitive observations are faithful',
                                'each unresolved factual or rule-subexpression Boolean has its complete two-valued domain'))


def observation_request(compiled,names):
    if not set(names)<=set(compiled['observations']):raise Unsupported('Unknown factual primitive')
    ledger=compiled['structure'].ledger
    units={c.id:ledger.text[c.start:c.end] for c in ledger.clauses}
    observations=[{**compiled['observations'][name],
        'fact_text':units[compiled['observations'][name]['entity_source']],
        'predicate_context':units[compiled['observations'][name]['predicate_source']]} for name in names]
    system=('Read the supplied factual text and report ONLY the atomic factual observations. '
        'Do not decide the original legal task or apply legal rules. For each named entity and quoted '
        'factual predicate, return true only if the facts establish it, false only if they establish its '
        'negation, and null if unknown. Do not treat absence as false. Quote the exact supporting fact '
        'substring for true/false; for null use an empty evidence string. Never infer legal eligibility '
        'or compare statutory numeric thresholds. Do not manufacture missing facts.')
    schema=obj({'observations':array(obj({'name':{'enum':list(names)},
        'value':{'type':['boolean','null']},'evidence':{'type':'string'}}))})
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(observations,ensure_ascii=False)}],schema


def accept_observations(compiled,names,response):
    _,schema=observation_request(compiled,names);validate_wire(response,schema)
    rows=response['observations']
    if len(rows)!=len(names) or {r['name'] for r in rows}!=set(names):
        raise Unsupported('Each requested observation needs exactly one result')
    ledger=compiled['structure'].ledger;units={c.id:ledger.text[c.start:c.end] for c in ledger.clauses}
    result={}
    for row in rows:
        text=units[compiled['observations'][row['name']]['entity_source']]
        if row['value'] is None and row['evidence'] or row['value'] is not None and (
                not row['evidence'] or row['evidence'] not in text):
            raise Unsupported('Resolved factual observations require verbatim fact evidence')
        result[row['name']]=row['value']
    return result
