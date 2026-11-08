"""Source-local PAL fragments for the actual A follow-up, preserving accepted K.

The model translates selected unknown rules or proper legal subexpressions.
It cannot replace the accepted query, rules, scopes or primitive meanings.
"""
from copy import deepcopy
import json

from .coverage import Unsupported
from .grounding import _numbers,expression_literal_audit
from .pal_frontend import parse_pal,render_pal,pal_runtime_contract
from .source_program import compile_source
from .scoped_program import compile_query
from .source_structure import compact_contexts
from .strict_contract import obj


def refinement_request(compiled,selected,closure,names,factual_task,factual_rows_schema,library=None):
    structure=compiled['structure'];program=compiled['program'];selected=set(selected)
    targets=[r for r in program['rule_residuals'] if r['source'] in selected]
    # New expressions can require current public literals. Charge their complete
    # factual regions in the exact physical payload used by the planner.
    units=set(closure)|{c.id for c in structure.ledger.clauses if structure.roles[c.id]['role']=='fact'}
    contexts=compact_contexts(structure)
    rows=[{'id':c.id,**structure.roles[c.id],'text':structure.ledger.text[c.start:c.end],
           'context':contexts[c.id]} for c in structure.ledger.clauses if c.id in units]
    accepted={k:v for k,v in program.items() if k!='query'}
    accepted['query_is_immutable']=True
    system=('Translate only the selected untranslated source rules or legal subexpressions. '
        'Return program_lines containing a compact Python fragment, plus factual_observations for exactly the listed existing fact tasks. '
        'Each program_lines entry is one physical Python line; preserve indentation and put comments on their actual lines. '
        'The runtime joins these strings with newline characters without repairing their contents. '
        'Use an empty program_lines array when no legal expression can be translated. '
        'For each selected proper legal residual, assign its existing b_name to the actual Boolean expression. '
        'You may add current public numeric/string literal assignments with exact # sN evidence, observations with explicit '
        'entity/entity_source/predicate/predicate_source, proper residuals, helper expressions and source-decorated @rule/@scope functions. '
        'No query declaration: the runtime preserves the accepted query and all earlier rule/scope definitions. '
        'Never redefine existing inputs or rules, assign guessed truth to legal conditions, or return a native answer. '
        'Legal thresholds and dates are expressions using grounded public inputs, never factual truth requests. '
        'Use ordinary arithmetic/comparisons, and/or/not and conditional expressions; no imports, loops, tools or arbitrary calls. '
        'Additional declarations must use the supplied source units. If a selected legal subexpression cannot be translated, '
        'leave it unchanged by omitting its replacement; missing semantics stay unresolved. '
        'Only factual_observations may contain current factual truth, with exact evidence or null when unsupported.')
    payload={'selected_source_units':sorted(selected),'charged_context_units':sorted(units),
        'selected_legal_subexpressions':targets,'CURRENT_units':rows,
        'accepted_program':render_pal(program),'factual_observation_tasks':factual_task,
        'runtime_contract':pal_runtime_contract(compiled['source'],library),
        'immutable_accepted_declarations':list(accepted)}
    if not names:factual_rows_schema={'type':'array','maxItems':0,'items':{'type':'null'}}
    schema=obj({'program_lines':{'type':'array','items':{'type':'string'}},'factual_observations':factual_rows_schema})
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],schema,sorted(units)


