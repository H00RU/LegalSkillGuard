"""Source scope containment, finite concepts and executable unknown guards."""
from copy import deepcopy
import unittest

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.relational_compiler import (
    SCHEMA, compile_skill, bind_records, read_schema)
from legal_skill_guard.skill_evolution.span_compiler import execute
from legal_skill_guard.skill_evolution.runtime import decoder_schema


def fixture():
    return {'kind':'relational_rule','rationale':'Synthetic codec fixture, not legal performance.',
        'frames':[{'name':'transfer','meaning':'An explicitly stated transfer relation.',
            'fields':[{'name':'owner','meaning':'The recipient owner stated by this relation.',
                'type':'string','domain':['same_actor','other_actor']},
                {'name':'roles','meaning':'The expressly covered role set.',
                    'type':'array','domain':['worker','partner']}]}],
        'source_examples':[], 'procedure':'def apply(inputs, premises):\n    r = premises["records"][0]\n    return {"handled": r["values"]["owner"] == "same_actor", "answer": "Entailment", "used_records": [0]}\n',
        'policy_text':None}


class RelationalCompilerChecks(unittest.TestCase):
    def test_schema_and_no_label_valued_source_fields(self):
        spec=fixture();self.assertEqual(strict_output_schema_issues(SCHEMA), [])
        compile_skill(spec, {}, restricted=True)
        self.assertEqual(strict_output_schema_issues(decoder_schema(read_schema(spec,[{'id':0}]))[0]), [])
        spec['frames'][0]['fields'][0]['domain']=['Entailment']
        with self.assertRaises(ValueError):compile_skill(spec, {}, restricted=True)

    def test_fields_cannot_take_evidence_from_an_unrelated_action(self):
        spans=[{'id':0,'text':'Actor passes data to its workers.'},
               {'id':1,'text':'Other actor owns partners.'}]
        value={'transfer':[{'support_ids':[0],'fields':{
            'owner':{'value':'same_actor','support_ids':[0]},
            'roles':{'value':['worker'],'support_ids':[1]}}}]}
        with self.assertRaises(ValueError):bind_records(fixture(),spans,value)
        value['transfer'][0]['fields']['roles']['support_ids']=[0]
        records=bind_records(fixture(),spans,value)
        self.assertEqual(records[0]['values']['roles'], ['worker'])
        self.assertFalse(records[0]['relation_semantics_verified'])

    def test_semantic_fields_can_share_actual_evidence_without_substring_ambiguity(self):
        spans=[{'id':0,'text':'Actor passes data to its workers.'}]
        value={'transfer':[{'support_ids':[0],'fields':{
            'owner':{'value':'same_actor','support_ids':[0]},
            'roles':{'value':['worker'],'support_ids':[0]}}}]}
        records=bind_records(fixture(),spans,value)
        self.assertTrue(execute(fixture()['procedure'],{}, {'records':records})['handled'])

    def test_unknown_is_omitted_and_cannot_turn_into_default_or_absence(self):
        spans=[{'id':0,'text':'Actor passes data to workers of unresolved ownership.'}]
        value={'transfer':[{'support_ids':[0],'fields':{
            'owner':{'value':None,'support_ids':[]},'roles':{'value':['worker'],'support_ids':[0]}}}]}
        records=bind_records(fixture(),spans,value)
        self.assertNotIn('owner',records[0]['values'])
        self.assertEqual(records[0]['unresolved_fields'],['owner'])
        for expression in ['r["values"]["owner"] == "same_actor"',
                'r["values"].get("owner", "same_actor") == "same_actor"',
                '"owner" not in r["values"]', 'not r["values"]',
                '"same_actor" in str(r["values"])',
                'r["values"].pop("owner", "same_actor") == "same_actor"']:
            code='def apply(inputs, premises):\n    r = premises["records"][0]\n    return {"handled": '+expression+', "answer": "Entailment", "used_records": [0]}\n'
            with self.assertRaises(ValueError):execute(code,{}, {'records':records})
        # A genuinely known field can still be used without reading an unknown.
        code='def apply(inputs, premises):\n    r = premises["records"][0]\n    return {"handled": "worker" in r["values"]["roles"], "answer": "Entailment", "used_records": [0]}\n'
        self.assertTrue(execute(code,{}, {'records':records})['handled'])

    def test_rejected_unknown_overwrite_does_not_alter_original_record(self):
        records=[{'values':{},'unresolved_fields':['owner']}];original=deepcopy(records)
        code='def apply(inputs, premises):\n    r = premises["records"][0]\n    r["values"]["owner"] = "same_actor"\n    return {"handled": True, "answer": "Entailment", "used_records": [0]}\n'
        with self.assertRaises(ValueError):execute(code,{}, {'records':records})
        self.assertEqual(records,original)


if __name__ == '__main__':unittest.main()
