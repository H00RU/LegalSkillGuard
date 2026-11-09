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
from .source_structure import inspect_source,compact_contexts
from .strict_contract import (obj,array,ref,interface_definitions,type_enum_schemas,
                              bounded_expressions,EXPRESSION_DEPTH,source_expression_operations)
from .wire_validation import validate_wire
from .clause_scope import lower_clauses,required_scope_sources,open_passive_condition,syntax_only_source_unit


OPERATORS=['if','not','xor','eq','ne','lt','le','sub','scale','divide_constant',
           'ceil_divide_constant','number_at','number_field','sum_numbers','min','max','and','or','add','array','pair','object','concat']


def factual_predicate_supported(predicate):
    return not re.search(r'\d|§|\b(?:shall|applies|applicable|entailment|contradiction|entitled|refer|subsection|section|half|more than|over|less than)\b',predicate,re.I)


def _operand_definitions(symbol):
    """Mirror pair-key and numeric-vector requirements of check_expression.

    Variables remain symbolic and undergo the original all-branch checker.
    No source value or missing declaration is inferred by this grammar.
    """
    variable=obj({'var':symbol})
    def conditional(kind):
        return obj({'op':{'enum':['if']},'args':{'type':'array',
            'prefixItems':[ref('bool_expr'),ref(kind),ref(kind)],'items':False,'minItems':3,'maxItems':3}})
    numeric=source_expression_operations(['add','sub','scale','divide_constant',
        'ceil_divide_constant','number_at','number_field','sum_numbers','min','max'])
    for operation in numeric:
        args=operation['properties']['args'];op=operation['properties']['op']['enum'][0]
        if op=='number_field':
            args['prefixItems']=[ref('expr'),ref('string_expr')]
            continue
        if op=='sum_numbers':
            args['items']=ref('numbers_expr')
            continue
        if 'prefixItems' in args:
            args['prefixItems'][1 if op=='scale' else 0]=ref('numbers_expr' if op=='number_at' else 'number_expr')
        else:args['items']=ref('number_expr')
    definitions={
        'string_expr':{'anyOf':[{'type':'string'},variable,conditional('string_expr')]},
        'number_expr':{'anyOf':[{'type':'integer'},variable,*numeric,conditional('number_expr')]},
        'numbers_expr':{'anyOf':[variable,
            obj({'op':{'enum':['array']},'args':{**array(ref('number_expr')),'minItems':1}}),
            obj({'op':{'enum':['concat']},'args':{**array(ref('numbers_expr')),'minItems':1}}),
            conditional('numbers_expr')]}}
    operations=source_expression_operations([op for op in OPERATORS if op!='pair'])
    for operation in operations:
        if operation['properties']['op']['enum']==['number_at']:
            operation['properties']['args']['prefixItems'][0]=ref('numbers_expr')
    operations.append(obj({'op':{'enum':['pair']},'args':{'type':'array',
        'prefixItems':[ref('string_expr'),ref('expr')],'items':False,'minItems':2,'maxItems':2}}))
    return definitions,operations


def source_unit_schema(ids):
    """Exact current sN IDs without XGrammar's large literal-alternation bug.

    Factor equal-length digit tries into character classes. This denotes the
    original finite set exactly; source IDs and all local checks stay intact.
    """
    values=sorted(set(ids))
    if not values or any(re.fullmatch(r's(?:0|[1-9][0-9]*)',v) is None for v in values):
        raise ValueError('Current source IDs must be canonical sN strings')
    def factor(words):
        if words==['']:return ''
        children={}
        for word in words:children.setdefault(word[0],[]).append(word[1:])
        suffixes={}
        for digit,tails in sorted(children.items()):suffixes.setdefault(factor(tails),[]).append(digit)
        parts=[]
        for tail,digits in sorted(suffixes.items()):
            head=digits[0] if len(digits)==1 else '['+''.join(digits)+']'
            parts.append(head+tail)
        return parts[0] if len(parts)==1 else '(?:'+'|'.join(parts)+')'
    widths={}
    for value in values:widths.setdefault(len(value)-1,[]).append(value[1:])
    # Fixed lengths also exclude a trailing newline accepted by Python's $
    # anchor, keeping local JSON Schema membership identical to the enum.
    variants=[{'type':'string','pattern':'^s'+factor(words)+'$',
               'minLength':width+1,'maxLength':width+1}
              for width,words in sorted(widths.items())]
    return variants[0] if len(variants)==1 else {'anyOf':variants}


