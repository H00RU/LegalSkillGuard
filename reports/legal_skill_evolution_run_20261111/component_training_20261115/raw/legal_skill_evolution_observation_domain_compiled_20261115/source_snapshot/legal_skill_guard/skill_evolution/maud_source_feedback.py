"""Execute learned source rules on one original MAUD material at a time.

No extraction rule, answer mapping or target enters this adapter. It supplies
the unchanged native view schema/scorer and checks the actual typed proof.
"""
import jsonschema

from .native import grade_view,record_schema,source_spans
from .open_acquisition import execute
from .scoped_grammar import constructors,material_public,term_sort
from .scoped_source_program import OUTPUT
from .span_compiler import execute_json,execution_source_units


def view_units(view):
    return execution_source_units(view['public']['source_text'],
                                  source_spans(material_public(view['public'])))[0]


def evaluate_view(library,observation,source,view,annotation=None):
    """Use only the supplied view; annotation=None performs unscored execution."""
    if source['split']!='train' or source['dataset']!='MAUD':
        raise ValueError('This adapter accepts only original MAUD TRAIN materials')
    matches=[v for v in source['views'] if v['id']==view['id']]
    if len(matches)!=1 or matches[0]!=view:
        raise ValueError('Use the exact current native view')
    v=observation['visible_inputs']
    if v['source_text']!=view['public']['source_text'] or v['units']!=view_units(view):
        raise ValueError('Distinct native materials must not be joined or substituted')
    try:
        if 'language' in library:
            executed=execute(library,observation);output=executed['source_output']
        else:
            output=execute_json(library['composition_program'],{
                'source_text':v['source_text'],'source_spans':v['units'],
                'source_output':v['source_output'],'semantic_answers':v['answers']},{},allow_helpers=True)
            executed={'source_output':output}
        jsonschema.validate({k:output[k] for k in ('statements','complete','unresolved')},OUTPUT)
        schema=constructors(library['spec']);current={u['id'] for u in v['units']};nodes=[]
        for i,row in enumerate(output['statements']):
            if not isinstance(row['term'],list):raise ValueError('Raw text is not a source-rule root')
            if not set(row['support_ids'])<=current:raise ValueError('Proof cites a noncurrent view unit')
            nodes.append({'id':i,'term':row['term'],'sort':term_sort(row['term'],schema),
                          'support_ids':row['support_ids'],'child_ids':[],'ambiguous':False,
                          'source_semantics_verified':False})
        interpretation={'nodes':nodes,'roots':list(range(len(nodes))),
            'complete':output['complete'],'unresolved':output['unresolved']}
        decision=execute_json(library['spec']['decision_program'],
            {'task_id':view['id'],'question':view['public']['question']},interpretation,allow_helpers=True)
        result_schema=record_schema({'handled':{'type':'boolean'},
            'answer':{'anyOf':[view['answer_schema'],{'type':'null'}]},
            'used_nodes':{'type':'array','uniqueItems':True,'items':{'type':'integer','minimum':0}}})
        jsonschema.validate(decision,result_schema)
        if not set(decision['used_nodes'])<=set(interpretation['roots']):
            raise ValueError('Consumer proof names a noncurrent source-rule root')
        if decision['handled'] and (decision['answer'] is None or not decision['used_nodes']):
            raise ValueError('A core answer requires actual typed source-rule evidence')
        score=grade_view('MAUD',view,annotation,decision['answer']) if annotation is not None and decision['handled'] else None
        row={'view':view['id'],'execution':{'value':decision},'score':score,
            'core_executed':decision['handled'],'corresponding_source_semantics_certified':False}
        feedback={'accepted':bool(score and score['correct']),
            'reason':'unscored_execution' if annotation is None else
                'native_constraints_satisfied' if score and score['correct'] else 'native_mismatch_or_uncovered',
            'native_labels_used':annotation is not None,'views':[row],
            'native_correctness_does_not_certify_all_source_semantics':True}
        return {'execution':executed,'feedback':feedback}
    except (ValueError,KeyError,TypeError,jsonschema.ValidationError) as error:
        return {'feedback':{'accepted':False,'reason':'execution_error','views':[],
            'error':type(error).__name__+': '+str(error),'native_labels_used':annotation is not None}}


def view_checker(spec,source,view,annotation):
    """Native theory callback for exact finite G learning on this view only."""
    if annotation is None:raise ValueError('G supervision must be explicit lawful TRAIN feedback')
    def check(output):
        # Execute the already-rendered theory through the same acquired
        # consumer without changing its terms, proof or native scoring.
        from .source_observations import encode_source_observations
        observation=encode_source_observations(source['key'],source_text=view['public']['source_text'],
            units=view_units(view),source_output=output,operations=[],queries=[],answers=[],scope='window')
        library={'spec':spec,'composition_program':
                 'def apply(inputs,premises):\n    return inputs["source_output"]\n'}
        return evaluate_view(library,observation,source,view,annotation)['feedback']
    return check
