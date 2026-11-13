"""Render acquired relational outputs into current-source typed terms.

Output templates are learned assets. The host supplies substitution, provenance
containment and existing constructor checks, never a missing legal rule.
"""
from copy import deepcopy

from .relational_rules import canonical, validate_language
from .scoped_grammar import constructors, term_sort


def validate_renderers(language, renderers):
    validate_language(language)
    signatures=language['signatures'];seen=set()
    for renderer in renderers:
        name=renderer['predicate']
        if name in seen or name not in signatures or signatures[name]['kind']!='output' or name=='keep_root':
            raise ValueError('Each constructed output needs one learned renderer')
        seen.add(name);sorts=signatures[name]['arguments'];used=set()
        def visit(value):
            if isinstance(value,dict):
                if set(value) not in ({'term_argument'},{'scalar_argument'}):
                    raise ValueError('Explicit term/scalar argument substitution required')
                key=next(iter(value));i=value[key]
                if type(i) is not int or i<0 or i>=len(sorts):raise ValueError('Renderer argument out of range')
                if (sorts[i]=='term') != (key=='term_argument'):
                    raise ValueError('A current term identity cannot become an invented scalar or vice versa')
                used.add(i)
            elif isinstance(value,list):
                if not value or not isinstance(value[0],str):raise ValueError('An output template needs its acquired constructor')
                for child in value[1:]:visit(child)
            else:
                raise ValueError('Source-dependent scalars must be bound from current input, not stored in a renderer')
        visit(renderer['term'])
        for field,sort in (('support_arguments','unit'),('support_from_terms','term')):
            if len(set(renderer[field]))!=len(renderer[field]):raise ValueError('Distinct provenance argument positions required')
            for i in renderer[field]:
                if type(i) is not int or i<0 or i>=len(sorts) or sorts[i]!=sort:
                    raise ValueError('Provenance must name a current unit or term argument')
                used.add(i)
        if not renderer['support_arguments'] and not renderer['support_from_terms']:
            raise ValueError('Constructed norms need current-source provenance')
        if used!=set(range(len(sorts))):raise ValueError('Unused output arguments hide distinctions from rendering')
    outputs={p for p,s in signatures.items() if s['kind']=='output'}-{'keep_root'}
    if seen!=outputs:raise ValueError('Every acquired output relation needs its declared renderer')
    if 'keep_root' in signatures and signatures['keep_root']!={'arguments':['term'],'kind':'output'}:
        raise ValueError('The public retain operation selects actual legacy roots')


def render_composition(language, renderers, encoded, result, spec):
    validate_renderers(language,renderers)
    if result['status']!='sat' or not result['complete']:
        raise ValueError('An incomplete solver result is not an executable source theory')
    by_name={r['predicate']:r for r in renderers};rows=[];uses=[]
    current_units={u['id'] for u in encoded['visible_inputs']['units']};schema=constructors(spec)
    def add(row,use):
        term_sort(row['term'],schema)
        if not row['support_ids'] or not set(row['support_ids'])<=current_units:
            raise ValueError('Rendered theory lacks actual current-source support')
        # Coalesce only identical terms/provenance, not similar legal entities.
        row={'term':row['term'],'support_ids':sorted(set(row['support_ids']))}
        if canonical(row) not in {canonical(r) for r in rows}:rows.append(row)
        uses.append(use)
    for output in result['certain_outputs']:
        if output.get('context_index',0)!=0:raise ValueError('Render one current-source context at a time')
        name=output['predicate'];args=output['arguments']
        if len(args)!=len(language['signatures'][name]['arguments']):raise ValueError('Output arity mismatch')
        if name=='keep_root':
            identity,=args
            if identity not in encoded['legacy_roots']:raise ValueError('Not an actual current root')
            add(deepcopy(encoded['legacy_roots'][identity]),{'predicate':name,'arguments':args,'retained_old_root':True})
            continue
        renderer=by_name[name]
        def instantiate(value):
            if isinstance(value,dict):
                if 'term_argument' in value:
                    identity=args[value['term_argument']]
                    if identity not in encoded['term_nodes']:raise ValueError('No current term at bound identity')
                    return deepcopy(encoded['term_nodes'][identity])
                return deepcopy(args[value['scalar_argument']])
            return [value[0],*(instantiate(v) for v in value[1:])]
        supports=[args[i] for i in renderer['support_arguments']]
        if any(type(u) is not int for u in supports):raise ValueError('A unit anchor is an actual integer identity')
        for i in renderer['support_from_terms']:
            if args[i] not in encoded['term_supports']:raise ValueError('Not a current term provenance')
            supports.extend(encoded['term_supports'][args[i]])
        add({'term':instantiate(renderer['term']),'support_ids':supports},
            {'predicate':name,'arguments':args,'retained_old_root':False})
    return {'statements':rows,'complete':False,
        'unresolved':deepcopy(encoded['visible_inputs']['source_output']['unresolved']),
        'composition_uses':uses,'source_semantics_verified':False,
        'possible_output_count':len(result['possible_outputs']),
        'unknown_observations_preserved':deepcopy(result['unknown_observations_preserved'])}
