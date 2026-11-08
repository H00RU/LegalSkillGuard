"""Compact Python expressions lowered to the existing checked source program.

This is a syntax frontend, not a Python executor or a source-to-answer parser.
The model supplies every input, rule, applicability condition and disabled value.
Source ownership and unresolved predicates survive lowering unchanged.
"""
import ast
import io
import json
import re
import tokenize
from copy import deepcopy

from .source_code import (_Parser, SourceCodeError, _arguments, _call_name,
                          _literal, _node_code, _render_expression, PRIMITIVES)
from .source_structure import inspect_source, compact_contexts,explicit_query_target
from .strict_contract import obj
from .coverage import digest


def pal_schema():
    return obj({'code': {'type': 'string'}})


def decode_pal_text(content):
    """Unwrap one complete optional code fence; never repair program syntax.

    Direct program text follows PAL's generation interface. No inferred newlines,
    indentation, rules, values or discarded surrounding prose are permitted.
    """
    if type(content) is not str or not content.strip():
        raise SourceCodeError('An explicit complete Python program is required')
    trimmed=content.strip()
    if trimmed.startswith('```'):
        match=re.fullmatch(r'```(?:python)?\r?\n([\s\S]*?)\r?\n```',trimmed)
        if not match:
            raise SourceCodeError('Use one complete Python block without surrounding prose')
        return match[1]
    return content


class _Expressions(_Parser):
    def __init__(self, tree, functions):
        super().__init__(tree)
        self.functions = functions

    def expression(self, node):
        if isinstance(node,ast.Call) and not node.keywords and len(node.args)==1:
            if _call_name(node)=='sum' and not isinstance(node.args[0],ast.Starred):
                return {'op':'sum_numbers','args':[self.expression(node.args[0])]}
            if _call_name(node)=='add' and isinstance(node.args[0],ast.Starred):
                return {'op':'sum_numbers','args':[self.expression(node.args[0].value)]}
        if isinstance(node,ast.Subscript) and not (isinstance(node.slice,ast.Constant) and type(node.slice.value) is int):
            return {'op':'number_field','args':[self.expression(node.value),self.expression(node.slice)]}
        if isinstance(node, ast.Call) and _call_name(node) in self.functions:
            if node.args or node.keywords:
                raise SourceCodeError('Source rule functions take no arguments')
            return {'var': _call_name(node)}
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Gt, ast.GtE)):
            return {'op': 'lt' if isinstance(node.ops[0], ast.Gt) else 'le',
                    'args': [self.expression(node.comparators[0]), self.expression(node.left)]}
        return super().expression(node)


