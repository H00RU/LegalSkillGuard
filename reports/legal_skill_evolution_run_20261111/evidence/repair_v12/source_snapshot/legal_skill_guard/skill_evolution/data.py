"""Native parent-source records, with actor inputs separate from annotations."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile
import tarfile
import re

from .objects import digest

MAUD_ARCHIVE_SHA256 = '75af5a33d038e9254864f043da38072490ffe11e8488d58d0a2dd39c8f554519'
MAUD_QUESTIONS = (
    'Knowledge Definition-Answer',
    'Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)',
    'Negative Interim Covenant includes carveout for pandemic responses-Answer (Y/N)',
)


def actor_view(source, view_id):
    """One native permission boundary; notably never mix OE EC and EV inputs."""
    views = [v for v in source['views'] if v['id'] == view_id]
    if len(views) != 1:
        raise ValueError('Native task view identity is missing or duplicated')
    return json.loads(json.dumps({'dataset': source['dataset'], 'task': views[0]}))


def maud_sources(archive, manifest):
    archive = Path(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != MAUD_ARCHIVE_SHA256:
        raise ValueError('The pinned native MAUD archive differs')
    selected = {r['original_contract_id']: (split, r)
                for split in ('train', 'dev', 'test') for r in manifest['datasets']['MAUD'][split]}
    if len(selected) != 64:
        raise ValueError('Use the exact fixed 24/8/32 parent manifest')
    native = {}
    counts = {}
    with zipfile.ZipFile(archive) as z:
        for split in ('train', 'dev', 'test'):
            name = 'data/MAUD_' + split + '.csv'
            reader = csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig')))
            number = 0
            for row in reader:
                number += 1
                if (row['data_type'] != 'main' or row['contract_name'] not in selected
                    or row['question'] not in MAUD_QUESTIONS):
                    continue
                key = (row['contract_name'], row['question'])
                if key in native:
                    raise ValueError('Ambiguous native main annotation; do not pick by answer')
                native[key] = {'row': row, 'native_file': name}
            counts[split] = number
        all_fulltext = {Path(name).stem: hashlib.sha256(z.read(name)).hexdigest()
                        for name in z.namelist() if name.startswith('data/contracts/') and name.endswith('.txt')}
    if counts != {'train': 25827, 'dev': 6753, 'test': 6651}:
        raise ValueError('Unexpected official row counts')
    if len(all_fulltext) != 152 or len(set(all_fulltext.values())) != 151:
        raise ValueError('Native full-document duplicate grouping differs')
    if all_fulltext['contract_148'] != all_fulltext['contract_149']:
        raise ValueError('Documented duplicate mother agreement was not reproduced')
    records = []
    public_hashes = {}
    for contract, (partition, expected) in selected.items():
        if expected['key'] != 'MAUD:' + digest(contract):
            raise ValueError('Original mother-source identity differs')
        views = []
        grading = {}
        expected_views = {v['question']: v for v in expected['native_task_views']}
        for question in MAUD_QUESTIONS:
            annotated = native[contract, question]
            row = annotated['row']
            if digest(row['text']) != expected_views[question]['context_sha256']:
                raise ValueError('Pinned native clause context differs: ' + contract)
            if len(row['text']) != expected_views[question]['context_characters']:
                raise ValueError('Native context length differs')
            labels = ['Actual knowledge', 'Constructive knowledge'] if question == MAUD_QUESTIONS[0] else ['Yes', 'No']
            if row['answer'] not in labels:
                raise ValueError('Unexpected native MAUD answer; no guessed normalization')
            views.append({'id': question, 'public': {'source_text': row['text'], 'question': question},
                          'answer_schema': {'type': 'string', 'enum': labels}})
            grading[question] = {'answer': row['answer'], 'native_file': annotated['native_file'],
                                 'native_row_question_id': row['id'], 'data_type': 'main'}
        raw_hash = all_fulltext[contract]
        if raw_hash in public_hashes:
            raise ValueError('Fixed partitions contain the same complete mother agreement twice')
        public_hashes[raw_hash] = partition
        records.append({'key': expected['key'], 'dataset': 'MAUD', 'split': partition,
            'parent_id': contract, 'fulltext_raw_sha256': raw_hash,
            'declared_full_contract_hash': expected['full_contract_hash'],
            'declared_task_input_hash': expected['task_input_hash'],
            'runtime_actor_views_sha256': digest(views), 'views': views, 'grading': grading})
    audit = {'archive_sha256': MAUD_ARCHIVE_SHA256, 'native_row_counts': counts,
        'original_parents': 152, 'raw_fulltext_clusters': 151,
        'fixed_source_counts': {p: sum(r['split'] == p for r in records) for p in ('train', 'dev', 'test')},
        'all_192_native_context_hashes_verified': True, 'duplicate_148_149_preserved_as_one_cluster': True,
        'runtime_hash_serialization': 'explicit task view object; original supplied task/fulltext hashes retained as provenance, not asserted byte-identical',
        'mechanical_annotation_preparation_only': True, 'model_or_teacher_test_access': False}
    return records, audit


def existing_four_sources(root, manifest):
    """Reuse verified public packets; restore CNLI's four native annotations.

    OE views remain separate: EV's legally supplied resolved EC information
    must never become part of the EC actor request.
    """
    root = Path(root)
    original_manifest = json.loads((root / 'reports/rr_v2_evidence/data_manifest.json').read_text())
    cache = root / 'data/packets/rr_v2'
    packet_hashes = original_manifest['packet_sha256']
    records = []
    labels = ('Entailment', 'Contradiction', 'NotMentioned')
    with zipfile.ZipFile(root / 'data/cache/rr_v2/contract-nli.zip') as z:
        contracts = {split: json.loads(z.read('contract-nli/' + split + '.json'))
                     for split in ('train', 'dev', 'test')}
    docs = {(split, str(doc['id'])): doc for split, data in contracts.items() for doc in data['documents']}
    with tarfile.open(root / 'data/cache/rr_v2/sara_v2.tar.gz') as t:
        sections = {Path(m.name).stem.removeprefix('section'): t.extractfile(m).read().decode()
                    for m in t.getmembers() if m.isfile() and m.name.startswith('sara_v2/statutes/source/section')}
    from legal_skill_guard.openexempt import answer_schema
    audit = {'original_packet_hashes_verified': {}, 'by_dataset': {},
        'CNLI_document_and_legacy_input_verified': 0, 'OE_view_permissions_separate': True,
        'reference_programs_or_hidden_case_metadata_in_actor_inputs': False,
        'mechanical_annotation_preparation_only': True}
    for split in ('train', 'dev', 'test'):
        p = cache / ('public_' + split + '.json')
        g = cache / 'grading_only' / (split + '.json')
        for path, key in ((p, 'public_' + split), (g, 'grading_' + split)):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != packet_hashes[key]:
                raise ValueError('Previously frozen native packet changed: ' + key)
            audit['original_packet_hashes_verified'][key] = actual
        public = {r['key']: r for r in json.loads(p.read_text())['sources']}
        grading = json.loads(g.read_text())['sources']
        for dataset in ('OpenExempt', 'SARA_v2_Binary', 'ContractNLI', 'RuleArena_Airline'):
            for expected in manifest['datasets'][dataset][split]:
                row = public[expected['key']]
                old = row['public']
                expected_hash = expected['legacy_nda11_content_hash'] if dataset == 'ContractNLI' else expected['content_hash']
                if row['group'] != expected['group'] or digest(old) != expected_hash or row['content_hash'] != expected_hash:
                    raise ValueError('Fixed original source identity or public content differs')
                native = grading[row['key']]
                views = []
                grade = {}
                if dataset == 'OpenExempt':
                    for family in ('EC', 'EV'):
                        views.append({'id': family, 'public': {'original_input': old['views'][family]},
                                      'answer_schema': answer_schema(family)})
                        grade[family] = {'answer': native['targets'][family], 'family': family}
                elif dataset == 'SARA_v2_Binary':
                    # Public legal context only. Resolve explicit references
                    # identically for NoSkill and all learned-library arms.
                    found = set(re.findall(r'\bsection\s+(\d+)\b', old['rules'], re.I))
                    related = {k: sections[k] for k in sorted(found) if k in sections and sections[k] != old['rules']}
                    views.append({'id': 'native', 'public': {'source_text': old['rules'],
                        'referenced_public_sections': related, 'facts': old['facts'], 'question': old['query']},
                        'answer_schema': {'type': 'string', 'enum': ['Entailment', 'Contradiction']}})
                    grade['native'] = {'answer': native['answer'], 'original_id': native['original_id']}
                elif dataset == 'RuleArena_Airline':
                    views.append({'id': 'native', 'public': {'source_text': old['rules'],
                        'facts': old['prompt'], 'question': 'What is the exact integer ticket plus fees for every current bag?'},
                        'answer_schema': {'type': 'integer', 'minimum': 0}})
                    grade['native'] = {'answer': native['answer']}
                else:
                    original_split = expected['native_split']
                    doc = docs[original_split, str(expected['original_document_id'])]
                    if doc['text'] != old['document']:
                        raise ValueError('Original NDA text differs')
                    annotations = doc['annotation_sets'][0]['annotations']
                    for question in manifest['query_views']['ContractNLI']:
                        item = annotations[question]
                        if item['choice'] not in labels:
                            raise ValueError('Unexpected original ContractNLI label')
                        views.append({'id': question, 'public': {'source_text': doc['text'],
                            'sentence_spans': doc['spans'],
                            'question': contracts[original_split]['labels'][question]['hypothesis']},
                            'answer_schema': {'type': 'string', 'enum': list(labels)}})
                        grade[question] = {'answer': item['choice'],
                            'evidence': item.get('spans') if item['choice'] != 'NotMentioned' else None}
                    audit['CNLI_document_and_legacy_input_verified'] += 1
                records.append({'key': row['key'], 'dataset': dataset, 'split': split,
                    'parent_id': row['group'], 'original_public_content_hash': expected_hash,
                    'runtime_actor_views_sha256': digest(views), 'views': views, 'grading': grade})
    for dataset in ('OpenExempt', 'SARA_v2_Binary', 'ContractNLI', 'RuleArena_Airline'):
        selected = [r for r in records if r['dataset'] == dataset]
        audit['by_dataset'][dataset] = {p: sum(r['split'] == p for r in selected) for p in ('train', 'dev', 'test')}
    return records, audit


def save_partitions(records, destination):
    destination = Path(destination)
    for split in ('train', 'dev', 'test'):
        selected = [r for r in records if r['split'] == split]
        folder = destination / ('sealed_test' if split == 'test' else split)
        folder.mkdir(parents=True, exist_ok=True)
        public = [{k: v for k, v in row.items() if k != 'grading'} for row in selected]
        grading = {row['key']: row['grading'] for row in selected}
        for name, value in (('public.json', public), ('grading.json', grading)):
            path = folder / name
            raw = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
            if path.exists() and path.read_text() != raw:
                raise ValueError('Prepared partition already differs; version changes explicitly')
            path.write_text(raw)
