"""Monotone source-level exposure facts checked before formal dispatch.

Incident records contain identities and hashes, never answer labels. An old
source lock or a renamed prepared directory cannot reset a later exposure.
"""
from pathlib import Path
import json


KNOWN_INCIDENT = Path(__file__).resolve().parents[1] / 'docs/HELDOUT_EXPOSURE_20261117.json'


class HeldoutExposureError(ValueError):
    pass


def inspect_exposure(source_lock, incidents_dir):
    selected = {split: set(source_lock['sources'][split]) for split in ('dev', 'test')}
    affected = {split: set() for split in selected}
    incidents, seen = [], {}
    # The known event travels with the source checkout. Missing ignored
    # artifact directories cannot erase this exposure when reproducing.
    paths = [KNOWN_INCIDENT, *sorted(Path(incidents_dir).glob('*.json'))]
    for path in paths:
        event = json.loads(path.read_text())
        identity = event['incident_id']
        if identity in seen:
            if seen[identity] != event:
                raise ValueError('An exposure event has conflicting revisions')
            continue
        seen[identity] = event
        cohorts = event['conservative_affected_cohorts']
        if not isinstance(cohorts, dict):
            raise ValueError('An exposure event needs explicit source cohorts')
        matches = {split: set() for split in selected}
        for cohort in cohorts.values():
            keys = cohort['sources']
            if not isinstance(keys, list) or any(not isinstance(key, str) for key in keys):
                raise ValueError('Exposure identities must be explicit source keys')
            # A formerly exposed DEV source is also exposed if moved to TEST.
            for split in selected:
                matches[split].update(selected[split].intersection(keys))
        for split in selected:
            affected[split].update(matches[split])
        if any(matches.values()):
            incidents.append({'incident_id': event['incident_id'], 'path': str(path),
                              'affected_counts': {s: len(v) for s, v in matches.items()}})
    return {'heldout_source_cohorts_unexposed': not any(affected.values()),
            'affected_counts': {split: len(keys) for split, keys in affected.items()},
            'incidents': incidents, 'answer_labels_read_by_this_gate': False,
            'new_model_requests': 0, 'source_lock_freshness_claim_cannot_reset_exposure': True}


def assert_unexposed_cohorts(source_lock, incidents_dir):
    receipt = inspect_exposure(source_lock, incidents_dir)
    if not receipt['heldout_source_cohorts_unexposed']:
        counts = receipt['affected_counts']
        raise HeldoutExposureError(
            f"Recorded heldout exposure affects DEV{counts['dev']}/TEST{counts['test']};"
            'preserve these cohorts as exposed evidence and resolve fresh inventory before dispatch')
    return receipt
