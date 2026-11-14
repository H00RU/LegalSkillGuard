"""ContractNLI unlabeled execution and original TRAIN-only learning feedback.

Uses the unchanged native consumer/scorer. It never turns an answer label into
an observed legal fact. Other dataset adapters stay in their existing paths.
"""
from .native import grade_view,source_spans
from .scoped_grammar import constructors,material_public,term_sort
from .scoped_reader import apply_current
from .span_compiler import execution_source_units,expand_unit_support


def contract_checker(spec,source,grading,*,view_ids=None):
    if grading is None:
        raise ValueError('Native scoring requires explicit lawful supervision')
    return _contract_feedback(spec,source,grading,view_ids=view_ids)


def contract_execution(spec,source,*,view_ids=None):
    """Execute native views for coverage without reading any answer labels."""
    return _contract_feedback(spec,source,None,view_ids=view_ids)


def _contract_feedback(spec,source,grading,*,view_ids=None):
    if source['dataset']!='ContractNLI':
        raise ValueError('This execution adapter accepts original ContractNLI only')
    if grading is not None and source['split']!='train':
        raise ValueError('Learning feedback accepts original ContractNLI TRAIN only')
    public=source['views'][0]['public'];text=public['source_text']
    if any(v['public']['source_text']!=text for v in source['views']):
        raise ValueError('Never combine distinct per-view materials')
    spans=source_spans(material_public(public));_,supports=execution_source_units(text,spans)
    schema=constructors(spec);views=[v for v in source['views'] if view_ids is None or v['id'] in view_ids]
    if not views or (view_ids is not None and set(view_ids)!={v['id'] for v in views}):
        raise ValueError('Explicit actual native target views required')
    if grading is not None and not {v['id'] for v in views}<=set(grading):
        raise ValueError('Missing lawful native TRAIN supervision')
    def check(output):
        rows=[];nodes=[]
        try:
            for i,row in enumerate(output['statements']):
                nodes.append({'id':i,'term':row['term'],'sort':term_sort(row['term'],schema),
                    'support_ids':expand_unit_support(row['support_ids'],supports),'child_ids':[],
                    'ambiguous':False,'source_semantics_verified':False})
            interpretation={'nodes':nodes,'roots':list(range(len(nodes))),'complete':output['complete'],
                'source_program_output':{k:output[k] for k in ('statements','complete','unresolved')},
                'unresolved':output['unresolved']}
            for view in views:
                result=apply_current(spec,{'rules':[],'disabled_rules':[],'acquired_pairs':[]},interpretation,view)
                value=result['value'];proof=sorted({spans[s]['public_sentence_id'] for n in value['used_nodes']
                    for s in nodes[n]['support_ids'] if 'public_sentence_id' in spans[s]})
                score=grade_view('ContractNLI',view,grading[view['id']],value['answer'],proof) if value['handled'] and grading is not None else None
                rows.append({'view':view['id'],'execution':result,'score':score,
                    'core_executed':value['handled'],'fallback_not_used_as_a_theory':not value['handled'],
                    'corresponding_source_semantics_certified':False})
        except (ValueError,KeyError,TypeError) as error:
            return {'accepted':False,'reason':'execution_error','error':type(error).__name__+': '+str(error),'views':rows}
        if grading is None:
            return {'accepted':False,'reason':'unscored_execution','views':rows,
                    'native_labels_used':False,'native_correctness_does_not_certify_all_source_semantics':True}
        accepted=all(r['core_executed'] and r['score']['correct'] for r in rows)
        return {'accepted':accepted,'reason':'native_constraints_satisfied' if accepted else 'native_mismatch_or_uncovered',
            'views':rows,'native_correctness_does_not_certify_all_source_semantics':True}
    return check
