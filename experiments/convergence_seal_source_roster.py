"""Lock the existing source roster against identity, exposure, and split receipts.

Uses identity metadata, public TRAIN versions, historical exposure and ledger
source IDs. Sealed TEST inputs and grading files stay closed.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.two_method_heldout_exposure_gate import KNOWN_INCIDENT
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/legal_skill_convergence_20261117'
HANDOFF = BASE / 'handoff'
OLD = ROOT / 'artifacts/two_method_followthrough_20261116'
PROTOCOL = ROOT / 'reports/legal_skill_convergence_20261117/protocol.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    cfg = read(PROTOCOL)['data']
    normalized = ROOT / read(HANDOFF / 'normalized_inputs_current.json')['artifact_root']
    roster = ROOT / read(HANDOFF / 'source_metadata_current.json')['artifact_root']
    maud = read(HANDOFF / 'contract_nearduplicate_current.json')
    diversity = read(HANDOFF / 'diversity_holdout_current.json')
    if not maud['candidate_pass'] or not diversity['all_selected_groups_distinct']:
        raise ValueError('An existing duplicate or exposure receipt does not permit sealing')
    normalized_protocol = read(normalized / 'protocol.json')
    if normalized_protocol['Diversity_holdout_root'] != diversity['artifact_root']:
        raise ValueError('The Diversity grouping receipt and current candidates differ')
    maud_protocol = read(ROOT / maud['artifact_root'] / 'protocol.json')
    if maud_protocol['input_root'] != str(normalized.relative_to(ROOT)):
        raise ValueError('The MAUD near-duplicate receipt covers a different normalized roster')

    identities = read(normalized / 'identity_metadata.json')
    by_source = {row['source']: row for row in identities}
    if len(identities) != len(by_source):
        raise ValueError('A source entered more than one partition')
    datasets = cfg['train_quota']
    expected_counts = {
        'train': Counter(datasets),
        'dev': Counter({dataset: cfg['dev_per_dataset'] for dataset in datasets}),
        'test': Counter({dataset: cfg['fresh_test_per_dataset'] for dataset in datasets}),
    }
    for partition, expected in expected_counts.items():
        actual = Counter(row['dataset'] for row in identities if row['project_split'] == partition)
        if actual != expected:
            raise ValueError('Fixed quota mismatch in ' + partition)

    def diversity_identity(row):
        body = row['views'][0]['public']['source_text']
        return row['dataset_revision'], row['native_config'], row['native_id'], digest(body)

    current_diversity = {diversity_identity(row): row['key']
                         for row in read(normalized / 'train/public.json')
                         if row['dataset'] == 'LegalBench_Diversity'}
    old_diversity = {diversity_identity(row): row['key']
                     for row in read(roster / 'TRAIN_raw_public.json')
                     if row['dataset'] == 'LegalBench_Diversity'}
    if (len(current_diversity) != datasets['LegalBench_Diversity']
            or old_diversity.keys() != current_diversity.keys()):
        raise ValueError('The native dataset revision, TRAIN index or raw Diversity text changed')
    # The prior metadata predates the native-split identity fix. Carry each
    # batch assignment over its explicit native row and unchanged text.
    aliases = {old_key: current_diversity[identity]
               for identity, old_key in old_diversity.items()
               if old_key != current_diversity[identity]}
    batches = {number: [] for number in range(1, cfg['batches'] + 1)}
    for old in read(roster / 'TRAIN_roster.json'):
        row = by_source[aliases.get(old['source'], old['source'])]
        if row['project_split'] != 'train' or row['dataset'] != old['dataset']:
            raise ValueError('Fixed training source identity or partition changed')
        batches[old['batch']].append(row)
    if (len({row['source'] for batch in batches.values() for row in batch}) != cfg['train_total_mother_sources']
            or any(len(batch) != cfg['batch_size'] for batch in batches.values())):
        raise ValueError('The eight fixed batches must cover every original TRAIN mother once')

    audit = ROOT / read(HANDOFF / 'source_audit_current.json')['artifact_root']
    pilot = read(audit / 'pilot20.json')
    pilot_set = {row['source'] for row in pilot}
    if len(pilot_set) != cfg['pilot_total_mother_sources']:
        raise ValueError('The structure-selected pilot changed')
    if any(by_source[row['source']]['project_split'] != 'train'
           or by_source[row['source']]['public_content_sha256'] != row['public_sha256'] for row in pilot):
        raise ValueError('A pilot source has a different normalized fingerprint')

    metadata_path = roster / 'TEST_candidate_identity_metadata.json'
    four_library = read(metadata_path)
    test_rows = [row for row in identities if row['project_split'] == 'test']
    if {row['key'] for row in four_library} != {
            row['source'] for row in test_rows if row['dataset'] != 'LegalBench_Diversity'}:
        raise ValueError('The four-library isolation audit covers different sources')
    if len({(row['dataset'], row['template_group']) for row in four_library}) != len(four_library):
        raise ValueError('Selected TEST candidates share a template group')

    historical = OLD / 'exposure/historical_exposure_index.json'
    historical_record = read(historical)
    if historical_record['failures']:
        raise ValueError('Historical exposure provenance could not be fully decoded')
    exposed = set(historical_record['source_keys'])
    incidents = sorted({Path(KNOWN_INCIDENT), *(OLD / 'exposure/incidents').glob('*.json')})
    for path in incidents:
        for cohort in read(path)['conservative_affected_cohorts'].values():
            exposed.update(cohort['sources'])
    ledger = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect(ledger.as_uri() + '?mode=ro', uri=True) as db:
        exposed.update(row[0] for row in db.execute('select distinct source from calls'))
        ledger_rows = db.execute('select count(*) from calls').fetchone()[0]
    conflicts = exposed.intersection(row['source'] for row in test_rows)
    if conflicts:
        raise ValueError(f'{len(conflicts)} TEST candidates conflict with current exposure records')

    binding = {
        'kind': 'convergence_source_roster_v1',
        'plan_protocol_sha256': sha(PROTOCOL),
        'normalized_root': str(normalized.relative_to(ROOT)),
        'identity_metadata_sha256': sha(normalized / 'identity_metadata.json'),
        'baseline_TRAIN_roster_sha256': sha(roster / 'TRAIN_roster.json'),
        'verified_native_split_key_migrations': aliases,
        'four_library_TEST_metadata_sha256': sha(metadata_path),
        'historical_exposure_sha256': sha(historical),
        'incident_sha256': {str(path.relative_to(ROOT)): sha(path) for path in incidents},
        'MAUD_duplicate_audit_sha256': sha(HANDOFF / 'contract_nearduplicate_current.json'),
        'Diversity_group_audit_sha256': sha(HANDOFF / 'diversity_holdout_current.json'),
        'pilot_sha256': sha(audit / 'pilot20.json'),
        'current_exposure_keys_sha256': digest(sorted(exposed)),
        'roster_code_sha256': sha(Path(__file__)),
        'ledger_rows_at_check': ledger_rows,
        'partition_counts': {partition: sum(value.values()) for partition, value in expected_counts.items()},
        'fixed_training_batches': list(batches.values()),
        'fixed_pilot': pilot,
        'sealed_TEST_identities': test_rows,
        'frozen_model_or_library': False,
    }
    out = BASE / 'sealed_source_roster_v1' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    receipt = {'artifact_root': str(out.relative_to(ROOT)), 'roster_sha256': digest(binding),
               'partition_counts': binding['partition_counts'], 'training_batches': len(batches),
               'pilot_sources': len(pilot), 'current_TEST_exposure_conflicts': 0,
               'TEST_text_or_grading_opened': False, 'full_model_and_library_freeze': False,
               'new_generation_calls': 0}
    immutable_json(out / 'receipt.json', receipt)
    (HANDOFF / 'sealed_source_roster_current.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    run()
