from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_m2_gate_evidence as audit


class M2TwoGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.example=audit.compute_example()

    def test_actual_F_example_explains_difference_from_accuracy_and_historical_replay(self):
        e=self.example
        self.assertEqual(e['source_native_accuracy'],{'columns':1.,'records':1.})
        self.assertEqual(e['full_paired_trace_historical_proxy'],{'columns':[0.,0.],'records':[0.,0.]})
        self.assertEqual(e['conditional_M2_empirical_risks'],{'columns':[1.,1.],'records':[0.,0.]})
        self.assertEqual(e['conditional_M2_selected_plan'],'records')
        self.assertEqual(e['ordinary_accuracy_selected_plan'],'columns')
        self.assertEqual(e['full_paired_trace_selected_plan'],'columns')

    def test_full_joint_trace_transfer_is_not_weakened_to_independent_field_noise(self):
        self.assertEqual(self.example['full_joint_trace_with_same_transfer_assumption'],
                         self.example['conditional_M2_empirical_risks'])

    def test_observationally_identical_channels_reverse_new_structure_risks(self):
        e=self.example
        self.assertTrue(e['counterexample_all_calibration_graph_pairs_observationally_identical'])
        self.assertEqual(e['calibration_observable_residual_mass'],{'columns':0.,'records':0.})
        self.assertEqual(e['two_observationally_equivalent_channels_target_risks']['stable_rewrites'],
                         {'columns':[1.,1.],'records':[0.,0.]})
        self.assertEqual(e['two_observationally_equivalent_channels_target_risks']['structure_dependent_rewrites'],
                         {'columns':[0.,0.],'records':[1.,1.]})
        self.assertEqual(e['target_risks_not_identified_without_additional_structure_transfer_restriction'],
                         {'columns':[0.,1.],'records':[0.,1.]})

    def test_actual_existing_records_fail_gates_without_labels_or_clients(self):
        from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
        from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
        original=Path.read_text
        def bounded(path,*args,**kwargs):
            if path.name=='grading.json' or 'sealed_test' in path.parts or 'dev' in path.parts:
                self.fail('M2 gate opened grading or heldout input')
            return original(path,*args,**kwargs)
        with (patch.object(Path,'read_text',bounded),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger'))):
            _,decision=audit.run()
        self.assertEqual(decision['real_candidate_families'],6)
        self.assertEqual(decision['real_families_all_upper_bounds_one'],6)
        self.assertFalse(decision['gate_1_passed']);self.assertFalse(decision['gate_2_passed'])
        self.assertFalse(decision['fixed_finite_real_validation_dispatch_allowed'])
        self.assertEqual(decision['M2_expansion_status'],'stopped_by_user_evidence_gate')

    def test_formal_entry_still_refuses_if_old_hold_and_exposure_are_mock_released(self):
        from experiments import two_method_formal_study as study
        original=study.read
        def current(path):
            if Path(path).name=='FORMAL_REVISION_HOLD_20261117.json':return {'formal_dispatch_on_hold':False}
            return original(path)
        with (patch.object(study,'assert_unexposed_cohorts'),patch.object(study,'read',current),
              patch.object(study,'prepare',side_effect=AssertionError('must not prepare or create clients'))):
            with self.assertRaises(audit.M2EvidenceGateError):study.run()


if __name__=='__main__':unittest.main()
