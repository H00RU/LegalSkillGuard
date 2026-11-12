"""Full edit mechanics from real rejected responses; no method-success claim."""
import ast
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.patterns import instantiate_edit, instantiate_skill_edit, learn, candidates
from legal_skill_guard.skill_evolution.revisions import VersionTable
from legal_skill_guard.skill_evolution.runtime import execute_helper
from tests.test_skill_evolution_runtime import helper


class CompleteEditTemplates(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.folder = root / 'reports/legal_skill_evolution_run_20261111/source_rule_evidence/legal_skill_evolution_source_rule_check_20261112'
        self.old = Library.load(self.folder / 'FreeEvolution/B2.json')
        self.candidate = json.loads((self.folder / 'FreeEvolution/B3_candidates/0.json').read_text())
        self.new = {r['skill_id']: Skill.from_dict(r['new']) for r in self.candidate['revisions']}

    def test_real_READ_and_query_edit_reconstructs_bindings_without_law_values(self):
        for sid, after in self.new.items():
            before = self.old.skills[sid]
            rebuilt = instantiate_skill_edit(before, after, before,
                skill_ids={s: s for s in self.old.skills})
            self.assertIsNotNone(rebuilt)
            self.assertEqual(ast.dump(ast.parse(rebuilt.procedure)), ast.dump(ast.parse(after.procedure)))
            for attribute in ('inputs', 'outputs', 'premises', 'reads', 'semantic_records', 'source_obligations'):
                self.assertEqual(getattr(rebuilt, attribute), getattr(after, attribute))
            self.assertTrue(all('value' not in p for p in rebuilt.premises.values()))
            self.assertEqual(rebuilt.version, before.version + 1)

    def test_actual_package_stays_rejected_and_creates_no_pattern(self):
        export = self.candidate['table']
        table = VersionTable(tuple(export['revision_hashes']), tuple(export['trigger']), tuple(export['history']))
        for c in export['mixed_version_table']:
            table.observe(c['mask'], c['source'], c['native_parent_grade'], c['trace'])
        library = Library(skills=self.new)
        for generic in (False, True):
            self.assertEqual(learn(library, self.old, self.candidate['revisions'], table,
                                   self.candidate['selected_mask'], generic=generic), [])
        self.assertEqual(library.revision_patterns, [])

    def test_full_and_Generic_share_complete_compilation_path_with_fixture_grades(self):
        # Synthetic admission ONLY tests routing. These are not research scores.
        exported = self.candidate['table']
        witness = next(c['trace'] for c in exported['mixed_version_table'] if c['mask'] == 3
                       and c['source'].startswith('ContractNLI:354'))
        for generic in (False, True):
            library = Library(skills=deepcopy(self.new))
            table = VersionTable(tuple(exported['revision_hashes']), ('fixture_only_parent',), ())
            fixture = deepcopy(witness);fixture['source'] = 'fixture_only_parent'
            for view in fixture['views']:
                for event in view['execution']['events']:
                    if 'source' in event:event['source'] = fixture['source']
            for mask in range(4):
                trace = deepcopy(fixture)
                for view in trace['views']:
                    view['score']['grade'] = float(mask == 3)
                    view['score']['correct'] = mask == 3
                trace['native_grade'] = trace['selection_grade'] = float(mask == 3)
                table.observe(mask, 'fixture_only_parent', float(mask == 3), trace)
            learned = learn(library, self.old, self.candidate['revisions'], table, 3, generic=generic)
            self.assertEqual(len(learned), 2)  # Two distinct measured receiver interpretations.
            # Only this isolated fixture receives that artificial pattern.
            target = Library(skills=deepcopy(self.old.skills), revision_patterns=deepcopy(library.revision_patterns))
            current = deepcopy(table.traces[0, 'fixture_only_parent'])
            proposed = candidates(target, [current], generic=generic)
            self.assertEqual(len(proposed), 1)
            self.assertTrue(proposed[0]['generated_before_teacher'])
            self.assertEqual(len(proposed[0]['revisions']), 2)
            for rev in proposed[0]['revisions']:
                skill = Skill.from_dict(rev['new'])
                after = self.new[skill.id]
                self.assertEqual(skill.reads, after.reads)
                self.assertEqual(skill.premises, after.premises)
            employee_pattern = next(p for p in library.revision_patterns
                if p['responsibility_evidence']['consumer_after_effects']['false'].get('output') == {'answer': 'NotMentioned'})
            thirdparty = deepcopy(current)
            thirdparty['views'] = [v for v in thirdparty['views'] if v['view'] == 'nda-7']
            target = Library(skills=deepcopy(self.old.skills), revision_patterns=[deepcopy(employee_pattern)])
            # A known different receiver interpretation blocks the legal prior;
            # the strong Generic memory may still try the whole measured edit.
            self.assertEqual(len(candidates(target, [thirdparty], generic=generic)), int(generic))
            identifiers = {sid: 'other_' + sid for sid in self.old.skills}
            renamed = {}
            for sid, skill in self.old.skills.items():
                inputs = deepcopy(skill.inputs)
                for port in inputs.values():
                    if port['mode'] == 'skill':port['skill_id'] = identifiers[port['skill_id']]
                renamed[identifiers[sid]] = replace(skill, id=identifiers[sid], inputs=inputs).validate()
            changed_trace = deepcopy(current)
            for v in changed_trace['views']:
                for event in v['execution']['events']:
                    for key in ('skill_id', 'producer', 'consumer'):
                        if event.get(key) in identifiers:event[key] = identifiers[event[key]]
            target = Library(skills=renamed, revision_patterns=deepcopy(library.revision_patterns))
            generated = candidates(target, [changed_trace], generic=generic)
            self.assertEqual(len(generated), 1)
            for rev in generated[0]['revisions']:
                skill = Skill.from_dict(rev['new'])
                for port in skill.inputs.values():
                    if port['mode'] == 'skill':self.assertIn(port['skill_id'], renamed)
            fallback_table = VersionTable(tuple(exported['revision_hashes']), ('fixture_only_parent',), ())
            for mask in range(4):
                trace = deepcopy(table.traces[mask, 'fixture_only_parent'])
                if mask == 3:
                    for view in trace['views']:view['execution']['core_executed'] = False
                fallback_table.observe(mask, 'fixture_only_parent', float(mask == 3), trace)
            empty = Library(skills=deepcopy(self.new))
            self.assertEqual(learn(empty, self.old, self.candidate['revisions'], fallback_table, 3, generic=generic), [])
        self.assertEqual(self.old.revision_patterns, [])

    def test_unchanged_constant_uses_target_value_and_provenance(self):
        before = helper()
        after = replace(before, version=2, procedure=(
            'def apply(inputs, premises):\n    return {"answer": inputs["a"] or premises["p"]}\n'))
        params = deepcopy(before.premises);params['p']['value'] = False
        params['p']['origin'] = {'source': 'other_actual_source'}
        current = replace(before, premises=params).validate()
        result = instantiate_skill_edit(before, after, current)
        self.assertIsNotNone(result)
        self.assertEqual(result.premises['p'], current.premises['p'])
        self.assertFalse(execute_helper(result, {'a': False}, {'p': False})['answer'])

    def test_unbound_new_rule_constant_is_not_copied(self):
        sid = next(iter(self.new));before, after = self.old.skills[sid], self.new[sid]
        premises = deepcopy(after.premises)
        name = next(iter(premises));premises[name] = {'mode': 'constant', 'type': premises[name]['type'],
            'value': ['invented target classes'], 'origin': before.source_provenance[0]}
        bad = replace(after, premises=premises).validate()
        self.assertIsNone(instantiate_skill_edit(before, bad, before))

    def test_target_interface_mismatch_is_unresolved(self):
        sid = next(iter(self.new));before, after = self.old.skills[sid], self.new[sid]
        inputs = deepcopy(before.inputs);inputs['current_question']['type'] = 'array'
        current = replace(before, inputs=inputs).validate()
        self.assertIsNone(instantiate_skill_edit(before, after, current))

    def test_new_READ_field_type_and_binding_must_match_the_new_port(self):
        sid = next(iter(self.new));before, after = self.old.skills[sid], self.new[sid]
        for mutation in ('field_type', 'binding'):
            readers = deepcopy(after.reads);reader = readers[0]
            name = next(iter(after.premises));field = after.premises[name]['field']
            if mutation == 'field_type':reader['fields'][field]['type'] = 'boolean'
            else:reader['bindings'][name] = 'missing_field'
            self.assertIsNone(instantiate_skill_edit(before, replace(after, reads=readers), before))

    def test_changed_numeric_law_literal_is_not_query_vocabulary(self):
        before = 'def apply(inputs, premises):\n    return {"answer": inputs["x"] > 0}\n'
        after = 'def apply(inputs, premises):\n    return {"answer": inputs["x"] > 999}\n'
        self.assertIsNone(instantiate_edit(before, after, before,
            declared_ports={'inputs': {'x'}}, allow_query_predicates=True))

    def test_alpha_renaming_keeps_new_local_from_capturing_a_target_local(self):
        before = 'def apply(inputs, premises):\n    a = inputs["x"]\n    return {"answer": a}\n'
        after = 'def apply(inputs, premises):\n    a = inputs["x"]\n    b = not a\n    return {"answer": a and b}\n'
        target = 'def apply(inputs, premises):\n    b = inputs["x"]\n    return {"answer": b}\n'
        program = instantiate_edit(before, after, target)
        self.assertIsNotNone(program)
        env = {};exec(program, env)
        self.assertFalse(env['apply']({'x': True}, {} )['answer'])

    def test_alpha_matching_cannot_swap_source_namespaces_or_primitive_operations(self):
        before = 'def apply(inputs, premises):\n    return {"answer": min(inputs["a"], premises["b"])}\n'
        after = 'def apply(inputs, premises):\n    return {"answer": inputs["a"]}\n'
        for target in (before.replace('min(', 'max('),
                       before.replace('inputs["a"], premises["b"]', 'premises["a"], inputs["b"]')):
            self.assertIsNone(instantiate_edit(before, after, target))


if __name__ == '__main__':unittest.main()
