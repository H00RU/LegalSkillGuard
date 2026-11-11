"""Accepted-version ancestry and the registered foreign-skill-off mask.

This module reads settled TRAIN checkpoints only. It neither dispatches models
nor infers a skill's origin from its name, dataset scores or teacher cohort.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from legal_skill_guard.skill_evolution.objects import Library, apply_revision_package


def load(path):return json.loads(Path(path).read_text())


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cited_sources(value):
    """Only literal Origin records count, rather than every context source."""
    sources = set()
    if isinstance(value, dict):
        if set(value) == {'source_id', 'view_id', 'quote'}:
            sources.add(value['source_id'])
        for item in value.values():sources.update(cited_sources(item))
    elif isinstance(value, (list, tuple)):
        for item in value:sources.update(cited_sources(item))
    return sources


def accepted_lineage(formal, arm, through_batch, source_datasets):
    formal = Path(formal)
    old = Library.load(formal / arm / 'B0.json')
    if old.skills:raise ValueError('Lineage must start at the actual empty formal library')
    files = {str(Path(arm) / 'B0.json'): sha(formal / arm / 'B0.json')}
    rows, pattern_origins = {}, {}
    for batch in range(1, through_batch + 1):
        paths = [Path(arm) / f'B{batch}.json', Path(arm) / f'update_B{batch}.json']
        new = Library.load(formal / paths[0])
        update = load(formal / paths[1])
        if update['old_library_hash'] != old.hash or update['new_library_hash'] != new.hash:
            raise ValueError('Accepted library ancestry does not match its update receipt')
        selected, mask = update['selected_candidate'], update['selected_mask']
        revisions, candidate = [], {}
        if selected is not None:
            path = Path(arm) / f'B{batch}_candidates' / f'{selected}.json'
            paths.append(path)
            candidate = load(formal / path)
            if type(mask) is not int or not 0 < mask < 1 << len(candidate['revisions']):
                raise ValueError('Invalid accepted candidate mask')
            if mask != candidate['selected_mask']:
                raise ValueError('Candidate and update acceptance masks differ')
            revisions = [r for index, r in enumerate(candidate['revisions']) if mask & (1 << index)]
        elif mask is not None:
            raise ValueError('An acceptance mask has no selected candidate')
        expected = apply_revision_package(old, revisions, old.hash)
        if {k: v.hash for k, v in expected.skills.items()} != {k: v.hash for k, v in new.skills.items()}:
            raise ValueError('The installed skills differ from the accepted revision package')
        for revision in revisions:
            identity = revision['skill_id']
            sources = cited_sources(revision['new'])
            pattern_donors = set()
            if revision['operation'] == 'learned_pattern':
                pattern_id = candidate.get('pattern_id')
                if pattern_id not in pattern_origins:
                    raise ValueError('A transplanted edit has no measured accepted pattern ancestry')
                pattern_donors = pattern_origins[pattern_id]
                sources.update(pattern_donors)
            if not sources or not sources <= set(source_datasets):
                raise ValueError('Accepted content has missing or non-TRAIN provenance')
            entry = {'batch': batch, 'operation': revision['operation'],
                'old_skill_hash': revision['old_hash'], 'new_skill_hash': revision['new_hash'],
                'cited_sources': sorted(sources),
                'cited_datasets': sorted({source_datasets[s] for s in sources}),
                'pattern_donor_sources': sorted(pattern_donors),
                'accepted_candidate': str(path), 'accepted_mask': mask}
            if identity not in rows:
                if revision['old_hash'] is not None:raise ValueError('A revised skill has no accepted ancestor')
                rows[identity] = {'skill_id': identity, 'first_batch': batch,
                    'first_sources': sorted(sources), 'first_datasets': entry['cited_datasets'],
                    'ancestral_sources': [], 'accepted_versions': []}
            row = rows[identity]
            row['ancestral_sources'] = sorted(set(row['ancestral_sources']) | sources)
            row['ancestral_datasets'] = sorted({source_datasets[s] for s in row['ancestral_sources']})
            row['accepted_versions'].append(entry)
            row['current_skill_hash'] = revision['new_hash']
        for pattern_id in update.get('learned_pattern_ids', []):
            if pattern_id not in {p['id'] for p in new.revision_patterns}:
                raise ValueError('An accepted learned pattern is absent from the actual library')
            donors = {s for r in revisions for s in rows[r['skill_id']]['ancestral_sources']}
            if not donors:raise ValueError('A learned edit pattern has no accepted content donors')
            pattern_origins[pattern_id] = donors
        files.update({str(path): sha(formal / path) for path in paths})
        old = new
    if set(rows) != set(old.skills):raise ValueError('The accepted lineage omits an installed skill')
    for identity, skill in old.skills.items():
        if rows[identity]['current_skill_hash'] != skill.hash:raise ValueError('Current accepted version changed')
    return {'arm': arm, 'through_batch': through_batch, 'library_hash': old.hash,
        'skills': rows, 'source_file_sha256': files,
        'pattern_donor_sources': {k: sorted(v) for k, v in pattern_origins.items()},
        'origin_policy': 'Union of literal TRAIN citations along accepted versions and accepted edit-pattern content donors; first acquisition separately retained.',
        'teacher_cohort_not_used_as_origin': True, 'new_model_calls': 0}


def foreign_off(library, lineage, target_dataset):
    """Keep target-only ancestry, then close removals over actual dependencies.

    Mixed-origin skills count as foreign for this target-only contrast. Pattern
    memory is left byte-identical because frozen inference never updates from it.
    """
    if library.hash != lineage['library_hash'] or set(library.skills) != set(lineage['skills']):
        raise ValueError('A transfer mask requires the exact accepted library lineage')
    removed = {identity: {'reason': 'foreign_or_mixed_accepted_ancestry',
                          'ancestral_datasets': row['ancestral_datasets']}
        for identity, row in lineage['skills'].items() if row['ancestral_datasets'] != [target_dataset]}
    while True:
        additional = {}
        for identity, skill in library.skills.items():
            if identity in removed:continue
            dependencies = {p['skill_id'] for p in skill.inputs.values() if p['mode'] == 'skill'}
            lost = dependencies & set(removed)
            if lost:additional[identity] = {'reason': 'depends_on_removed_skill', 'lost_producers': sorted(lost)}
        if not additional:break
        removed.update(additional)
    result = Library(skills={k: deepcopy(v) for k, v in library.skills.items() if k not in removed},
                     revision_patterns=deepcopy(library.revision_patterns))
    missing = {k: sorted({p['skill_id'] for p in s.inputs.values()
                         if p['mode'] == 'skill' and p['skill_id'] not in library.skills})
               for k, s in library.skills.items()}
    return result, {'target_dataset': target_dataset, 'unmasked_library_hash': library.hash,
        'masked_library_hash': result.hash, 'kept_skill_ids': sorted(result.skills),
        'removed_skills': removed, 'preexisting_missing_dependencies': {k: v for k, v in missing.items() if v},
        'mask_uses_TEST_labels_or_scores': False, 'retraining': False,
        'pattern_memory_unchanged': result.revision_patterns == library.revision_patterns,
        'interpretation': 'Full B8 versus fixed target-only accepted ancestry; dependency closure is part of removing foreign availability.'}


def actual_use(parent, library, lineage):
    """Separate executed attempts from skills that supplied the final answer."""
    if parent['library_hash'] != library.hash or lineage['library_hash'] != library.hash:
        raise ValueError('Execution and lineage must refer to the same library')
    rows = []
    for view in parent['views']:
        execution = view['execution']
        applied = set()
        for event in execution['events']:
            if event.get('kind') != 'APPLY':continue
            identity = event['skill_id']
            if identity not in library.skills or event['skill_hash'] != library.skills[identity].hash:
                raise ValueError('An APPLY trace differs from the actual frozen skill version')
            applied.add(identity)
        final = set()
        if execution['core_executed']:
            pending = [execution['terminal_skill']]
            while pending:
                identity = pending.pop()
                if identity in final:continue
                if identity not in applied:raise ValueError('The claimed final path lacks its actual APPLY trace')
                final.add(identity)
                pending.extend(p['skill_id'] for p in library.skills[identity].inputs.values() if p['mode'] == 'skill')
        foreign = sorted(k for k in final if lineage['skills'][k]['ancestral_datasets'] != [parent['dataset']])
        rows.append({'source': parent['source'], 'dataset': parent['dataset'], 'view': view['view'],
            'applied_skill_ids': sorted(applied), 'final_answer_skill_ids': sorted(final),
            'foreign_final_answer_skill_ids': foreign, 'fallback': execution['fallback'],
            'core_executed': execution['core_executed'], 'native_grade': view['score']['grade'],
            'fully_correct_foreign_core': bool(foreign) and bool(view['score']['correct'])})
    return rows
