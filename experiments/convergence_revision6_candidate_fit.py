"""Fit the OpenExempt relation update using candidate-driven TRAIN source groups."""

import argparse
from pathlib import Path
import sqlite3

from experiments import convergence_revision5_oe_assertion_coverage as archive
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, _group_digest, _validate_relation, pointer
from experiments.convergence_m2_train_scope import ownership_groups
from experiments.convergence_m2_update_probe import measure_natural_projection
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_oe_joint_native_gate import physical_native
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE/'revision6_formal_candidate_M2'
POINTER = HANDOFF/'revision6_formal_candidate_M2_current.json'


def value_for_asset(output, asset):
    native = output['EV']['answer']
    values = {row['claim_value'] for row in (native or {}).get(asset, []) if row['claim_value'] > 0}
    return next(iter(values)) if len(values) == 1 else None


def choose(groups, before, after):
    """Rank computable stale-copy risks grounded in each candidate's actual original EV response."""
    risk = {}
    for key, group in groups.items():
        first, _ = group['cases']
        amount = first.primitives['amount']
        lead = value_for_asset(before[key], first.public['asset']) if key in before else None
        proposed = value_for_asset(after[key], first.public['asset']) if key in after else None
        # Hypothetical failure programs keep an observed full amount after its literal edit.
        # The reference withholds ownership and requires the exact edited stated value.
        known = {'incumbent': lead, 'candidate': proposed}
        hypotheses = {}
        for role, value in known.items():
            if value == amount:
                forecast = [{'ownership':None, 'stated_value':value} for _ in group['cases']]
                hypotheses[role] = not any(matches_assertions(forecast, signature)
                                           for signature in group['shared']['signatures'].values())
        risk[key] = {'identity': _group_digest(group), 'modeled_stale_full_amount':hypotheses,
                     'candidate_only_risk':hypotheses.get('candidate',False) and
                     lead is not None and not hypotheses.get('incumbent',False),
                     'both_original_native_reads_available':lead is not None and proposed is not None,
                     'planned_pair_reads':2 * len(group['cases'])}
    order = {key:i for i,key in enumerate(groups)}
    legacy = next(reversed(groups))
    selected = max(groups, key=lambda key: (
        risk[key]['candidate_only_risk'] / risk[key]['planned_pair_reads'],
        risk[key]['modeled_stale_full_amount'].get('candidate',False) / risk[key]['planned_pair_reads'],
        risk[key]['both_original_native_reads_available'], order[key]))
    return {'previous':legacy, 'candidate_driven':selected}, risk


