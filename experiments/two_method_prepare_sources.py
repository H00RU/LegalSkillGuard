"""Prepare new source-isolated DEV/TEST and a fixed 32-mother pilot cohort.

Native labels are handled mechanically and written to grading-only files.
No model, teacher or held-out prediction is run by this entry point.
"""
from __future__ import annotations

from collections import defaultdict, Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
import zipfile

from experiments.two_method_exposure_audit import normalized_hash
from legal_skill_guard.openexempt import active_case_input, answer_schema
from legal_skill_guard.rr.adapters import contractnli, sara_v2, rulearena_airline
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.oracles import airline
from legal_skill_guard.skill_evolution.data import MAUD_QUESTIONS
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'
OUT = BASE / 'prepared'
CACHE = ROOT / 'history/rr_v2_20261106/data/cache/rr_v2'


def read(path):
    return json.loads(Path(path).read_text())


def template(text):
    text = re.sub(r'["“][A-Z][A-Za-z0-9 .,&\'-]{2,80}["”]', ' ENTITY ', text)
    text = re.sub(r'\d+', ' NUMBER ', text)
    return normalized_hash(text.casefold())


def clusters(rows):
    parent, seen = list(range(len(rows))), {}
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, row in enumerate(rows):
        for key in row['isolation_keys']:
            if key in seen:
                a, b = find(i), find(seen[key])
                parent[max(a, b)] = min(a, b)
            else:
                seen[key] = i
    grouped = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[find(i)].append(row)
    for group in grouped.values():
        identity = digest(sorted({key for row in group for key in row['isolation_keys']}))
        for row in group:
            row['template_group'] = identity
    return rows


