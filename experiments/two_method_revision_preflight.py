"""Metadata-only preparation under hard no-client and no-grade-parse guards."""
import json
from pathlib import Path
from unittest.mock import patch

from experiments import two_method_formal_study as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


def run():
    extra=study.BASE/'OE_inventory_port_source_reviews_v1/22683c520de7626652bc2252c5733315babfec66f74fba5b0152cfd1bb0c5ea7/manifest.json'
    original=Path.read_text
    def bounded(path,*args,**kwargs):
        if path.name=='grading.json':
            raise AssertionError('Native grading parse prohibited during metadata preparation')
        return original(path,*args,**kwargs)
    with (patch.object(Path,'read_text',bounded),
          patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
          patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
          patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger'))):
        out,protocol,sources,registry,roles,readiness=study.prepare(extra)
    receipt={'artifact_root':str(out.relative_to(study.ROOT)),
        'source_reference_ready':readiness['full_prefix_ready'],
        'ready_views':readiness['ready_source_views'],
        'source_binding_count':len(protocol['source_sha256']),
        'formal_dispatch_on_hold':protocol['formal_revision_hold']['formal_dispatch_on_hold'],
        'heldout_cohorts_unexposed':protocol['heldout_exposure_status']['heldout_source_cohorts_unexposed'],
        'new_model_requests':0,'client_or_ledger_constructed':False,
        'native_grading_parsed':False,'goal_complete':False,
        'current_method':'observable-rewrite-set-transfer-v1',
        'ready_references_do_not_imply_valid_candidates_or_method_advantage':True}
    target=study.BASE/'revision_20261117/preflight'/digest(receipt)
    immutable_json(target/'receipt.json',receipt)
    print(json.dumps({**receipt,'receipt_path':str((target/'receipt.json').relative_to(study.ROOT))},ensure_ascii=False),flush=True)
    return target,receipt


if __name__=='__main__':run()
