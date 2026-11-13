"""Verify the actual query-as-premise defect using facts-only evidence IDs.

Two changed-input executor requests on the already exposed failure case. This
is engineering recovery, never new independent method validation. No teacher,
law/skill edits, labels or additional cases are used.
"""
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_callable_source_trial import ARMS, OUT as PARENT, ROOT
from experiments.legal_skill_evolution_refutation_learning import read, sha
from experiments.legal_skill_evolution_teacher_proof_evaluate import READ_QUESTION, validate_case_bindings
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import bind_case_premises, evaluate
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError

RUN='legal_skill_evolution_case_evidence_recovery_20261113'
OUT=ROOT/'artifacts'/RUN


def run():
    previous=read(PARENT/'protocol.json')
    key=previous['source_ids'][2]
    source=next(s for s in read(ROOT/previous['public_manifest']) if s['key']==key)
    view=source['views'][0]
    files=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/callable_rules.py',
        ROOT/'legal_skill_guard/skill_evolution/runtime.py']
    p={'run_id':RUN,'same_goal':True,'goal_complete':False,'source_ids':[key],
        'workload':'Two executor fact-evidence recovery checks, one per unchanged learned arm on the same already exposed failure. No teacher or independent success claim.',
        'change':'Keep native question in invocation_arguments for scope; only case facts have evidence span IDs. Never replace a rejected value or add source rules.',
        'executor_profile':previous['executor_profile'],
        'source_sha256':{str(f.relative_to(ROOT)):sha(f) for f in files},
        'libraries_sha256':{arm:digest(read(PARENT/arm/'library.json')) for arm in ARMS},
        'no_native_grading_labels_loaded':True}
    immutable_json(OUT/'protocol.json',p)
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        rows=[list(r) for r in db.execute('select * from calls order by id')]
    assert not any(r[6]=='reserved' for r in rows)
    immutable_json(OUT/'ledger_before.json',{'rows':rows})
    for f in files:
        t=OUT/'source_snapshot'/f.relative_to(ROOT);t.parent.mkdir(parents=True,exist_ok=True)
        if t.exists():assert t.read_bytes()==f.read_bytes()
        else:t.write_bytes(f.read_bytes())
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':[key],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);client.readiness();reads=FrozenReads(client)
    # Scope is still model-visible, but cannot be cited as factual evidence.
    case={**view,'public':{'facts':view['public']['facts']}}
    for arm in ARMS:
        target=OUT/arm/'result.json'
        if target.exists():continue
        assert all(sha(ROOT/n)==h for n,h in p['source_sha256'].items())
        old=read(PARENT/'execution'/arm/key.replace(':','_')/'result.json')
        lib=read(PARENT/arm/'library.json')
        assert digest(lib)==p['libraries_sha256'][arm]
        event,error,rejected,values=None,None,[],{}
        try:
            raw,event=reads.read(source,case,question=READ_QUESTION,
                fields=old['plan']['fields'],locator='case facts; native query supplied only as scope argument',
                invocation_arguments={'current_question':view['public']['question']},
                purpose='skill_replay',allow_unresolved=True,require_case_support=True)
            checked,rejected=validate_case_bindings(old['plan']['fields'],raw,event)
            values,more=bind_case_premises(checked,event);rejected+=more
        except LocalReadError as e:event=e.event;error=str(e)
        result=evaluate(lib,old['plan'],values)
        record={'source':key,'arm':arm,'changed_evidence_namespace':True,
            'unchanged_law_program_and_case':True,'read_event':event,'read_error':error,
            'accepted_values':values,'rejected_values':rejected,'actual_program_result':result,
            'engineering_recovery_not_independent_method_validation':True,
            'no_native_labels_or_score_used':True,'goal_complete':False}
        immutable_json(target,record)
        print(json.dumps({'arm':arm,'answer':result['answer'],'known':values,'error':error}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_case_evidence_recovery.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);run()