def program_schema(source,library=None):
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema
    from .source_format import query_expression_schema
    structure=inspect_source(source)
    unit_ids=[c.id for c in structure.ledger.clauses]
    unit=source_unit_schema(unit_ids)
    rules=[key for key,value in structure.roles.items() if value['role']=='rule']
    facts=[key for key,value in structure.roles.items() if value['role']=='fact']
    rule_unit=source_unit_schema(rules) if rules else unit
    fact_unit=source_unit_schema(facts) if facts else unit
    string={'type':'string'}
    symbol={'type':'string','pattern':'^[A-Za-z_][A-Za-z0-9_]{0,63}$'}
    boolean_symbol={'type':'string','pattern':'^b_[A-Za-z0-9_]{1,62}$'}
    definitions=interface_definitions(unit_ids,literal_text=structure.ledger.text)
    for binding in definitions['binding']['anyOf']:
        binding['properties']['name']=symbol
        binding['properties'].pop('source')
        binding['properties']['sources']={**array(unit),'minItems':1,'maxItems':len(unit_ids)}
        # Select the primitive type and evidence before generating its value.
        # This is the same mapping contract, without a value-first union.
        binding['properties']={key:binding['properties'][key] for key in ('name','type','sources','value')}
        binding['required']=list(binding['properties'])
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
    operands,operations=_operand_definitions(symbol);definitions.update(operands)
    definitions['expr']={'anyOf':[{'type':'integer'},{'type':'boolean'},string,
        {'type':'null'},
        obj({'var':symbol}),*operations]}
    definitions['bool_expr']={'anyOf':[{'type':'boolean'},obj({'var':symbol}),
        obj({'op':{'enum':['and','or']},'args':array(ref('bool_expr'))}),
        obj({'op':{'enum':['not']},'args':{**array(ref('bool_expr')),'minItems':1,'maxItems':1}}),
        obj({'op':{'enum':['xor']},'args':{**array(ref('bool_expr')),'minItems':2,'maxItems':2}}),
        obj({'op':{'enum':['eq','ne','lt','le']},'args':{**array(ref('expr')),'minItems':2,'maxItems':2}}),
        obj({'op':{'enum':['if']},'args':{**array(ref('bool_expr')),'minItems':3,'maxItems':3}})]}
    definitions['result_expr']=query_expression_schema(source['dataset'],symbol)
    recursive={name:definitions[name] for name in ('expr','bool_expr','connector','result_expr',*operands)}
    definitions.update(bounded_expressions(recursive))
    for name in recursive:
        definitions[name]=ref(f'{name}_{EXPRESSION_DEPTH}')
    definitions['node']={'anyOf':[
        obj({'name':symbol,'kind':{'enum':['expression']},'body':ref('expr')}),
        obj({'name':symbol,'kind':{'enum':['connector']},'body':obj({'graph':ref('connector'),
            'project':{'enum':['identity','amount_value','amount_values','entailment_label']}})})]}
    schema=obj({'bindings':array(ref('binding')),'observations':array(obj({
        'name':boolean_symbol,'entity':string,'entity_source':fact_unit,
        'predicate':string,'predicate_source':rule_unit})),
        'rule_residuals':array(obj({'name':boolean_symbol,
            'source':rule_unit,'quote':string})),
        'nodes':array(ref('node')),
        'scopes':array(obj({'name':symbol,'source':rule_unit,'condition':ref('bool_expr')})),
        'clauses':array(obj({'name':symbol,'sources':{**array(rule_unit),
            'maxItems':len(rules)},'value':ref('expr'),'otherwise':ref('expr')})),
        'query':ref('result_expr')})
    if not facts or not rules:schema['properties']['observations']['maxItems']=0
    if not rules:
        for key in ('rule_residuals','scopes','clauses'):schema['properties'][key]['maxItems']=0
    schema['$defs']=definitions
    type_enum_schemas(schema)
    return strict_output_schema(schema)