def original(batch):
    parent = ROOT/read(pointer(batch))['artifact_root']
    bound, end = read(parent/'binding.json'), read(parent/'terminal.json')
    decisions = read(parent/'matched_decisions.json')
    if (parent.name != digest(bound) or digest(decisions) != end['matched_decisions_sha256']
            or end['TEST_opened'] or end['batch'] != batch):
        raise ValueError('Use the exact settled native candidate and teacher decision')
    checkpoint = ROOT/bound['checkpoint_root']
    study = read(checkpoint/'binding.json')
    roster = load_roster(study)
    journal = TrainingJournal(checkpoint, study, roster)
    ordered = [s for b in roster[:batch] for s in b]
    cohort = [s for s in roster[batch-1] if s['dataset']==OE]
    artifact = read(parent/'candidates'/ORDINARY/OE/'measurements.json')
    m2 = decisions['relation'][OE]
    if (digest(artifact['candidate']) != m2['matched_proposal_sha256']
            or digest(artifact['predictions']) != decisions['teacher'][ORDINARY][OE]['predictions_sha256']):
        raise ValueError('The candidate must be the same actual TRAIN proposal in both acquisition modes')
    incumbent = journal.library(M2,batch-1)['programs'][OE]
    before, after, calls = {}, {}, set()
    measured = journal._observations(M2,batch)
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for source in cohort:
            key = source['key']
            saved = read(journal.directory(M2,batch)/'predictions'/(digest(key)+'.json'))
            if digest(saved) != measured['predictions'][key]:
                raise ValueError('Use the same entering measurements')
            a,b = saved['result'], artifact['predictions'][key]
            calls.update(physical_native(db,key,a))
            calls.update(physical_native(db,key,b))
            before[key], after[key] = a['native'],b['native']
    groups, coverage = ownership_groups(ordered)
    if _group_digest(groups[next(reversed(groups))]) != bound['natural_group_public_sha256']:
        raise ValueError('The previous acquisition must reproduce within the common group pool')
    chosen, rank = choose(groups,before,after)
    source_paths = [Path(__file__).resolve(), ROOT/'experiments/convergence_m2_train_scope.py',
                    ROOT/'experiments/convergence_m2_update_probe.py',
                    ROOT/'legal_skill_guard/paired_interfaces/shared_semantics.py',
                    ROOT/'legal_skill_guard/paired_interfaces/shared_semantics_validation.py']
    spec = {'stage':'revision6_formal_candidate_group_selection','batch':batch,'executor':study['executor'],
            'TRAIN_only':True, 'original_fit_sha256':sha(parent/'terminal.json'),
            'before_program_sha256':digest(incumbent), 'candidate_sha256':digest(artifact['candidate']),
            'selection':chosen, 'eligible_groups':rank, 'source_audits':coverage,
            'matched_native_sha256':digest(m2['native_comparisons']), 'bound_original_native_reads':len(calls),
            'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in source_paths}}
    return spec, groups, ordered, (incumbent,artifact['candidate']), m2['native_comparisons'], parent


def direct_check(group, outputs):
    """Exact positive source assertions plus the shared title variable seen by the relation."""
    ownership = [row['ownership'] for row in outputs if row['ownership'] is not None]
    amounts = [row['stated_value'] for row in outputs]
    expected = [c.primitives['amount'] for c in group['cases']]
    supported = all(a is None or a == b for a,b in zip(amounts,expected,strict=True))
    if len(set(ownership)) > 1 or not supported:
        return 'rejected_by_shared_explanation'
    if ownership:
        return 'rejected_unsupported_literal_assertion'
    if all(a is None for a in amounts):
        return 'insufficient_positive_supervision'
    return 'eligible_train_update'


def run(batch, execute=False):
    spec, groups, ordered, programs, native_pairs, parent = original(batch)
    out = HOME/digest(spec)
    pointer_path = POINTER.with_name(POINTER.stem+f'_B{batch}.json')
    immutable_json(out/'binding.json',spec)
    if (out/'terminal.json').exists():
        print(out,flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','eligible_groups':len(groups)},pointer_path)
        print(out,flush=True)
        return
    if ROOT/read(pointer_path)['artifact_root'] != out:
        raise ValueError('Prepare the exact candidate and audited group pool before dispatch')
    for name, expected in spec['source_sha256'].items():
        dest = out/'source_snapshot'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        if sha(dest) != expected:
            raise ValueError('Bound implementation changed')
    visible = [s['key'] for s in ordered]
    ledger = EvolutionLedger(LEDGER,run_id=f'revision6-M2-B{batch}-'+out.name[:12],
        sources={'train':visible,'dev':[],'test':[]},binding=spec)
    reader = FrozenExecutor(ledger,out,spec['executor'])
    reader.exact_replay_roots = [parent,*(ROOT/read(pointer(i))['artifact_root'] for i in range(2,batch))]
    incumbent,candidate = programs
    results = {}
    by_key = {}
    for policy,key in spec['selection'].items():
        group = groups[key]
        if key not in by_key:
            write_status(out,{'status':'running','acquisition':policy},pointer_path)
            baseline = [measure_natural_projection(reader,out,incumbent,case) for case in group['cases']]
            validation = _validate_relation(reader,out,candidate,group,visible,native_pairs)
            obs, = validation['explanation_state']['observations']
            outputs = obs['actual_signature']
            supported = direct_check(group,outputs)
            has_gain = sum(r['patch_utility']-r['baseline_utility'] for r in native_pairs)>0
            if supported == 'eligible_train_update' and not has_gain:
                supported = 'retain_incumbent_on_native_train'
            if supported != validation['status']:
                raise ValueError('The matched direct and shared gates disagree on the bound legal relation')
            selected = candidate if validation['status']=='eligible_train_update' else incumbent
            by_key[key] = {'status':validation['status'],'matched_direct_status':supported,
                           'candidate_actual':validation,'incumbent_actual':baseline,
                           'logical_projection_budget':spec['eligible_groups'][key]['planned_pair_reads'],
                           'program':selected}
        decision = by_key[key]
        skill = sealed({'batch':batch,'acquisition':policy,'dataset':OE,'program':decision['program'],
                        'candidate_decision_sha256':digest(decision),
                        'original_fit_sha256':spec['original_fit_sha256']},'snapshot_sha256')
        immutable_json(out/'TRAIN_batch_libraries'/f'{policy}.json',skill)
        results[policy] = {**decision,'snapshot_sha256':skill['snapshot_sha256']}
    with ledger.transaction() as db:
        physical = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                                  (ledger.run_id+':%',)))
        if physical.get('reserved'):
            raise ValueError('Reconcile pending projections')
        forward = archive.archived_pairs(db) if batch == 7 else None
    evidence = {}
    if forward:
        bank,terminal,roles,count,grade_path = forward
        scope = bank[8]
        for policy, result in results.items():
            role, = (k for k,v in roles.items() if v == digest(result['program']))
            values = scope['raw'][role]
            evidence[policy] = {'adopted_program_role':role,'forward_predictions_sha256':digest(values),
                'forward_native':archive.score(scope['original_views'], scope['raw'], read(grade_path))[role]}
        evidence['original_forward_binding'] = terminal
        evidence['verified_native_reads'] = count
    record = sealed({'status':'settled_revision6_formal_candidate_M2','binding_sha256':out.name,
                     'decisions':results,'new_physical_requests':physical,'forward_TRAIN':evidence,
                     'TEST_opened':False},'terminal_sha256')
    immutable_json(out/'terminal.json',record)
    write_status(out,{'status':record['status'],'terminal_sha256':record['terminal_sha256']},pointer_path)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    parser.add_argument('--batch',type=int,choices=(7,8),default=7)
    args=parser.parse_args()
    run(args.batch,args.phase=='run')
