"""Typed finite relational hypotheses for source-conditioned rule acquisition.

No legal rule or native label is supplied here. Predicates, static semantic
vocabulary and candidate compositions are learned assets. Context namespaces
isolate laws; they cannot be inspected or memorized by a candidate rule.
Only positive heads and explicit positive/negative body observations are used.
Absence of an observation is never compiled into a negative factual literal.
"""
import json
import re

from .objects import digest

PREFIX = 'lsg_internal_'
CONTEXT = 'LSGContext'


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def _name(value,variable=False):
    pattern=r'[A-Z][A-Za-z0-9_]*' if variable else r'[a-z][a-z0-9_]*'
    if not isinstance(value,str) or not re.fullmatch(pattern,value):
        raise ValueError('Explicit relational identifier required')
    if value.startswith(PREFIX) or value==CONTEXT:
        raise ValueError('Reserved solver identity')


def _variable(term):
    if isinstance(term,dict):
        if set(term)!={'var'}:
            raise ValueError('A variable is exactly a var record')
        _name(term['var'],True)
        return term['var']
    if type(term) not in (str,int,float,bool):
        raise ValueError('Ground terms are JSON scalars; unknown is not a fact')
    canonical(term)
    return None


def check_atom(atom,signatures,*,ground=False,variable_types=None,constants=None):
    predicate=atom['predicate'];_name(predicate)
    if predicate not in signatures or atom['sign'] not in ('positive','negative'):
        raise ValueError('Declared predicate and explicit factual polarity required')
    signature=signatures[predicate]
    if len(atom['arguments'])!=len(signature['arguments']):
        raise ValueError('Relation arity differs from its learned declaration')
    variables=set()
    for term,sort in zip(atom['arguments'],signature['arguments']):
        name=_variable(term)
        if name:
            if ground:
                raise ValueError('A case observation or constraint must be grounded')
            if name in variable_types and variable_types[name]!=sort:
                raise ValueError('A shared variable has incompatible nominal types')
            variable_types[name]=sort;variables.add(name)
        elif constants is not None and canonical(term) not in {canonical(x) for x in constants.get(sort,[])}:
            raise ValueError('Composition constant is not in the learned static vocabulary')
    return variables


def validate_language(language):
    signatures=language['signatures'];constants=language['constants'];seen=set()
    for name,signature in signatures.items():
        _name(name)
        if signature['kind'] not in ('observed','derived','output') or not isinstance(signature['arguments'],list):
            raise ValueError('Explicit source relation kind and argument sorts required')
        if any(not isinstance(sort,str) or not sort for sort in signature['arguments']):
            raise ValueError('Nominal argument sorts required')
    for values in constants.values():
        if not isinstance(values,list) or len({canonical(x) for x in values})!=len(values):
            raise ValueError('Static vocabulary must be a finite distinct list')
        for value in values:
            if _variable(value):raise ValueError('Static vocabulary cannot contain a variable')
    for rule in language['rules']:
        identity=rule['id']
        if not isinstance(identity,str) or not identity or identity in seen:
            raise ValueError('Distinct learned rule identifiers required')
        seen.add(identity)
        if type(rule['cost']) is not int or rule['cost']<1:
            raise ValueError('A positive frozen hypothesis cost is required')
        if not rule['body']:
            raise ValueError('A source composition needs actual observed/derived support')
        types={};positive=set()
        for atom in rule['body']:
            variables=check_atom(atom,signatures,variable_types=types,constants=constants)
            # Strongly negative observations also bind variables. They are
            # ground evidence, unlike default negation of an absent relation.
            positive|=variables
            if atom['sign']=='negative' and signatures[atom['predicate']]['kind']!='observed':
                raise ValueError('Only explicit negative observations are supported, not missing derived facts')
        head=rule['head']
        if head['sign']!='positive' or signatures[head['predicate']]['kind']=='observed':
            raise ValueError('Rules cannot overwrite source observations or introduce negative defaults')
        head_variables=check_atom(head,signatures,variable_types=types,constants=constants)
        all_variables=set(types)
        if not (all_variables|head_variables)<=positive:
            raise ValueError('Every variable must be range-restricted by a positive body relation')
    return language