def compiler_prompt(source,library=None,accepted_program=None,validation_feedback=None,factual_observation_task=None):
    from .source_format import language_contract
    from .compiler_contract import COMPILER_FIELDS,encode_compiler_program
    structure=inspect_source(source)
    contexts=compact_contexts(structure)
    units=[{'id':c.id,**structure.roles[c.id],'text':structure.ledger.text[c.start:c.end],
            'context':contexts[c.id]} for c in structure.ledger.clauses]
    system=(
        'Compile the CURRENT public rule task into the seven-field structured program in the response schema: '
        +', '.join(COMPILER_FIELDS)+'. '
        'Declare public inputs and unresolved factual/legal predicates first, then local computations, scopes, '
        'guarded clauses and the final query. Empty declaration arrays are allowed when no such input is used. '
        'Use the actual JSON AST, not Python, function-call text, code strings, a native answer or a coverage claim. '
        'No tools or grading information are available. Internal names are unique ASCII identifiers of at most64 '
        'characters across all declarations; a name has no implicit semantic meaning. '
        'Provenance uses exact sN unit IDs; task_id is logging metadata and never a valid unit ID or operand. '
        'Binding evidence and clause ownership list each actual source unit at most once. These are finite '
        'source sets, not repeated sequences. Never repeat source IDs to fill an array. '
        'Do not enumerate source paragraphs into primitive inputs or repeat a declaration. '
        'Primitive inputs are bindings records {name,type,sources,value}, following language_contract. '
        'Every numeric value and public string must be grounded in the cited units. A relation has actual factual '
        'witness rows, one cell per column, citing all required factual lines. Source IDs are metadata, never '
        'relation cells, numerical inputs or legal citations. Boolean primitives require literal true/false in '
        'the cited text; paragraph numbers, years and0/1 are not truth values. '
        'Observations have unique names beginning b_, an exact entity quote and factual entity_source, and an '
        'exact predicate quote and rule predicate_source. You do not provide their truth values in the program. '
        'Reuse one observation for identical quotes. Legal effects, thresholds, arithmetic, dates and comparisons '
        'belong in executable expressions, not factual observations. '
        'Untranslated proper legal/numeric subexpressions may use rule_residuals with unique b_ names, an actual '
        'rule source and exact proper subquote. They retain both False/True and are never sent to the fact '
        'observer. The containing clause or scope must actually read them. Do not replace an entire rule, '
        'final claim or numerical comparison with a guessed fact or Boolean. '
        'scopes is keyed by every actual rule unit ID. Each entry is null or {name,condition}; condition is a '
        'Boolean AST. Null means no accepted scope translation, retaining the existing unknown scope; it never '
        'means false. Use null for units that need no separate scope or whose scope is untranslated. '
        'Only nonconditional structural titles may use literal true. Supply executable conditions for all '
        'required_scope_sources before claiming their context covered, including conditional prefaces. '
        'The fixed scope keys do not themselves translate or cover any rule. '
        'clauses contains {name,sources,value,otherwise}. Own only the rule units actually translated. The engine '
        'physically guards each output using every inherited scope in the transitive source context. State the '
        'disabled value explicitly and with the proper type; do not guess it. A reference, unused scope or local '
        'calculation cannot cover an untranslated rule. Partial translations leave unowned units unknown. '
        'The full policy requires residual source to be parsed before certification; answer_separating selects '
        'remaining source using the actual completion check, never by guessing away unknown effects. '
        'Read a declared symbol with {"var":"its_declared_name"}; a string is a literal, not a variable or '
        'a request to read a source unit. Names and source IDs are not executable facts. '
        'An expression is a JSON integer, string, boolean or null, a variable object with exactly key var, or an '
        'operation object with exactly keys op and args. args is an array of operand expressions. '
        'Operations are if, not, xor, eq, ne, lt, le, sub, scale, divide_constant, ceil_divide_constant, number_at, number_field, sum_numbers, '
        'min, max, and, or, add, array, pair, object, concat. sum_numbers takes one exact numeric list without coercion. if has exactly three operands: Boolean condition, '
        'then value, else value. and/or take separate Boolean expressions in args, never an array expression as '
        'one Boolean operand. Empty and/or are supported. All branches must type check. '
        'scale requires a literal integer multiplier first; divide_constant and ceil_divide_constant require '
        'the numeric expression first and a nonzero/positive literal denominator second. number_at takes a '
        'numeric vector and nonnegative literal integer index, without an out-of-range default. '
        'pair takes exactly two operands: a string key first, then its value. object takes separate pair '
        'expressions as args. A record/pair/string array is not a numeric vector. '
        'A denominator100 for percent or2 for one-half is only the stated conversion, not a new amount. '
        'Local expression nodes contain {name,kind:expression,body:AST}. Connector nodes contain '
        '{name,kind:connector,body:{graph,project}}, using the seven graph operators and actual parameter '
        'shapes in language_contract. Projections are identity, amount_value, amount_values and entailment_label. '
        'When an available learned graph matches the actual slot/column obligations, use its pattern hash, '
        'variant and complete slots/columns mapping. Copying its operators is not library use. Do not insert '
        'irrelevant graph calls to claim reuse. '
        'Every consumption of one allowance bank shares one thread_allowance result; never clone or re-consume '
        'its bank. Read allocations from that single amount_values output. '
        'Expressions and graphs have at most16 nested operations; factor longer calculations into named nodes. '
        'The final query combines guarded clause outputs and public inputs into language_contract.query_result_schema. '
        'Do not bypass guards through a helper or scope name, and do not return a constant native result. '
        'Do not invent laws, witnesses, dates, amounts or missing operators. Timing policies are not executable '
        'date comparisons; use supported numeric expressions or retain proper unknown legal subexpressions. '
        'accepted_program is the previously accepted translation. Preserve unchanged names, quotations and '
        'definitions to retain factual evidence. validation_feedback is source-only diagnosis, never target '
        'answers. Repair concrete errors without coercion or invented rules. ')
    if factual_observation_task is not None:
        system+=('Return requested factual_observations separately from the program: truth only for the requested '
            'factual predicates, null for unknown, and verbatim factual evidence for true/false. Never resolve '
            'legal residuals as facts. ')
    payload={'dataset':source['dataset'],'task_id':source['key'],
        'task_metadata':{'answer_type':source['public'].get('answer_type')},
        'language_contract':language_contract(source['dataset'],literal_text=structure.ledger.text),
        'required_scope_sources':required_scope_sources(structure),
        'accepted_program':encode_compiler_program(accepted_program,source) if accepted_program is not None else None,
        'validation_feedback':validation_feedback,
        'requested_factual_observations':factual_observation_task,
        'available_learned_patterns':[{k:item[k] for k in ('pattern_hash','pattern')}
            for item in (library or {}).get('patterns',[])],
        'units':units}
    from .compiler_examples import compiler_examples_for_source
    examples=compiler_examples_for_source(library,source)
    if examples:
        system+=(' Compiler training examples below belong to earlier TRAIN sources. '
            'Their source IDs, names and public values are local to each example. '
            'Use their IR construction to write a fresh program grounded in the CURRENT units. '
            'Every current declaration, scope, clause and query still needs its own valid provenance.')
        payload['compiler_training_examples']=examples
    return system,json.dumps(payload,ensure_ascii=False,separators=(',',':'))


