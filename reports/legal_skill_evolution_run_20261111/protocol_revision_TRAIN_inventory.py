"""Inventory original TRAIN objects before the newly authorized finite study.

No model calls, grading labels, DEV/TEST examples or predictions are loaded.
Exposure flags describe preserved teacher receipts, never a fresh blind split.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from legal_skill_guard.skill_evolution.objects import Library, coupled_blocks

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text())


def main():
    public = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    manifest_path = ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json'
    sources = read(public);manifest = read(manifest_path)
    metadata = {row['key']: row for data in manifest['datasets'].values() for row in data['train']}
    if len(sources) != 128 or {s['key'] for s in sources} != set(metadata):
        raise ValueError('The original TRAIN identity set changed')
    evidence = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (public, manifest_path)}
    seen_by_teacher, receipt_count = set(), 0
    base = ROOT / 'artifacts/legal_skill_evolution_20261111'
    for folder in sorted(base.iterdir()):
        if not folder.name.startswith(('pilot_v', 'formal_v', 'repair_v')):continue
        for path in sorted(folder.glob('*/teacher_B*.json')):
            reply = read(path)
            seen_by_teacher.update(reply['source_ids']);receipt_count += 1
            evidence[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    parent_rows = []
    for source in sources:
        meta = metadata[source['key']]
        views = []
        for view in source['views']:
            supplied = view['public'];question = supplied.get('question', '')
            views.append({'view': view['id'], 'question': question,
                'public_fields': sorted(supplied), 'separate_case_facts_supplied': 'facts' in supplied,
                'explicit_question_section_numbers': re.findall(r'(?:section|Section|§)\s*(\d+(?:\([a-zA-Z0-9]+\))*)', question),
                'referenced_public_section_keys': sorted(supplied.get('referenced_public_sections', {})),
                'source_text_sha256': hashlib.sha256(supplied.get('source_text', supplied.get('original_input', '')).encode()).hexdigest()})
        if source['dataset'] != 'MAUD' and source['parent_id'] != meta['group']:
            raise ValueError('Prepared mother group differs from its original manifest')
        parent_rows.append({'source': source['key'], 'dataset': source['dataset'],
            'mother_group': source['parent_id'],
            'fulltext_cluster_members': meta['source_cluster_members'] if source['dataset'] == 'MAUD' else [source['parent_id']],
            'original_document_id': meta.get('original_document_id'),
            'prior_study_teacher_receipt_exposure': source['key'] in seen_by_teacher,
            'all_original_TRAIN_parents_already_had_executor_initial_attempts': True,
            'views': views})
    assets, hashes = [], set()
    for stage in ('formal_v5', 'pilot_v11'):
        for arm in ('Full', 'FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Lift+GenericJoint', 'AllPorts+CoRev'):
            for path in sorted((base / stage / arm).glob('B[0-8].json')):
                library = Library.load(path)
                for skill in library.skills.values():
                    if skill.hash in hashes:continue
                    hashes.add(skill.hash)
                    blocks = [b for b in coupled_blocks(skill)
                              if all(skill.premises[n]['mode'] == 'constant' for n in b)]
                    dependencies = [p for p in skill.inputs.values() if p['mode'] == 'skill']
                    if not blocks and not dependencies and stage != 'pilot_v11':continue
                    assets.append({'library': str(path.relative_to(ROOT)), 'skill_id': skill.id,
                        'skill_hash': skill.hash, 'intent': skill.intent,
                        'constant_premise_blocks': blocks, 'dependency_inputs': dependencies,
                        'source_origins': sorted({p['source_id'] for p in skill.source_provenance}),
                        'accepted_in_prior_run_is_not_new_mechanism_evidence': True})
                    evidence[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    # Preserve the already measured independent SARA acquisitions as scoped
    # assets. They are not silently imported into a new learning arm.
    for arm in ('Full', 'FreeEvolution'):
        path = REPORT / 'activation_evidence/body_adapter_replay' / arm / 'B1.json'
        library = Library.load(path)
        for skill in library.skills.values():
            if skill.hash in hashes:continue
            hashes.add(skill.hash)
            assets.append({'library': str(path.relative_to(ROOT)), 'skill_id': skill.id,
                'skill_hash': skill.hash, 'intent': skill.intent,
                'constant_premise_blocks': [b for b in coupled_blocks(skill)
                    if all(skill.premises[n]['mode'] == 'constant' for n in b)],
                'dependency_inputs': [p for p in skill.inputs.values() if p['mode'] == 'skill'],
                'source_origins': sorted({p['source_id'] for p in skill.source_provenance}),
                'accepted_in_prior_run_is_not_new_mechanism_evidence': True,
                'new_source_reuse_not_validated': True,
                'comparison_mode_and_acquisition_cost_attribution_must_be_explicit': True})
        evidence[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    remaining = Counter(row['dataset'] for row in parent_rows if not row['prior_study_teacher_receipt_exposure'])
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'grading_labels_loaded': False, 'DEV_TEST_examples_or_predictions_loaded': False,
        'original_TRAIN_parent_count': len(parent_rows), 'parent_rows': parent_rows,
        'preserved_teacher_receipts_scanned': receipt_count,
        'parents_without_known_prior_study_teacher_receipt_exposure': dict(remaining),
        'exposure_interpretation': 'Known original-study teacher receipt exposure only; all sources are already-seen TRAIN. Absence from receipts is not a claim of no historical exposure or a new blind evaluation.',
        'source_topics_are_navigation_not_semantic_dependency_proof': True,
        'prior_skill_assets': assets, 'evidence_sha256': evidence,
        'no_sources_selected_or_model_protocol_started_yet': True,
        'next': 'Read source clauses and actual legal computations to select a finite natural-mechanism cohort; exclude pure rendering edges and reuse already completed negative evidence.'}
    (REPORT / 'protocol_revision_TRAIN_inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'original_TRAIN_parents': len(parent_rows), 'known_teacher_exposed_parents': sum(r['prior_study_teacher_receipt_exposure'] for r in parent_rows),
        'parents_without_known_current_study_teacher_exposure': dict(remaining),
        'prior_skill_asset_versions': len(assets), 'new_model_calls': 0, 'grading_or_DEV_TEST_data_loaded': False}))


if __name__ == '__main__':main()
