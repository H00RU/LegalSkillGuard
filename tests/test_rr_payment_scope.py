import unittest
from legal_skill_guard.rr.payment_scope import decode_payments,scope_sum


def event(payer,payee,amount,work,evidence):
    return dict(payer=payer,payee=payee,amount_span=amount,work_activity=work,
                remuneration_kind='wages',payment_medium=None,service_period=None,event_evidence=evidence)


class PaymentScopeRegression(unittest.TestCase):
    def test_direction_and_all_recipient_rows(self):
        a='P paid wages of $11 to Q and $13 to R for field work.'
        b='Q paid wages of $17 to P for other work.'
        d=decode_payments({'events':[event('P','Q','$11','field work',a),event('P','R','$13','field work',a),
                                    event('Q','P','$17','other work',b)]},a+' '+b)
        r=scope_sum(d,payer='P',kind='wages',work_classify=lambda v:1,threshold=20)
        self.assertEqual(r['sum_lower'],'24');self.assertEqual(r['sum_upper'],'24')
        self.assertEqual([x['status'] for x in r['trace']],['included','included','excluded'])
        self.assertIsNone(r['native_legal_answer'])

    def test_unknown_class_is_not_a_false_fact(self):
        a='P paid wages of $11 to Q for unspecified work.'
        d=decode_payments({'events':[event('P','Q','$11','unspecified work',a)]},a)
        r=scope_sum(d,payer='P',kind='wages',work_classify=lambda v:2,threshold=5)
        self.assertEqual((r['sum_lower'],r['sum_upper']),('0','11'))
        self.assertIsNone(r['at_least_threshold'])

    def test_role_pointer_outside_its_event_is_rejected(self):
        a='P paid wages of $11 to Q for field work.';b='R received $13.'
        with self.assertRaisesRegex(ValueError,'outside'):
            decode_payments({'events':[event('P','Q','$13','field work',a)]},a+' '+b)

    def test_duplicate_event_cannot_inflate_a_sum(self):
        a='P paid wages of $11 to Q for field work.';e=event('P','Q','$11','field work',a)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            decode_payments({'events':[e,e]},a)

    def test_invented_medium_remains_rejected_after_schema_clarification(self):
        a='P paid wages of $11 to Q for field work.';e=event('P','Q','$11','field work',a)
        e['payment_medium']='payment'
        with self.assertRaisesRegex(ValueError,'payment'):
            decode_payments({'events':[e]},a)


if __name__=='__main__':unittest.main()
