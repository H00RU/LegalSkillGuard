"""No-model request accounting, persistence and preflight guards."""
import pytest

from legal_skill_guard.rr.ledger import DATASETS, BudgetError, BudgetLedger


def sources():
    return {d: [f"{d}:train{i}" for i in range(4)] for d in DATASETS}


def ledger(tmp_path):
    return BudgetLedger(tmp_path / "ledger.sqlite3", sources=sources(), code_hash="code", config_hash="cfg")


def test_failures_and_resume_stay_charged_without_redispatch(tmp_path):
    b = ledger(tmp_path)
    args = dict(role="executor", purpose="thinking_probe", source=sources()[DATASETS[0]][0], request={"thinking": True})
    assert b.reserve("id", **args)["dispatch"]
    with pytest.raises(BudgetError, match="implicit"):
        ledger(tmp_path).reserve("id", **args)
    b.finish("id", status="failed", result={"error": "timeout"})
    assert ledger(tmp_path).export()["executor_used"] == 1
    with pytest.raises(BudgetError):
        b.reserve("id", **args)


def test_completed_reuse_requires_exact_binding(tmp_path):
    b = ledger(tmp_path)
    args = dict(role="executor", purpose="pilot_ingestion", source=sources()[DATASETS[0]][0], request={"input": "x"})
    b.reserve("id", **args)
    b.finish("id", status="completed", result={"answer": True})
    assert ledger(tmp_path).reserve("id", **args) == {"dispatch": False, "result": {"answer": True}}
    assert b.export()["executor_used"] == 1
    with pytest.raises(BudgetError):
        b.reserve("id", **{**args, "request": {"input": "changed"}})
    with pytest.raises(BudgetError, match="binding"):
        BudgetLedger(b.path, sources=sources(), code_hash="new", config_hash="cfg")


def test_allowlist_purpose_training_limit_and_one_probe_per_profile(tmp_path):
    b, s = ledger(tmp_path), sources()[DATASETS[0]][0]
    with pytest.raises(BudgetError, match="allowlist"):
        b.reserve("bad", role="executor", purpose="pilot_ingestion", source="test1", request={})
    with pytest.raises(BudgetError, match="forbidden"):
        b.reserve("bad", role="executor", purpose="frozen_test", source=s, request={})
    for i in range(2):
        b.reserve(f"pilot{i}", role="executor", purpose="pilot_ingestion", source=s, request={})
    with pytest.raises(BudgetError, match="third"):
        b.reserve("pilot2", role="executor", purpose="pilot_ingestion", source=s, request={})
    for i in (True, False):
        b.reserve(f"probe{i}", role="executor", purpose="thinking_probe", source=s, request={"thinking": i})
    with pytest.raises(BudgetError, match="sweep"):
        b.reserve("probeagain", role="executor", purpose="thinking_probe", source=s, request={"thinking": True})
    assert b.export()["executor_used"] == 4


def test_one_targeted_bug_round_and_teacher_cap(tmp_path):
    b, s = ledger(tmp_path), sources()[DATASETS[0]][0]
    with pytest.raises(BudgetError):
        b.reserve("retry", role="executor", purpose="preflight_bug_retry", source=s, request={})
    b.start_bugfix_round(reason="parser incorrectly rejects explicit negative polarity", affected_sources=[s])
    b.reserve("retry", role="executor", purpose="preflight_bug_retry", source=s, request={})
    with pytest.raises(BudgetError, match="one"):
        b.start_bugfix_round(reason="another sweep", affected_sources=[s])
    for i in range(2):
        b.reserve(f"teacher{i}", role="teacher", purpose="pilot_teacher_summary", source=s, request={})
    with pytest.raises(BudgetError, match="cap"):
        b.reserve("teacher2", role="teacher", purpose="pilot_teacher_summary", source=s, request={})
    assert b.export()["teacher_used"] == 2


def test_durable_combined_oracle_budget_and_no_contractnli_variants(tmp_path):
    b, s = ledger(tmp_path), sources()[DATASETS[0]][0]
    for i in range(4):
        ledger(tmp_path).reserve_oracle(s, str(i))
    with pytest.raises(BudgetError):
        b.reserve_oracle(s, "fifth")
    with pytest.raises(BudgetError, match="ContractNLI"):
        b.reserve_oracle(sources()["ContractNLI"][0], "v1")


