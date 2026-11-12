"""Actual Full companion-output breakage must not count as legal co-revision."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from legal_skill_guard.skill_evolution.patterns import compatible_dependency_versions


class ActualFragmentInterfaces(unittest.TestCase):
    def test_all_companion_dependency_ports_cross_both_producer_versions(self):
        path = Path(__file__).with_name('fixtures') / 'skill_evolution_actual_fragment_interfaces_20261112.json'
        data = json.loads(path.read_text())
        producer, consumer = 'nda_representative_exception_applicability', 'nda_disclosure_permission_consequence'
        old_p, old_c = (SimpleNamespace(**data['old'][n]) for n in (producer, consumer))
        for arm, expected in [('Full', False), ('Lift+GenericJoint', True)]:
            new_p, new_c = (SimpleNamespace(**data['new'][arm][n]) for n in (producer, consumer))
            self.assertEqual(compatible_dependency_versions(old_p, new_p, old_c, new_c, 'exception_applies'), expected)
        added = data['new']['Full'][consumer]['inputs']['general_third_party_prohibition']
        self.assertNotIn(added['field'], data['old'][producer]['outputs'])
        self.assertEqual(added['type'], 'boolean')


if __name__ == '__main__':unittest.main()