def _ground_inline_fact_literals(compiled,prepared,fragment):
    """Hoist an existing constant only when exactly one charged fact owns it."""
    before=deepcopy(fragment);structure=compiled['structure'];units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    linked=set(compiled['covered'])|{s for b in compiled['program']['bindings'] for s in b['sources']}
    text='\n'.join(units[s] for s in linked)
    facts={s:_numbers(units[s]) for s in prepared['context_closure'] if structure.roles[s]['role']=='fact'}
    reserved={r['name'] for p in (compiled['program'],fragment) for field,rows in p.items() if field!='query' for r in rows}
    hoisted={};proofs=[]
    def visit(value,syntax=False):
        if type(value) is int and not syntax and not expression_literal_audit(value,text,compiled['source']['dataset'])['pass']:
            owners=[s for s,numbers in facts.items() if value in numbers]
            if len(owners)!=1:return value
            if value not in hoisted:
                index=len(hoisted);name='_fact_literal_'+str(index)
                while name in reserved:index+=1;name='_fact_literal_'+str(index)
                reserved.add(name);hoisted[value]=name
                fragment['bindings'].append({'name':name,'type':'integer','value':value,'sources':owners})
                proofs.append({'kind':'existing_integer_literal_to_explicit_public_input','name':name,'value':value,'source':owners[0]})
            return {'var':hoisted[value]}
        if isinstance(value,dict) and 'op' in value:
            result=deepcopy(value)
            result['args']=[visit(v,(value['op']=='number_at' and i==1) or (value['op']=='scale' and i==0) or
                (value['op'] in {'divide_constant','ceil_divide_constant'} and i==1)) for i,v in enumerate(value['args'])]
            return result
        return value
    for field,keys in [('nodes',('body',)),('scopes',('condition',)),('clauses',('value','otherwise'))]:
        for row in fragment[field]:
            if field=='nodes' and row['kind']!='expression':continue
            for key in keys:row[key]=visit(row[key])
    values={name:value for value,name in hoisted.items()}
    def inline(value):
        if isinstance(value,dict):
            if set(value)=={'var'} and value['var'] in values:return values[value['var']]
            return {k:inline(v) for k,v in value.items()}
        if isinstance(value,list):return [inline(v) for v in value]
        return value
    restored=inline(fragment);restored['bindings']=[r for r in restored['bindings'] if r['name'] not in values]
    if restored!=before:raise Unsupported('Literal adaptation must preserve the exact expression AST after inlining')
    return proofs


def normalize_fact_evidence(compiled,rows):
    result=deepcopy(rows);proofs=[];structure=compiled['structure']
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    for row in result:
        source=compiled['observations'][row['name']]['entity_source'];prefix=source+'#'
        if row['evidence'].startswith(prefix):
            quote=row['evidence'][len(prefix):]
            if quote and quote in units[source]:
                row['evidence']=quote;proofs.append({'kind':'exact_self_source_marker_removed_from_fact_quote','name':row['name'],'source':source})
    return result,proofs


def apply_refinement(compiled,prepared,code,*,library=None):
    functions=[r['name'] for field in ('scopes','clauses') for r in compiled['program'][field]]
    fragment=parse_pal(code,require_query=False,external_functions=functions)
    if 'query' in fragment:raise Unsupported('A local legal refinement cannot replace the accepted query')
    adaptations=_ground_inline_fact_literals(compiled,prepared,fragment)
    program=deepcopy(compiled['program']);selected=set(prepared['selected'])
    allowed=set(prepared['context_closure']);targets={r['name'] for r in program['rule_residuals'] if r['source'] in selected}
    fields=('bindings','observations','rule_residuals','nodes','scopes','clauses')
    old_names={r['name'] for field in fields for r in program[field]}
    replacements=set()
    for field in fields:
        for row in fragment[field]:
            name=row['name']
            if name in old_names:
                if name not in targets or field!='nodes' or row['kind']!='expression':
                    raise Unsupported('A local refinement cannot change accepted declarations: '+name)
                replacements.add(name)
            cited=set(row.get('sources',[]))|{row[k] for k in ('source','entity_source','predicate_source') if k in row}
            if not cited<=allowed:raise Unsupported('A local refinement cites text outside the charged context')
            if field in {'scopes','clauses','rule_residuals'} and not cited&selected:
                raise Unsupported('A new legal declaration must translate a selected source obligation')
    program['rule_residuals']=[r for r in program['rule_residuals'] if r['name'] not in replacements]
    for field in fields:program[field].extend(fragment[field])
    updated=compile_source(compiled['source'],program,library=library)
    # Replacements retain the same Boolean interface. The unchanged parent
    # rule and its real applicability still govern every result.
    compile_query([{k:n[k] for k in ('name','kind','body')} for n in updated['query'].nodes],
        updated['query'].query,updated['slots'],
        domains={name:(False,True) for name in set(updated['observations'])|set(updated['rule_residuals'])},
        boolean_nodes=replacements)
    updated['deterministic_adaptations']=adaptations
    return updated
