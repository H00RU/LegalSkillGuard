import json
import unittest

from legal_skill_guard.skill_evolution.residual_reader import execute,residual_answers
from test_skill_evolution_semantic_execution import OracleClient as QuotedOracle,PROGRAM,OPS,UNITS,BUNDLE

class OracleClient(QuotedOracle):
    def generate(self,*args,**kwargs):
        result=super().generate(*args,**kwargs)
        value=json.loads(result['content'])
        for a in value['answers'].values():
            a['support_ids']=[w['unit_id'] for w in a.pop('evidence')]
        result['content']=json.dumps(value)
        return result

MONITOR='''def apply(inputs,premises):
    changes=[]
    for a in inputs['semantic_answers']:
        if a['id']=='gate' and a['choice']=='skip':
            changes.append({'id':'gate','choice':'need','evidence':[{'unit_id':4,'quote':'current'}]})
    return {'corrections':changes}
'''

class ResidualTests(unittest.TestCase):
    def test_real_new_branch_demands_are_executed_after_correction(self):
        client=OracleClient('skip')
        r=execute(client,'r','s',BUNDLE,'',UNITS,scope='window',lookup='take',monitor=MONITOR)
        self.assertEqual(client.queries,['gate','value'])
        self.assertEqual(r['source_output']['statements'][0]['term'],['result','found'])
        self.assertEqual(r['learned_corrections'],1)
        change=next(e for e in r['events'] if e['kind']=='residual')['changes'][0]
        self.assertEqual(change['before']['choice'],'skip')
        self.assertEqual(change['after']['choice'],'need')

    def test_no_monitor_preserves_old_reading(self):
        client=OracleClient('skip')
        r=execute(client,'r','s',BUNDLE,'',UNITS,scope='window',lookup='take')
        self.assertEqual(client.queries,['gate']);self.assertEqual(r['learned_corrections'],0)
        self.assertEqual(r['source_output']['statements'],[])

    def test_unobserved_query_cannot_be_fabricated(self):
        code=MONITOR.replace("a['id']=='gate'","a['id']=='gate'").replace("'id':'gate'","'id':'value'")
        with self.assertRaisesRegex(ValueError,'no invented observations'):
            execute(OracleClient('skip'),'r','s',BUNDLE,'',UNITS,scope='window',lookup='take',monitor=code)

    def test_bad_choice_and_quote_are_rejected(self):
        for code in [MONITOR.replace("'choice':'need'","'choice':'invented'"),
                     MONITOR.replace("'quote':'current'","'quote':'absent'")]:
            with self.assertRaises(ValueError):
                execute(OracleClient('skip'),'r','s',BUNDLE,'',UNITS,scope='window',lookup='take',monitor=code)

    def test_unknown_is_not_coerced_by_host(self):
        r=execute(OracleClient('unknown'),'r','s',BUNDLE,'',UNITS,scope='window',lookup='take',monitor=MONITOR)
        self.assertEqual(r['learned_corrections'],0);self.assertEqual(r['source_output']['statements'],[])

    def test_nonequiv_change_without_quotes_does_not_pass(self):
        code=MONITOR.replace("[{'unit_id':4,'quote':'current'}]","[]")
        with self.assertRaisesRegex(ValueError,'needs current evidence'):
            execute(OracleClient('skip'),'r','s',BUNDLE,'',UNITS,scope='window',lookup='take',monitor=code)

    def test_restored_valid_observations_are_not_requested_again(self):
        initial=[{'id':'gate','choice':'need','evidence':[{'unit_id':4,'quote':'current'}]}]
        client=OracleClient('skip')
        r=execute(client,'r','s',BUNDLE,'',UNITS,scope='window',lookup='take',initial_observations=initial)
        self.assertEqual(client.queries,['value']);self.assertEqual(r['restored_observation_count'],1)
        self.assertEqual(r['source_output']['statements'][0]['term'],['result','found'])

    def test_bad_restored_quote_is_still_rejected(self):
        initial=[{'id':'gate','choice':'need','evidence':[{'unit_id':4,'quote':'made up'}]}]
        with self.assertRaisesRegex(ValueError,'Nonverbatim'):
            execute(OracleClient('skip'),'r','s',BUNDLE,'',UNITS,scope='window',lookup='take',initial_observations=initial)
