"""Source-only repair of the actual common-kernel quantifier/input mismatch."""
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_execution_kernel_bank as bank
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


ROOT = bank.ROOT
RUN = 'legal_skill_evolution_execution_kernel_repair_20261114'
OUT = ROOT / 'artifacts' / RUN
SYSTEM = bank.SYSTEM + '''

Repair the actual previous two-kernel proposal using its supplied source and
offline diagnosis. Future case facts and native annotations remain withheld.
Keep the same two names/scope and return the same output schema.

The actual wage program adds current AND preceding years into one total. This
changes the source quantifier. Keep SEPARATE totals by calendar year, accepting
a threshold witness in either year; do not combine two individually insufficient
years. This is source logic, not a request to fit a native label.

The fixed SARA data uses dated remuneration/service event periods, not a guessed
exact payment day. Accept raw event period_start/period_end for a stated wage
amount covering that period, alongside payer/payee/stated_labor/wages_given.
Do not invent payment_date. A period wholly within one calendar year permits
that year's amount; an unallocated cross-year total remains unresolved and
must never be duplicated across years. Known threshold witnesses may suffice
despite unrelated unresolved events. Current claimant and query year are literal
question roles. The supplied benchmark models these as finite case events.

SARA's ORIGINAL finite/native case semantics permits local negation-as-failure
on unmentioned case predicates. Do not add a requirement that the text explicitly
declare an exhaustive full-year history. A failed/unknown neural extraction is
different from an absent predicate in the fully supplied finite case record.
Use extraction status to retain the former as unresolved, not default false.

For residence, accept raw joint residence intervals {persons:[string,...],
start_date:ISO,end_date:ISO} from the finite case record. Persons who lived in the
same home share that interval; an address need not be invented. Compute clipped
union days for the queried pair/year. Do not require an unprovided named address
or an extra explicit principal_abode_given assertion for this fixed case model.
Passing residence alone still cannot prove the full qualifying-child claim.
Missing observed dates/ambiguous extraction remains unknown. No new legal rule,
unprovided case fact, target answer or source/identity-specific branch.
All available pure calls are supplied below; type(value) is allowed, class
construction is not. Use only actual source thresholds and the shared calendar.
'''


def main():
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        parent = bank.read(bank.OUT / 'protocol.json')
        before = bank.rows(); assert not any(r[6] == 'reserved' for r in before)
        task = {'source_only_task': bank.read(bank.OUT / 'teacher_task.json'),
            'actual_previous_proposal': bank.read(bank.OUT / 'teacher.json')['value'],
            'source_logic_and_interface_diagnosis': bank.read(bank.OUT / 'unbound_semantic_diagnosis_v2.json'),
            'future_native_case_facts_or_labels': None}
        immutable_json(OUT / 'teacher_task.json', task)
        files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/span_compiler.py',
            ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py',
            ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py',
            ROOT / 'tests/test_skill_evolution_calendar_execution_contract.py',
            ROOT / 'legal_skill_guard/skill_evolution/clients.py', ROOT / 'legal_skill_guard/skill_evolution/ledger.py']
        p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'sources': parent['sources'],
            'teacher_profile': parent['teacher_profile'], 'executor_profile': parent['executor_profile'],
            'parent_common_acquisition': bank.RUN, 'original_response_and_cost_retained': True,
            'source_only_semantic_and_interface_repair_shared_with_all_arms': True,
            'new_sources_or_future_native_labels': 0,
            'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
            'task_sha256': hashlib.sha256((OUT / 'teacher_task.json').read_bytes()).hexdigest()}
        immutable_json(OUT / 'protocol.json', p)
        immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
        for f in files:
            dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
        from legal_skill_guard.skill_evolution.span_compiler import CALLS, METHODS
        system = SYSTEM + '\nAllowed calls: ' + ','.join(sorted(CALLS)) + '\nAllowed attributes: ' + ','.join(sorted(METHODS))
        user = json.dumps(task, ensure_ascii=False, separators=(',', ':'))
        assert not bank.prior.strict_output_schema_issues(bank.SCHEMA)
        assert len(bank.prior.render_structured_codex_prompt(system, user)) <= bank.prior.CODEX_TURN_INPUT_CHARACTER_LIMIT
        ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
            sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
        if not (OUT / 'teacher.json').exists():
            response = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':source_only_repair',
                source_ids=p['sources'], system_prompt=system, user_prompt=user, output_schema=bank.SCHEMA)
            immutable_json(OUT / 'teacher.json', response)
        print('Source-only common kernel repair saved', flush=True)


if __name__ == '__main__':
    main()