def test_entire_preflight_allocation_deducts_from_original_buckets(tmp_path):
    b = ledger(tmp_path)
    all_sources = [s for v in sources().values() for s in v]
    b.start_bugfix_round(reason="fixed transport envelope bug", affected_sources=all_sources)
    for i, s in enumerate(all_sources):
        for thinking in (True, False):
            b.reserve(f"probe{i}:{thinking}", role="executor", purpose="thinking_probe", source=s,
                      request={"thinking": thinking})
        for step in range(2):
            b.reserve(f"pilot{i}:{step}", role="executor", purpose="pilot_ingestion", source=s, request={})
        b.reserve(f"retry{i}", role="executor", purpose="preflight_bug_retry", source=s, request={})
    report = b.export()
    assert report["executor_used"] == 100
    assert sum(report["original_allocation"].values()) == 6000
    assert sum(c["bucket"] == "full_build_including_pilot" for c in report["calls"]) == 40
    assert sum(c["bucket"] == "shared_retries_and_recovery" for c in report["calls"]) == 20
    with pytest.raises(BudgetError, match="cap"):
        b.reserve("101", role="executor", purpose="preflight_bug_retry", source=all_sources[0], request={})


def test_new_user_policy_keeps_old_charges_and_exact_planned_two_pass_scope(tmp_path):
    from legal_skill_guard.rr.coverage import digest
    b=ledger(tmp_path);s=sources()[DATASETS[0]][0]
    # Simulate the persisted96/2 terminal history, including failures.
    with b.transaction() as db:
        for role,n in [('executor',96),('teacher',2)]:
            for i in range(n):
                db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?)',
                    (f'old:{role}:{i}',role,'preflight_bug_retry' if role=='executor' else 'pilot_teacher_summary',
                     'shared_retries_and_recovery' if role=='executor' else 'teacher',s,str(i),'failed',0,'{}'))
    auth=dict(authority='explicit_user_chat_authorization',executor_original_study_max=6000,
        teacher_original_study_max=20,preflight_executor_cap_removed=True,preflight_teacher_cap_removed=True,
        main_training_enabled=False,no_new_sources=True)
    before=b.export()['calls'];b.register_study_authorization(auth)
    binding={'code_hash':'newcode','config_hash':'cfg'}
    b.register_study_revision('fixed',new_binding=binding,change='real fix',offline_evidence_hash='tested')
    b=BudgetLedger(b.path,sources=sources(),**binding)
    for step in (0,1):
        req={'thinking':True,'payload':{'messages':[str(step)]}}
        b.register_study_request(f'new:{step}',revision='fixed',source=s,request=req,step=step)
        args=dict(role='executor',purpose='preflight_bug_retry',source=s,request=req)
        assert b.reserve(f'new:{step}',**args)['dispatch']
        b.finish(f'new:{step}',status='completed',result={'ok':True})
        assert not b.reserve(f'new:{step}',**args)['dispatch']
    assert b.export()['executor_used']==98 and b.export()['teacher_used']==2
    assert b.export()['calls'][:98]==before
    with pytest.raises(BudgetError,match='Unchanged'):
        b.register_study_request('repeat',revision='fixed',source=s,request=req,step=1)
    with pytest.raises(BudgetError,match='code/config'):
        b.register_study_request('third',revision='fixed',source=s,request={'thinking':True,'payload':{'x':3}},step=1)
    with pytest.raises(BudgetError):
        b.reserve('unplanned',role='executor',purpose='preflight_bug_retry',source=s,request=req)
    teacher_request={'source_ids':[v for values in sources().values() for v in values][:16]}
    b.register_study_request('teacher3',revision='fixed',source=s,request=teacher_request,role='teacher')
    assert b.reserve('teacher3',role='teacher',purpose='pilot_teacher_summary',source=s,request=teacher_request)['dispatch']
    b.finish('teacher3',status='failed',result={})
    assert b.export()['teacher_used']==3
    with pytest.raises(BudgetError,match='implicit'):
        b.reserve('teacher3',role='teacher',purpose='pilot_teacher_summary',source=s,request=teacher_request)