def parse_pal(code, *, require_query=True, external_functions=()):
    """Read the complete program without executing generated code or filling holes."""
    if type(code) is not str:
        raise SourceCodeError('The model must supply Python source text')
    try:
        tree = ast.parse(code)
        comments = {t.start[0]: t.string for t in tokenize.generate_tokens(io.StringIO(code).readline)
                    if t.type == tokenize.COMMENT}
    except (SyntaxError, tokenize.TokenError, RecursionError) as exc:
        raise SourceCodeError('Incomplete or invalid Python source: ' + str(exc),
            [{'path':'code','line':getattr(exc,'lineno',None),'column':getattr(exc,'offset',None),
              'expected':'complete valid Python source','actual':str(exc)}]) from exc
    functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}|set(external_functions)
    parser = _Expressions(tree, functions)
    declared = set()
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            name = statement.targets[0].id
        elif isinstance(statement, ast.FunctionDef):
            name = statement.name
        else:
            raise SourceCodeError('Only named assignments and source-decorated rule/scope functions are supported')
        if name in declared:
            raise SourceCodeError('Duplicate declaration: ' + name)
        declared.add(name)
        if isinstance(statement, ast.FunctionDef):
            args = statement.args
            if (args.posonlyargs or args.args or args.kwonlyargs or args.vararg or args.kwarg or
                    statement.returns or len(statement.decorator_list) != 1 or
                    len(statement.body) != 1 or not isinstance(statement.body[0], ast.Return) or
                    statement.body[0].value is None):
                raise SourceCodeError('A rule/scope function has no arguments and one explicit return expression')
            decorator = statement.decorator_list[0]
            kind = _call_name(decorator)
            if kind not in {'rule', 'scope'}:
                raise SourceCodeError('Use one @rule(SOURCE_IDS, otherwise=EXPRESSION) or @scope(SOURCE_ID)')
            if kind == 'scope':
                values = _arguments(decorator, ('source',))
                parser.program['scopes'].append({'name': name, 'source': _literal(values['source']),
                    'condition': parser.expression(statement.body[0].value)})
            else:
                if not decorator.args or any(kw.arg != 'otherwise' for kw in decorator.keywords) or len(decorator.keywords) != 1:
                    raise SourceCodeError('A rule needs actual source IDs and an explicit otherwise expression')
                parser.program['clauses'].append({'name': name,
                    'sources': [_literal(a) for a in decorator.args],
                    'value': parser.expression(statement.body[0].value),
                    'otherwise': parser.expression(decorator.keywords[0].value)})
            continue
        value = statement.value
        if name == 'query':
            parser.program['query'] = parser.expression(value)
        elif isinstance(value, ast.Constant) and type(value.value) in (int, str, bool):
            comment = comments.get(statement.end_lineno, '')
            if not re.fullmatch(r'#\s*s[0-9]+(?:\s*,\s*s[0-9]+)*\s*', comment):
                raise SourceCodeError('A public literal assignment requires exact trailing source IDs: # sN[,sM]')
            parser.program['bindings'].append({'name': name, 'sources': re.findall(r's[0-9]+', comment),
                'type': 'integer' if type(value.value) is int else 'scalar', 'value': value.value})
        elif _call_name(value) in {'scope', 'clause'}:
            raise SourceCodeError('Source rules and applicability use the declared Python function syntax')
        else:
            parser.declaration(name, value)
    if require_query and 'query' not in parser.program:
        raise SourceCodeError('An explicit query using guarded rule outputs is required')
    return parser.program


