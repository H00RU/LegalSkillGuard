"""Metadata-only remaining official stock, with monotone exposure exclusions.

Native adapters mechanically separate source annotations in memory. No labels,
case text or questions are returned or saved; no prepared heldout file is read.
This checks the existing pinned releases, not hypothetical future new releases.
"""
from collections import Counter
import json
from pathlib import Path
import sqlite3

from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_heldout_exposure_gate import KNOWN_INCIDENT
from experiments.two_method_prepare_sources import native_stock, clusters
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def run():
    exposure = read(BASE/'exposure/historical_exposure_index.json')
    keys = set(exposure['source_keys'])
    ledger = ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True) as db:
        keys.update(r[0] for r in db.execute('select distinct source from calls'))
        physical = db.execute('select count(*) from calls').fetchone()[0]
        reserved = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    for path in [KNOWN_INCIDENT,*sorted((BASE/'exposure/incidents').glob('*.json'))]:
        for cohort in read(path)['conservative_affected_cohorts'].values():
            keys.update(cohort['sources'])
    keys.update(read(BASE/'prepared/source_lock.json')['sources']['train'])
    exposure = {**exposure,'source_keys':sorted(keys)}
    original = read(ROOT/'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    stocks,excluded = native_stock(exposure,original,include_grading=False)
    assert all(not row['grading'] for rows in stocks.values() for row in rows)
    # OE template hashes are metadata in the original eligibility audit.
    eligible = read(BASE/'prospective_inventory/OpenExempt/inventory_audit.json')['eligible_candidates']
    used_structures = {r['public_structure_sha256'] for r in eligible if r['key'] in keys}
    stocks['OpenExempt'] = [r for r in stocks['OpenExempt']
        if not any(k.startswith('oe-public-structure:') and k.split(':',1)[1] in used_structures for k in r['isolation_keys'])]
    summaries,metadata = {},{}
    for dataset in ('SARA_v2_Binary','ContractNLI','MAUD','RuleArena_Airline','OpenExempt'):
        rows = clusters(stocks.get(dataset,[]))
        summaries[dataset] = {'remaining_candidate_mothers':len(rows),
            'remaining_template_groups':len({r['template_group'] for r in rows}),
            'by_native_split':dict(Counter(r['native_split'] for r in rows)),
            'counts_not_a_frozen_blind_test_or_verified_F_coverage':True}
        metadata[dataset] = [{k:r[k] for k in ('key','native_split','template_group','isolation_keys')} for r in rows]
    protocol = {'name':'remaining-pinned-official-source-stock-20261117',
        'code_sha256':{str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),
            'experiments/two_method_prepare_sources.py':sha(ROOT/'experiments/two_method_prepare_sources.py'),
            'legal_skill_guard/rr/adapters.py':sha(ROOT/'legal_skill_guard/rr/adapters.py')},
        'historical_exposure_index_sha256':sha(BASE/'exposure/historical_exposure_index.json'),
        'incident_sha256':sha(KNOWN_INCIDENT), 'exposed_keys_sha256':digest(sorted(keys)),
        'source_lock_sha256':sha(BASE/'prepared/source_lock.json'),
        'pinned_official_inputs_sha256':{str(p):sha(p) for p in [
            ROOT/'history/rr_v2_20261106/data/cache/rr_v2/sara_v2.tar.gz',
            ROOT/'history/rr_v2_20261106/data/cache/rr_v2/contract-nli.zip',
            Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip'),
            ROOT/'history/rr_v2_20261106/data/cache/rr_v2/RuleArena/airline/reference_rules.txt',
            *sorted((ROOT/'history/rr_v2_20261106/data/cache/rr_v2/RuleArena/airline/synthesized_problems').glob('comp_*.jsonl')),
            BASE/'prospective_inventory/OpenExempt/construction_and_grading_only.json',
            BASE/'prospective_inventory/OpenExempt/inventory_audit.json']},
        'continuous_physical_requests':physical,'reserved':reserved,
        'heldout_grading_files_read':False,'labels_returned_saved_or_used_to_select_sources':False,
        'native_source_labels_mechanically_separated_in_memory':True,
        'new_model_or_teacher_requests':0, 'official_new_release_downloaded':False}
    out = BASE/'revision_20261117/official_stock'/digest(protocol)
    immutable_json(out/'protocol.json',protocol)
    for name,expected in protocol['code_sha256'].items():
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes((ROOT/name).read_bytes())
        assert sha(target)==expected
    immutable_json(out/'candidate_identity_metadata.json',metadata)
    summary = {'artifact_root':str(out.relative_to(ROOT)), 'datasets':summaries,
        'exclusions':excluded,'new_model_or_teacher_requests':0,
        'remaining_SARA_full_release_check':'See the separate full96 source audit; all16 original eligible candidates are now exposed',
        'no_test_sampling_or_formal_execution':True,'goal_complete':False}
    immutable_json(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return out,summary


if __name__=='__main__':run()
