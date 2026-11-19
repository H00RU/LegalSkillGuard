"""Count exact TRAIN rule coverage on the original B8 public OpenExempt DEV inputs."""

from collections import Counter
import json
from pathlib import Path

from experiments.convergence_formal_curves import pointer
from experiments.convergence_pilot_b0 import HANDOFF, ROOT, read, sha
from experiments.convergence_revision5_oe_scoped_forms import REGIME, title_at_anchor
from experiments.convergence_revision5_oe_scoped_forms_controls import literal_ports
from legal_skill_guard.paired_interfaces.asset_interfaces import context_from_public
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def run():
    current = read(HANDOFF / 'revision5_OE_scoped_forms_current.json')
    comparison = ROOT / current['artifact_root']
    fit = read(comparison / 'binding.json')
    assert comparison.name == digest(fit) and fit['partition'] == 'TRAIN'
    runner = next(name for name in fit['source_sha256'] if name.endswith('/convergence_revision5_oe_scoped_forms.py'))
    assert sha(ROOT / runner) == fit['source_sha256'][runner]
    terminal = comparison / 'terminal.json'
    assert read(terminal)['status'] == current['status'] == 'settled_OE_scoped_form_relation_TRAIN'
    study = ROOT / read(pointer(8))['artifact_root']
    binding = read(study / 'binding.json')
    assert study.name == digest(binding) and not read(study / 'terminal.json')['TEST_opened']
    b0 = ROOT / binding['b0_dev_data_root']
    public = read(b0 / 'public_DEV_sources.json')
    assert len(public) == 80 and digest(public) == read(b0 / 'binding.json')['DEV_public_sha256']
    scope = [s for s in public if s['dataset'] == 'OpenExempt' and s['project_split'] == 'dev']
    assert len(scope) == 16
    counts = {family: Counter() for family in ('EC', 'EV')}
    for source in scope:
        for view in source['views']:
            text = view['public']
            family = view['id']
            if family not in counts:
                continue
            context = context_from_public(text)
            if context['governing_regime'] != REGIME:
                continue
            count = counts[family]
            count['pennsylvania_views'] += 1
            inventory = public_inventory(text['original_input'])
            if inventory is None or not context['public_task_assumptions']:
                continue
            count['inventory_and_assumption_covered'] += 1
            try:
                titles = {slot: title_at_anchor(a['source_quote']) for slot, a in inventory.items()}
            except ValueError:
                continue
            count['title_rule_covered'] += 1
            outside = sum(all(v is None for v in literal_ports(a['description'], titles[slot]).values())
                          for slot, a in inventory.items())
            count['covered_views_with_unmatched_nouns'] += bool(outside)
            count['title_covered_assets'] += len(inventory)
            count['title_covered_assets_with_unmatched_nouns'] += outside
    receipt = {'original_B8_DEV_binding': study.name, 'public_DEV_sha256': digest(public),
               'TRAIN_terminal_sha256': sha(terminal), 'coverage': counts,
               'public_inputs_only': True, 'new_model_requests': 0, 'runner_sha256': sha(Path(__file__))}
    immutable_json(comparison / 'public_B8_DEV_coverage.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    run()
