"""Persist actual paired calibration reads and seal a new-mother selection.

No generation or gold access. Input utilities/fidelity come from already
settled, source-verified TRAIN rows. All four profiles must be paired on the
same mother before the library may choose a template for another mother.
"""
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces import diversity_relational
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'


def read(p):return json.loads(p.read_text())


def run():
    pointer=read(BASE/'handoff/diversity_reader_probe_current.json');calibration=ROOT/pointer['artifact_root']
    binding=read(calibration/'binding.json')
    if binding['name']!='convergence_Diversity_all_candidate_calibration_01' or not (calibration/'terminal.json').exists():
        raise ValueError('Wait for the actual four-candidate calibration terminal; never start another job')
    for p,h in binding['source_sha256'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Calibration implementation changed; use its snapshot')
    data=ROOT/binding['normalized_input_root'];identities=read(data/'identity_metadata.json')
    sources={p:[r['source'] for r in identities if r['project_split']==p] for p in ('train','dev','test')}
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id='convergence-Diversity-reader-'+digest(binding)[:16],sources=sources,binding=binding)
    executor=FrozenExecutor(ledger,calibration,binding['executor'])
    actor=InterfaceActor(executor,calibration,plan_assets={},source_inputs=None,
        pipeline_binding=binding['source_sha256'],relational_provider=diversity_relational.Provider())
    source=read(calibration/'public_TRAIN_source.json');view=actor.views(source)[0]
    plans={p['name']:p for p in view['plans']}
    decoded=[read(p) for p in (calibration/'interface_reads').glob('*/decoded.json')]
    rows={r['plan']:r for r in decoded}
    comparisons={r['plan']:r for r in (read(p) for p in (calibration/'comparison_rows').glob('*.json'))}
    if set(rows)!=set(plans) or set(comparisons)!=set(plans):raise ValueError('Paired candidate denominator incomplete')
    provenance={'calibration_root':pointer['artifact_root'],'calibration_binding_sha256':digest(binding),
        'trainer_source_sha256':hashlib.sha256((ROOT/'legal_skill_guard/paired_interfaces/formal_training.py').read_bytes()).hexdigest(),
        'driver_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'new_calls':0}
    out=BASE/'actual_interface_library_v1'/digest(provenance)
    immutable_json(out/'binding.json',provenance)
    learner=RelationalInterfaceLibrary(out,actor=actor,train_sources=sources['train'],
        initial_common_library_sha256=binding['common_external_library_sha256'])
    for name,plan in plans.items():
        comparison=comparisons[name]
        learner.observe(source,view,plan,rows[name],native_utility=int(comparison['native_correct']),
            source_fidelity={'all_local_relations_source_faithful':comparison['all_local_relations_source_faithful'],
                'native_labels_used_to_complete_unknowns':False,
                'reference_evidence_sha256':digest(comparison['source_fidelity'])},visible_prefix=[source['key']])
    snapshot=learner.snapshot(batch=0,visible_prefix=[source['key']])
    restored=RelationalInterfaceLibrary.restore(out,actor=actor,train_sources=sources['train'],snapshot=snapshot)
    pilot_path=ROOT/read(BASE/'handoff/source_audit_current.json')['artifact_root']/'pilot20.json'
    pilot={r['source'] for r in read(pilot_path)}
    # Pick the next different preselected mother of the same2-claim grammar,
    # without seeing a native target, source reference or current model read.
    candidates=[s for s in read(data/'train/public.json') if s['key'] in pilot and s['dataset']=='LegalBench_Diversity'
        and s['key']!=source['key']]
    candidates.sort(key=lambda s:(s['native_config'],digest(s)),reverse=True)
    selection=None
    for target in candidates:
        target_view=actor.views(target)[0];plan,receipt=restored.choose(target,target_view)
        if receipt['unseen_mother_reuse']:
            selection={'source':target['key'],'source_public_sha256':digest(target),
                'selected_plan_version':plan['version'],'library_sha256':snapshot['snapshot_sha256'],**receipt}
            break
    if selection is None:raise ValueError('No same-grammar different pilot mother available; do not manufacture reuse')
    immutable_json(out/'next_source_selection_before_read.json',selection)
    summary={'artifact_root':str(out.relative_to(ROOT)),'paired_actual_profiles':len(rows),
        'learning_mothers':1,'source_evidence_entailed_native_wins':sum(int(r['native_correct'] and r['all_local_relations_source_faithful']) for r in comparisons.values()),
        'selected_next_source':selection['source'],'selected_profile':selection['selected_profile'],
        'restored_library_sha256':snapshot['snapshot_sha256'],'next_source_gold_or_current_read_used':False,
        'next_source_actual_reuse_not_yet_executed':True,'new_model_calls':0,'no_method_efficacy_estimate':True}
    immutable_json(out/'summary.json',summary)
    (BASE/'handoff/actual_interface_library_current.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':run()
