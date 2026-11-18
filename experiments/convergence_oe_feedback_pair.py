"""Isolate shared-explanation feedback on the locked OpenExempt TRAIN pilot."""

import argparse
from copy import deepcopy
import json
from statistics import mean
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, _group, _measure as measure_native, _validate_relation
from experiments.convergence_formal_train_fit import pointer as fit_pointer
from experiments.convergence_m2_forward_oe import prepare_conditioning
from experiments.convergence_oe_component_probe import (
    POINTER as TYPED_POINTER, SCHEMA as TYPED_SCHEMA, SYSTEM as TYPED_SYSTEM, _measure as measure_components,
)
from experiments.convergence_oe_conditioned_value_probe import _validate
from experiments.convergence_oe_scoped_proposal import OWNERSHIP_FIELD, PROJECTION_FIELD
from experiments.convergence_oe_title_value_probe import _materials as literal_materials
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.control_programs import validate_program
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import EVInventoryActor
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.shared_semantics import allowed_relation, matches_assertions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'B8_OE_feedback_pair_current.json'
SCHEMA = record_schema({OWNERSHIP_FIELD: {'type': 'string'}})
ROLES = ('independent_completions', 'shared_explanation')
SYSTEM = (
    'Revise only the reusable source-level ownership policy of an OpenExempt EC/EV reader. '
    'The same replacement policy enters the native reader and the local title projection. '
    'The executable composition, native task instructions and local projection instructions are fixed. '
    'Use the supplied scope and observed TRAIN evidence to remove errors while preserving valid native outputs. '
    'Maintain the distinction between possession and title. Read a stated valuation independently of title. '
    'Retain unresolved assertions unless the source establishes them. Use the reported admissible '
    'allocations only as feedback about the policy. Do not encode case identifiers, example amounts, '
    'case-specific labels or a lookup table. Return a general policy for new source facts.'
)


def edit_policy(program, policy, source_ids):
    """Replace the one policy field in both of the existing reader channels."""
    policy = policy.strip()
    if not policy or any(source in policy for source in source_ids):
        raise ValueError('The ownership policy must be a reusable instruction')
    base = program[OWNERSHIP_FIELD]
    prefix = '\nSource-level ownership rules:\n'
    native = program['predicates'][0]['prompt']
    projection = program[PROJECTION_FIELD]
    if (not native.endswith(prefix + base) or not projection.startswith(base + '\nRequested-component computation:\n')):
        raise ValueError('Preserve the original native and local reader construction')
    candidate = deepcopy(program)
    candidate['predicates'][0]['prompt'] = native.removesuffix(base) + policy
    candidate[OWNERSHIP_FIELD] = policy
    candidate[PROJECTION_FIELD] = policy + projection[len(base):]
    validate_program(candidate)
    return candidate


def signatures(context, mode):
    return list(allowed_relation(context['theory'], context['cases'], mode=mode)['signatures'].values())


def feedback_rows(context, terminal):
    """Use the same primitive facts and recorded tags in both teacher conditions."""
    reports = [terminal['details'][role]['reads'] for role in ('incumbent', 'candidate')]
    rows = []
    for case, query, before, after in zip(context['cases'], context['inputs'], *reports, strict=True):
        if any(row['case'] != case.source_id or row['source_sha256'] != digest(case.public)
               or row['failure'] is not None for row in (before, after)):
            raise ValueError('Only the bound physically audited partial observations can enter feedback')
        rows.append({
            'component': query['requested_component'],
            'literal_facts': query['independently_verified_source_facts'],
            'earlier_reader_observation': before['read_tag'],
            'current_reader_observation': after['read_tag'],
        })
    return rows


def teacher_inputs(program, context, typed, baseline):
    independent = signatures(context, 'independent_completions')
    shared = signatures(context, 'shared')
    if len(shared) != 2 or len(independent) != 16:
        raise ValueError('Preserve the original case relation and factorization')
    shared_marginals = [sorted(set(column)) for column in zip(*shared, strict=True)]
    marginals = [sorted(set(column)) for column in zip(*independent, strict=True)]
    if shared_marginals != marginals:
        raise ValueError('Both teachers must have identical per-query legal possibilities')
    common = {'starting_policy': program[OWNERSHIP_FIELD], 'fixed_queries': feedback_rows(context, typed),
              'per_query_allowed_amounts': marginals, 'native_pilot_aggregate': baseline,
              'main_path': 'Each native answer must bind the original asset and cite only the supplied jurisdiction.',
              'unknown_observation_rule': 'An unresolved observation leaves that position unasserted.'}
    relation = {
        'independent_completions': {
            'constraint': 'Each query is assessed against its own allowed set.',
            'independently_allowed_allocations': 'All combinations of the already supplied per-query amounts.',
        },
        'shared_explanation': {
            'constraint': 'One scoped title assignment must explain every asserted slot across the four queries.',
            'jointly_allowed_allocations': shared,
        },
    }
    return {role: {**common, 'interpretation_feedback': relation[role]} for role in ROLES}


