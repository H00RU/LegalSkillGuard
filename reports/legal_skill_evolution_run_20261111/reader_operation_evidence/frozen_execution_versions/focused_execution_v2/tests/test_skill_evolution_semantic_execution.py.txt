import json
import unittest

from legal_skill_guard.skill_evolution.semantic_execution import (demand_program,execute,
    focused_messages,operation_groups,answer_schema,decode_answers)
from legal_skill_guard.skill_evolution.semantic_operations import finish


PROGRAM='''def take(answers,qid,op,errors,required):
    a=answers.get(qid)
    if a is None:
        if required:
            errors.append('missing')
        return None
    if a['choice']=='unknown':
        errors.append('unknown')
        return None
    return a['choice']

def apply(inputs,premises):
    if inputs['phase']=='plan':
        return {'queries':[{'id':'gate','operation':'gate','unit_ids':[4]},
                           {'id':'value','operation':'value','unit_ids':[4]}]}
    answers={a['id']:a for a in inputs['semantic_answers']}
    errors=[]
    gate=take(answers,'gate','gate',errors,True)
    statements=[]
    if gate=='need':
        value=take(answers,'value','value',errors,True)
        if value is not None:
            statements.append({'term':['result',value],'support_ids':[4]})
    return {'statements':statements,'complete':not errors,'unresolved':errors}
'''
OPS=[{'name':'gate','question':'Neutral branch decision',
      'choices':[{'name':s,'meaning':s} for s in ['need','skip']],'examples':[]},
     {'name':'value','question':'Neutral value reading',
      'choices':[{'name':'found','meaning':'found'}],'examples':[]}]
UNITS=[{'id':4,'text':'current words'}]
BUNDLE={'program':PROGRAM,'operations':OPS}


class OracleClient:
    def __init__(self,gate): self.gate=gate;self.queries=[]
    def generate(self,*args,**kwargs):
        self.assert_off=kwargs['thinking'] is False
        content=json.loads(kwargs['messages'][1]['content']);answers={}
        for q in content['current_queries']:
            self.queries.append(q['id']);choice=self.gate if q['id']=='gate' else 'found'
            answers[q['id']]={'choice':choice,
                            'evidence':[] if choice=='unknown' else [{'unit_id':4,'quote':'current'}]}
        return {'finish_reason':'stop','content':json.dumps({'answers':answers}),'mock_not_physical':True}


class SemanticExecutionTests(unittest.TestCase):
    def test_duplicate_conflicting_query_keys_are_rejected(self):
        q=[{'id':'gate','operation':'gate','unit_ids':[4]}]
        raw='{"answers":{"gate":{"choice":"need","evidence":[]},"gate":{"choice":"unknown","evidence":[]}}}'
        with self.assertRaisesRegex(ValueError,'Duplicate JSON object key'):
            decode_answers(OPS,q,UNITS,raw)

    def test_fixed_query_identity_choice_and_quote_constraints(self):
        import jsonschema
        q=[{'id':'gate','operation':'gate','unit_ids':[4]}]
        for value in [{'answers':{}},{'answers':{'other':{'choice':'need','evidence':[]}}},
                      {'answers':{'gate':{'choice':'fabricated','evidence':[]}}}]:
            with self.assertRaises(jsonschema.ValidationError):
                decode_answers(OPS,q,UNITS,json.dumps(value))
        for evidence in [[],[{'unit_id':5,'quote':'current'}],[{'unit_id':4,'quote':'not present'}]]:
            with self.assertRaises(ValueError):
                decode_answers(OPS,q,UNITS,json.dumps({'answers':{'gate':{'choice':'need','evidence':evidence}}}))

    def test_skip_does_not_acquire_unread_value(self):
        client=OracleClient('skip');result=execute(client,'run','source',BUNDLE,'',UNITS,
                                                 scope='window',lookup='take')
        self.assertEqual(client.queries,['gate'])
        eager=[{'id':'gate','operation':'gate','choice':'skip'},
               {'id':'value','operation':'value','choice':'found'}]
        self.assertEqual(result['source_output'],finish(PROGRAM,'',UNITS,eager))
        self.assertEqual(result['unread_queries'],1)

    def test_positive_demand_follows_actual_control_flow(self):
        client=OracleClient('need');result=execute(client,'run','source',BUNDLE,'',UNITS,
                                                 scope='focus_last',lookup='take')
        self.assertEqual(client.queries,['gate','value'])
        self.assertEqual(result['demand_rounds'],[['gate'],['value']])
        self.assertEqual(result['source_output']['statements'][0]['term'],['result','found'])
        self.assertTrue(client.assert_off)

    def test_unknown_is_terminal_without_default_or_resampling(self):
        client=OracleClient('unknown');result=execute(client,'run','source',BUNDLE,'',UNITS,
                                                    scope='window',lookup='take')
        self.assertEqual(client.queries,['gate'])
        self.assertEqual(result['source_output']['statements'],[])
        self.assertEqual(result['source_output']['unresolved'],['unknown'])

    def test_probe_preserves_original_body_for_complete_inputs(self):
        probe=demand_program(PROGRAM,'take')
        for gate in ['need','skip','unknown']:
            answers=[{'id':'gate','operation':'gate','choice':gate},
                     {'id':'value','operation':'value','choice':'found'}]
            self.assertEqual(finish(probe,'',UNITS,answers),finish(PROGRAM,'',UNITS,answers))

    def test_eager_mode_is_available_for_other_acquired_programs(self):
        client=OracleClient('skip');result=execute(client,'run','source',BUNDLE,'',UNITS,scope='window')
        self.assertEqual(client.queries,['gate','value'])
        self.assertEqual(result['unread_queries'],0)

    def test_groups_preserve_all_query_identities_and_separate_operations(self):
        queries=[{'id':str(i),'operation':'a' if i%2 else 'b'} for i in range(30)]
        groups=operation_groups(queries)
        self.assertEqual({q['id'] for batch in groups for q in batch},{q['id'] for q in queries})
        self.assertEqual(sum(map(len,groups)),30)
        self.assertTrue(all(len({q['operation'] for q in batch})==1 and len(batch)<=12 for batch in groups))

    def test_window_mode_does_not_silently_change_acquired_scope(self):
        q=[{'id':'q','operation':'gate','unit_ids':[4]}]
        prompt=focused_messages(OPS,q,UNITS,scope='window')
        self.assertNotIn('focus_unit_id',prompt[1]['content'])
        with self.assertRaises(ValueError):focused_messages(OPS,q,UNITS,scope='guessed')

    def test_nonopaque_answer_access_does_not_get_lazy_equivalence_claim(self):
        program=PROGRAM.replace("    errors=[]\n", "    count=len(answers)\n    errors=[]\n")
        with self.assertRaisesRegex(ValueError,'outside the declared lookup'):
            demand_program(program,'take')
