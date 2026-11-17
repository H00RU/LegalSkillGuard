"""Role-safe source normalization and native metric invariants."""
import unittest
from legal_skill_guard.paired_interfaces.diversity import audit_source,reference_outputs,structural_group,public_source,score,GOLD_FIELDS


class DiversityAdapterTests(unittest.TestCase):
    def test_same_pair_aggregates_but_different_defendants_do_not(self):
        s='Amy is from Texas. Bob is from Maine. Carl is from Utah. Amy sues Bob for $40,000 and $40,000. Amy sues Carl for $80,000.'
        self.assertEqual(reference_outputs(audit_source(s)),{'answer':'Yes','parties_are_diverse':True,'aic_is_met':True})
        s='Amy is from Texas. Bob is from Maine. Carl is from Utah. Amy sues Bob for $40,000. Amy sues Carl for $40,000.'
        self.assertFalse(reference_outputs(audit_source(s))['aic_is_met'])

    def test_names_and_state_names_do_not_create_new_mothers(self):
        a=audit_source('Amy is from Texas. Bob is from Maine. Amy sues Bob for $80,000.')
        b=audit_source('Jo is from Utah. Ken is from Nevada. Jo sues Ken for $80,000.')
        self.assertEqual(structural_group(a),structural_group(b))
        c=audit_source('Jo is from Utah. Ken is from Utah. Jo sues Ken for $80,000.')
        self.assertNotEqual(structural_group(a),structural_group(c))

    def test_annotations_are_not_public_reader_fields(self):
        row={'index':'0','text':'Amy is from Texas. Bob is from Maine. Amy sues Bob for $80,000.',
             'answer':'Yes','parties_are_diverse':'true','aic_is_met':'true'}
        value=public_source(row,'diversity_1',project_split='train')
        public=value['views'][0]['public']
        self.assertEqual(public['source_text'],row['text'])
        self.assertTrue(public['question']);self.assertIn('$75,000',public['rules'])
        self.assertFalse(GOLD_FIELDS&set(public))

    def test_native_indices_restart_without_aliasing_mother_sources(self):
        row={'index':'0','text':'Amy is from Texas. Bob is from Maine. Amy sues Bob for $80,000.'}
        train=public_source(row,'diversity_1',project_split='train')
        dev=public_source(row,'diversity_1',project_split='dev')
        test=public_source(row,'diversity_1',project_split='test')
        self.assertNotEqual(train['key'],test['key'])
        self.assertEqual(dev['key'],test['key'])

    def test_balanced_accuracy_and_failures_keep_all_sources(self):
        targets={str(i):{'native':{'answer':'Yes' if i<3 else 'No'}} for i in range(4)}
        result=score({'0':'Yes','1':'Yes','2':None,'3':'Yes'},targets)
        self.assertEqual(result['accuracy'],0.5)
        self.assertEqual(result['balanced_accuracy'],1/3)
        self.assertEqual(result['invalid_or_abstained'],1)


if __name__=='__main__':unittest.main()
