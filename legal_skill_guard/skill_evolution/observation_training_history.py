"""Expose failed revisions, not just the retained library, to the next update.

All records come from completed original TRAIN batches. The same history goes
to both arms, including unsuccessful proposals that would otherwise disappear
when candidate selection retains the old library. No DEV/TEST is read.
"""
from copy import deepcopy
import json
from pathlib import Path

from .objects import digest


def teaching_rows(value):
    """Avoid resending deterministic graph dumps in every actual case row.

    Observations, conversions, execution, native/source feedback and full errors
    stay byte-value identical. The graph's hash is retained, and the unchanged
    author program plus public dependency algorithm are supplied once instead.
    Full original rows remain in their immutable artifacts.
    """
    value = deepcopy(value)
    if isinstance(value, dict):
        if isinstance(value.get('plan'), dict) and 'public_dependency' in value['plan']:
            graph = value['plan'].pop('public_dependency')
            value['plan']['public_dependency_sha256'] = digest(graph)
        return {k: teaching_rows(v) for k, v in value.items()}
    if isinstance(value, list):
        return [teaching_rows(v) for v in value]
    return value


def completed_history(folder, before_batch, arms, *, prior_folders=()):
    folder = Path(folder)
    read = lambda p: json.loads(p.read_text())
    history = []
    for batch in range(1, before_batch):
        choices = [Path(p) / f'B{batch}' for p in (folder, *prior_folders)]
        root = next((p for p in choices if (p / 'checkpoint.json').exists()
            and all((p / arm / 'teacher.json').exists() for arm in arms)), choices[0])
        checkpoint = root / 'checkpoint.json'
        if not checkpoint.exists():
            raise ValueError('Do not learn from an unfinished preceding batch')
        scores = {str(p.relative_to(root / 'candidate_scores')): teaching_rows(read(p))
            for p in sorted((root / 'candidate_scores').rglob('*.json'))}
        history.append({'batch': batch, 'actual_initial_rows': teaching_rows(read(root / 'initial_scored_results.json')),
            'original_public_TRAIN_cases': read(root / 'teacher_task.json')['acquisition_cases'],
            'actual_candidate_execution_and_source_reviews': scores,
            'actual_teacher_proposals': {arm: read(root / arm / 'teacher.json')['value'] for arm in arms},
            'actual_selected_checkpoint': read(checkpoint),
            'only_repeated_deterministic_graph_metadata_projected_not_source_or_error': True,
            'failed_revisions_retained_even_when_old_library_selected': True})
    return history
