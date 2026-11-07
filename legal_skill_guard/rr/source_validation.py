"""Source-only diagnostics for a rejected compiler candidate; never a repair.

This module reads public source text and candidate syntax. It does not observe
facts, infer missing legal rules, open a grading packet or change the candidate.
"""
import json
from collections import Counter

from .clause_scope import required_scope_sources
from .grounding import binding_literal_audit
from .ir_types import IRTypeError,check_expression
from .scoped_program import expression_reads
from .source_program import proper_rule_subexpression
from .source_structure import inspect_source


def incomplete_feedback(content):
    """Diagnose complete declarations before truncation; never recover an IR.

    Only complete JSON values at the root or in a declaration array are read.
    An incomplete row, a duplicate JSON key or an unknown future declaration
    cannot supply evidence. Checks use the real expression type checker and
    do not infer missing bindings, truth values, clauses or query results.
    """
    from .raw_recovery import _unique_object
    decoder=json.JSONDecoder(object_pairs_hook=_unique_object)
    try:decoder.decode(content)
    except json.JSONDecodeError:pass
    except ValueError:return None
    else:return None
    groups={'bindings','observations','rule_residuals','nodes','scopes','clauses'}
    records=[];fields=[];pos=0
    def whitespace(at):
        while at<len(content) and content[at] in ' \t\r\n':at+=1
        return at
    pos=whitespace(pos)
    if content[pos:pos+1]!='{':return None
    pos+=1
    while True:
        pos=whitespace(pos)
        try:key,end=decoder.raw_decode(content,pos)
        except (ValueError,TypeError):break
        if not isinstance(key,str) or key in fields:break
        pos=whitespace(end)
        if content[pos:pos+1]!=':':break
        pos=whitespace(pos+1);fields.append(key)
        try:value,end=decoder.raw_decode(content,pos)
        except (ValueError,TypeError):
            # The complete rows of the first incomplete declaration array
            # remain unambiguous; never append closing bytes or parse its tail.
            if key in groups and key!='scopes' and content[pos:pos+1]=='[':
                at=pos+1;i=0
                while True:
                    at=whitespace(at)
                    try:row,end=decoder.raw_decode(content,at)
                    except (ValueError,TypeError):break
                    records.append((key,f'{key}[{i}]',row));i+=1
                    at=whitespace(end)
                    if content[at:at+1]!=',':break
                    at+=1
            break
        if key=='scopes' and isinstance(value,dict):
            records.extend((key,f'scopes.{sid}',row) for sid,row in value.items() if row is not None)
        elif key in groups and isinstance(value,list):
            records.extend((key,f'{key}[{i}]',row) for i,row in enumerate(value))
        pos=whitespace(end)
        if content[pos:pos+1]!=',':break
        pos+=1
    issues={};declared={};types={}
    def issue(path,expected,actual):
        identity=json.dumps([expected,actual],ensure_ascii=False,sort_keys=True)
        if identity in issues:issues[identity]['occurrences']+=1
        else:issues[identity]={'path':path,'expected':expected,'actual':actual,'occurrences':1}
    for _,path,row in records:
        if not isinstance(row,dict) or not isinstance(row.get('name'),str):continue
        name=row['name']
        if name in declared:issue(path+'.name','unique symbol name',{'name':name,'first_path':declared[name]})
        else:declared[name]=path+'.name'
    counts=Counter(row['name'] for _,_,row in records if isinstance(row,dict) and isinstance(row.get('name'),str))
    for group,_,row in records:
        if not isinstance(row,dict) or not isinstance(row.get('name'),str) or counts.get(row['name'])!=1:continue
        if group in {'observations','rule_residuals'}:types[row['name']]={'boolean'}
        elif group=='bindings':
            kind=row.get('type');value=row.get('value')
            if kind in {'integer','rational'}:types[row['name']]={'number'}
            elif kind=='scalar' and type(value) in (bool,int,str):
                types[row['name']]={{bool:'boolean',int:'number',str:'string'}[type(value)]}
            elif kind=='relation':types[row['name']]={'relation'}
    for group,path,row in records:
        if not isinstance(row,dict):continue
        keys=('condition',) if group=='scopes' else ('value','otherwise') if group=='clauses' else \
             ('body',) if group=='nodes' and row.get('kind')=='expression' else ()
        for key in keys:
            if key not in row or not expression_reads(row[key])<=set(types):continue
            body={'op':'not','args':[row[key]]} if group=='scopes' else row[key]
            prefix='program.body.query.args[0]' if group=='scopes' else 'program.body.query'
            try:
                result=check_expression({'query':body},{},slot_types=types)
                if group=='nodes' and counts.get(row.get('name'))==1:
                    types[row['name']]=set(result['result_types'])
            except IRTypeError as exc:
                for d in exc.diagnostics:issue(path+'.'+key+d['path'].removeprefix(prefix),d['expected'],d['actual'])
            except (TypeError,ValueError,KeyError,IndexError):
                # Malformed syntax is diagnosed by normal full-response
                # validation, never by guessing a type from an incomplete IR.
                continue
    return {'source_only':True,'prefix_only':True,'candidate_reconstructed':False,
        'complete_declaration_count':len(records),'issue_count':sum(d['occurrences'] for d in issues.values()),
        'issues':sorted(issues.values(),key=lambda d:d['expected']=='unique symbol name')[:12],
        'instruction':'These are errors in complete earlier declarations, not a recovered program. Return a complete fresh source-grounded translation; do not extend or copy the truncated tail.'}


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
        if not audit['pass'] and binding['type']=='relation':
            for r,row in enumerate(binding['value']['rows']):
                for c,cell in enumerate(row):
                    if not isinstance(cell,str) or cell.casefold() not in text.casefold():
                        issue(f'bindings[{i}].value.rows[{r}][{c}]',
                            'exact public witness text; keep source-unit IDs in provenance fields',
                            {'cell':cell,'sources':cited,'cited_text':text})
        elif not audit['pass']:
            issue(f'bindings[{i}].value',audit['basis'],{
                'value':binding['value'],'sources':cited,'cited_text':text})
        kind=binding['type'];value=binding['value']
        if kind in {'integer','rational'}:types.setdefault(binding['name'],{'number'})
        elif kind=='scalar':
            scalar={bool:'boolean',int:'number',str:'string'}.get(type(value))
            if scalar:types.setdefault(binding['name'],{scalar})
        else:types.setdefault(binding['name'],{kind})
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
        known=expression_reads(expression)<=set(types)
        body={'op':'not','args':[expression]} if boolean else expression
        try:check_expression({'query':body},{},slot_types=types)
        except IRTypeError as exc:
            prefix='program.body.query.args[0]' if boolean else 'program.body.query'
            for row in exc.diagnostics:
                # Arity is knowable even when a future definition has no
                # inferred type. Do not invent its type to diagnose siblings.
                if known or row['expected'].startswith('arity '):
                    issue(path+row['path'].removeprefix(prefix),row['expected'],row['actual'])
        def unbound(node,at):
            if isinstance(node,dict):
                if set(node)=={'var'} and node['var'] not in declared:
                    issue(at+'.var','declared IR symbol',node['var'])
                for key,value in node.items():unbound(value,at+'.'+key)
            elif isinstance(node,list):
                for i,value in enumerate(node):unbound(value,at+f'[{i}]')
        unbound(expression,path)
    for i,node in enumerate(program['nodes']):
        if node['kind']=='expression':check(node['body'],f'nodes[{i}].body')
    for i,scope in enumerate(program['scopes']):check(scope['condition'],f'scopes[{i}].condition',True)
    for i,clause in enumerate(program['clauses']):
        for key in ('value','otherwise'):check(clause[key],f'clauses[{i}].{key}')
    check(program['query'],'query')
    required=set(required_scope_sources(structure));provided={s['source'] for s in program['scopes']}
    for unit in sorted(required-provided):issue('scopes','executable scope for conditional public preface',{'source':unit,'text':units[unit]})
    clause_names={c['name'] for c in program['clauses']}
    if not expression_reads(program['query'])&clause_names:
        issue('query','read at least one guarded clause output',sorted(expression_reads(program['query'])))
    return {'issues':issues,'source_only':True,'grading_information_used':False,
        'candidate_modified':False,
        'instruction':'Return a complete fresh candidate grounded in the public source. Preserve unknowns; do not coerce numbers to truth, invent missing rules, or substitute paragraph IDs for legal conclusions.'}
