import unittest
from legal_skill_guard.rr.payment_scope import decode_payments
from reports.method_redesign_20261109.process_payment_scope import render_null_sentinels
from tests.test_rr_payment_scope import event


class NullRenderingRegression(unittest.TestCase):
    def test_actual_null_sentinel_has_unique_unknown_interpretation(self):
        text='P paid wages of $11 to Q for field work.'
        e=event('P','Q','$11','field work',text);e['payment_medium']='null';raw={'events':[e]}
        rendered,changes=render_null_sentinels(raw,text)
        self.assertEqual(raw['events'][0]['payment_medium'],'null')
        self.assertIsNone(rendered['events'][0]['payment_medium']);self.assertEqual(len(changes),1)
        self.assertEqual(len(decode_payments(rendered,text)['events']),1)

    def test_literal_source_null_is_ambiguous_and_stays_literal(self):
        text='P paid wages of $11 to Q for null work.'
        e=event('P','Q','$11','null',text);rendered,changes=render_null_sentinels({'events':[e]},text)
        self.assertEqual(rendered['events'][0]['work_activity'],'null');self.assertEqual(changes,[])

    def test_nonnullable_evidence_cannot_be_filled_with_unknown(self):
        text='P paid wages of $11 to Q for field work.';e=event('P','Q','$11','field work','null')
        rendered,changes=render_null_sentinels({'events':[e]},text)
        self.assertEqual(changes,[])
        with self.assertRaises(ValueError):decode_payments(rendered,text)

    def test_payment_is_not_a_null_alias(self):
        text='P paid wages of $11 to Q for field work.';e=event('P','Q','$11','field work',text);e['payment_medium']='payment'
        rendered,changes=render_null_sentinels({'events':[e]},text);self.assertEqual(changes,[])
        with self.assertRaises(ValueError):decode_payments(rendered,text)


if __name__=='__main__':unittest.main()