def native_stock(exposure, old_manifest, *, include_grading=True):
    hashes, keys = set(exposure['normalized_text_hashes']), set(exposure['source_keys'])
    old_keys = {r['key'] for d in old_manifest['datasets'].values() for p in ('train', 'dev', 'test') for r in d[p]}
    keys |= old_keys
    old_index = read(BASE / 'reconciliation/assets.json')['data_inventory']['candidate_inventory']
    candidates = {d: {r['key'] for r in rows} for d, rows in old_index.items()}
    result, excluded = defaultdict(list), Counter()
    native_cni = contractnli(CACHE / 'contract-nli.zip')
    exposed_cni_templates = {template(s.public['document']) for s in native_cni.sources
                             if s.key in keys or normalized_hash(s.public['document']) in hashes}
    with zipfile.ZipFile(CACHE / 'contract-nli.zip') as archive:
        cni = {p: json.loads(archive.read('contract-nli/' + p + '.json')) for p in ('train', 'dev', 'test')}
    docs = {(p, str(doc['id'])): doc for p, data in cni.items() for doc in data['documents']}
    sources = {'ContractNLI': native_cni, 'SARA_v2_Binary': sara_v2(CACHE / 'sara_v2.tar.gz'),
               'RuleArena_Airline': rulearena_airline(CACHE / 'RuleArena/airline')}
    with tarfile.open(CACHE / 'sara_v2.tar.gz') as archive:
        sections = {Path(m.name).stem.removeprefix('section'): archive.extractfile(m).read().decode()
                    for m in archive.getmembers() if m.isfile() and m.name.startswith('sara_v2/statutes/source/section')}
    for dataset, prepared in sources.items():
        by_key = defaultdict(list)
        for source in prepared.sources:
            by_key[source.key].append(source)
        for key, alternatives in by_key.items():
            # Cross-native clusters are retained only in the native TEST pool.
            # Do not accidentally prefer train because it sorts after test.
            source = next((s for s in alternatives if s.native_split == 'test'), alternatives[0])
            if key not in candidates[dataset] or key in keys:
                excluded[dataset + ':known_source'] += 1
                continue
            field = {'ContractNLI': 'document', 'SARA_v2_Binary': 'facts', 'RuleArena_Airline': 'prompt'}[dataset]
            if normalized_hash(source.public[field]) in hashes:
                excluded[dataset + ':historical_prompt_text'] += 1
                continue
            native_grade = prepared.grading[digest({'key': key, 'split': source.native_split, 'content': source.content_key})]
            views, grading = [], {}
            if dataset == 'ContractNLI':
                family = template(source.public['document'])
                if family in exposed_cni_templates:
                    excluded[dataset + ':historical_template'] += 1
                    continue
                original_id = str(native_grade['original_id'])
                document = docs[source.native_split, original_id]
                annotations = document['annotation_sets'][0]['annotations']
                for query in ('nda-5', 'nda-7', 'nda-16', 'nda-20'):
                    views.append({'id': query, 'public': {'source_text': document['text'],
                        'sentence_spans': document['spans'], 'question': cni[source.native_split]['labels'][query]['hypothesis']},
                        'answer_schema': {'type': 'string', 'enum': ['Entailment', 'Contradiction', 'NotMentioned']}})
                    if include_grading:
                        item = annotations[query]
                        grading[query] = {'answer': item['choice'], 'evidence': item.get('spans') if item['choice'] != 'NotMentioned' else None}
                isolation = ['cni-template:' + family, 'parent:' + source.group]
            elif dataset == 'SARA_v2_Binary':
                public = source.public
                related = {k: sections[k] for k in sorted(set(re.findall(r'\bsection\s+(\d+)\b', public['rules'], re.I)))
                           if k in sections and sections[k] != public['rules']}
                views = [{'id': 'native', 'public': {'source_text': public['rules'], 'referenced_public_sections': related,
                    'facts': public['facts'], 'question': public['query']},
                    'answer_schema': {'type': 'string', 'enum': ['Entailment', 'Contradiction']}}]
                original_id = native_grade['original_id']
                if include_grading:
                    grading['native'] = {'answer': native_grade['answer'], 'original_id': original_id}
                isolation = ['sara-stem:' + re.sub(r'_(pos|neg)$', '', original_id), 'parent:' + source.group]
            else:
                public = source.public
                views = [{'id': 'native', 'public': {'source_text': public['rules'], 'facts': public['prompt'],
                    'question': 'What is the exact integer ticket plus fees for every current bag?'},
                    'answer_schema': {'type': 'integer', 'minimum': 0}}]
                if include_grading:
                    grading['native'] = {'answer': airline(native_grade['reference_arguments'], root=CACHE / 'RuleArena/airline'),
                                          'reference_arguments': native_grade['reference_arguments']}
                original_id = source.group
                isolation = ['parent:' + source.group]
            result[dataset].append({'key': key, 'dataset': dataset, 'native_split': source.native_split,
                                    'parent_id': source.group, 'original_id': original_id,
                                    'views': views, 'grading': grading, 'isolation_keys': isolation})
    with zipfile.ZipFile('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip') as archive:
        fulltexts = {Path(n).stem: hashlib.sha256(archive.read(n)).hexdigest()
                     for n in archive.namelist() if n.startswith('data/contracts/') and n.endswith('.txt')}
        rows = defaultdict(lambda: defaultdict(list))
        for partition in ('train', 'dev', 'test'):
            for row in csv.DictReader(io.StringIO(archive.read('data/MAUD_' + partition + '.csv').decode('utf-8-sig'))):
                if row['data_type'] == 'main' and row['question'] in MAUD_QUESTIONS:
                    rows[row['contract_name']][row['question']].append((partition, row))
        for entry in old_index['MAUD']:
            key, contract = entry['key'], entry['original_contract_id']
            if key in keys:
                excluded['MAUD:known_source'] += 1
                continue
            if any(len(rows[contract][q]) != 1 for q in MAUD_QUESTIONS):
                excluded['MAUD:ambiguous_native_main_context'] += 1
                continue
            chosen = [rows[contract][q][0] for q in MAUD_QUESTIONS]
            if any(normalized_hash(row['text']) in hashes for partition, row in chosen):
                excluded['MAUD:historical_prompt_text'] += 1
                continue
            views, grading, isolation = [], {}, ['parent:' + fulltexts[contract]]
            for partition, row in chosen:
                query = row['question']
                labels = ['Actual knowledge', 'Constructive knowledge'] if query == MAUD_QUESTIONS[0] else ['Yes', 'No']
                views.append({'id': query, 'public': {'source_text': row['text'], 'question': query},
                              'answer_schema': {'type': 'string', 'enum': labels}})
                if include_grading:
                    grading[query] = {'answer': row['answer'], 'native_file': 'data/MAUD_' + partition + '.csv',
                                      'native_row_question_id': row['id']}
                isolation.append('maud-view:' + digest([query, normalized_hash(row['text'])]))
            result['MAUD'].append({'key': key, 'dataset': 'MAUD', 'native_split': 'self_grouped',
                'parent_id': contract, 'original_id': contract, 'views': views, 'grading': grading,
                'isolation_keys': isolation})
    oe_root = BASE / 'prospective_inventory/OpenExempt'
    oe = read(oe_root / 'construction_and_grading_only.json')
    oe_audit = read(oe_root / 'inventory_audit.json')
    eligible_oe = {r['group']: r for r in oe_audit['eligible_candidates']}
    for source in oe['sources']:
        group, key = source['group'], 'OpenExempt:' + digest(source['group'])
        if group not in eligible_oe or key in keys:
            continue
        if any(normalized_hash(source['tasks'][family]['components']['facts']) in hashes for family in ('EC', 'EV')):
            excluded['OpenExempt:historical_prompt_text'] += 1
            continue
        views = [{'id': family, 'public': {'original_input': active_case_input(source['tasks'][family])},
                  'answer_schema': answer_schema(family)} for family in ('EC', 'EV')]
        result['OpenExempt'].append({'key': key, 'dataset': 'OpenExempt', 'native_split': 'prospective_official_generation',
            'parent_id': group, 'original_id': group, 'views': views,
            'grading': ({family: {'answer': source['targets'][family], 'family': family} for family in ('EC', 'EV')}
                        if include_grading else {}),
            'isolation_keys': ['parent:' + group, 'oe-public-structure:' + eligible_oe[group]['public_structure_sha256']]})
    return result, dict(excluded)


