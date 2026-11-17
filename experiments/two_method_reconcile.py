"""Reconcile existing TRAIN reads and unexposed source inventory, without calls.

Native annotations are processed only by the existing preparation adapters.
This entry never prints them, never chooses sources by labels, and does not
load existing TEST predictions or create an experiment ledger policy.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile
import csv
import io

from legal_skill_guard.rr.adapters import contractnli, openexempt, rulearena_airline, sara_v2
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/two_method_followthrough_20261116/reconciliation'
SOURCE_KEY = re.compile(r'^(?:OpenExempt|SARA_v2_Binary|ContractNLI|RuleArena_Airline|MAUD):[0-9a-f]{64}$')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_keys(node):
    if isinstance(node, str):
        return {node} if SOURCE_KEY.fullmatch(node) else set()
    if isinstance(node, dict):
        return set().union(*(source_keys(k) | source_keys(v) for k, v in node.items())) if node else set()
    if isinstance(node, (list, tuple)):
        return set().union(*(source_keys(v) for v in node)) if node else set()
    return set()


def existing_reads(db, train_sources):
    physical, by_output = {}, defaultdict(list)
    for identity, source, request_hash, result in db.execute(
        "SELECT id,source,request_hash,result FROM calls WHERE role='executor' AND status='completed'"):
        if source in train_sources:
            value = json.loads(result)
            physical[identity] = {'source': source, 'request_hash': request_hash, 'result': value}
            try:
                by_output[(source, digest(json.loads(value['content'])))].append(identity)
            except (KeyError, ValueError, TypeError, RecursionError):
                pass
    records, errors, version_cache = [], Counter(), {}
    for root in sorted((ROOT / 'artifacts').glob('legal_skill_evolution*')):
        for kind in ('component_reads', 'relation_reads'):
            for path in sorted((root / kind).glob('*.json')):
                row = read(path)
                if row.get('source') not in train_sources:
                    continue
                if row.get('value') is None:
                    errors['logical_read_without_value'] += 1
                    continue
                receipt = row.get('receipt', {})
                identity = receipt.get('reused_physical_call_id')
                if not identity:
                    raw_path = root / 'raw_responses' / path.name
                    if raw_path.is_file():
                        raw = read(raw_path)
                        identity = raw.get('reused_physical_call_id')
                        folder = raw.get('artifact_directory')
                        if not identity and folder and (Path(folder) / 'request.json').is_file():
                            identity = read(Path(folder) / 'request.json').get('id')
                if not identity:
                    candidate = root.name + ':read:' + path.stem
                    identity = candidate if candidate in physical else None
                if not identity:
                    matches = by_output.get((row['source'], digest(row['value'])), [])
                    # Recover copied caches from the settled physical record;
                    # exact elapsed time and usage distinguish repeated equal
                    # outputs. Ambiguous provenance stays unreconciled.
                    exact = [i for i in matches
                             if receipt.get('usage') == physical[i]['result'].get('usage')
                             and receipt.get('elapsed_seconds') == physical[i]['result'].get('elapsed_seconds')]
                    identity = exact[0] if len(exact) == 1 else None
                if identity not in physical:
                    errors['physical_identity_not_reconciled'] += 1
                    continue
                paid = physical[identity]
                if paid['source'] != row['source']:
                    raise ValueError('Physical response belongs to another mother source')
                response = paid['result']
                try:
                    same_output = json.loads(response['content']) == row['value']
                except (KeyError, ValueError, TypeError, RecursionError):
                    same_output = False
                if not same_output:
                    errors['logical_value_differs_from_original_response'] += 1
                    continue
                request_path = Path(response.get('artifact_directory', '')) / 'request.json'
                if not request_path.is_file():
                    errors['original_request_missing'] += 1
                    continue
                request = read(request_path)
                if request.get('request_hash') != paid['request_hash']:
                    raise ValueError('Physical request hash differs from the continuous ledger')
                payload = request['payload']
                if payload.get('chat_template_kwargs', {}).get('enable_thinking') is not False:
                    errors['thinking_OFF_not_bound'] += 1
                    continue
                if identity not in version_cache:
                    input_message = json.loads(payload['messages'][-1]['content'])
                    schema = input_message.get('output_schema')
                    # This strict signature includes instantiated schema. Do
                    # not silently pool source-dependent copy grammars.
                    origin = request_path.parent.parent.parent
                    origin_protocol = read(origin / 'protocol.json') if (origin / 'protocol.json').is_file() else {}
                    executor = origin_protocol.get('executor_profile', origin_protocol.get('executor', {}))
                    signature = {
                        'profile': {k: v for k, v in payload.items() if k not in ('messages', 'response_format')},
                        'system_messages': [m for m in payload['messages'] if m['role'] == 'system'],
                        'schema': schema,
                        'model_root': executor.get('model_root'),
                        'reader_task_contract': {
                            k: input_message.get('task', {}).get(k)
                            for k in ('requested_relation', 'shared_key_domain', 'component_meanings',
                                      'component_meaning', 'relation_meaning')
                            if isinstance(input_message.get('task'), dict) and k in input_message['task']},
                    }
                    version_cache[identity] = {
                        'strict_reader_version': digest(signature),
                        'request_path': str(request_path.relative_to(ROOT)),
                        'request_file_sha256': sha(request_path),
                        'wire_payload_sha256': digest(payload),
                        'schema_sha256': digest(schema),
                        'finish_reason': response.get('finish_reason'),
                        'model_revision_bound': bool(executor.get('model_root')),
                        'upstream_observations_preserved_in_full_request': True,
                        'calibration_context_requires_review': True,
                    }
                records.append({
                    'source': row['source'], 'logical_artifact': str(path.relative_to(ROOT)),
                    'physical_call_id': identity, 'read_kind': kind,
                    'component_id': row.get('component_id'),
                    'logical_validation_error': row.get('error'),
                    'logical_reinterpretation': receipt.get('reuse_kind'),
                    **version_cache[identity],
                    'source_reference_graph_verified': False,
                    'new_physical_requests': 0,
                })
    distinct = {r['physical_call_id']: r for r in records}
    by_source = defaultdict(set)
    for row in distinct.values():
        by_source[row['source']].add(row['strict_reader_version'])
    return {'logical_records': records, 'physical_records': list(distinct.values()),
            'unreconciled_counts': dict(errors),
            'sources_with_multiple_strict_reader_versions': {
                sid: sorted(versions) for sid, versions in by_source.items() if len(versions) >= 2},
            'complete_source_checked_graph_pairs': 0,
            'boundary': 'Physical responses and versions recovered; source-grounded reference graphs remain to be audited.'}


def inventory(db, manifest):
    # All historically selected source keys remain excluded even when a
    # corresponding request was not completed. A new name never resets them.
    exposed = source_keys(manifest)
    exposed.update(r[0] for r in db.execute('SELECT DISTINCT source FROM calls'))
    for (payload,) in db.execute('SELECT value FROM meta'):
        try:
            exposed.update(source_keys(json.loads(payload)))
        except (TypeError, ValueError):
            continue
    oracle_columns = [r[1] for r in db.execute('PRAGMA table_info(oracle_views)')]
    for column in ('source', 'source_id', 'source_key'):
        if column in oracle_columns:
            exposed.update(r[0] for r in db.execute('SELECT DISTINCT ' + column + ' FROM oracle_views'))
    cache = ROOT / 'history/rr_v2_20261106/data/cache/rr_v2'
    prepared = {
        'OpenExempt': openexempt(cache / 'openexempt_generated.json'),
        'SARA_v2_Binary': sara_v2(cache / 'sara_v2.tar.gz'),
        'ContractNLI': contractnli(cache / 'contract-nli.zip'),
        'RuleArena_Airline': rulearena_airline(cache / 'RuleArena/airline'),
    }
    summary, candidates = {}, {}
    for dataset, values in prepared.items():
        unique = {s.key: s for s in values.sources}
        fresh = sorted(key for key in unique if key not in exposed)
        candidates[dataset] = [{'key': key, 'native_split': unique[key].native_split,
                                'group': unique[key].group, 'content_hash': unique[key].content_key}
                               for key in fresh]
        summary[dataset] = {'available_mothers': len(unique),
                            'historically_selected_or_called': len(set(unique) & exposed),
                            'not_in_current_exposure_index': len(fresh),
                            'freshness_certified': False,
                            'native_adapter': values.audit}
    maud = Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip')
    with zipfile.ZipFile(maud) as archive:
        docs = {Path(n).stem: hashlib.sha256(archive.read(n)).hexdigest()
                for n in archive.namelist() if n.startswith('data/contracts/') and n.endswith('.txt')}
        views = defaultdict(set)
        from legal_skill_guard.skill_evolution.data import MAUD_QUESTIONS, MAUD_ARCHIVE_SHA256
        if sha(maud) != MAUD_ARCHIVE_SHA256:
            raise ValueError('Pinned MAUD archive hash differs')
        for partition in ('train', 'dev', 'test'):
            for row in csv.DictReader(io.StringIO(archive.read('data/MAUD_' + partition + '.csv').decode('utf-8-sig'))):
                if row['data_type'] == 'main' and row['question'] in MAUD_QUESTIONS:
                    views[row['contract_name']].add(row['question'])
    old_maud_hashes = {docs[row['original_contract_id']]
                       for p in ('train', 'dev', 'test') for row in manifest['datasets']['MAUD'][p]}
    maud_candidates = {}
    for contract, value in docs.items():
        key = 'MAUD:' + digest(contract)
        if value not in old_maud_hashes and key not in exposed and len(views[contract]) == len(MAUD_QUESTIONS):
            maud_candidates.setdefault(value, {'key': key, 'original_contract_id': contract,
                                             'fulltext_sha256': value})
    candidates['MAUD'] = sorted(maud_candidates.values(), key=lambda x: x['key'])
    summary['MAUD'] = {'available_mothers': len(set(docs.values())),
                       'not_in_current_exposure_index': len(maud_candidates),
                       'freshness_certified': False, 'native_archive_sha256': sha(maud)}
    return {'datasets': summary, 'candidate_inventory': candidates,
            'excluded_source_count': len(exposed),
            'boundary': 'Candidates only: reconcile older non-ledger exposure, template overlap and rule structures before locking DEV/TEST.',
            'labels_used_for_selection_or_printed': False}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = read(ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    train = {row['key'] for item in manifest['datasets'].values() for row in item['train']}
    ledger = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    before = sha(ledger)
    db = sqlite3.connect('file:' + str(ledger) + '?mode=ro', uri=True)
    assert not db.execute("SELECT 1 FROM calls WHERE status='reserved'").fetchone()
    reads = existing_reads(db, train)
    data = inventory(db, manifest)
    counts = db.execute('SELECT role,status,count(*) FROM calls GROUP BY role,status ORDER BY role,status').fetchall()
    db.close()
    assert sha(ledger) == before
    result = {'historical_train_mothers': len(train),
              'raw_read_reconciliation': reads, 'data_inventory': data,
              'ledger_counts': counts, 'ledger_sha256': before,
              'new_physical_requests': 0, 'ledger_unchanged': True}
    (OUT / 'assets.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'historical_train_mothers': len(train),
                      'reconciled_physical_reads': len(reads['physical_records']),
                      'multi_version_train_sources': len(reads['sources_with_multiple_strict_reader_versions']),
                      'complete_source_checked_graph_pairs': 0,
                      'unreconciled': reads['unreconciled_counts'],
                      'candidate_inventory': {k: v['not_in_current_exposure_index'] for k, v in data['datasets'].items()},
                      'freshness_certified': False, 'new_physical_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
