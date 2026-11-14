"""Acquire a small common, source-only legal kernel bank for execution controls.

No future case facts or native labels are supplied. The existing family A rule
is retained verbatim; the two new kernels only cover their actual source claim
or a necessary false gate. Shared acquisition is charged to all execution arms.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_gap_acquisition as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_execution_kernels_20261114'
OUT = ROOT / 'artifacts' / RUN
PREFIXES = ('3e22604a20', 'd9d6b23646', '5c29a3a22f')
SCHEMA = record_schema({'rationale': {'type': 'string'},
    'kernels': {'type': 'array', 'items': record_schema({
        'name': {'type': 'string'}, 'query_clause': {'type': 'string'},
        'input_fields_json': {'type': 'string'}, 'program': {'type': 'string'},
        'source_quote': {'type': 'string'},
        'scope': {'type': 'string', 'enum': ['exact_clause', 'necessary_false_gate']}})}})
SYSTEM = '''Provide TWO common legal kernels from the supplied fixed source only.
These are shared by every execution control, not an independent C advantage.
Future case facts, native labels and execution results are withheld. Do not use
tools. Do not invent cases, facts, tax rules, exceptions or unprovided roles.

1. agricultural_employer_threshold: the actual section3306(a)(2)(A) threshold
claim. Read the supplied definition, not outside statute versions. Inputs must
be current claimant/query year and primitive payment/wage event records with
their actual payer, payee, stated labor, amount and time. Do not ask a neural
reader to decide employer status or supply a legal final total. Explicitly
GIVEN wages may be consumed as given; do not manufacture a second wage test.
Compute the current/preceding-year threshold inside the kernel. Unknown event
allocation is not zero; a known threshold witness may suffice despite unrelated
unknowns. State any limits in rationale. Mark exact_clause.

2. qualifying_child_residence_gate: the supplied section152(c)(1) shared-abode
duration requirement. Use raw dated residence events, child/taxpayer and query
year. Clip to the query year and compare against the actual statutory fraction.
This is a necessary-false gate for the complete c(1) query: return a handled
Contradiction only when the supplied finite case observations establish failure
of this mandatory residence condition. Passing this one gate does not establish
all other c(1) criteria. Handle actual source exceptions and explicit givens if
applicable; do not assume missing age, return status or conditions false. Mark
necessary_false_gate. No invented negative facts or defaults.

Return each input_fields_json as a JSON object mapping input port names to
{type,description}, using primitive JSON types including array/object. Describe
the raw event member structure in description. Legal thresholds stay in code
with the quoted actual source, not reader answers. Current case roles/year may
come from the current literal question, not source names or IDs.

Each program is a complete pure module of top-level functions with
apply(inputs,premises). It returns {handled:boolean,answer:string|null}; handled
answers use Entailment/Contradiction. Unknown or uncovered stays unhandled/null.
Only supplied facts may support a handled result. No imports/nested functions,
lambdas/files/network/reflection or source/company/name/year-ID branches.
Law-free calendar_year, year_days, inclusive_year_overlap_days and
elapsed_year_overlap_days are shared available primitives. Ordinary min/max/sum,
Python arithmetic and container/string operations are available. No exceptions
as success/defaults. Preserve temporal orientation and literal event roles.
Give one verbatim source_quote supporting each kernel. Keep code compact.
The existing correct family A subrule is included only as interface context;
do not replace or rewrite it. Its A-positive result suffices for the actual
parent query, while A-negative alone cannot prove the full parent c(5) false.
'''


def read(path):
    return json.loads(path.read_text())


def rows():
    import sqlite3
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        return db.execute('select * from calls order by id').fetchall()


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    public = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    sources = [next(s for s in public if s['key'].split(':')[1].startswith(p)) for p in PREFIXES]
    assert all(s['split'] == 'train' for s in sources)
    family = read(ROOT / 'artifacts/legal_skill_evolution_case_support_check_20261112/generated_library.json')
    task = {'source_only_materials': [{'source_id': s['key'], 'source_text': s['views'][0]['public']['source_text']}
        for s in sources[1:]], 'unchanged_family_subrule_context': next(iter(family['skills'].values())),
        'future_facts_and_native_labels_withheld': True,
        'shared_law_free_calendar_code': (ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py').read_text()}
    immutable_json(OUT / 'teacher_task.json', task)
    before = rows(); assert not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/clients.py',
        ROOT / 'legal_skill_guard/skill_evolution/ledger.py', ROOT / 'legal_skill_guard/skill_evolution/calendar_ops.py',
        ROOT / 'legal_skill_guard/inference/codex_cli_client.py', ROOT / 'legal_skill_guard/rr/ledger.py']
    for f in files:
        target = OUT / 'source_snapshot' / f.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    old = read(ROOT / 'artifacts/legal_skill_evolution_source_gap_20261114/protocol.json')
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': [s['key'] for s in sources], 'teacher_profile': old['teacher_profile'],
        'executor_profile': old['executor_profile'], 'new_sources': 0,
        'shared_acquisition_charged_to_all_execution_arms': True,
        'one_common_teacher_acquisition_planned': True, 'executor_calls_here': 0,
        'future_native_facts_and_labels_withheld': True,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'task_sha256': hashlib.sha256((OUT / 'teacher_task.json').read_bytes()).hexdigest()}
    immutable_json(OUT / 'protocol.json', p)
    return p


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'acquire'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        for f, h in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h
        assert hashlib.sha256((OUT / 'teacher_task.json').read_bytes()).hexdigest() == p['task_sha256']
        task = read(OUT / 'teacher_task.json'); user = json.dumps(task, ensure_ascii=False, separators=(',', ':'))
        issues = prior.strict_output_schema_issues(SCHEMA)
        assert not issues and len(prior.render_structured_codex_prompt(SYSTEM, user)) <= prior.CODEX_TURN_INPUT_CHARACTER_LIMIT
        immutable_json(OUT / 'preflight.json', {'schema_issues': issues,
            'request_characters': len(prior.render_structured_codex_prompt(SYSTEM, user)),
            'future_facts_and_labels_absent': True})
        if phase == 'acquire' and not (OUT / 'teacher.json').exists():
            ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
                run_id=RUN, sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
            result = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':common_legal_kernels',
                source_ids=p['sources'], system_prompt=SYSTEM, user_prompt=user, output_schema=SCHEMA)
            immutable_json(OUT / 'teacher.json', result)
            print('Common source-only kernel proposal saved', flush=True)


if __name__ == '__main__':
    main()
