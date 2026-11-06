"""Production recovery through the paid77th first response; deny new work."""
import base64
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent))
from audit_build import sql_state
from legal_skill_guard.rr import formal
from legal_skill_guard.rr.coverage import digest


def read(path):return json.loads(Path(path).read_text())
def tree(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in root.rglob('*') if p.is_file() and p.name!='controller.lock'}


class NextRequestReady(RuntimeError):pass


def main():
    run = ROOT/'artifacts/rr_v2_formal_build_20261106/run_citation_fix'
    receipt = read(run/'processing_repair.json')
    cfg = read(ROOT/'configs/rr_v2_preflight.json')
    ledger = ROOT/cfg['ledger_path']
    before_db, before_tree = sql_state(ledger), tree(run)
    assert not any(r[6]=='reserved' for r in before_db['calls'])
    cached_id = receipt['cached_call_id']
    directory = run/'calls'/digest(cached_id)
    req = read(directory/'request.json')
    original = json.loads(base64.b64decode(read(directory/'wire_request.json')['body_b64']))
    state_writes, reserve_calls, learn_results = [], [], []
    def deny(*a, **kw):raise RuntimeError('Paid-frontier proof cannot generate, dispatch or mutate ledger')
    owner = formal.FormalRun(ROOT, partition='train')
    original_reserve = owner.ledger.reserve
    known = {r[0] for r in before_db['calls']}
    def reserve(cid, **kw):
        if cid not in known:raise RuntimeError('New physical reservation prohibited')
        reserve_calls.append(cid)
        return original_reserve(cid, **kw)
    def tokenize(messages, *, thinking=None):
        if messages==original['messages'] and thinking is False:
            return deepcopy(req['tokenization'])
        raise NextRequestReady('The next new request reached token-cost construction')
    def state_write(path, value):
        if Path(path)!=run/'state.json':raise RuntimeError('Unexpected state output')
        state_writes.append(deepcopy(value))
    actual_immutable = formal.immutable_json
    def immutable(path, value):
        if not Path(path).exists():raise RuntimeError('New run artifact prohibited during check')
        return actual_immutable(path, value)
    actual_learn = formal.learn_source
    def learn(source, grade, oracle, **kw):
        result = actual_learn(source, grade, oracle, **kw)
        learn_results.append({'source':source['key'],'status':result['status'],
                              'oracle_views':len(result['oracle_views'])})
        return result
    reached = False
    with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny), \
            patch.object(subprocess,'run',deny),patch.object(subprocess,'Popen',deny), \
            patch.object(owner.ledger,'reserve',reserve),patch.object(owner.ledger,'finish',deny), \
            patch.object(owner.ledger,'reserve_oracle',deny),patch.object(owner.executor,'tokenize',tokenize), \
            patch.object(formal,'atomic_json',state_write),patch.object(formal,'immutable_json',immutable), \
            patch.object(formal,'learn_source',learn),redirect_stdout(StringIO()):
        try:owner.train()
        except NextRequestReady:reached=True
    assert reached
    assert reserve_calls == [cached_id], reserve_calls
    assert learn_results and learn_results[0]['source'] == cached_id.split(':',1)[1].rsplit(':',1)[0]
    assert all(s['complete_sources']>=76 for s in state_writes)
    assert all(r['oracle_views']==0 for r in learn_results)
    assert before_db == sql_state(ledger)
    assert before_tree == tree(run)
    result = {'generation_binding':owner.binding,'processing_binding':owner.processing_binding,
        'restored_existing_sources':76,'paid_cached_call_id':cached_id,
        'paid_request_hash':receipt['cached_request_hash'],
        'cached_reserve_calls':reserve_calls,'source77_learning_after_reference_fix':learn_results,
        'next_new_request_construction_reached':True,'new_dispatch_intentionally_blocked':True,
        'persisted_state_not_rewound':True,'minimum_captured_progress':min(s['complete_sources'] for s in state_writes),
        'all_existing_run_bytes_unchanged':True,'calls_meta_oracle_unchanged':True,
        'new_model_calls':0,'new_oracle_views':0,'network_and_subprocesses_blocked':True}
    (OUT/'paid_frontier_recovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
