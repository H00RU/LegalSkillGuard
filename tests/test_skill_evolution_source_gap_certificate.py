import unittest
from copy import deepcopy
from experiments.legal_skill_evolution_source_gap_certificate import certify

class CertificateTests(unittest.TestCase):
    def test_actual_positive_error_bounds_do_not_require_zero_training_loss(self):
        rows=[{'source':'one','actual_loss':0,'lower_bound':0,'lower_bound_basis':'nonnegative_native_loss_and_actual_zero_loss_prior','hard_constraints_satisfied':True,'unknown_worlds':False},
              {'source':'two','actual_loss':2,'lower_bound':2,'lower_bound_basis':'completed_exact_reachable_profile','hard_constraints_satisfied':True,'unknown_worlds':False}]
        self.assertEqual(certify(rows)['actual_prior_native_loss'],2)
        for key,value in [('actual_loss',3),('unknown_worlds',True),('hard_constraints_satisfied',False),('lower_bound_basis','incomplete_search')]:
            invalid=deepcopy(rows);invalid[1][key]=value
            with self.assertRaises(ValueError):certify(invalid)
