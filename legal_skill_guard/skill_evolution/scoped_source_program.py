"""Execute the acquired source compiler on current text and typed scope nodes."""
import jsonschema

from .native import source_spans, record_schema
from .scoped_grammar import material_public, parse, current_scope_nodes, constructors, term_sort, subterms
from .scoped_reader import match_template
from .span_compiler import execute_json, occurrences


OUTPUT = record_schema({'statements': {'type':'array','items':record_schema({
    'term': {'type':['array','string']},
    'support_ids': {'type':'array','minItems':1,'uniqueItems':True,
                    'items':{'type':'integer','minimum':0}}})},
    'complete':{'type':'boolean'}, 'unresolved':{'type':'array','items':{'type':'string'}}})


def run_source(program, spec, grammar, source):
    public=material_public(source['views'][0]['public']);text=public['source_text'];spans=source_spans(public)
    scope_nodes=current_scope_nodes(grammar,text)
    matched=parse(grammar,text)
    scoped={(n['start'],n['end'],n['sort']) for n in scope_nodes}
    grounded=[n for n in matched if not n['ambiguous'] and (n['start'],n['end'],n['sort']) not in scoped]
    raw=execute_json(program, {'source_text':text,'source_spans':spans},
        {'grammar_nodes':grounded,'scope_nodes':scope_nodes,'scope_patterns':grammar.get('scope_patterns',[])},
        allow_helpers=True)
    jsonschema.validate(raw,OUTPUT)
    schema=constructors(spec);nodes=[]
    for i,row in enumerate(raw['statements']):
        if not isinstance(row['term'],list):raise ValueError('Raw text is not a source interpretation')
        sort=term_sort(row['term'],schema)
        if any(s>=len(spans) for s in row['support_ids']):raise ValueError('Absent source compiler witness')
        evidence=' '.join(spans[s]['text'] for s in row['support_ids'])
        audits=[]
        for path,t in subterms(row['term']):
            if isinstance(t,str):audits.append({'path':list(path),'value':t,
                'verbatim_in_cited_source':bool(occurrences(evidence,t)),'semantic_support_verified':False})
        nodes.append({'id':i,'sort':sort,'term':row['term'],'support_ids':row['support_ids'],
                      'child_ids':[],'ambiguous':False,'text_argument_audit':audits,
                      'source_semantics_verified':False})
    scope_matches=[]
    for node in scope_nodes:
        pattern=next(p for p in grammar['scope_patterns'] if p['id']==node['pattern_id'])
        # Reuse the generic template matcher; scope variables have distinct
        # storage spelling but the same acquired type/binding discipline.
        def pattern_term(value):
            if isinstance(value,dict):return {'$':value['$scope']}
            if isinstance(value,list):return [pattern_term(t) for t in value]
            return value
        template=pattern_term(pattern['template'])
        uses=[]
        for n in nodes:
            terms=[n['term'],*(t for _,t in subterms(n['term']))]
            if any(match_template(template,t,pattern['inherited_sorts'],schema) for t in terms):uses.append(n['id'])
        scope_matches.append({'scope_node':node['id'],'pattern_id':node['pattern_id'],
                              'root_matches':uses,'structural_match_not_causal_proof':True})
    return {'nodes':nodes,'roots':[n['id'] for n in nodes], 'complete':raw['complete'],
            'unresolved':raw['unresolved'],'source_program_output':raw,
            'current_grammar_nodes':grounded,'current_scope_nodes':scope_nodes,
            'scope_matches':scope_matches}, {'kind':'EXECUTE_ACQUIRED_SOURCE_COMPILER',
                'new_physical_calls':0,'source_semantics_verified':False}
