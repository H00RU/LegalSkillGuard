"""Source-only diagnostics for a rejected compiler candidate; never a repair.

This module reads public source text and candidate syntax. It does not observe
facts, infer missing legal rules, open a grading packet or change the candidate.
"""
from .clause_scope import required_scope_sources
from .grounding import binding_literal_audit
from .ir_types import IRTypeError,check_expression
from .scoped_program import expression_reads
from .source_program import proper_rule_subexpression
from .source_structure import inspect_source


def validation_feedback(source,program):
    structure=inspect_source(source)
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    issues=[];declared={};types={}
    def issue(path,expected,actual):
        issues.append({'path':path,'expected':expected,'actual':actual})
    for group in ('bindings','observations','rule_residuals','nodes','scopes','clauses'):
        for i,item in enumerate(program[group]):
            path=f'{group}[{i}].name';name=item['name']
            if name in declared:issue(path,'unique symbol name',{'name':name,'first_path':declared[name]})
            else:declared[name]=path
    names={b['name'] for b in program['bindings']}
    for i,binding in enumerate(program['bindings']):
        cited=binding['sources'];text='\n'.join(units.get(s,'') for s in cited)
        audit=binding_literal_audit(binding['type'],binding['value'],text,names)
        if not audit['pass']:
            issue(f'bindings[{i}].value',audit['basis'],{
                'value':binding['value'],'sources':cited,'cited_text':text})
        kind=binding['type'];value=binding['value']
        if kind in {'integer','rational'}:types.setdefault(binding['name'],{'number'})
        elif kind=='scalar':
            scalar={bool:'boolean',int:'number',str:'string'}.get(type(value))
            if scalar:types.setdefault(binding['name'],{scalar})
    for i,observation in enumerate(program['observations']):
        types.setdefault(observation['name'],{'boolean'})
        for field,role in (('entity_source','fact'),('predicate_source','rule')):
            actual=structure.roles.get(observation[field],{}).get('role','unknown')
            if actual!=role:issue(f'observations[{i}].{field}',role,{
                'source':observation[field],'role':actual})
        for field,key in (('entity','entity_source'),('predicate','predicate_source')):
            if not observation[field] or observation[field] not in units.get(observation[key],''):
                issue(f'observations[{i}].{field}','exact substring of cited source',observation[field])
    for i,hole in enumerate(program['rule_residuals']):
        types.setdefault(hole['name'],{'boolean'})
        if not proper_rule_subexpression(hole['quote'],units.get(hole['source'],'')):
            issue(f'rule_residuals[{i}].quote','proper rule subexpression; a removed paragraph prefix does not translate the rule',hole['quote'])
    # Infer only definitions whose dependencies are already known. Diagnosing
    # an invalid candidate does not pretend that an unbound name has a type.
    remaining=[n for n in program['nodes'] if n['kind']=='expression']
    while remaining:
        ready=[n for n in remaining if expression_reads(n['body'])<=set(types)]
        if not ready:break
        for node in ready:
            try:types.setdefault(node['name'],set(check_expression({'query':node['body']},{},slot_types=types)['result_types']))
            except IRTypeError:pass
            remaining.remove(node)
    def check(expression,path,boolean=False):
        if not expression_reads(expression)<=set(types):return
        body={'op':'not','args':[expression]} if boolean else expression
        try:check_expression({'query':body},{},slot_types=types)
        except IRTypeError as exc:
            prefix='program.body.query.args[0]' if boolean else 'program.body.query'
            for row in exc.diagnostics:
                issue(path+row['path'].removeprefix(prefix),row['expected'],row['actual'])
    for i,scope in enumerate(program['scopes']):check(scope['condition'],f'scopes[{i}].condition',True)
    check(program['query'],'query')
    required=set(required_scope_sources(structure));provided={s['source'] for s in program['scopes']}
    for unit in sorted(required-provided):issue('scopes','executable scope for conditional public preface',{'source':unit,'text':units[unit]})
    clause_names={c['name'] for c in program['clauses']}
    if not expression_reads(program['query'])&clause_names:
        issue('query','read at least one guarded clause output',sorted(expression_reads(program['query'])))
    return {'issues':issues,'source_only':True,'grading_information_used':False,
        'candidate_modified':False,
        'instruction':'Return a complete fresh candidate grounded in the public source. Preserve unknowns; do not coerce numbers to truth, invent missing rules, or substitute paragraph IDs for legal conclusions.'}