def pilot_sources(train, manifest):
    recovered = read(BASE / 'recovered_service_graphs/source_checked_pairs.json')
    fixed_development = set(recovered['sources'])
    selected = {}
    for dataset, count in [('SARA_v2_Binary', 8), ('ContractNLI', 8), ('MAUD', 8), ('OpenExempt', 4), ('RuleArena_Airline', 4)]:
        eligible = [s for s in train if s['dataset'] == dataset]
        if dataset == 'SARA_v2_Binary':
            eligible = [s for s in eligible if re.search(r'\b(service|services|work|employed|paid)\b', s['views'][0]['public']['facts'], re.I)]
        eligible.sort(key=lambda s: (s['key'] not in fixed_development,
                                    digest({'salt': 'two-method-pilot-source-v1', 'key': s['key']})))
        if len(eligible) < count:
            raise ValueError('Predeclared source structure cannot supply the fixed pilot: ' + dataset)
        selected[dataset] = eligible[:count]
    roles = {'SARA_v2_Binary': (3, 3), 'ContractNLI': (1, 4), 'MAUD': (2, 4),
             'OpenExempt': (1, 2), 'RuleArena_Airline': (1, 3)}
    rows = []
    for dataset, sources in selected.items():
        development, calibration = roles[dataset]
        for i, source in enumerate(sources):
            role = 'development' if i < development else 'calibration' if i < development + calibration else 'structure_evaluation'
            rows.append({'key': source['key'], 'dataset': dataset, 'role': role,
                         'public_sha256': digest(source), 'views': [v['id'] for v in source['views']],
                         'source_selection_uses_answers_or_model_outcomes': False})
    assert len(rows) == 32 and fixed_development <= {r['key'] for r in rows if r['role'] == 'development'}
    return {'rows': rows, 'role_counts': dict(Counter(r['role'] for r in rows)),
            'public_eligibility': {'SARA_v2_Binary': 'facts explicitly mention service/services/work/employed/paid',
                                   'others': 'fixed original TRAIN mothers, selected by salted public-source hash'},
            'native_source_structure_and_rule_groups_still_to_be_bound': True,
            'not_the_final_pilot_execution_lock': True}


