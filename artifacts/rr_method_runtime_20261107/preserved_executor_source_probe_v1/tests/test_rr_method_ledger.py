"""No model calls: preserve legacy accounting while replacing revoked stops."""
import json

import pytest

from legal_skill_guard.rr.ledger import BudgetError, BudgetLedger, DATASETS
from legal_skill_guard.rr.method_ledger import MethodLedger


def fixture(tmp_path):
    sources = {d:[d+':'+str(i) for i in range(4)] for d in DATASETS}
    old = BudgetLedger(tmp_path/'ledger.sqlite3', sources=sources, code_hash='old', config_hash='old')
    source = sources[DATASETS[0]][0]
    with old.transaction() as db:
        for i in range(20):
            db.execute('insert into calls values (?,?,?,?,?,?,?,?,?)',
                ('old:'+str(i),'teacher','pilot_teacher_summary','teacher',source,'hash','completed',i,'{}'))
        before = db.execute('select * from calls order by id').fetchall()
        old_meta = db.execute('select * from meta order by key').fetchall()
    current = MethodLedger(old.path, run_id='new', binding={'code_hash':'new','config_hash':'new'},
        sources={'train':[s for group in sources.values() for s in group], 'dev':['OpenExempt:dev']},
        authorization_hash='current_user_authorization', question='Verify current source-contract repair')
    return old,current,source,before,old_meta


def test_revoked_teacher_cap_is_not_enforced_and_history_is_immutable(tmp_path):
    old,current,source,before,meta = fixture(tmp_path)
    call = current.reserve('new:compile',role='teacher',purpose='method_train_compile',source=source,request={'source':'public'})
    assert call['dispatch']
    current.finish('new:compile',status='completed',result={'value':{},'usage':{}})
    assert current.export()['teacher_used'] == 21
    with old.transaction() as db:
        assert db.execute("select * from calls where id like 'old:%' order by id").fetchall() == before
        assert all(db.execute('select value from meta where key=?',(k,)).fetchone()[0]==v for k,v in meta)
    assert current.spec['original_teacher_cap']==20  # historical origin was not rewritten
    assert current.policy['physical_call_caps'] is None


def test_identical_paid_request_is_reused_without_dispatch(tmp_path):
    _,current,source,_,_ = fixture(tmp_path)
    args = {'role':'executor','purpose':'method_primitive_observation','source':source,'request':{'payload':{'x':1}}}
    current.reserve('new:parse',**args)
    current.finish('new:parse',status='completed',result={'content':'saved'})
    assert current.reserve('new:parse',**args)=={'dispatch':False,'result':{'content':'saved'}}
    with pytest.raises(BudgetError,match='identity'):
        current.reserve('new:parse',**{**args,'request':{'payload':{'x':2}}})


def test_failure_remains_charged_and_pending_request_blocks_duplicates(tmp_path):
    _,current,source,_,_ = fixture(tmp_path)
    args = {'role':'executor','purpose':'method_primitive_observation','source':source,'request':{}}
    current.reserve('new:one',**args)
    with pytest.raises(BudgetError,match='Reconcile'):
        current.reserve('new:two',**args)
    current.finish('new:one',status='failed',result={'error':'transport'})
    with pytest.raises(BudgetError,match='stay charged'):
        current.reserve('new:one',**args)
    assert current.export()['executor_used']==1
    with pytest.raises(BudgetError,match='immutable'):
        current.finish('new:one',status='completed',result={})


def test_fixed_partitions_and_no_test_oracle_are_enforced(tmp_path):
    _,current,source,_,_ = fixture(tmp_path)
    with pytest.raises(BudgetError):
        current.reserve('new:test',role='executor',purpose='method_dev',source='OpenExempt:test',request={})
    with pytest.raises(BudgetError):
        current.reserve('new:leak',role='executor',purpose='method_dev',source=source,request={})
    with pytest.raises(BudgetError):
        current.reserve_oracle('OpenExempt:dev','view')
    with pytest.raises(BudgetError):
        current.reserve_oracle('ContractNLI:0','view')


def test_changed_policy_cannot_replace_an_existing_namespace(tmp_path):
    old,current,_,_,_ = fixture(tmp_path)
    with pytest.raises(BudgetError,match='independent run'):
        MethodLedger(old.path, run_id='new',binding={'code_hash':'changed','config_hash':'new'},
            sources=current.sources,authorization_hash='current_user_authorization',
            question='Verify current source-contract repair')
