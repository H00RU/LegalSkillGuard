"""B8-gated materialization of the prequalified native TEST set.

This module cannot dispatch models. Before B8 it never opens sealed TEST or
the native ContractNLI annotation archive. Original packets stay untouched.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.adapters import _clusters
from legal_skill_guard.rr.partitions import Source, normalized_text
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.data import existing_four_sources, maud_sources
from experiments.legal_skill_evolution_formal import ARMS, schedule, PROFILE as ACTIVE_FORMAL_PROFILE

ROOT = Path(__file__).resolve().parents[1]


def load(path):return json.loads(path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def require_B8(root):
    root = Path(root)
    profile_path = root / ACTIVE_FORMAL_PROFILE.relative_to(ROOT)
    profile = load(profile_path)
    formal = root / profile['artifacts']
    complete_path = formal / 'training_DEV_completed.json'
    if not complete_path.exists():raise ValueError('B8 learning and all registered DEV points are not complete; TEST stays sealed')
    complete = load(complete_path)
    if complete['training_sources'] != 128 or complete['batches'] != 8:
        raise ValueError('The fixed complete study is required before TEST')
    execution = load(formal / 'execution_manifest.json')
    if sha(profile_path) != execution['profile_sha256']:raise ValueError('Formal profile changed')
    for relative, expected in {**execution['code'], **execution['data']}.items():
        if sha(root / relative) != expected:raise ValueError('Frozen formal dependency changed: ' + relative)
    manifest = load(root / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    batches = [[r['source_key'] for r in b['sources']] for b in manifest['source_sequence']]
    libraries = {}
    for arm in ARMS:
        if Library.load(formal / arm / 'B0.json').skills:raise ValueError('A formal arm did not start empty')
        for batch, expected in enumerate(batches, 1):
            initial = load(formal / arm / f'initial_B{batch}.json')
            if initial['binding']['source_ids'] != expected or [r['source'] for r in initial['results']] != expected:
                raise ValueError('Formal first-attempt sources differ from the fixed order')
            if arm != 'NoSkill':
                update = load(formal / arm / f'update_B{batch}.json')
                if update['new_library_hash'] != Library.load(formal / arm / f'B{batch}.json').hash:
                    raise ValueError('An accepted update and library differ')
        library = Library.load(formal / arm / 'B8.json')
        if library.hash != complete['B8_library_hashes'][arm]:raise ValueError('B8 library differs from completion record')
        libraries[arm] = library
    for action, arm, batch in schedule():
        if action != 'dev':continue
        point = load(formal / 'dev' / arm / f'B{batch}.json')
        if point['library_hash'] != Library.load(formal / arm / f'B{batch}.json').hash:
            raise ValueError('Registered DEV point is missing or uses another library')
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('An in-flight physical request remains; do not start frozen evaluation')
    return profile, formal, libraries


def replacement_record(doc, group, hypothesis_definitions, expected):
    """Only called on authorized frozen annotations after the B8 gate."""
    legacy = Source('ContractNLI', group, {'document': doc['text'],
        'query': hypothesis_definitions['nda-11']['hypothesis'], 'answer_type': 'contract_nli'}, 'test')
    if (str(doc['id']) != str(expected['id']) or legacy.key != expected['key']
            or legacy.content_key != expected['content_hash'] or group != expected['group']):
        raise ValueError('Native replacement differs from the prequalified identity and body')
    views, grading = [], {}
    annotations = doc['annotation_sets'][0]['annotations']
    for question in ('nda-5', 'nda-7', 'nda-16', 'nda-20'):
        annotation = annotations[question]
        choice = annotation['choice']
        if choice not in ('Entailment', 'Contradiction', 'NotMentioned'):
            raise ValueError('Unexpected native label; do not guess a normalization')
        views.append({'id': question, 'public': {'source_text': doc['text'],
            'sentence_spans': doc['spans'], 'question': hypothesis_definitions[question]['hypothesis']},
            'answer_schema': {'type': 'string', 'enum': ['Entailment', 'Contradiction', 'NotMentioned']}})
        grading[question] = {'answer': choice, 'evidence': annotation.get('spans') if choice != 'NotMentioned' else None}
    public = {'key': legacy.key, 'dataset': 'ContractNLI', 'split': 'test', 'parent_id': group,
        'original_public_content_hash': legacy.content_key, 'runtime_actor_views_sha256': digest(views), 'views': views}
    return public, grading


def materialize(root=ROOT):
    root = Path(root)
    profile, formal, libraries = require_B8(root)  # Must precede every TEST read.
    plan_path = root / 'reports/legal_skill_evolution_run_20261111/qualified_TEST_identity_plan.json'
    plan = load(plan_path)
    if plan['teacher_request_key_audit']['qualified_identity_mentions_for_review'] or plan['continuous_ledger_qualified_TEST_requests']:
        raise ValueError('Resolve the known qualified-source exposure records before freezing')
    old_key = plan['known_exposed_removed_for_confirmatory_freeze']['key']
    replacement = plan['predeclared_hash_order_replacement']
    destination = root / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'
    existing = destination / 'native_materialization.json'
    if existing.exists():
        saved = load(existing)
        if (saved['original_B8_hashes'] != {a: l.hash for a, l in libraries.items()}
                or sha(destination / 'prepared_test/public.json') != saved['qualified_public_sha256']
                or sha(destination / 'prepared_test/grading.json') != saved['qualified_grading_sha256']):
            raise ValueError('Existing B8 materialization no longer matches its frozen data/libraries')
        print(json.dumps({'B8_verified': True, 'existing_materialization_reused': True, 'new_model_calls': 0}))
        return
    prepared = root / 'artifacts/legal_skill_evolution_20261111/prepared/sealed_test'
    public, grading = load(prepared / 'public.json'), load(prepared / 'grading.json')
    # Rebuild from the same pinned native sources rather than treating a
    # conveniently present grading cache as an independent authority.
    source_manifest = load(root / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    four, _ = existing_four_sources(root, source_manifest)
    maud_archive = Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip')
    maud, _ = maud_sources(maud_archive, source_manifest)
    rebuilt = [r for r in four + maud if r['split'] == 'test']
    rebuilt_public = [{k: v for k, v in r.items() if k != 'grading'} for r in rebuilt]
    rebuilt_grading = {r['key']: r['grading'] for r in rebuilt}
    if public != rebuilt_public or grading != rebuilt_grading:
        raise ValueError('The original sealed TEST packet differs from pinned native reconstruction')
    archive = root / 'data/cache/rr_v2/contract-nli.zip'
    if sha(archive) != plan['native_ContractNLI_archive_sha256_before_TEST']:
        raise ValueError('The native annotation archive changed after identity qualification')
    documents = []
    with zipfile.ZipFile(archive) as z:
        for split in ('train', 'dev', 'test'):
            data = json.loads(z.read('contract-nli/' + split + '.json'))
            for doc in data['documents']:documents.append((split, doc, data['labels']))
    keys = [['url:' + doc['url'] if doc['url'] else '', 'text:' + normalized_text(doc['text'])]
            for _, doc, _ in documents]
    groups = _clusters([doc for _, doc, _ in documents], keys)
    candidates = [(doc, group, definitions) for (split, doc, definitions), group in zip(documents, groups)
                  if split == 'test' and str(doc['id']) == str(replacement['id'])]
    if len(candidates) != 1:raise ValueError('The native replacement must identify one original TEST document')
    new_public, new_grading = replacement_record(*candidates[0], replacement)
    if sum(r['key'] == old_key for r in public) != 1:raise ValueError('The original exposed mother identity changed')
    qualified_public = [new_public if r['key'] == old_key else r for r in public]
    qualified_grading = {k: v for k, v in grading.items() if k != old_key}
    qualified_grading[new_public['key']] = new_grading
    if set(r['key'] for r in qualified_public) != set(plan['qualified_TEST_source_keys']):
        raise ValueError('Materialized identities differ from the qualification plan')
    if set(qualified_grading) != set(plan['qualified_TEST_source_keys']):raise ValueError('Grading/source partition differs')
    development = {r['key'] for dataset in source_manifest['datasets'].values()
                   for split in ('train', 'dev') for r in dataset[split]}
    if set(qualified_grading) & development:raise ValueError('Qualified TEST overlaps TRAIN/DEV')
    if len(qualified_public) != 160 or sum(len(r['views']) for r in qualified_public) != 352:
        raise ValueError('Fixed TEST parent/view count changed')
    immutable_json(destination / 'prepared_test/public.json', qualified_public)
    immutable_json(destination / 'prepared_test/grading.json', qualified_grading)
    for arm, library in libraries.items():
        # Provisional TRAIN replay logs are audit artifacts, not inference
        # objects. Remove them without changing the frozen functional hash.
        runtime = Library(skills=deepcopy(library.skills), revision_patterns=deepcopy(library.revision_patterns))
        if runtime.hash != library.hash:raise ValueError('Runtime compaction changed the B8 function')
        runtime.save(destination / 'libraries' / (arm + '_B8.json'))
    receipt = {'materialized_utc': datetime.now(timezone.utc).isoformat(), 'batch': 8,
        'original_formal_profile_sha256': sha(root / ACTIVE_FORMAL_PROFILE.relative_to(ROOT)),
        'original_B8_hashes': {arm: library.hash for arm, library in libraries.items()},
        'qualified_public_sha256': sha(destination / 'prepared_test/public.json'),
        'qualified_grading_sha256': sha(destination / 'prepared_test/grading.json'),
        'native_ContractNLI_archive_sha256': sha(archive), 'identity_plan_sha256': sha(plan_path),
        'native_MAUD_archive_sha256': sha(maud_archive), 'original_native_reconstruction_equal': True,
        'identity_adapter_code_sha256': {p: sha(root / p) for p in (
            'legal_skill_guard/rr/adapters.py', 'legal_skill_guard/rr/partitions.py', 'legal_skill_guard/rr/coverage.py')},
        'TEST_source_count': 160, 'TEST_native_views': 352, 'new_model_calls': 0,
        'original_sealed_packets_unchanged': True, 'teacher_TEST_access': False,
        'original_537_retained_only_in_original_packet': True, 'new_native_document_id': replacement['id']}
    immutable_json(destination / 'native_materialization.json', receipt)
    print(json.dumps({'B8_verified': True, 'qualified_TEST_parents': 160, 'native_views': 352, 'new_model_calls': 0}))


if __name__ == '__main__':materialize()