def support(context, rows):
    """Measure the information in real partial tags without filling unknown values."""
    observed = [row['value'] for row in rows]
    if any(row['failure'] is not None for row in rows):
        raise ValueError('An invalid response does not constitute a typed partial read')
    return {
        mode: {'possible': len(universe),
               'retained': sum(matches_assertions(observed, row) for row in universe)}
        for mode in ('shared', 'independent_completions')
        for universe in (signatures(context, mode),)
    }


def materials():
    fit = ROOT / read(fit_pointer(8))['artifact_root']
    fit_binding, end = (read(fit/name) for name in ('binding.json', 'terminal.json'))
    if (fit.name != digest(fit_binding) or end['status'] != 'completed_all_five_TRAIN_updates'
            or end['batch'] != 8 or end['TEST_opened']):
        raise ValueError('The feedback comparison requires the sealed B8 training')
    checkpoint = ROOT / fit_binding['checkpoint_root']
    study = read(checkpoint/'binding.json')
    batches = load_roster(study)
    visible = [source for batch in batches for source in batch]
    source_map = {row['key']: row for row in visible}
    journal = TrainingJournal(checkpoint, study, batches)
    base = journal.library(M2, 8)
    archive_pointer = read(TYPED_POINTER)
    typed_root = ROOT / archive_pointer['artifact_root']
    typed = read(typed_root/'terminal.json')
    typed_binding = read(typed_root/'binding.json')
    typed_archive = read(typed_root/'source_snapshot_receipt.json')
    witness_path = HANDOFF/'B8_OE_typed_partial_shared_witness_20261119.json'
    witness = read(witness_path)
    binding_matches = (digest(study) == fit_binding['study_binding_sha256'],
                       end['arm_receipts'][M2] == journal._completed_batch(M2, 8)['completed_batch_sha256'],
                       typed_root.name == digest(typed_binding) == typed_archive['archived_terminal_binding'],
                       typed_binding['B8_terminal_sha256'] == sha(fit/'terminal.json'),
                       typed_binding['program_sha256']['candidate'] == digest(base['programs'][OE]),
                       typed_root.name == witness['typed_binding'],
                       sha(typed_root/'terminal.json') == witness['typed_terminal_sha256'])
    if (not all(binding_matches) or typed['executor_calls'] != 8 or typed['TEST_opened'] or witness['TEST_opened']):
        raise ValueError('The actual scoped observation and incumbent binding changed')
    context = prepare_conditioning(visible, fit_binding['executor'])
    _, _, root, audited_title, _, _, _, _ = literal_materials()
    literal, _ = _group([source for cohort in batches[:4] for source in cohort])
    if (literal is None or [case.public for case in literal['cases']] != [case.public for case in audited_title['cases']]):
        raise ValueError('The literal check must use its original audited two-field source cases')
    roster_receipt = read(HANDOFF/'sealed_source_roster_current.json')
    roster = read(ROOT/roster_receipt['artifact_root']/'binding.json')
    pilot = [row for row in roster['fixed_pilot'] if source_map[row['source']]['dataset'] == OE]
    sources = [source_map[row['source']] for row in pilot]
    if (digest(roster) != study['roster_sha256'] or len(pilot) != 4
            or root not in {source['key'] for source in sources}
            or {case.root_id for case in context['cases']} != {root}
            or any(digest(source) != row['public_sha256'] for source,row in zip(sources,pilot,strict=True))):
        raise ValueError('Use only the four unchanged OpenExempt sources in the locked TRAIN pilot')

    previous = [fit, ROOT/fit_binding['observations_root'], typed_root]
    previous.extend(ROOT/path for path in fit_binding['fit_replay_roots'])
    bound = set(typed_binding['source_sha256']) | {'experiments/convergence_oe_feedback_pair.py'}
    observed = read(ROOT/fit_binding['observations_root']/'binding.json')
    grade_path = observed['native_grade_paths'][OE]
    spec = {
        'study': 'paired_partial_shared_feedback_on_fixed_TRAIN_pilot',
        'teacher_profile': study['teacher_profile'], 'teacher_config': study['teacher_config'],
        'executor': study['executor'], 'B8_training_library_sha256': base['snapshot_sha256'],
        'paired_pilot_sources_sha256': digest(sources), 'pilot_root': root,
        'typed_witness_sha256': sha(witness_path), 'typed_terminal_sha256': sha(typed_root/'terminal.json'),
        'original_context': context['binding'], 'roles': ROLES,
        'teacher_contract_sha256': digest([SCHEMA,SYSTEM]),
        'typed_contract_sha256': digest([TYPED_SCHEMA,TYPED_SYSTEM]),
        'replay_roots': {str(path.relative_to(ROOT)): sha(path/'terminal.json') for path in previous},
        'native_TRAIN_grade_path': grade_path,
        'native_TRAIN_grade_sha256': observed['native_grade_sha256'][grade_path],
        'source_sha256': {name: sha(ROOT/name) for name in sorted(bound)},
        'teacher_calls_per_condition': 1, 'TEST_opened': False,
    }
    return spec, study, base, visible, sources, literal, context, typed


