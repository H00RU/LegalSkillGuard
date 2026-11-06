"""Readiness of the current repair, with explicit generation provenance.

Receipts prove implementation/preflight acceptance; launch gates remain separate.
Historical receipts are retained and cannot authorize this changed implementation.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .checkpoint import immutable_json
from .coverage import digest
from .learning import SkillLibrary
from .preflight import science_files, scientific_code_binding

OPERATIONAL_FILES = {'configs/rr_v2_preflight.json', 'configs/rr_v2_formal.json',
                     'reports/legalskillguard_rule_reasoning_protocol_v2.json'}
RECEIPT = 'reports/rr_v2_evidence/formal_readiness_method_gaps.json'
STAGE = 'artifacts/rr_v2_preflight/method_gap_repair_v1/current_material'
EVIDENCE = 'reports/rr_v2_evidence/method_gap_repair'


def _file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_binding(root):
    config = json.loads((root/'configs/rr_v2_preflight.json').read_text())
    protocol = json.loads((root/'reports/legalskillguard_rule_reasoning_protocol_v2.json').read_text())
    manifest = json.loads((root/config['source_manifest']).read_text())
    for name,key in [('public_train.json','public_train'),('grading_only/train.json','grading_train')]:
        if _file_hash(root/'data/packets/rr_v2'/name)!=manifest['packet_sha256'][key]:
            raise ValueError('Fixed TRAIN packet changed')
    semantic = {'executor':config['executor'], 'teacher':config['teacher'],
        'protocol_methods':protocol['methods'], 'A_limits':protocol['A_limits'], 'B_limits':protocol['B_limits'],
        'training':protocol['training'], 'thinking':protocol['thinking']}
    return {'code_hash':scientific_code_binding(science_files(root)), 'config_hash':digest(semantic),
        'data_hash':manifest['data_hash'], 'source_manifest_hash':digest(manifest)}


def prepare(root):
    root=Path(root)
    if not (root/STAGE/'pilot_completion.json').exists():
        raise ValueError('Current actual preflight, teacher batch and restore evidence required')
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    manifest=json.loads((root/cfg['source_manifest']).read_text())
    binding=current_binding(root);files=science_files(root)
    def read(name):return json.loads((root/name).read_text())
    offline=read('reports/rr_v2_evidence/offline_latest.json')
    required={n for n in files if n.startswith(('legal_skill_guard/rr/','experiments/rr_v2','tests/test_rr')) and n.endswith('.py')}
    if offline['exit_code'] or not offline['network_blocked'] or not required<=set(offline['files']) or any(
            _file_hash(root/n)!=h for n,h in offline['files'].items()):
        raise ValueError('Current complete offline regression absent or stale')
    paths=[EVIDENCE+'/'+n+'.json' for n in ['backend','restore','historical_core','replay_before_live','current_restore']]
    evidence={p:read(p) for p in paths}
    if any(e['binding']!=binding for e in evidence.values()):
        raise ValueError('Current preflight evidence binding differs')
    backend=evidence[EVIDENCE+'/backend.json']
    restored=evidence[EVIDENCE+'/current_restore.json']
    if not backend['all_checks_passed'] or not backend['local_serving_tokens_exact'] or \
            not backend['measured_request_cost']['wire_body_sha256'] or \
            not restored['exact_records_and_library'] or not restored['network_and_subprocess_blocked'] or \
            restored['new_model_calls'] or restored['new_oracle_views'] or len(restored['controls'])!=120:
        raise ValueError('Actual request cost or current free restore incomplete')
    live='artifacts/rr_v2_preflight/method_gap_repair_v1/live/'
    seal=read(live+'seal.json');primary=read(live+'primary_path.json');wire=read(live+'wire_contract.json')
    if seal['binding']!=binding or seal['protected_files']!=files or primary['binding']!=binding or wire['binding']!=binding or \
            not primary['checks']['A']['semantic_pass'] or not primary['checks']['B']['semantic_pass'] or \
            not wire['wire_schema_pass'] or not wire['parser_structural_pass'] or \
            primary['record']['generation_thinking'] is not False or wire['generation_thinking'] is not False:
        raise ValueError('Current real A/B semantics and affected wire contract need verification')
    checkpoint=read(STAGE+'/checkpoint.json');completion=read(STAGE+'/pilot_completion.json')
    records=[read(p) for p in checkpoint['source_record_paths']]
    if checkpoint['binding']!=binding or checkpoint['complete_sources']!=manifest['pilot_order'] or \
            [r['source'] for r in records]!=manifest['pilot_order'] or \
            [digest(r) for r in records]!=checkpoint['source_record_hashes'] or any(
            r['binding']!=binding or r['offline_mock'] or len(r['calls'])>2 or len(r['learning']['oracle_views'])>4 for r in records):
        raise ValueError('All fixed source records and per-source limits must be preserved')
    frozen=SkillLibrary.restore(root/STAGE/'partial_library.frozen.json')
    if digest(frozen.export())!=checkpoint['library_sha256'] or not completion['restore_verified']:
        raise ValueError('Current material/frozen library restore differs')
    teacher=read(STAGE+'/teacher_batch1.json');transport=read(STAGE+'/teacher_transport.json')
    if not teacher['batch_record_accepted'] or teacher['offline_mock'] or teacher['source_ids']!=manifest['pilot_order'][:16] or \
            teacher['reuse_requires_matching_binding']!=binding or teacher['response']['model']!=cfg['teacher']['model'] or \
            _file_hash(Path(transport['executable']))!=transport['executable_sha256']:
        raise ValueError('Current teacher batch or verified transport differs')
    with sqlite3.connect(root/cfg['ledger_path']) as db:
        rows=db.execute('select * from calls order by id').fetchall()
        spec=json.loads(db.execute("select value from meta where key='spec'").fetchone()[0])
        off=db.execute("select value from meta where key='executor_thinking_off_authorization'").fetchone()
    if any(r[6] not in {'completed','failed'} for r in rows) or not off or cfg['executor']['enable_thinking'] is not False:
        raise ValueError('Terminal same ledger and explicit OFF profile required')
    counts={role:sum(r[1]==role for r in rows) for role in ('executor','teacher')}
    if counts['executor']>6000 or counts['teacher']>20:
        raise ValueError('Original study allocation exceeded')
    paths += [live+n for n in ['seal.json','primary_path.json','wire_contract.json']]
    paths += checkpoint['source_record_paths']
    paths += [STAGE+'/'+n for n in ['checkpoint.json','pilot_completion.json','partial_library.frozen.json',
        'B1_preflight_partial.json','teacher_batch1.json','teacher_transport.json','MB_preflight_examples.frozen.json']]
    result={'schema':2,'scope':'current_method_implementation_and_bounded_preflight_only',
        'engineering_ready':True,'formal_launch_authorized':False,'execution_binding':binding,
        'preflight_binding':binding,'preflight_artifact_directory':STAGE,
        'ledger_origin_binding':{k:spec[k] for k in ('code_hash','config_hash')},
        'protected_scientific_files':{n:h for n,h in files.items() if n not in OPERATIONAL_FILES},
        'preserved_pilot_files':{p:_file_hash(root/p) for p in paths},
        'original_call_ids':[r[0] for r in rows], 'original_call_rows_hash':digest(rows), 'preflight_counts':counts,
        'teacher_transport':transport,'offline_receipt_hash':digest(offline),
        'core_A_primary_semantic_pass':True,'core_B_primary_semantic_pass':True,
        'fallback_counts_as_core_success':False,'historical_generation_provenance_preserved':True,
        'historical_predictions_reused_as_OFF_predictions':False,'not_a_formal_performance_result':True}
    immutable_json(root/RECEIPT,result)
    return result


def validate(root, preflight_binding=None):
    root=Path(root);result=json.loads((root/RECEIPT).read_text())
    if not result['engineering_ready'] or current_binding(root)!=result['execution_binding'] or \
            preflight_binding is not None and preflight_binding!=result['preflight_binding']:
        raise ValueError('Current readiness binding differs')
    files={n:h for n,h in science_files(root).items() if n not in OPERATIONAL_FILES}
    if files!=result['protected_scientific_files'] or any(
            _file_hash(root/p)!=h for p,h in result['preserved_pilot_files'].items()):
        raise ValueError('Current implementation or preserved evidence changed')
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    with sqlite3.connect(root/cfg['ledger_path']) as db:
        ids=result['original_call_ids']
        rows=db.execute('select * from calls where id in ('+','.join('?' for _ in ids)+') order by id',ids).fetchall()
    if digest(rows)!=result['original_call_rows_hash']:
        raise ValueError('Historical charged calls changed')
    t=result['teacher_transport']
    if _file_hash(Path(t['executable']))!=t['executable_sha256']:
        raise ValueError('Verified teacher transport changed')
    return result
