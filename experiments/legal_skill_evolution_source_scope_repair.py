"""Finite source-semantic repair on two already fixed TRAIN mothers.

Both independent teachers receive identical current libraries, full sources and
partial semantic feedback. No new data, evaluator change or executor request.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_gap_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, INSTRUCTION, PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues, render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT

RUN = 'legal_skill_evolution_source_scope_repair_20261114'
OUT = e.ROOT / 'artifacts' / RUN
PREFIXES = ('de427b59', '6fce8464')
REVIEW = '''Partial source-semantic repair feedback, not new native labels:
de42 units39-41:39 supplies return OR destroy all CI and copies.40 supplies
nonformation of the business relationship within three months after BOTH parties
signed.41 supplies prompt compliance upon request at any time. A context-derived
trigger on39 alone omits its supporting clauses and the stated deadline. Preserve
the two event/deadline branches separately or faithfully in a typed alternative.
Do not treat the 3-month nonformation deadline as a request compliance deadline.

6fce units10 and12:10 defines listed employees/officers/directors/consultants/
affiliates/subsidiaries/agents as Representatives involved in the Project.12
limits access to Representatives bound IN WRITING on terms no less stringent.
Current C independently emits employee/consultant/agent permissions from10 with
confidentiality not_stated and a separate Representatives permission from12.
Source concept membership and qualification scope must actually connect; preserve
local statement information and do not deliberately drop existing scope hints to
create a fake need for G. Fixed-radius windows are not legal scope boundaries.

6fce15: return upon request OR destroy within ten business days of Project end.
This does not entail destroy upon request. The common incoming old Norm DOES
incorrectly offer return/destroy under request with no exceptions. Both current
libraries preserve it; valid old roots must remain, this false root must not be
laundered by keep_root or ignored merely because a later correct Norm also exists.
16/18 supply backup/archive and one legal-department dispute copy exceptions with
continuing confidentiality.24/26 repeat them. Keep raw qualifiers and correct
action/material/exception scope; backup permission is not unlimited retention.

6fce20 is a parent trigger: written demand OR Agreement termination.21 supplies
return of CI/copies/notes/extracts and ten business days after receipt of demand.
C currently never acquires this separate obligation. Free does acquire both
events, but does not encode every exception. Do not transfer the demand-receipt
deadline to termination without source support. Source semantics and native
interpretation are separate. Project-end or affiliate-exit is not an acquired
Agreement-termination branch just because a native consumer groups them.

6fce61: contracting party must CAUSE its corporate affiliate to return/destroy
on request before affiliate exit, in accordance with Section5. Do not replace
this by an unconditional direct personal duty or drop the Section5 reference.
Source bound responsibility/actor and reference can be retained explicitly;
unresolved details remain unresolved. No missing legal consequence is supplied
by an adapter. Native scores are not a complete source correctness certificate.

These are partial actual source checks for acquisition, not a new all-fields-
perfect or zero-fallback acceptance gate. Other actual current shortcomings may
remain. Do not fabricate source absences, treat unreviewed as false, hard-code
mother IDs/company names, or change the official native metric/labels.
'''
COMMON = '''One targeted actual repair of the supplied current programs using
the SAME two already-fixed original TRAIN mothers, original raw sources,
TRAIN supervision and actual partial source review. Both teachers have identical
information and all previous current C/Free code. Independent ordinary Free has
full program capacity and may use the same decomposition. This is not new data
or held-out validation. Current acquisition scores are C25/32 and Free21/32 on8;
same-C-consumer Free23/32, so do not attribute consumer differences to acquisition.
No U learning is claimed by this shared semantic repair. The objective is to
acquire missing source scope without conflicting old roots, not game native EM.

Keep both current decision programs UNCHANGED: decision_functions must be[].
No neural questions needed in this source-only repair: operations and reading_
contracts=[], planner_functions may keep/replace plan with {queries:[]}.
source_program is a COMPLETE SELF-CONTAINED pure module with apply(inputs,
premises). Inputs contain source_text, source_spans with integer IDs and text,
and common source_output. Return statements:{term,support_ids}[],complete,
unresolved. No imports, nested defs/lambdas, source IDs, network/files. Existing
well-grounded incoming legal roots remain; false incoming roots may be replaced
only by an actual current-source justified correction. Every multi-clause field
has its actual joint source support. Don't blindly propagate support unit U from
root_support(A,U) as one independent witness: support_from_terms on A preserves
the source term's entire evidence. Constructors/meanings and generic observation
API are supplied. Only truly new constructor names can be declared.

Prefer a local source representation that preserves role definitions, membership,
qualified scopes, action identity, header-child and explicit references. Current
raw terms/hints may remain: do not delete useful data to manufacture collisions.
For C, actual learned G must compose qualifications/actors/action scope where
needed; a single pre-completed policy packet switch is not evidence of learning
those relations. No new Norms bypass G in C; existing valid incoming Norms may
remain. G output argument sorts match supplied encoder (term_scalar is scalar),
all head variables bound, every output argument used by legal template/evidence.
Use output-provenance TERM coordinates and support_from_terms for joint evidence.
For Free, unrestricted pure source/composition code can emit typed Norms directly.
No future test, full training, fresh model config, synthetic case or new source.
Keep module compact and executable in the actual supplied interface.
'''


def setup():
    path = OUT / 'protocol.json'
    if not path.exists():
        old_protocol, _, _ = e.setup()
        old_task = e.read(e.OUT / 'teacher_task.json')
        tasks = [t for t in old_task['tasks'] if any(t['source_id'].startswith('ContractNLI:' + p) for p in PREFIXES)]
        assert len(tasks) == 2
        libraries = {'ConstraintAcquire': e.read(e.OUT / 'unbound_provenance_replay/library.json'),
            'FreeUpdate': e.read(e.OUT / 'FreeUpdate/compiled.json')}
        for t in tasks:
            t['actual_before'] = {arm: e.read(e.OUT / 'unbound_pure_preview' / arm / e.name_for(t['source_id']))['actual']
                for arm in e.ARMS}
        task = {'tasks': tasks, 'actual_current_libraries_both_available': libraries,
            'partial_source_semantic_review': REVIEW, 'observed_signatures': old_task['common_observed_signatures'],
            'encoder_code': old_task['encoder_code'], 'same_information_and_full_program_capacity': True}
        packed = pack_programs(task)
        assert unpack_programs(packed) == task
        immutable_json(OUT / 'teacher_task.json', task)
        rows = e.previous.prior.rows()
        assert not any(r[6] == 'reserved' for r in rows)
        immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in rows})
        files = [Path(__file__), *sorted((e.ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))]
        protocol = {'same_goal': True, 'goal_complete': False, 'run_id': RUN,
            'acquisition_sources': [t['source_id'] for t in tasks], 'executor_requests_planned': 0,
            'finite_serial_teacher_acquisitions_planned': 2, 'U_dictionary': [],
            'no_new_full_training_DEV_TEST_or_paper': True,
            'executor_profile': old_protocol['executor_profile'], 'teacher_profile': old_protocol['teacher_profile'],
            'source_sha256': {str(f.relative_to(e.ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
            'data_sha256': {'teacher_task.json': hashlib.sha256((OUT / 'teacher_task.json').read_bytes()).hexdigest()},
            'task_logical_sha256': digest(task)}
        for f in files:
            dst = OUT / 'source_snapshot' / f.relative_to(e.ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
        immutable_json(path, protocol)
    protocol = e.read(path)
    for file, value in protocol['source_sha256'].items():
        assert hashlib.sha256((e.ROOT / file).read_bytes()).hexdigest() == value, file
    for file, value in protocol['data_sha256'].items():
        assert hashlib.sha256((OUT / file).read_bytes()).hexdigest() == value, file
    return protocol, EvolutionLedger(e.previous.prior.prior.LEDGER, run_id=RUN,
        sources={'train': protocol['acquisition_sources'], 'dev': [], 'test': []}, binding=digest(protocol))


def request(arm):
    protocol, ledger = setup()
    task = e.read(OUT / 'teacher_task.json')
    system = COMMON + '\n' + (e.C_PART + '\n' + e.previous.prior.prior.C_SPEC if arm == 'ConstraintAcquire' else e.FREE_PART)
    system += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
    system += '\nAllowed pure attributes:' + ','.join(sorted(e.METHODS)) + '\nAllowed pure calls:' + ','.join(sorted(e.CALLS))
    schema = e.C_SCHEMA if arm == 'ConstraintAcquire' else e.FREE_SCHEMA
    user = json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':'))
    issues = strict_output_schema_issues(schema)
    size = len(render_structured_codex_prompt(system, user))
    assert not issues and size <= CODEX_TURN_INPUT_CHARACTER_LIMIT
    immutable_json(OUT / arm / 'preflight.json', {'schema_issues': issues, 'request_characters': size,
        'task_logical_sha256': digest(task), 'transport_roundtrip_exact': unpack_programs(pack_programs(task)) == task})
    return protocol, ledger, {'source_ids': protocol['acquisition_sources'], 'system_prompt': system,
        'user_prompt': user, 'output_schema': schema}


def acquire():
    for arm in e.ARMS:
        if (OUT / arm / 'teacher.json').exists():
            continue
        protocol, ledger, args = request(arm)
        result = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(RUN + ':' + arm + ':teacher', **args)
        immutable_json(OUT / arm / 'teacher.json', result)
        print(json.dumps({'arm': arm, 'paid_source_scope_repair_saved': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'acquire'])
    args = parser.parse_args()
    with (e.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'preflight':
            for arm in e.ARMS:
                request(arm)
        else:
            acquire()
