"""Reference source edits and shared explanations; no model calls."""
from dataclasses import replace
import unittest

from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase,Theory,DerivedField,ExplanationState,allowed_relation,source_variant,
    choose_groups,canonical)
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch


PROVENANCE=({'kind':'independent_source_audit','evidence_sha256':'a'*64},)


def threshold(v,law):return v['amount']>=law['threshold']


def theory():
    return Theory({'law:v1':[{'threshold':3000},{'threshold':3600}]},
                  {'root:A':[{}],'root:B':[{}]},threshold,'b'*64,PROVENANCE,
                  allowed_edits=frozenset({'amount'}))


def case(value=3200,root='root:A'):
    text='The payment is $'+str(value)+'.'
    return SourceCase('source:'+root,root,'law:v1',{'facts':text},{'amount':value},
                      {'amount':('facts',text.index('$'),text.index('.'))})


class SharedSemanticsTests(unittest.TestCase):
    def test_same_explanation_rejects_tuple_allowed_by_cartesian_completions(self):
        t=theory();a=case();b=replace(case(3500),interventions={'amount':3500})
        shared=allowed_relation(t,[a,b]);independent=allowed_relation(t,[a,b],mode='independent_completions')
        self.assertEqual(set(shared['signatures']),{canonical([True,True]),canonical([False,False])})
        self.assertNotIn(canonical([True,False]),shared['signatures'])
        self.assertIn(canonical([True,False]),independent['signatures'])

    def test_cumulative_law_explanation_not_reselected_per_group(self):
        t=theory();state=ExplanationState(t,'c'*64)
        self.assertEqual(state.observe([case()], [True],physical_call_ids=['symbolic:1'])['status'],'not_refuted')
        result=state.observe([case(3500,root='root:B')],[False],physical_call_ids=['symbolic:2'])
        self.assertTrue(result['locally_allowed']);self.assertEqual(result['status'],'refuted')
        self.assertFalse(result['native_correctness_certified'])

    def test_unknown_case_facts_share_only_within_mother_and_edits_override(self):
        t=Theory({'law:v1':[{}]},{'A':[{'owns':False},{'owns':True}],
            'B':[{'owns':False},{'owns':True}]},lambda v,l:v['permission'],'d'*64,PROVENANCE,
            derived=(DerivedField('permission',('owns',),lambda v,l:v['owns']),),allowed_edits=frozenset({'owns'}))
        a=SourceCase('a','A','law:v1',{'facts':'an asset'},{});b=replace(a,source_id='b',root_id='B')
        self.assertIn(canonical([True,False]),allowed_relation(t,[a,b])['signatures'])
        self.assertNotIn(canonical([True,False]),allowed_relation(t,[a,replace(a,source_id='a2')])['signatures'])
        edited=replace(a,source_id='edited',interventions={'owns':True})
        self.assertEqual(set(allowed_relation(t,[a,edited])['signatures']),{canonical([False,True]),canonical([True,True])})
        self.assertEqual(source_variant(a,t,{'owns':True},{'owns':str})['status'],'UNREALIZABLE')

    def test_source_edit_preserves_frame_and_recomputes_derived_closure(self):
        t=replace(theory(),derived=(DerivedField('net',('amount',),lambda v,l:v['amount']+100),))
        a=case();result=source_variant(a,t,{'amount':3500},{'amount':lambda v:'$'+str(v)})
        self.assertEqual(result['status'],'REALIZABLE');b=result['case']
        self.assertEqual(b.public['facts'],'The payment is $3500.')
        self.assertEqual(t.complete(b,{'threshold':3000},{})['net'],3600)
        self.assertEqual(source_variant(a,t,{'date':'tomorrow'},{'date':str})['status'],'UNREALIZABLE')
        bad=replace(a,primitives={'amount':9999})
        self.assertEqual(source_variant(bad,t,{'amount':3500},{'amount':lambda v:'$'+str(v)})['status'],'UNREALIZABLE')

    def test_resume_preserves_omega_and_new_roots_do_not_reset_old_factors(self):
        t=theory();s=ExplanationState(t,'f'*64)
        s.observe([case()],[True],physical_call_ids=['symbolic:1'])
        saved=s.snapshot();restored=ExplanationState.restore(t,saved)
        self.assertEqual(restored.observe([case(3500,root='root:B')],[False],physical_call_ids=['symbolic:2'])['status'],'refuted')
        changed=replace(t,law_alternatives={'law:v1':[{'threshold':3000}]})
        with self.assertRaisesRegex(ValueError,'alternatives changed'):
            ExplanationState.restore(changed,saved)
        extra=replace(t,root_alternatives={**t.root_alternatives,'new_root':[{}]})
        self.assertEqual(ExplanationState.restore(extra,saved).factors,s.factors)

    def test_empty_K_cannot_be_used_to_reject_every_update(self):
        t=replace(theory(),constraint_holds=lambda v,l:False)
        with self.assertRaisesRegex(ValueError,'empty relation'):
            allowed_relation(t,[case()])

    def test_different_law_versions_do_not_share_an_interpretation(self):
        t=replace(theory(),law_alternatives={'law:v1':[{'threshold':3000}],
                                           'law:v2':[{'threshold':3600}]})
        a=case();b=replace(case(3500,'root:B'),law_scope='law:v2')
        self.assertEqual(set(allowed_relation(t,[a,b])['signatures']),{canonical([True,False])})

    def test_disagreement_is_not_reference_truth(self):
        t=theory();group=[case(),case(3500)]
        result=choose_groups(t,[group],[{'legitimate1':[True,True],'legitimate2':[False,False]}])
        self.assertEqual(result['selected_indices'],[])
        result=choose_groups(t,[group],[{'wrong':[True,False],'legitimate':[True,True]}])
        self.assertEqual(result['refuted_candidate_classes'],['wrong'])
        self.assertFalse(result['physical_model_evidence_established_by_selection'])

    def test_selects_combined_conflict_with_two_locally_admissible_signatures(self):
        groups = [[case()], [case(3500, root='root:B')]]
        signatures = [{'scope_switch': [True], 'consistent': [True]},
                      {'scope_switch': [False], 'consistent': [True]}]
        result = choose_groups(theory(), groups, signatures, max_groups=2)
        self.assertTrue(all(not row['rejected_candidates'] for row in result['groups']))
        self.assertEqual(result['selected_indices'], [0, 1])
        self.assertEqual(result['refuted_candidate_classes'], ['scope_switch'])
        self.assertEqual(choose_groups(theory(), groups, signatures, max_groups=1)['selected_indices'], [])

    def test_abstention_keeps_explanations_and_concrete_contradictions_refute(self):
        state = ExplanationState(theory(), 'c'*64)
        group = [case(), case(3500, root='root:B')]
        abstained = state.observe(group, [None, {'status': 'unread'}], physical_call_ids=['x', 'y'])
        self.assertTrue(abstained['locally_allowed'])
        self.assertFalse(abstained['asserted_output_present'])
        self.assertFalse(abstained['all_unknown_is_positive_evidence'])
        self.assertTrue(state.observe(group, [True, None], physical_call_ids=['u', 'v'])['locally_allowed'])
        contradicted = state.observe(group, [None, False], physical_call_ids=['p', 'q'])
        self.assertTrue(contradicted['locally_allowed'])
        self.assertEqual(contradicted['status'], 'refuted')

    def test_patch_gate_distinguishes_joint_refutation_from_paired_native_gain(self):
        groups = [
            {'cases': [case()], 'outputs': [True], 'physical_call_ids': ['read-a']},
            {'cases': [case(3500, root='root:B')], 'outputs': [False], 'physical_call_ids': ['read-b']},
        ]
        native = [{'source': 'root:A', 'baseline_utility': 0, 'patch_utility': 1}]
        kwargs = {'visible_train': {'root:A', 'root:B'}, 'verify_projection': lambda *args: True,
                  'verify_native_pair': lambda *args: True}
        receipt = validate_patch(theory(), 'c'*64, groups, native, **kwargs)
        self.assertEqual(receipt['status'], 'rejected_by_shared_explanation')
        self.assertTrue(all(group['independent_per_case_compatible'] for group in receipt['matched_controls']))
        groups[1]['outputs'] = [True]
        receipt = validate_patch(theory(), 'c'*64, groups, native, **kwargs)
        self.assertEqual(receipt['status'], 'eligible_train_update')
        groups[0]['outputs'] = [None]
        groups[1]['outputs'] = [None]
        self.assertEqual(validate_patch(theory(), 'c'*64, groups, native, **kwargs)['status'],
                         'insufficient_positive_supervision')
        with self.assertRaisesRegex(ValueError, 'visible TRAIN'):
            validate_patch(theory(), 'c'*64, groups, native, **(kwargs | {'visible_train': {'root:A'}}))

    def test_off_scope_and_physical_evidence_are_not_fabricated(self):
        t=replace(theory(),well_formed=lambda v,l:v['amount']>=0)
        self.assertIn(canonical([{'status':'off_scope'}]),allowed_relation(t,[case(-1)])['signatures'])
        state=ExplanationState(t,'e'*64)
        with self.assertRaisesRegex(ValueError,'verifier'):
            state.observe([case()],[True],physical_call_ids=['not-a-receipt'],evidence_kind='actual_model')
        result=state.observe([case()],[True],physical_call_ids=['symbolic'])
        self.assertFalse(result['physical_model_evidence_verified'])
        self.assertTrue(result['native_positive_supervision_required'])

    def test_possible_ownership_is_not_a_supported_literal_assertion(self):
        source = case()
        edited = replace(case(3500), source_id='amount_edit')
        review = replace(theory(), root_alternatives={'root:A': [
            {'ownership': False}, {'ownership': True}],
        }, reference=lambda values, law: {
            'ownership': values['ownership'], 'stated_value': values['amount'],
        })
        inputs = {
            'cases': [source, edited], 'outputs': [
                {'ownership': True, 'stated_value': 3200}, {'ownership': True, 'stated_value': 3500},
            ],
            'physical_call_ids': ['source', 'edit'], 'literal_assertion_fields': ('ownership', 'stated_value'),
        }
        arguments = {'visible_train': {'root:A'}, 'verify_projection': lambda *args: True,
                     'verify_native_pair': lambda *args: True}
        native = [{'source': 'root:A', 'baseline_utility': 0, 'patch_utility': 1}]
        result = validate_patch(review, 'c' * 64, [inputs], native, **arguments)
        assert result['matched_controls'][0]['shared_prefix_compatible']
        assert result['status'] == 'rejected_unsupported_literal_assertion'
        assert result['matched_controls'][0]['unsupported_literal_assertions'] == [
            {'case_index': 0, 'field': 'ownership'}, {'case_index': 1, 'field': 'ownership'},
        ]
        for output in inputs['outputs']:
            output['ownership'] = None
        result = validate_patch(review, 'c' * 64, [inputs], native, **arguments)
        assert result['status'] == 'eligible_train_update'

    def test_candidate_predictions_cannot_supply_audited_K(self):
        with self.assertRaisesRegex(ValueError,'independently'):
            replace(theory(),provenance=({'kind':'candidate_prediction','evidence_sha256':'a'*64},))


if __name__=='__main__':unittest.main()
