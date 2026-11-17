import unittest

from legal_skill_guard.paired_interfaces.source_context import enclosing_section,SourceContextUnavailable


class EnclosingSectionTests(unittest.TestCase):
    def test_toc_duplicate_number_and_late_proviso_remain_in_exact_section(self):
        parent=('Section 4.1 Overview ........ 62\nSection 4.2 Overview ........ 63\n'
            '\nSection 4.1 Covenants of A.\n(a) A shall operate in the ordinary course.\n'
            'The following proviso limits the same duty.\n\n(b) A shall not dispose of assets.\n'
            'Section 4.2 Covenants of B.\nB has other duties.\n')
        text,receipt=enclosing_section(parent,'(a) A shall operate in the ordinary course. (Page 62)')
        self.assertEqual(text,parent[slice(*receipt['parent_section_span'])])
        self.assertIn('following proviso',text);self.assertIn('(b)',text)
        self.assertNotIn('Section 4.2',text)
        self.assertEqual(receipt['section_number'],'4.1')
        self.assertFalse(receipt['native_task_scope_complete'])

    def test_only_whitespace_and_terminal_page_annotation_are_normalized(self):
        parent='Section 2.1 Covenants.\r\nA\tshall\r\nnot sell.\nSection 2.2 Next.\n'
        text,receipt=enclosing_section(parent,'A shall not sell. (Page 8–9)')
        self.assertIn('A\tshall\r\nnot sell.',text)
        with self.assertRaises(SourceContextUnavailable):enclosing_section(parent,'A shall sell.')
        with self.assertRaises(SourceContextUnavailable):enclosing_section(parent,'a shall not sell.')

    def test_repeated_anchor_is_refused_even_if_one_occurrence_has_wanted_topic(self):
        parent='Section 1.1 First.\nA shall act. Topic.\nSection 1.2 Second.\nA shall act.\n'
        with self.assertRaisesRegex(SourceContextUnavailable,'ambiguous'):enclosing_section(parent,'A shall act.')

    def test_over_budget_section_is_refused_without_cutting_late_material(self):
        parent='Section 1.1 First.\nA shall act.\n'+'Later condition. '*20+'\nSection 1.2 Next.\n'
        with self.assertRaisesRegex(SourceContextUnavailable,'budget'):
            enclosing_section(parent,'A shall act.',max_characters=80)

    def test_cross_section_excerpt_is_refused(self):
        parent='Section 1.1 First.\nA shall act.\nSection 1.2 Next.\nB shall act.\n'
        with self.assertRaisesRegex(SourceContextUnavailable,'crosses'):
            enclosing_section(parent,'A shall act.\nSection 1.2 Next.\nB shall act.')

    def test_topic_changes_in_suffix_do_not_change_anchor_or_boundaries(self):
        a='Section 1.1 First.\nA shall act.\nCondition: weather.\nSection 1.2 Next.\n'
        b=a.replace('weather','illness')
        _,ra=enclosing_section(a,'A shall act.');_,rb=enclosing_section(b,'A shall act.')
        self.assertEqual(ra['parent_section_span'],rb['parent_section_span'])
        self.assertEqual(ra['normalized_anchor_sha256'],rb['normalized_anchor_sha256'])
        self.assertNotEqual(ra['section_sha256'],rb['section_sha256'])

    def test_revised_input_keeps_other_tasks_and_replaces_stale_input_declaration(self):
        from copy import deepcopy
        from experiments.two_method_maud_context_repair import revised_source
        from legal_skill_guard.skill_evolution.objects import digest
        source={'key':'MAUD:fixture','declared_task_input_hash':'old-declaration',
            'views':[{'id':'a','public':{'source_text':'old'}},{'id':'b','public':{'source_text':'unchanged'}}]}
        source['runtime_actor_views_sha256']=digest(source['views']);before=deepcopy(source)
        _,receipt=enclosing_section('Section 1.1 First.\nold\nSuffix.\nSection 1.2 Next.\n','old')
        revised=revised_source(source,'a','new full section',receipt)
        self.assertEqual(source,before)
        self.assertEqual(revised['views'][1],source['views'][1])
        self.assertNotIn('declared_task_input_hash',revised)
        self.assertEqual(revised['source_context_revision']['original_declared_task_input_hash'],'old-declaration')
        self.assertEqual(revised['runtime_actor_views_sha256'],digest(revised['views']))
        self.assertFalse(revised['source_context_revision']['new_independent_mother_or_blind_test'])

    def test_actual_fixed_TRAIN_case_without_other_parents_grading_or_clients(self):
        from pathlib import Path
        import zipfile
        from unittest.mock import patch
        from experiments import two_method_maud_context_repair as audit
        from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
        from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
        original=Path.read_text;zip_read=zipfile.ZipFile.read
        def bounded(path,*args,**kwargs):
            if path.name=='grading.json' or 'sealed_test' in path.parts or 'dev' in path.parts:
                self.fail('Heldout or grading input was opened')
            return original(path,*args,**kwargs)
        def parent_only(archive,name,*args,**kwargs):
            if name!='data/contracts/contract_145.txt':self.fail('An unrelated official case was opened')
            return zip_read(archive,name,*args,**kwargs)
        with (patch.object(Path,'read_text',bounded),patch.object(zipfile.ZipFile,'read',parent_only),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger'))):
            _,summary=audit.run()
        self.assertEqual(summary['original_excerpt_characters'],911)
        self.assertGreater(summary['proposed_source_characters'],911)
        self.assertTrue(summary['shared_public_context_matches_interface_and_control_actors'])
        self.assertFalse(summary['old_reference_units_binding_matches_proposal'])
        self.assertTrue(summary['old_registry_actual_reuse_rejected'])
        self.assertTrue(summary['default_formal_input_not_switched'])


if __name__=='__main__':unittest.main()
