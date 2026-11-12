"""The real failed teacher body binds only its already-declared port names."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from legal_skill_guard.skill_evolution.objects import Library, apply_revision_package
from legal_skill_guard.skill_evolution.runtime import SkillRuntime
from legal_skill_guard.skill_evolution.teacher import compile_block, bind_declared_free_ports


class ImplicitPortTests(unittest.TestCase):
    def test_actual_body_is_recovered_with_its_original_rule_and_constant(self):
        f = json.loads((Path(__file__).parent / 'fixtures' /
                        'skill_evolution_actual_implicit_ports_20261112.json').read_text())
        source = f['source'];raw = f['raw_skill'];before = deepcopy(raw)
        revisions = compile_block({'revisions': [{'operation': 'create', 'skill': raw}]},
                                  Library(), {source['key']: source}, 'Full')
        self.assertEqual(raw, before)
        adaptation = revisions[0]['representation_adaptation']['explicit_port_bindings']
        self.assertEqual(adaptation['bindings']['case_family_relations'], 'inputs')
        self.assertEqual(adaptation['bindings']['excluded_employer_relations_to_employee'], 'premises')
        skill = revisions[0]['new']
        self.assertEqual(skill['premises']['excluded_employer_relations_to_employee']['value'],
                         raw['premises'][0]['value'])
        def forbidden(*args, **kwargs):raise AssertionError('No fresh model call in raw-output recovery')
        result = SkillRuntime(SimpleNamespace(read=forbidden)).run(source, source['views'][0],
            apply_revision_package(Library(), revisions, Library().hash), fallback=False)
        self.assertTrue(result['core_executed'])
        self.assertEqual(result['answer'], 'Entailment')

    def test_ambiguous_or_locally_assigned_names_are_never_guessed(self):
        p = 'def apply(inputs, premises):\n    return {"answer": x}\n'
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            bind_declared_free_ports(p, [{'name': 'x'}], [{'name': 'x'}])
        local = 'def apply(inputs, premises):\n    x = 2\n    return {"answer": x}\n'
        self.assertEqual(bind_declared_free_ports(local, [{'name': 'x'}], []), (local, None))
        self.assertEqual(bind_declared_free_ports(p, [], []), (p, None))


if __name__ == '__main__':unittest.main()
