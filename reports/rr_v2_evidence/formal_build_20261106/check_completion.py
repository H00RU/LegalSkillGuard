"""Check this build's saved material and, after termination, cached recovery.

No generation, new oracle labels, evaluation, or changes to saved run records.
The recovery check runs production FormalRun.train with its state writes captured.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

from audit_build import ROOT, RUN, OUT, RUN_ID, read, dump, sha, sql_state
from legal_skill_guard.rr.controls import ARMS, SharedMaterial, project_material
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.example_synthesis import fit_shared_examples
from legal_skill_guard.rr.learning import SkillLibrary


def deny(*args, **kwargs):
    raise RuntimeError('Completion checks cannot generate, obtain labels, or dispatch subprocesses')


def immutable_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'), allow_nan=False)+'\n').encode()


def local_only(stack):
    stack.enter_context(patch.object(socket.socket, 'connect', deny))
    stack.enter_context(patch.object(socket.socket, 'connect_ex', deny))
    stack.enter_context(patch.object(subprocess, 'run', deny))
    stack.enter_context(patch.object(subprocess, 'Popen', deny))


def checkpoint_materials():
    state = read(RUN/'state.json')
    cfg = read(ROOT/'configs/rr_v2_preflight.json')
    manifest = read(ROOT/cfg['source_manifest'])
    order = manifest['formal_train_order']
    public = {s['key']: s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    grading = read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources']
    batch_count = state['complete_sources']//16
    records = [read(RUN/'sources'/(digest(s)+'.json')) for s in order[:batch_count*16]]
    library = SkillLibrary(stage='formal_train')
    snapshots, projections, ordinary = [], [], []
    with ExitStack() as stack:
        local_only(stack)
        for index, record in enumerate(records):
            if record['run_id'] != RUN_ID or record['binding'] != state['binding']:
                raise ValueError('Source record belongs to another run/binding')
            if record['learning'].get('learned_pattern'):
                library.add(record['learning']['learned_pattern'], source=record['source'])
            if (index+1)%16:
                continue
            batch = (index+1)//16
            snapshot = read(RUN/'batches'/f'B{batch}.json')
            if snapshot['library'] != library.export():
                raise ValueError(f'B{batch} saved library differs from fresh source prefix')
            teacher = snapshot['teacher_batch_record']
            if teacher != read(RUN/'batches'/f'B{batch}'/'teacher_batch1.json'):
                raise ValueError(f'B{batch} teacher reference differs')
            for rec in records[index-15:index+1]:
                grade = grading[rec['source']]
                labels = grade['targets'] if rec['dataset']=='OpenExempt' else {'answer': grade['answer']}
                proposals = [{'decoded_proposal': c['analysis'].get('proposal'),
                              'raw_content': c['raw_content'], 'parse_status': c['analysis']['program_status'],
                              'wire_request_hash': c['request_hash']} for c in rec['calls']]
                material = SharedMaterial(rec['source'], proposals, labels, rec['learning']['oracle_views'],
                    {'batch_record': digest(teacher), 'summary': teacher['response']['value']
                     if teacher['response'] else {'status': teacher['status']}},
                    [rec['learning']['learned_pattern']] if rec['learning'].get('learned_pattern') else [])
                expected = {arm: project_material(material, arm) for arm in ARMS}
                path = RUN/'arm_shared_material'/(digest(rec['source'])+'.json')
                if path.read_bytes() != immutable_bytes(expected):
                    raise ValueError('Shared-arm material differs: '+rec['source'])
                projections.append({'source': rec['source'], 'arms': sorted(expected), 'sha256': sha(path)})
            if batch in (1, 8):
                path = RUN/f'B{batch}.MB.frozen.json'
                expected = fit_shared_examples(public, records[:index+1], grading)
                if path.read_bytes() != immutable_bytes(expected) or expected['sha256'] != digest(expected['content']):
                    raise ValueError(f'B{batch} ordinary shared-example control differs')
                ordinary.append({'checkpoint': f'B{batch}', 'sha256': sha(path),
                    'content_hash': expected['sha256'], 'source_count': expected['content']['source_count'],
                    'source_answers_stored_as_patterns': expected['content']['source_answers_stored_as_patterns'],
                    'extra_model_calls': expected['content']['extra_model_calls']})
            snapshots.append({'batch': batch, 'sources': index+1, 'sha256': sha(RUN/'batches'/f'B{batch}.json'),
                              'library_exact': True, 'teacher_exact': True})
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'binding': state['binding'],
              'source_prefix': len(records), 'batches': snapshots, 'shared_source_materials': projections,
              'ordinary_control_frozen': ordinary, 'new_model_calls': 0, 'new_oracle_views': 0,
              'formal_evaluation_performed': False, 'network_and_subprocesses_blocked': True}
    dump(OUT/'material_audit.json', result)
    print(json.dumps({k:v for k,v in result.items() if k!='shared_source_materials'}), flush=True)
    return result


def cached_recovery():
    # Refuse a live or partially committed build. This is a terminal check only.
    identity = read(RUN/'process_identity.json')
    proc = Path('/proc')/str(identity['pid'])
    alive = proc.exists() and (proc/'stat').read_text().split()[21] == identity['start_ticks']
    state = read(RUN/'state.json')
    if alive or identity['status']!='complete' or state['complete_sources']!=128:
        raise RuntimeError('Cached recovery requires a terminal complete 128-source controller')
    from legal_skill_guard.rr import formal, learning, preflight
    from legal_skill_guard.rr.client import ExecutorClient, TeacherClient
    cfg = read(ROOT/'configs/rr_v2_preflight.json')
    ledger_path = ROOT/cfg['ledger_path']
    before_db = sql_state(ledger_path)
    if any(r[6]=='reserved' for r in before_db['calls']):
        raise RuntimeError('Cannot audit recovery with a pending physical request')
    before_files = {str(p.relative_to(RUN)): sha(p) for p in RUN.rglob('*') if p.is_file()}
    owner = formal.FormalRun(ROOT, partition='train')
    captured, packets = [], []
    def capture_state(path, value):
        if path != RUN/'state.json':
            raise ValueError('Unexpected mutable file during recovery')
        captured.append(value)
    def require_existing(path, value):
        if not path.exists() or path.read_bytes()!=immutable_bytes(value):
            raise ValueError('Recovery attempted to create/change immutable artifact: '+str(path))
    original_packet = owner.packet
    def train_packet(kind, partition):
        if partition!='train':
            raise ValueError('Recovery tried to access an evaluation partition')
        packets.append((kind, partition))
        return original_packet(kind, partition)
    output = io.StringIO()
    with ExitStack() as stack:
        local_only(stack)
        stack.enter_context(patch.object(owner, 'packet', train_packet))
        stack.enter_context(patch.object(owner, '_call', deny))
        stack.enter_context(patch.object(owner.ledger, 'reserve', deny))
        stack.enter_context(patch.object(owner.ledger, 'reserve_oracle', deny))
        stack.enter_context(patch.object(owner.ledger, 'finish', deny))
        stack.enter_context(patch.object(ExecutorClient, 'generate', deny))
        stack.enter_context(patch.object(ExecutorClient, 'tokenize', deny))
        stack.enter_context(patch.object(TeacherClient, 'summarize', deny))
        stack.enter_context(patch.object(formal, 'atomic_json', capture_state))
        for module in (formal, learning, preflight):
            stack.enter_context(patch.object(module, 'immutable_json', require_existing))
        stack.enter_context(redirect_stdout(output))
        restored = owner.train()
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    if len(captured)!=128 or captured[-1]!=state or [x['complete_sources'] for x in captured]!=list(range(1,129)):
        raise ValueError('Recovery did not reproduce the complete state sequence')
    if len(events)!=128 or [x['index'] for x in events]!=list(range(1,129)):
        raise ValueError('Recovery did not visit all original source records')
    if restored != read(RUN/'completion.json'):
        raise ValueError('Production cached recovery differs from terminal completion')
    after_db = sql_state(ledger_path)
    after_files = {str(p.relative_to(RUN)): sha(p) for p in RUN.rglob('*') if p.is_file()}
    if before_db!=after_db or before_files!=after_files:
        raise ValueError('Read-only recovery changed the ledger or saved run')
    receipt = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'binding': state['binding'],
        'production_entry': 'FormalRun.train', 'sources': 128, 'batches': 8,
        'new_model_calls': 0, 'new_oracle_views': 0, 'network_and_subprocesses_blocked': True,
        'generation_tokenization_and_ledger_reservations_denied': True,
        'training_packets_only': packets, 'all_run_file_bytes_unchanged': True,
        'ledger_tables_unchanged': True, 'ledger_tables_hash': digest(before_db),
        'state_writes_captured_read_only': True, 'final_state_and_completion_exact': True,
        'formal_evaluation_performed': False}
    dump(OUT/'cached_recovery.json', receipt)
    print(json.dumps(receipt), flush=True)
    return receipt


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    checkpoint_materials()
    if args.restore:
        cached_recovery()