def main():
    # Reuse the preserved grading dependencies in their archived location;
    # do not install packages into or upgrade the frozen inference environment.
    sys.path.insert(0, str(ROOT / 'history/rr_v2_20261106/.local-tools/rr-v2-deps'))
    manifest = read(ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    exposure_path = BASE / 'exposure/historical_exposure_index.json'
    exposure = read(exposure_path)
    if exposure['failures']:
        raise ValueError('Resolve historical decoding failures before claiming source isolation')
    stocks, exclusions = native_stock(exposure, manifest)
    selected, metadata = {'dev': [], 'test': []}, {}
    for dataset in ('OpenExempt', 'SARA_v2_Binary', 'ContractNLI', 'RuleArena_Airline', 'MAUD'):
        rows = clusters(stocks[dataset])
        used_groups = set()
        native = dataset in ('SARA_v2_Binary', 'ContractNLI')
        tests = [r for r in rows if not native or r['native_split'] == 'test']
        tests.sort(key=lambda r: digest({'salt': 'two-method-fresh-test-v1', 'key': r['key']}))
        tests = tests[:32]
        used_groups.update(r['template_group'] for r in tests)
        devs = [r for r in rows if r['template_group'] not in used_groups
                and (not native or r['native_split'] == ('dev' if dataset == 'ContractNLI' else 'train'))]
        devs.sort(key=lambda r: digest({'salt': 'two-method-fresh-dev-v1', 'key': r['key']}))
        devs = devs[:16]
        selected['dev'].extend(devs)
        selected['test'].extend(tests)
        metadata[dataset] = {'eligible_mothers': len(rows), 'dev': len(devs), 'test': len(tests),
                             'dev_template_groups': len({r['template_group'] for r in devs}),
                             'test_template_groups': len({r['template_group'] for r in tests}),
                             'native_split_policy': 'native_test; native_dev or untouched_native_train for DEV' if native else 'new parent/template grouped split'}
    old_train = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    train, train_grading = read(old_train / 'public.json'), read(old_train / 'grading.json')
    train_keys = {r['key'] for r in train}
    new_keys = {p: {r['key'] for r in rows} for p, rows in selected.items()}
    assert not train_keys & (new_keys['dev'] | new_keys['test'])
    assert not new_keys['dev'] & new_keys['test']
    assert not {r['template_group'] for r in selected['dev']} & {r['template_group'] for r in selected['test']}
    outputs = {}
    for split in ('dev', 'test'):
        rows = selected[split]
        folder = OUT / ('sealed_test' if split == 'test' else split)
        public = [{**{k: v for k, v in row.items() if k not in ('grading', 'isolation_keys')}, 'split': split} for row in rows]
        grading = {row['key']: row['grading'] for row in rows}
        outputs[split] = {'public': immutable_json(folder / 'public.json', public),
                          'grading': immutable_json(folder / 'grading.json', grading)}
    outputs['train'] = {'public': hashlib.sha256((old_train / 'public.json').read_bytes()).hexdigest(),
                         'grading': hashlib.sha256((old_train / 'grading.json').read_bytes()).hexdigest()}
    pilot = pilot_sources(train, manifest)
    immutable_json(OUT / 'pilot_sources.json', pilot)
    lock = {'source_protocol': 'paired-interface-source-lock-v1', 'models_called': False,
            'source_unit': 'mother_source', 'training_mothers': len(train),
            'train_reuses_exposed_original_128_mothers': True,
            'training_batches': [[r['source_key'] for r in b['sources']] for b in manifest['source_sequence']],
            'datasets': metadata, 'sources': {'train': sorted(train_keys), 'dev': sorted(new_keys['dev']), 'test': sorted(new_keys['test'])},
            'prepared_sha256': outputs, 'exclusion_counts': exclusions,
            'exposure_index_sha256': hashlib.sha256(exposure_path.read_bytes()).hexdigest(),
            'native_labels_never_printed_or_used_to_select_sources': True,
            'old_TEST_not_renamed_or_reused': True, 'teacher_access_to_DEV_TEST': False,
            'M2_rule_and_structure_holdout_is_separate_from_source_blindness': True,
            'OE_uses_the_shared_native_generator_and_rule_package': True,
            'source_and_public_template_fingerprints_isolated': True,
            'pilot_source_sha256': digest(pilot), 'new_research_requests': 0}
    immutable_json(OUT / 'source_lock.json', lock)
    print(json.dumps({'training_mothers': len(train), 'datasets': metadata,
                      'pilot_role_counts': pilot['role_counts'], 'new_research_requests': 0,
                      'native_labels_printed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
