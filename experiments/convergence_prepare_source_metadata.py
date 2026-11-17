"""Versioned candidate roster and isolated four-library fresh TEST metadata.

No model/teacher/scorer. Reuses the complete historical exposure index, current
ledger and confirmed incidents. Only IDs/hashes/counts leave this preparation;
fresh source texts remain in sealed_test candidates and must not be inspected
by the development agent. Diversity DEV/TEST and final input/task normalization
are deliberately not claimed complete by this intermediate artifact.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.two_method_prepare_sources import native_stock,clusters
from experiments.two_method_heldout_exposure_gate import KNOWN_INCIDENT
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/two_method_followthrough_20261116'
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'
DATASETS=('OpenExempt','ContractNLI','MAUD','RuleArena_Airline','LegalBench_Diversity')
QUOTA={'OpenExempt':32,**{d:24 for d in DATASETS[1:]}}


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    exposure=read(OLD/'exposure/historical_exposure_index.json')
    if exposure['failures']:raise ValueError('Historical exposure decoding gaps must not be ignored')
    exposed=set(exposure['source_keys'])
    ledger=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True) as db:
        exposed.update(r[0] for r in db.execute('select distinct source from calls'))
        baseline=db.execute('select count(*) from calls').fetchone()[0]
        reserved=db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    if reserved:raise ValueError('A physical research request is live; verify its binding before preparing another run')
    incidents={str(KNOWN_INCIDENT)}|{str(p) for p in (OLD/'exposure/incidents').glob('*.json')}
    for name in sorted(incidents):
        for cohort in read(Path(name))['conservative_affected_cohorts'].values():exposed.update(cohort['sources'])
    original_train_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    original_train=read(original_train_path);exposed.update(s['key'] for s in original_train)
    diversity_summary=read(BASE/'handoff/diversity_train_current.json')
    diversity_root=ROOT/diversity_summary['artifact_root']
    train=[deepcopy(s) for s in original_train if s['dataset'] in DATASETS]+read(diversity_root/'public.json')
    if Counter(s['dataset'] for s in train)!=Counter(QUOTA) or len({s['key'] for s in train})!=128:
        raise ValueError('The fixed128-source TRAIN candidate roster changed')
    # Exact deterministic stratification:4 OE +3 of each other library per batch.
    # Only public IDs and seed45 determine order; no score/annotation enters.
    batches=[[] for _ in range(8)]
    for dataset in DATASETS:
        rows=sorted((s for s in train if s['dataset']==dataset),key=lambda s:digest({'seed':45,'source':s['key']}))
        width=4 if dataset=='OpenExempt' else 3
        for b in range(8):batches[b].extend(rows[b*width:(b+1)*width])
    roster=[]
    for b,rows in enumerate(batches,1):
        assert len(rows)==16
        rows.sort(key=lambda s:digest({'seed':45,'batch':b,'source':s['key']}))
        for s in rows:roster.append({'source':s['key'],'dataset':s['dataset'],'batch':b,'role':'training',
            'raw_public_sha256':digest(s),'existing_native_views':[v['id'] for v in s['views']],
            'input_scope_task_normalization_pending':True})
    # The old DEV cohort is exposed, which the new contract explicitly permits.
    # Its public inputs are already known; it is never renamed a blind set.
    dev=[s for s in read(OLD/'prepared/dev/public.json') if s['dataset'] in DATASETS]
    assert Counter(s['dataset'] for s in dev)==Counter({d:16 for d in DATASETS if d!='LegalBench_Diversity'})
    assert not {s['key'] for s in dev}&{s['key'] for s in train}
    old_manifest=read(ROOT/'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    stock,exclusions=native_stock({**exposure,'source_keys':sorted(exposed)},old_manifest,include_grading=False)
    oe_eligible=read(OLD/'prospective_inventory/OpenExempt/inventory_audit.json')['eligible_candidates']
    exposed_oe_groups={r['public_structure_sha256'] for r in oe_eligible if r['key'] in exposed}
    stock['OpenExempt']=[r for r in stock['OpenExempt'] if not any(
        k.startswith('oe-public-structure:') and k.split(':',1)[1] in exposed_oe_groups for k in r['isolation_keys'])]
    selected=[];inventory={};deficits={}
    for dataset in DATASETS:
        if dataset=='LegalBench_Diversity':continue
        candidates=clusters(stock[dataset]);eligible=[r for r in candidates if dataset!='ContractNLI' or r['native_split']=='test']
        eligible.sort(key=lambda r:digest({'seed':45,'partition':'test','source':r['key']}))
        groups=set();chosen=[]
        for r in eligible:
            if r['template_group'] in groups:continue
            groups.add(r['template_group']);chosen.append(r)
            if len(chosen)==32:break
        assert all(not r['grading'] and r['key'] not in exposed for r in chosen)
        selected.extend(chosen);deficits[dataset]=max(0,32-len(chosen))
        inventory[dataset]={'fresh_candidate_mothers':len(candidates),
            'eligible_native_pool_groups':len({r['template_group'] for r in eligible}),
            'selected_TEST_candidate_groups':len(chosen),'remaining_deficit':deficits[dataset]}
    binding={'name':'convergence-fixed-source-metadata-v1','seed':45,
        'original_TRAIN_public_sha256':sha(original_train_path),'diversity_TRAIN_protocol_sha256':sha(diversity_root/'protocol.json'),
        'historical_exposure_sha256':sha(OLD/'exposure/historical_exposure_index.json'),
        'combined_exposed_source_keys_sha256':digest(sorted(exposed)),
        'incident_sha256':{str(Path(p).relative_to(ROOT)):sha(Path(p)) for p in sorted(incidents)},
        'code_sha256':{str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),
            'experiments/two_method_prepare_sources.py':sha(ROOT/'experiments/two_method_prepare_sources.py')},
        'ledger_rows':baseline,'all128_enter_training':True,'input_scope_and_scoring_tasks_still_to_normalize':True,
        'Diversity_DEV_TEST_not_prepared':True,'not_a_complete_data_or_model_freeze':True,
        'scorer_reads_TEST_labels':False,'development_agent_receives_TEST_text_or_labels':False,
        'isolated_preparation_worker_reads_source_for_grouping':True,'new_research_calls':0}
    out=BASE/'source_metadata_v1'/digest(binding)
    immutable_json(out/'protocol.json',binding);immutable_json(out/'TRAIN_roster.json',roster)
    immutable_json(out/'TRAIN_raw_public.json',train);immutable_json(out/'DEV_exposed_raw_public.json',dev)
    # No target annotations are exported here; native grader opens them only
    # after the final B8 model/library freeze under the source manifest.
    immutable_json(out/'sealed_test_candidate/public.json',[{k:v for k,v in r.items() if k!='grading'} for r in selected])
    metadata=[{k:r[k] for k in ('key','dataset','native_split','parent_id','original_id','template_group','isolation_keys')}|
        {'project_split':'test_candidate','public_sha256':digest(r['views']),'agent_exposed':False} for r in selected]
    immutable_json(out/'TEST_candidate_identity_metadata.json',metadata)
    summary={'artifact_root':str(out.relative_to(ROOT)),'TRAIN_roster':128,'batches':8,'sources_per_batch':16,
        'all128_enter_training':True,'exposed_nontrain_DEV_candidates':64,'fresh_TEST_candidates':len(selected),
        'inventory':inventory,'TEST_deficits':deficits,'Diversity_DEV_TEST_pending':True,
        'CNI_full17_and_MAUD_context_normalization_pending':True,'full_protocol_locked':False,
        'test_content_seen_by_development_agent':False,'new_model_calls':0,'exclusions':exclusions}
    immutable_json(out/'summary.json',summary);immutable_json(BASE/'handoff/source_metadata_current.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':prepare()
