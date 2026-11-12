"""TRAIN-only native lineage and mechanism opportunity, with no model calls.

Do not reconstruct all splits through data.existing_four_sources/maud_sources:
those entry points prepare TEST as well. Compare only current TRAIN mothers.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from legal_skill_guard.skill_evolution.data import MAUD_ARCHIVE_SHA256


def read(path):return json.loads(path.read_text())
def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def audit(root):
    prepared = root / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    public, grading = read(prepared / 'public.json'), read(prepared / 'grading.json')
    manifest = read(root / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    fixed = root / 'history/fixed_study_20261111'
    packets = fixed / 'data/packets/rr_v2'
    provenance = read(fixed / 'reports/rr_v2_evidence/data_manifest.json')
    packet_checks = {}
    for path, label in ((packets / 'public_train.json', 'public_train'),
                        (packets / 'grading_only/train.json', 'grading_train')):
        packet_checks[label] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert packet_checks[label] == provenance['packet_sha256'][label]
    frozen = read(root / 'artifacts/legal_skill_evolution_20261111/formal_v5/execution_manifest.json')
    prepared_checks = {}
    for path in (prepared / 'public.json', prepared / 'grading.json'):
        key = str(path.relative_to(root));prepared_checks[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert prepared_checks[key] == frozen['data'][key]
    legacy = {s['key']: s for s in read(packets / 'public_train.json')['sources']}
    old_grades = read(packets / 'grading_only/train.json')['sources']
    records, lineage = [], []
    for source in public:
        dataset, key = source['dataset'], source['key']
        expected = next(s for s in manifest['datasets'][dataset]['train'] if s['key'] == key)
        assert source['parent_id'] == (expected['original_contract_id'] if dataset == 'MAUD' else expected['group'])
        law_hashes = []
        for view in source['views']:
            if dataset == 'OpenExempt':
                text = view['public']['original_input']
                assert text.count('Statutes:\n') == 1 and text.count('\nFacts:\n') == 1
                # The native prompt supplies these explicit section boundaries.
                text = text.split('Statutes:\n', 1)[1].split('\nFacts:\n', 1)[0]
            else:text = view['public']['source_text']
            law_hashes.append(sha(text))
        item = {'source': key, 'dataset': dataset, 'parent': source['parent_id'],
            'view_ids': [v['id'] for v in source['views']], 'source_text_hash_per_view': law_hashes,
            'same_source_across_views': len(set(law_hashes)) == 1,
            'native_label_counts': dict(Counter(str(grading[key][v['id']]['answer'])
                for v in source['views'] if dataset in ('ContractNLI', 'MAUD', 'SARA_v2_Binary')))}
        if dataset == 'SARA_v2_Binary':
            item['referenced_section_ids'] = sorted(source['views'][0]['public']['referenced_public_sections'])
            item['complete_public_law_bundle_sha256'] = sha(json.dumps({k: source['views'][0]['public'][k]
                for k in ('source_text', 'referenced_public_sections')}, sort_keys=True))
        records.append(item)
        if dataset == 'MAUD':continue
        old = legacy[key]['public'];g = old_grades[key]
        for view in source['views']:
            a = grading[key][view['id']]
            if dataset == 'OpenExempt':
                assert view['public']['original_input'] == old['views'][view['id']]
                assert a['answer'] == g['targets'][view['id']]
            elif dataset == 'SARA_v2_Binary':
                assert view['public']['source_text'] == old['rules']
                assert view['public']['facts'] == old['facts'] and view['public']['question'] == old['query']
                assert a['answer'] == g['answer'] and a['original_id'] == g['original_id']
            elif dataset == 'RuleArena_Airline':
                assert view['public']['source_text'] == old['rules'] and view['public']['facts'] == old['prompt']
                assert a['answer'] == g['answer']
            else:continue
            lineage.append({'source': key, 'view': view['id'], 'public_and_native_answer_match': True,
                'basis': 'Pinned original TRAIN packet; not a new independent reference-program rerun'})
    # Only the native train member is opened. All current CNLI TRAIN parents
    # are verified to come from that native split before any annotation access.
    selected = manifest['datasets']['ContractNLI']['train']
    assert {s['native_split'] for s in selected} == {'train'}
    wanted = {str(s['original_document_id']): s['key'] for s in selected}
    current = {s['key']: s for s in public}
    with zipfile.ZipFile(fixed / 'data/cache/rr_v2/contract-nli.zip') as z:
        native = json.loads(z.read('contract-nli/train.json'))
    for doc in native['documents']:
        if str(doc['id']) not in wanted:continue
        key = wanted[str(doc['id'])];source = current[key]
        for view in source['views']:
            annotation = doc['annotation_sets'][0]['annotations'][view['id']]
            assert view['public']['source_text'] == doc['text']
            assert view['public']['sentence_spans'] == doc['spans']
            assert view['public']['question'] == native['labels'][view['id']]['hypothesis']
            assert grading[key][view['id']]['answer'] == annotation['choice']
            assert grading[key][view['id']]['evidence'] == (annotation.get('spans') if annotation['choice'] != 'NotMentioned' else None)
            lineage.append({'source': key, 'view': view['id'], 'public_and_native_answer_match': True,
                'basis': 'Original ContractNLI train document, hypothesis, choice and evidence span IDs'})
    maud = Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip')
    assert hashlib.sha256(maud.read_bytes()).hexdigest() == MAUD_ARCHIVE_SHA256
    wanted_maud = {s['parent_id']: s for s in public if s['dataset'] == 'MAUD'}
    with zipfile.ZipFile(maud) as z:
        files = {a['native_file'] for s in wanted_maud.values() for a in grading[s['key']].values()}
        for name in sorted(files):
            for row in csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))):
                if row['contract_name'] not in wanted_maud or row['data_type'] != 'main':continue
                source = wanted_maud[row['contract_name']];key = source['key']
                if row['question'] not in grading[key]:continue
                a = grading[key][row['question']]
                if a['native_file'] != name or a['native_row_question_id'] != row['id']:continue
                view = next(v for v in source['views'] if v['id'] == row['question'])
                assert view['public']['source_text'] == row['text'] and a['answer'] == row['answer']
                lineage.append({'source': key, 'view': view['id'], 'public_and_native_answer_match': True,
                    'basis': 'Pinned MAUD main row for the selected current TRAIN mother, native row ID, question and context'})
    assert len(lineage) == 280 and len({(r['source'], r['view']) for r in lineage}) == 280
    counts = {}
    for dataset in sorted({s['dataset'] for s in public}):
        rows = [r for r in records if r['dataset'] == dataset];groups = Counter(h for r in rows for h in set(r['source_text_hash_per_view']))
        per_view = defaultdict(set)
        for row in rows:
            for view, h in zip(row['view_ids'], row['source_text_hash_per_view']):per_view[view].add(h)
        counts[dataset] = {'parents': len(rows), 'native_views': sum(len(r['view_ids']) for r in rows),
            'distinct_source_texts_across_selected_views': len(groups), 'source_group_sizes': sorted(groups.values(), reverse=True),
            'distinct_source_texts_per_view': {k: len(v) for k, v in per_view.items()},
            'parents_with_different_view_local_contexts': sum(not r['same_source_across_views'] for r in rows)}
    partition_overlap = {}
    for dataset, data in manifest['datasets'].items():
        if dataset not in counts:continue
        train = {s['key'] for s in data['train']}
        partition_overlap[dataset] = {p: len(train & {s['key'] for s in data[p]}) for p in ('dev', 'test')}
    assert not any(v for x in partition_overlap.values() for v in x.values())
    return {'TRAIN_only_semantic_audit': True, 'frozen_DEV_TEST_evaluations_or_annotations_not_opened': True,
        'new_model_calls': 0, 'sources_unchanged': True, 'labels_unchanged': True,
        'parents': len(public), 'native_views': len(lineage), 'native_lineage_checks': lineage,
        'pinned_legacy_TRAIN_packet_hashes': packet_checks, 'original_formal_TRAIN_hashes': prepared_checks,
        'dataset_summary': counts, 'partition_ID_overlap': partition_overlap, 'sources': records,
        'scope_limits': ['Native label lineage is verified; it does not prove every human annotation unambiguous.',
            'MAUD has different public clause contexts per native question; a first-view-only contract reader cannot be applied to all three questions.',
            'Case counts do not equal independent law texts; shared-law datasets cannot establish cross-law compilation by themselves.',
            'The current prototype supports ContractNLI native outputs. Five-dataset application requires appropriate native consequence/output interfaces and actual evidence; no claim of present five-way compiler support.']}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1];result = audit(root)
    output = root / 'reports/legal_skill_evolution_run_20261111/current_TRAIN_fit_20261112.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('parents', 'native_views', 'dataset_summary', 'new_model_calls')}, ensure_ascii=False))
