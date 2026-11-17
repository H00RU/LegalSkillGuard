"""Reconcile all pinned Binary SARA source identities after recorded exposure.

The existing native adapter mechanically separates its annotations. Only keys,
hashes and counts leave this entry; labels, public cases and questions do not.
No new source generation, native scoring, inference or teacher call occurs.
"""
from collections import Counter
from pathlib import Path
import json
import sqlite3

from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_reconcile import source_keys
from experiments.two_method_heldout_exposure_gate import KNOWN_INCIDENT
from legal_skill_guard.rr.adapters import sara_v2
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def prepare():
    archive = ROOT / 'history/rr_v2_20261106/data/cache/rr_v2/sara_v2.tar.gz'
    old_manifest = ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json'
    inventory_path = BASE / 'reconciliation/assets.json'
    source_lock_path = BASE / 'prepared/source_lock.json'
    old_inventory = read(inventory_path)['data_inventory']
    prior_candidates = {r['key'] for r in old_inventory['candidate_inventory']['SARA_v2_Binary']}
    exposed = source_keys(read(old_manifest))
    ledger = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(ledger) + '?mode=ro', uri=True) as db:
        exposed.update(row[0] for row in db.execute('select distinct source from calls'))
        # A registered prospective source-key list is metadata, not access to
        # its text or labels. Count actual calls/oracles and exposure events;
        # otherwise the new study's own registration would expose all its stock
        # by definition and erase the distinction this audit must preserve.
        columns = {row[1] for row in db.execute('pragma table_info(oracle_views)')}
        for column in ('source', 'source_id', 'source_key'):
            if column in columns:
                exposed.update(row[0] for row in db.execute('select distinct ' + column + ' from oracle_views'))
        physical = db.execute('select count(*) from calls').fetchone()[0]
        reserved = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    prior_exposure = read(BASE / 'exposure/historical_exposure_index.json')
    exposed.update(prior_exposure['source_keys'])
    lock = read(source_lock_path)
    incidents = []
    affected = set()
    for path in [KNOWN_INCIDENT, *sorted((BASE / 'exposure/incidents').glob('*.json'))]:
        event = read(path)
        for cohort in event['conservative_affected_cohorts'].values():
            affected.update(cohort['sources'])
        incidents.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
    prepared = sara_v2(archive)
    available = {s.key for s in prepared.sources}
    legacy = available.intersection(exposed)
    newly_affected = available.intersection(affected) - legacy
    remaining = available - exposed - affected
    selected = {p: set(lock['sources'][p]).intersection(available) for p in ('dev', 'test')}
    record = {
        'protocol': 'pinned-SARA-Binary-full-source-identity-exposure-audit-v1',
        'archive_path': str(archive.relative_to(ROOT)), 'archive_sha256': sha(archive),
        'source_code_sha256': {str(Path(__file__).resolve().relative_to(ROOT)): sha(Path(__file__)),
                              'legal_skill_guard/rr/adapters.py': sha(ROOT / 'legal_skill_guard/rr/adapters.py')},
        'original_inventory_path': str(inventory_path.relative_to(ROOT)),
        'original_inventory_sha256': sha(inventory_path),
        'source_lock_path': str(source_lock_path.relative_to(ROOT)),
        'source_lock_sha256': sha(source_lock_path),
        'incidents': incidents, 'native_adapter_audit': prepared.audit,
        'all_available_unique_mothers': len(available),
        'historical_selected_called_or_oracle_exposed': len(legacy),
        'newly_exposed_unique_mothers': len(newly_affected),
        'remaining_unexposed_unique_mothers': len(remaining),
        'remaining_by_native_split': dict(Counter(s.native_split for s in prepared.sources if s.key in remaining)),
        'original_candidate_mothers': len(prior_candidates),
        'original_candidates_all_now_exposed': not (prior_candidates - exposed - affected),
        'original_selected_DEV_mothers': len(selected['dev']),
        'original_selected_TEST_mothers': len(selected['test']),
        'selected_DEV_TEST_sources_affected': selected['dev'].union(selected['test']).issubset(exposed | affected),
        'prospective_source_identity_registration_alone_not_counted_as_label_exposure': True,
        'all_available_source_keys_sha256': digest(sorted(available)),
        'remaining_source_keys': sorted(remaining),
        'no_new_cases_no_numeric_task_switch_no_relabelled_old_cases': True,
        'native_adapter_mechanically_separated_labels_not_printed_or_used_for_selection': True,
        'prepared_DEV_TEST_grading_files_not_opened_by_this_audit': True,
        'native_answers_public_questions_and_case_text_not_returned': True,
        'new_model_requests': 0, 'new_teacher_requests': 0,
        'continuous_physical_requests': physical, 'reserved': reserved,
        'scope': 'All original pinned local Binary release under the unchanged transitive stem/fact grouping;no assertion about future independent data outside this release',
        'implication': 'If zero remain,the original requirement of a fresh SARA Binary test cannot be satisfied from this local release;original TEST is exposed evidence and cannot be renamed fresh',
        'goal_complete': False}
    out = BASE / 'heldout_inventory_audit_v1' / digest(record)
    immutable_json(out / 'summary.json', record)
    return out, record


if __name__ == '__main__':
    out, summary = prepare()
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)),
                      **{k: summary[k] for k in ('all_available_unique_mothers',
                          'historical_selected_called_or_oracle_exposed', 'newly_exposed_unique_mothers',
                          'remaining_unexposed_unique_mothers', 'original_selected_DEV_mothers',
                          'original_selected_TEST_mothers', 'new_model_requests', 'reserved')}}, ensure_ascii=False))