def proper_rule_subexpression(quote,text):
    operative=re.sub(r'^\s*(?:\([A-Za-z0-9]+\)\s*)+','',text).strip()
    return bool(quote and quote in text and quote.strip() not in {text.strip(),operative})


def residual_context_proof(structure,program,hole):
    """A full physical list fragment can be part of a translated enclosing rule.

    This is not a guessed footprint from a heading: require an actual ancestor
    conditional with an open passive predicate, an executable Boolean compound
    owned by that ancestor, a real data dependency on this residual and another
    represented input. Whole standalone rules and unused context still fail.
    """
    unit=hole['source'];quote=hole['quote'];name=hole['name']
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    if structure.roles.get(unit,{}).get('role')!='rule':return None
    if proper_rule_subexpression(quote,units[unit]):return {'basis':'proper_local_subexpression'}
    if not quote or quote not in units[unit]:return None
    child=re.sub(r'^\s*(?:\([A-Za-z0-9]+\)\s*)+','',units[unit]).strip()
    # Explicit nested list grammar, not a general legal relevance heuristic.
    if not re.match(r'^by\b',child,re.I):return None
    parents=structure.ledger.closure({unit})-{unit}
    definitions={n['name']:n['body'] for n in program['nodes'] if n['kind']=='expression'}
    definitions.update({s['name']:s['condition'] for s in program['scopes']})
    definitions.update({c['name']:c['value'] for c in program['clauses']})
    inputs={b['name'] for b in program['bindings']}|{o['name'] for o in program['observations']}|{
        r['name'] for r in program['rule_residuals']}
    def reads(expression):
        seen=set();pending=list(expression_reads(expression))
        while pending:
            key=pending.pop()
            if key in seen:continue
            seen.add(key)
            if key in definitions:pending.extend(expression_reads(definitions[key]))
        return seen
    for parent in program['clauses']:
        for ancestor in set(parent['sources'])&parents:
            text=units[ancestor].strip()
            if not open_passive_condition(text):continue
            body=parent['value']
            if not isinstance(body,dict) or body.get('op') not in {'and','or','if'}:continue
            dependencies=reads(body)
            if name in dependencies and (dependencies&inputs)-{name}:
                return {'basis':'explicit_enclosing_conditional_compound','parent_source':ancestor,
                    'parent_declaration':parent['name'],'residual_source':unit,
                    'residual_domain_unchanged':[False,True]}
    return None


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
        if not factual_predicate_supported(observation['predicate']):
            raise Unsupported('Compile legal effects and numerical comparisons into rule ASTs')
        specs[name]=observation;by_fact.setdefault(fs,[]).append(name)
    domains={name:(False,True) for name in specs};residual_contexts={}
    for hole in program['rule_residuals']:
        name=hole['name'];unit=hole['source'];quote=hole['quote']
        if name in slots or name in specs or name in holes or structure.roles[unit]['role']!='rule':
            raise Unsupported('Rule residuals need unique names and actual rule provenance')
        proof=residual_context_proof(structure,program,hole)
        if proof is None:
            raise Unsupported('A rule residual must quote a proper subexpression, not a whole untranslated clause')
        residual_contexts[name]=proof
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
    # A translated rule's citation address is public provenance even when the
    # model omits its redundant identity scope. No operative context is added.
    covered.update(s for s in structure.ledger.closure(covered) if syntax_only_source_unit(units[s]))
    dependencies=query.completion_dependencies()
    if not dependencies:
        raise Unsupported('Native answer literals are not a source-derived main program')
    reachable=set();pending=list(expression_reads(program['query']))
    while pending:
        name=pending.pop()
        if name in reachable:continue
        reachable.add(name)
        if name in by_name:pending.extend(query.node_reads(by_name[name]))
    # A record used exclusively as a numeric lookup receiver cannot expose its
    # field labels in the native output. Labels are then local addresses, like
    # variable names; all selected values and source literals remain checked.
    field_receivers=set();other_reads=set()
    def field_uses(expression,receiver=False):
        if isinstance(expression,dict) and set(expression)=={'var'}:
            (field_receivers if receiver else other_reads).add(expression['var'])
        elif isinstance(expression,dict):
            for i,arg in enumerate(expression.get('args',[])):
                field_uses(arg,expression.get('op')=='number_field' and i==0)
    field_uses(program['query'])
    for name in reachable:
        if name not in by_name:continue
        node=by_name[name]
        if node['kind']=='expression':field_uses(node['body'])
        else:other_reads.update(query.node_reads(node))
    field_only_records=field_receivers-other_reads
    text='\n'.join(units[s] for s in covered|binding_sources)
    checks=[expression_literal_audit(program['query'],text,source['dataset'],numeric_field_addresses=True)]
    for node in nodes:
        if node['kind']=='expression':
            checks.append({'node':node['name'],**expression_literal_audit(node['body'],text,
                source['dataset'],structural_keys=node['name'] not in reachable or node['name'] in field_only_records,
                allow_system_null=True,numeric_field_addresses=True)})
    checks+=binding_checks
    if not all(c['pass'] for c in checks):
        raise Unsupported('Public literal grounding failed: '+str([c for c in checks if not c['pass']]))
    return {'source':source,'program':program,'query':query,'structure':structure,
            'slots':slots,'observations':specs,'by_fact':by_fact,'covered':covered,
            'rule_residuals':holes,'by_rule':by_rule,'grounding':checks,'translation_hash':digest(program),
            'numeric_field_only_record_nodes':sorted(field_only_records),
            'residual_context_proofs':residual_contexts,
            'scope_bindings':lowered['scope_bindings'],'missing_scope_sources':lowered['missing_scope_sources'],
            'derived_context_scopes':lowered['derived_context_scopes'],
            'effective_scopes':lowered['effective_scopes'],
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
            syntax_only_source_unit(ledger.text[clause.start:clause.end]) or \
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
    query_text=compiled['source']['public'].get('query','')
    reference_years=sorted(set(int(v) for v in re.findall(r'\b(?:for(?:\s+the)?(?:\s+taxable|\s+calendar)?(?:\s+year)?|in)\s+((?:19|20)[0-9]{2})\b',query_text,re.I)))
    observations=[{**compiled['observations'][name],
        'fact_text':units[compiled['observations'][name]['entity_source']],
            'predicate_context':units[compiled['observations'][name]['predicate_source']],
            'public_reference_years':reference_years} for name in names]
    system=('Read the supplied factual text and report ONLY the atomic factual observations. '
        'Do not decide the original legal task or apply legal rules. For each named entity and quoted '
        'factual predicate, return true only if the facts establish it, false only if they establish its '
        'negation, and null if unknown. Do not treat absence as false. Quote the exact supporting fact '
        'substring for true/false; for null use an empty evidence string. Never infer legal eligibility '
        'or compare statutory numeric thresholds. Use supplied public reference years only to scope factual temporal statements; '
        'do not treat an old factual episode as a claim about every year. Do not manufacture missing facts.')
    schema=obj({'observations':array(obj({'name':{'type':'string','enum':list(names)},
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