def lower_pal(source,code):
    """Separate rule ownership from redundant, already-declared fact evidence.

    No expression, input value, observation or scope is changed. Fact evidence
    cannot create coverage: it must already be present in a public primitive or
    observation, and its context cannot introduce a rule guard. Every original
    annotation is retained in the returned audit. Unknown/query IDs are errors.
    """
    program=parse_pal(code);structure=inspect_source(source)
    accounted={u for b in program['bindings'] for u in b['sources']}|{
        o['entity_source'] for o in program['observations']}
    audit=[]
    for clause in program['clauses']:
        original=list(clause['sources']);rules=[];facts=[]
        if len(set(original))!=len(original):raise SourceCodeError('Duplicate provenance IDs are not a source set')
        for unit in original:
            role=structure.roles.get(unit,{}).get('role')
            if role=='rule':rules.append(unit)
            elif role=='fact':
                if unit not in accounted or any(structure.roles[u]['role']=='rule' for u in structure.ledger.closure({unit})):
                    raise SourceCodeError('A factual rule annotation needs its existing primitive/observation evidence without a new rule guard')
                facts.append(unit)
            else:raise SourceCodeError('A rule annotation requires real rule or already-declared fact evidence')
        if not rules:raise SourceCodeError('Factual provenance cannot replace rule ownership')
        if facts:
            audit.append({'declaration':clause['name'],'original_sources':original,
                'rule_owners':rules,'already_declared_fact_evidence':facts,
                'new_inputs_or_coverage_or_semantic_expressions':False})
            clause['sources']=rules
    # A citation-qualified Boolean cannot be resolved as a factual primitive.
    # Before any observations exist, retaining that exact same named Boolean
    # as a legal unknown preserves every valuation and executable expression.
    # This is not a translation of the qualifier or a fact-truth repair.
    from .source_program import factual_predicate_supported,residual_context_proof
    texts={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    eligible=[]
    for observation in program['observations']:
        if not all(type(observation.get(k)) is str for k in ('name','entity','entity_source','predicate','predicate_source')):continue
        fs=observation['entity_source'];rs=observation['predicate_source'];predicate=observation['predicate']
        if (not factual_predicate_supported(predicate) and
            re.search(r'§|\b(?:sections?|subsections?|paragraphs?)\b',predicate,re.I) and
            structure.roles.get(fs,{}).get('role')=='fact' and structure.roles.get(rs,{}).get('role')=='rule' and
            observation['entity'] and observation['entity'] in texts[fs] and predicate and predicate in texts[rs]):
            hole={'name':observation['name'],'source':rs,'quote':predicate}
            if residual_context_proof(structure,program,hole):eligible.append((observation,hole))
    candidates={o['name'] for o,_ in eligible}
    retained_fact_sources={u for b in program['bindings'] for u in b['sources']}|{
        o['entity_source'] for o in program['observations'] if o['name'] not in candidates}
    before_expressions=digest({k:program[k] for k in ('bindings','nodes','scopes','clauses','query')})
    before_domains={o['name']:(False,True) for o in program['observations']+program['rule_residuals']}
    before_facts={o['entity_source'] for o in program['observations']}|{
        u for b in program['bindings'] for u in b['sources'] if structure.roles.get(u,{}).get('role')=='fact'}
    promoted=[]
    for observation,hole in eligible:
        if observation['entity_source'] not in retained_fact_sources:continue
        program['observations'].remove(observation);program['rule_residuals'].append(hole)
        promoted.append(observation['name'])
        audit.append({'declaration':observation['name'],'kind':'citation_qualified_predicate_retained_as_legal_unknown',
            'original_observation':deepcopy(observation),'legal_residual':deepcopy(hole),
            'domain_before':[False,True],'domain_after':[False,True],
            'entity_and_scope_preserved_in_original_observation':True,
            'new_rules_or_truth_values':False})
    after_domains={o['name']:(False,True) for o in program['observations']+program['rule_residuals']}
    after_facts={o['entity_source'] for o in program['observations']}|{
        u for b in program['bindings'] for u in b['sources'] if structure.roles.get(u,{}).get('role')=='fact'}
    if (before_expressions!=digest({k:program[k] for k in ('bindings','nodes','scopes','clauses','query')}) or
        before_domains!=after_domains or before_facts!=after_facts):
        raise SourceCodeError('Unknown-kind normalization must preserve expressions, every Boolean valuation and factual coverage')
    if promoted:
        audit.append({'basis':'exact_symbolic_program_preservation','executable_AST_sha256':before_expressions,
            'Boolean_domains_sha256':digest(before_domains),'factual_coverage':sorted(before_facts),
            'all_executable_expressions_and_domains_and_fact_coverage_unchanged':True,
            'factual_truth_was_not_observed':True,'normalized_declarations':promoted})
    return program,audit


def render_pal(program, *, include_query=True):
    """Lossless rendering of an already accepted program; never source inference."""
    lines = []
    for b in program['bindings']:
        if b['type'] in {'integer', 'scalar'} and type(b['value']) in (int, str, bool):
            lines.append(b['name'] + ' = ' + repr(b['value']) + ' # ' + ','.join(b['sources']))
        else:
            if b['type'] not in PRIMITIVES:
                raise SourceCodeError('Unknown source input type')
            lines.append(b['name'] + ' = ' + b['type'] + '(' + repr(b['value']) + ', sources=' + repr(b['sources']) + ')')
    for field, kind, keys in [('observations', 'observation', ('entity', 'entity_source', 'predicate', 'predicate_source')),
                              ('rule_residuals', 'residual', ('source', 'quote'))]:
        for row in program[field]:
            lines.append(row['name'] + ' = ' + kind + '(' + ', '.join(k+'='+repr(row[k]) for k in keys) + ')')
    lines += [n['name'] + ' = ' + _node_code(n) for n in program['nodes']]
    for row in program['scopes']:
        lines.append('@scope(' + repr(row['source']) + ')\ndef ' + row['name'] + '():\n    return ' + _render_expression(row['condition']))
    for row in program['clauses']:
        lines.append('@rule(' + ', '.join(repr(s) for s in row['sources']) + ', otherwise=' + _render_expression(row['otherwise']) + ')\ndef ' + row['name'] + '():\n    return ' + _render_expression(row['value']))
    if include_query:lines.append('query = ' + _render_expression(program['query']))
    return '\n'.join(lines) + '\n'


def pal_runtime_contract(source,library=None):
    from .source_format import language_contract
    contract=language_contract(source['dataset'])
    return {'typed_input_constructor':'name = TYPE(value=EXACT_PUBLIC_VALUE, sources=["sN"])',
        'binding_value_schemas':contract['binding_value_schemas'],
        'binding_semantics':contract['binding_semantics'],
        'graph_call':'OP(INPUT[,INPUT], params={...}) with the actual signatures below',
        'graph_signatures':contract['connector_syntax']['signatures'],
        'graph_semantics':contract['connector_semantics'],
        'projections':contract['connector_projection'],
        'learned_call':'learned(pattern=HASH, variant=INDEX, slots={ROLE:DECLARED_NAME}, columns={ROLE:CURRENT_COLUMN})',
        'available_learned_patterns':[{k:item[k] for k in ('pattern_hash','pattern')}
            for item in (library or {}).get('patterns',[])]}


def _example_units(previous,current):
    def signature(structure):
        return [(c.id,c.context,structure.ledger.text[c.start:c.end]) for c in structure.ledger.clauses if structure.roles[c.id]['role']=='rule']
    shared=signature(previous)==signature(current)
    return {'units':[{'id':c.id,**previous.roles[c.id],'text':previous.ledger.text[c.start:c.end]}
        for c in previous.ledger.clauses if not shared or previous.roles[c.id]['role']!='rule'],
        **({'rule_text_and_contexts_are_identical_CURRENT_units_by_id':True,
            'shared_rule_source_ids':[c.id for c in previous.ledger.clauses if previous.roles[c.id]['role']=='rule']} if shared else {})}


def pal_prompt(source, library=None, *, feedback=None,full_template=False):
    from .compiler_examples import validate_compiler_example
    from .source_format import native_schema
    from .clause_scope import required_scope_sources, structural_heading
    from .compiler_templates import validate_template
    from .source_program import source_theory
    structure = inspect_source(source)
    contexts = compact_contexts(structure)
    units = [{'id': c.id, **structure.roles[c.id], 'text': structure.ledger.text[c.start:c.end],
              'context': contexts[c.id]} for c in structure.ledger.clauses]
    system = (
        ('Translate CURRENT source rules into a compact Python program, returned in the code string. ' if full_template else
         'Return only a complete Python program as direct text with real line breaks and indentation. No JSON wrapper or escaped-code string. ') +
        'Use meaningful variables and ordinary arithmetic, comparisons, Boolean and/or/not, and conditional expressions. '
        'This program is parsed without executing arbitrary Python and passes the existing source, type, scope, '
        'resource and completion checks. No imports, tools, loops, attributes or extra output. '
        'A public numeric/string input is a plain assignment with exact evidence comment: variable = literal # sN. '
        'Do not enumerate or copy source paragraphs into variables. Derived quantities are expressions. '
        'Factual predicates remain unresolved: declare b_ variables by observation(entity=EXACT_ENTITY, entity_source=FACT_SOURCE_ID, '
        'predicate=EXACT_RULE_PREDICATE, predicate_source=RULE_SOURCE_ID). Use named arguments to preserve these four different roles. '
        'An entity is an actual name from factual text, never an sN source ID. '
        'Quotes must be literal substrings of the indicated source. Do not supply their truth values. '
        'Never use an observation for a legal conclusion, numeric comparison, threshold, year or date calculation. '
        'A partly untranslated legal subexpression uses b_name = residual(RULE_SOURCE_ID, EXACT_PROPER_SUBQUOTE); '
        'the containing rule must read it. It stays both true/false, never a guessed answer. '
        'A legal output is a no-argument function: decorate with @rule("sN", "sM", otherwise=EXPLICIT_DISABLED_VALUE), '
        'then def meaningful_name(): return EXPRESSION. The rule IDs own precisely the full rules actually translated. '
        'An additional factual source ID is evidence only and must already occur in an input or observation; '
        'the compiler retains it as provenance without creating inputs, truth or rule coverage. '
        'Its disabled value must be supplied explicitly with the correct type; it is not inferred. '
        'Applicability is a no-argument function with @scope("sN") and return BOOLEAN_EXPRESSION. '
        'Every inherited applicability scope is physically enforced on affected rule outputs by the source context. '
        'Literal True is allowed as scope only for the supplied structural_title_sources; actual conditions require executable predicates. '
        'Never enumerate all paragraphs as True scopes; a scope does not itself translate a rule output. '
        'Unused scopes, ordinary calculations and references do not cover untranslated rules. '
        'Declare each name once; reference a rule result by its name or a no-argument call. '
        'Finish with query = EXPRESSION using guarded rule outputs and the exact native output shape. '
        'Do not substitute a native answer literal, an unguarded local result or a fallback. '
        'Python lists/dictionaries, min/max and sum(NUMERIC_LIST) are supported. All branches must type check. '
        'Exact division uses an integer denominator; monetary results must remain exact. '
        'The runtime contract lists actual typed-input constructors, the seven connector operators, their parameter shapes '
        'and output projections. Use explicit learned(pattern=...,variant=...,slots=...,columns=...) calls only when an '
        'available graph matches current witness/quantity obligations. Copying graph operators is not stored-pattern reuse. '
        'All current facts, amounts, relation witnesses and resource metadata need exact source grounding; do not invent them. '
        'Partial source remains unresolved; do not invent missing rules to claim completion. '
        'Earlier examples teach syntax only; CURRENT has its own entities, years, rules and native result.')
    if full_template:
        system+=(' This request acquires a reusable FULL-SOURCE TRAIN compiler template, not only a short solution '
            'to the current query. Translate every substantive rule unit into its meaningful source-linked rule '
            'definition, numerical calculation, or inherited applicability condition, including rules outside '
            'the current query dependency closure. Structural titles may only supply their real scope context. '
            'Keep missing factual predicates and proper legal subexpressions explicit with their two-valued '
            'domains. Do not label operative rules as True scopes or cite unrelated units to claim coverage. '
            'No final answer stability is required for this template: unresolved observations may stay unknown. '
            'Preserve every missing source obligation if a full faithful translation is unavailable.')
    examples = []
    for item in (library or {}).get('compiler_templates', []):
        checked=validate_template(item)
        if item['source']['key']==source['key']:
            raise ValueError('A compiler example cannot supply the current source program')
        if item['language']!='source_annotated_python_v1' or item['source']['dataset']!=source['dataset']:
            continue
        st=inspect_source(item['source'])
        examples.append({'template_hash':item['template_hash'],
            **_example_units(st,structure),
            'untranslated_source_units':[r.source for r in source_theory(checked).residuals if r.unknown_scope],
            'code':item['code']})
    for example in (library or {}).get('compiler_examples', []):
        previous, _, compiled = validate_compiler_example(example)
        if previous['key'] == source['key']:
            raise ValueError('A compiler example cannot supply the current source program')
        if native_schema(previous['dataset']) != native_schema(source['dataset']):
            continue
        st = compiled['structure']
        examples.append({'example_hash': example['example_hash'],
            **_example_units(st,structure),
            'code': render_pal(compiled['program'])})
    payload = {}
    if examples:
        payload['earlier_TRAIN_examples'] = examples
    payload.update(CURRENT={'dataset': source['dataset'], 'units': units,
        'explicit_query_target':explicit_query_target(source),
        'required_scope_sources': list(required_scope_sources(structure)),
        'structural_title_sources':[u['id'] for u in units if u['role']=='rule' and structural_heading(u['text'])],
        'native_output_schema': native_schema(source['dataset'])},
        runtime_contract=pal_runtime_contract(source,library),source_only_feedback=feedback)
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}]
