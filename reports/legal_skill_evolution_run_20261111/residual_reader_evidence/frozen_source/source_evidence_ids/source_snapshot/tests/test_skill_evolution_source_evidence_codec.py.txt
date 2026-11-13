import json
import unittest
import jsonschema
from legal_skill_guard.skill_evolution.source_evidence_codec import decode,messages,schema
from test_skill_evolution_semantic_execution import OPS,UNITS

Q=[{'id':'q','operation':'gate','unit_ids':[4]}]

class EvidenceCodecTests(unittest.TestCase):
    def test_exact_text_is_attached_without_new_semantics(self):
        raw={'answers':{'q':{'choice':'need','support_ids':[4]}}}
        _,rows=decode(OPS,Q,UNITS,json.dumps(raw))
        self.assertEqual(rows[0]['choice'],'need')
        self.assertEqual(rows[0]['evidence'][0]['quote'],UNITS[0]['text'])
        self.assertFalse(rows[0]['source_semantics_verified'])

    def test_false_source_identity_and_unwitnessed_definite_value_fail(self):
        for ids in [[5],[]]:
            with self.assertRaises((ValueError,jsonschema.ValidationError)):
                decode(OPS,Q,UNITS,json.dumps({'answers':{'q':{'choice':'need','support_ids':ids}}}))

    def test_unknown_is_not_filled_with_an_implicit_negative(self):
        _,rows=decode(OPS,Q,UNITS,json.dumps({'answers':{'q':{'choice':'unknown','support_ids':[]}}}))
        self.assertEqual(rows[0]['choice'],'unknown');self.assertEqual(rows[0]['evidence'],[])

    def test_duplicate_support_ids_remain_host_rejected(self):
        with self.assertRaisesRegex(ValueError,'Repeated'):
            decode(OPS,Q,UNITS,json.dumps({'answers':{'q':{'choice':'need','support_ids':[4,4]}}}))

    def test_prompt_changes_only_output_mechanics(self):
        prompt=messages(OPS,Q,UNITS,scope='focus_last')
        self.assertIn('Missing information is unknown',prompt[0]['content'])
        self.assertIn('support_ids instead of copying text',prompt[0]['content'])
        self.assertNotIn('For every non-unknown choice, quote',prompt[0]['content'])
        self.assertEqual(json.loads(prompt[1]['content'])['current_queries'][0]['focus_unit_id'],4)
