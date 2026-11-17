"""Resolve the actual teacher without silent model changes or credential output."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from legal_skill_guard.skill_evolution.clients import configured_teacher_profile,FrozenTeacher
from legal_skill_guard.rr.ledger import BudgetError


class TeacherProfileTests(unittest.TestCase):
    def profile(self,path):
        path.write_text('model="gpt-6.1-sol"\nmodel_reasoning_effort="xhigh"\nprivate_provider_value="do-not-export"\n')
        return configured_teacher_profile(path)

    def test_whitelist_and_effort_override_do_not_export_other_configuration(self):
        with TemporaryDirectory() as t:
            p=Path(t)/'config.toml';v=self.profile(p)
            self.assertEqual(v['model'],'gpt-6.1-sol');self.assertEqual(v['reasoning_effort'],'high')
            self.assertEqual(v['observed_default_reasoning_effort'],'xhigh')
            self.assertNotIn('do-not-export',repr(v));self.assertFalse(v['model_response_verified'])
            self.assertIn('xhigh',p.read_text())

    def test_current_model_requires_explicit_ledger_binding(self):
        with TemporaryDirectory() as t:
            v=self.profile(Path(t)/'config.toml');cfg={'model':'gpt-6.1-sol','reasoning_effort':'high',
                'retries':0,'timeout_seconds':600,'executable':'codex'}
            with self.assertRaises(BudgetError):FrozenTeacher(SimpleNamespace(policy={}),t,cfg,authorized_profile=v)
            ledger=SimpleNamespace(policy={'execution_binding':{'teacher_profile':v}})
            with patch('legal_skill_guard.skill_evolution.clients.CodexCLIClient') as adapter:
                FrozenTeacher(ledger,t,cfg,authorized_profile=v)
                self.assertEqual(adapter.call_args.kwargs['model'],'gpt-6.1-sol')

    def test_historical_profile_still_rejects_an_unannounced_model_change(self):
        cfg={'model':'gpt-6.1-sol','reasoning_effort':'high','retries':0}
        with self.assertRaises(BudgetError):FrozenTeacher(SimpleNamespace(policy={}),'/tmp',cfg)


if __name__=='__main__':unittest.main()