def _native_scores(sources, predictions, reference):
    scores = {}
    for source in sources:
        key = source['key']
        scores[key] = {}
        for task in source['views']:
            name = task['id']
            answer = predictions[key]['native'][name]
            scores[key][name] = (grade_view(OE, task, reference[key][name], answer['answer'])['grade']
                                 if answer['handled'] else 0.0)
    return scores


def _aggregate(scores):
    return {view: mean(item[view] for item in scores.values()) for view in ('EC', 'EV')}


def main(execute):
    spec, study, base, visible, pilot, literal, context, typed = materials()
    stage = BASE/'B8_OE_feedback_pair'/digest(spec)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root'] != stage):
        raise ValueError('Use the prepared TRAIN sources, programs and feedback binding')
    immutable_json(stage/'binding.json', spec)
    if (stage/'terminal.json').exists():
        print(json.dumps(read(stage/'terminal.json')['outcome'],sort_keys=True),flush=True)
        return
    if (HANDOFF/'formal_B8_TEST_current.json').exists():
        raise ValueError('Use the paired feedback only during closed-TEST development')
    if not execute:
        write_status(stage, {'status':'prepared','pilot_sources':4,'teacher_conditions':len(ROLES),'TEST_opened':False}, POINTER)
        print(stage.relative_to(ROOT),flush=True)
        return
    for name in ('formal_B8_DEV_current.json', 'formal_B8_transfer_current.json'):
        prior = HANDOFF / name
        if prior.exists() and read(prior)['status'] == 'running':
            raise ValueError('Wait for the live fixed DEV stage to settle before dispatch')
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('The serial generation stage is still in use')
    keys = [source['key'] for source in pilot]
    visible_keys = [source['key'] for source in visible]
    run_id = 'convergence-B8-OE-feedback-pair-' + stage.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':keys,'dev':[],'test':[]},binding=spec)
    reader = FrozenExecutor(ledger,stage,spec['executor'])
    reader.exact_replay_roots = [ROOT/path for path in spec['replay_roots']]
    reader.readiness()
    teacher = FrozenTeacher(ledger,stage,spec['teacher_config'],authorized_profile=spec['teacher_profile'])
    actor = EVInventoryActor(ConvergenceActor(stage,program_actor=ProgramActor(reader,stage,max_calls=1),
                             interface_actor=None,providers={},train_sources=visible_keys,study_binding=study),
                             jurisdiction_scope=True)
    grade_path = ROOT/spec['native_TRAIN_grade_path']
    if sha(grade_path) != spec['native_TRAIN_grade_sha256']:
        raise ValueError('The native TRAIN scoring reference changed')
    reference = read(grade_path)
    starting = base['programs'][OE]
    write_status(stage, {'status':'running','arm':'incumbent','TEST_opened':False}, POINTER)
    before_predictions = measure_native(actor,base,pilot)
    before = _native_scores(pilot,before_predictions,reference)
    immutable_json(stage/'incumbent.json',{'native':before,'predictions':before_predictions})
    payloads = teacher_inputs(starting,context,typed,_aggregate(before))
    common = [{k:v for k,v in payload.items() if k!='interpretation_feedback'} for payload in payloads.values()]
    if common[0] != common[1]:
        raise ValueError('Only the explanation feedback may vary between the two teachers')
    immutable_json(stage/'paired_teacher_contract.json',{
        'common_payload_sha256':digest(common[0]),
        'request_payload_sha256':{role:digest(body) for role,body in payloads.items()}})
    proposals = {}
    for role in ROLES:
        write_status(stage, {'status':'running','arm':role,'step':'teacher','TEST_opened':False}, POINTER)
        call = run_id+':teacher:'+role
        response = teacher.propose(call,source_ids=keys,system_prompt=SYSTEM,
                                   user_prompt=json.dumps(payloads[role],sort_keys=True),output_schema=SCHEMA)
        if response['model'] != spec['teacher_profile']['model']:
            raise ValueError('The paired teacher profile changed')
        proposals[role] = (call,response['value'][OWNERSHIP_FIELD])

    outcomes = {}
    for role,(call,policy) in proposals.items():
        write_status(stage, {'status':'running','arm':role,'step':'executor','TEST_opened':False}, POINTER)
        controls = dict.fromkeys(('native_only','literal_only','shared_explanation',
                                  'independent_completions','single_interpretation'),False)
        try:
            candidate = edit_policy(starting,policy,visible_keys)
        except ValueError as error:
            outcomes[role] = {'teacher_call':call,'invalid_policy':str(error),'controls':controls}
            continue
        child = sealed({**{k:v for k,v in base.items() if k!='snapshot_sha256'},
                        'programs':{**base['programs'],OE:candidate}},'snapshot_sha256')
        predictions = measure_native(actor,child,pilot)
        scores = _native_scores(pilot,predictions,reference)
        native_pairs = [{'source':key,'baseline_utility':mean(before[key].values()),
                         'patch_utility':mean(scores[key].values())} for key in keys]
        native_gain = mean(row['patch_utility']-row['baseline_utility'] for row in native_pairs)
        row = {'teacher_call':call,'native':_aggregate(scores),'native_mean_gain':native_gain}
        controls['native_only'] = native_gain > 0
        audit = {}
        if native_gain > 0:
            literal_result = _validate_relation(reader,stage,candidate,literal,visible_keys,native_pairs)
            controls['literal_only'] = literal_result['status']=='eligible_train_update'
            audit['literal'] = literal_result
            if controls['literal_only']:
                reads = measure_components(reader,stage,candidate,context)
                audit['typed_reads'] = reads
                if not any(x['failure'] is not None for x in reads):
                    retained = support(context,reads)
                    validation, checks = _validate(context['theory'],context['cases'],reads,candidate,native_pairs,visible)
                    audit.update(support=retained, validation=validation)
                    for mode in ('shared','independent_completions'):
                        bounds = retained[mode]
                        controls['shared_explanation' if mode=='shared' else mode] = (
                            0 < bounds['retained'] < bounds['possible'])
                    controls['single_interpretation'] = checks['single_compatible']
        immutable_json(stage/(role+'.json'),{'candidate':candidate,'measurements':predictions,'native':scores,
                                             'controls':controls,'audit':audit})
        outcomes[role] = {**row,'program_sha256':digest(candidate),'controls':controls}

    def chosen(rule):
        eligible = [role for role in ROLES if outcomes[role]['controls'][rule]]
        return max(eligible,key=lambda role: (outcomes[role]['native_mean_gain'],-ROLES.index(role)),default=None)

    selected = {rule:chosen(rule) for rule in outcomes[ROLES[0]]['controls']}
    outcome = {'incumbent':_aggregate(before),'condition_results':outcomes,'selector_choices':selected,
               'distinct_shared_selection':selected['shared_explanation'] is not None and
               selected['shared_explanation'] != selected['independent_completions']}
    native = [outcomes[role].get('native') for role in ROLES]
    if all(native):
        outcome['shared_feedback_minus_independent'] = {
            view:native[1][view]-native[0][view] for view in ('EC','EV')
        }
    with ledger.transaction() as db:
        calls = db.execute('select role,status,result from calls where id like ?', (run_id+':%',)).fetchall()
    if any(status!='completed' for _,status,_ in calls):
        raise ValueError('Preserve every physically dispatched comparison response')
    counts = {role:sum(row[0]==role for row in calls) for role in ('executor','teacher')}
    if counts['teacher'] != 2:
        raise ValueError('The feedback treatment must give each teacher one proposal')
    usage = {'executor':0,'teacher':0}
    for role,_,raw in calls:
        row = json.loads(raw)
        if role == 'executor':
            usage[role] += row['usage']['total_tokens']
        else:
            token_counts = row['invocation']['usage']
            usage[role] += token_counts.get('input_tokens',0)+token_counts.get('output_tokens',0)
    result = {'status':'completed_B8_OE_feedback_pair','outcome':outcome,'physical_calls':counts,'tokens':usage,
              'training_library_changes':0,'TEST_opened':False}
    immutable_json(stage/'terminal.json',result)
    write_status(stage, {'status':result['status'],'physical_calls':counts,'TEST_opened':False}, POINTER)
    print(json.dumps(outcome,sort_keys=True),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    main(parser.parse_args().phase=='run')