def validate_context(context,language):
    signatures=language['signatures'];identity=context['id']
    if not isinstance(identity,str) or not identity:
        raise ValueError('Current-source context identity required')
    for atom in context['facts']:
        check_atom(atom,signatures,ground=True)
        if signatures[atom['predicate']]['kind']!='observed':
            raise ValueError('Source input cannot silently precompute a derived output')
    for group in context['unknown_groups']:
        if not group or any(not isinstance(branch,list) for branch in group):
            raise ValueError('Unknown needs an explicit nonempty finite set of possible observation branches')
        for branch in group:
            for atom in branch:
                check_atom(atom,signatures,ground=True)
                if signatures[atom['predicate']]['kind']!='observed':
                    raise ValueError('A possible observation is not a derived legal conclusion')
    for field in ('required','forbidden'):
        for atom in context[field]:
            check_atom(atom,signatures,ground=True)
            if signatures[atom['predicate']]['kind']!='output' or atom['sign']!='positive':
                raise ValueError('Partial supervision constrains explicit source-output relations')
    if 'theory_constraints' in context:
        value=context['theory_constraints']
        if value['status']!='complete' or value['language_sha256']!=language_identity(language) \
                or value['context_sha256']!=context_identity(context):
            raise ValueError('Admissible theories must be complete and bound to current language/observations/constraints')
        vocabulary={canonical(a) for a in value['vocabulary']}
        for a in value['vocabulary']:
            check_atom(a,signatures,ground=True)
            if signatures[a['predicate']]['kind']!='output' or a['sign']!='positive':
                raise ValueError('A theory is a set of grounded output relations')
        for theory in value['allowed_theories']:
            if len({canonical(a) for a in theory})!=len(theory) or any(canonical(a) not in vocabulary for a in theory):
                raise ValueError('Allowed theory lies outside the frozen grounded vocabulary')
        if value.get('optimization')=='native_loss':
            seen=set()
            for row in value['scored_theories']:
                theory=row['theory'];key=canonical(sorted(theory,key=canonical))
                if key in seen or type(row['native_loss']) is not int or row['native_loss']<0:
                    raise ValueError('Distinct completely checked theories with nonnegative integer native loss required')
                seen.add(key)
                if len({canonical(a) for a in theory})!=len(theory) or any(canonical(a) not in vocabulary for a in theory):
                    raise ValueError('Scored theory lies outside the frozen output vocabulary')
    return context


def context_identity(context):
    return digest({k:context[k] for k in ('id','facts','unknown_groups','required','forbidden')})


def term(value):
    import clingo
    name=_variable(value)
    return name if name else str(clingo.String(canonical(value)))


def atom_text(atom,context):
    sign='-' if atom['sign']=='negative' else ''
    args=[str(context)]+[term(t) for t in atom['arguments']]
    return sign+atom['predicate']+'('+','.join(args)+')'


def rule_text(rule,index,*,selectable):
    body=[atom_text(a,CONTEXT) for a in rule['body']]
    body.insert(0,PREFIX+'context('+CONTEXT+')')
    if selectable:body.append(PREFIX+'take('+str(index)+')')
    return atom_text(rule['head'],CONTEXT)+' :- '+','.join(body)+'.'


def observation_program(context,index,*,world=None):
    lines=[PREFIX+'context('+str(index)+').']
    lines += [atom_text(a,index)+'.' for a in context['facts']]
    for group_number,branches in enumerate(context['unknown_groups']):
        if world is not None:
            lines += [atom_text(a,index)+'.' for a in branches[world[group_number]]]
            continue
        choices=[PREFIX+'alternative('+','.join(map(str,(index,group_number,j)))+')' for j in range(len(branches))]
        lines.append('1 {'+';'.join(choices)+'} 1.')
        for choice,branch in zip(choices,branches):
            lines += [atom_text(a,index)+' :- '+choice+'.' for a in branch]
    return '\n'.join(lines)


def output_projection(language):
    lines=['#show '+PREFIX+'alternative/3.','#show '+PREFIX+'take/1.']
    lines += ['#show '+name+'/'+str(len(s['arguments'])+1)+'.'
              for name,s in language['signatures'].items() if s['kind']=='output']
    return '\n'.join(lines)


def decode_outputs(symbols,language):
    import clingo
    rows=[]
    for text in symbols:
        symbol=clingo.parse_term(text)
        if symbol.name not in language['signatures'] or language['signatures'][symbol.name]['kind']!='output':
            continue
        rows.append({'context_index':symbol.arguments[0].number,'predicate':symbol.name,
            'arguments':[json.loads(t.string) for t in symbol.arguments[1:]],'sign':'positive'})
    return sorted(rows,key=canonical)


def language_identity(language):
    validate_language(language)
    return digest(language)
