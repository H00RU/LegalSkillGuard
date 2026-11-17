from copy import deepcopy
import json
import unittest

from experiments.convergence_replay_diversity_references import reference_reading
from legal_skill_guard.paired_interfaces.diversity import public_source
from legal_skill_guard.paired_interfaces import diversity_relational,relational_program
from legal_skill_guard.paired_interfaces.production_decode import decode_response


class ComposedProgramTests(unittest.TestCase):
    def source(self):
        return public_source({'index':'fixture','text':'Amy is from Texas. Bob is from Maine. Carl is from Utah. '
            'Amy sues Bob for $40,000 and $40,000. Amy sues Carl for $30,000 and $40,000.'},'diversity_4',project_split='train')

    def test_auto_generated_joint_aggregate_preserves_same_pair_binding(self):
        source=self.source();view=diversity_relational.views(source)[0]
        self.assertEqual(len(view['plans']),4)
        for plan in view['plans']:
            raw,_=reference_reading(source,plan)
            got=decode_response(source,view,plan,{'content':json.dumps(raw),'finish_reason':'stop'})
            self.assertFalse(got['production_errors']);self.assertEqual(got['native']['native']['answer'],'No')
            self.assertFalse(got['decoder_receipt']['diagnostics']['aic_is_met'])
        generated=view['plans'][-1]
        self.assertTrue(all(f['operation']=='relation' for u in generated['relational_program']['units'].values() for f in u['asset']['features']))
        self.assertFalse(diversity_relational.locator(source['views'][0]['public']['source_text'])['source_values_or_native_labels_supplied'])

    def test_exchanged_local_identity_or_nonstop_never_executes(self):
        source=self.source();view=diversity_relational.views(source)[0];plan=view['plans'][-1]
        raw,_=reference_reading(source,plan)
        raw['claim_pair_0']['observation']['source_anchor']='claim_pair_1'
        got=decode_response(source,view,plan,{'content':json.dumps(raw),'finish_reason':'stop'})
        self.assertTrue(got['production_errors'])
        self.assertFalse(got['native']['native']['handled'])
        got=decode_response(source,view,plan,{'content':json.dumps(raw),'finish_reason':'length'})
        self.assertTrue(got['production_errors'])

    def test_three_valued_composition_does_not_replace_unknown_with_false(self):
        self.assertIsNone(relational_program.evaluate({'all':[{'local':['a','x']},{'constant':True}]},{}))
        self.assertIs(relational_program.evaluate({'all':[{'local':['a','x']},{'constant':False}]},{}),False)


if __name__=='__main__':unittest.main()
