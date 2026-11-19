"""Replay ownership-policy updates without replacing their unrelated native claims."""

from collections import Counter
from pathlib import Path
import json
import math
import sqlite3
from statistics import mean

from experiments import convergence_oe_feedback_pair as initial
from experiments import convergence_revision5_oe_repair as corrective
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_oe_joint_native_gate import physical_native
from experiments.convergence_revision5_oe_native_amount_bound import amount_guard, clip_claims
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_scoped_policy_replay_20261119'
STAGES = ('initial', 'corrective')
MODES = ('incumbent', 'whole_policy', 'title_scope', 'preserve_existing_amounts', 'add_only', 'direct_amount_bound')
FAMILIES = ('EC', 'EV')
OE = 'OpenExempt'


def by_citation(claims, family):
    index = {claim if family == 'EC' else claim['citation']: claim for claim in claims}
    if len(index) != len(claims):
        raise ValueError('Ambiguous duplicate claim on one exact asset')

    if family == 'EV' and any(not math.isfinite(item['claim_value']) for item in index.values()):
        raise ValueError('Nonfinite amount in native EV claims')
    return index


def merge(incumbent,candidate,inventory,law,family,public):
    """Use a proposal only on source-bound assets with unresolved title."""
    scoped = dict(incumbent)
    fixed = dict(incumbent)
    added = dict(incumbent)
    proposed = Counter()
    for asset in inventory.values():
        name = asset['description']
        if name not in candidate or candidate[name] == incumbent.get(name):
            continue
        title = asset['filing_interest_established']
        if title is not None:
            proposed['excluded_established_title_rows'] += 1
            continue
        try:
            original = by_citation(incumbent.get(name, []),family)
            update = by_citation(candidate[name],family)
        except ValueError:
            proposed['ambiguous_claim_rows'] += 1
            continue
        if not (set(original) | set(update)) <= law:
            proposed['excluded_out_of_scope_rows'] += 1
            continue
        proposed['routed_unknown_title_rows'] += 1
        scoped[name] = list(update.values())
        fixed[name] = [original.get(citation, item) for citation,item in update.items()]
        added[name] = list(original.values()) + [item for key,item in update.items() if key not in original]
        proposed['added_citations'] += len(update.keys()-original.keys())
        proposed['removed_citations'] += len(original.keys()-update.keys())
        proposed['changed_common_citation_amounts'] += sum(update[k] != original[k] for k in update.keys() & original.keys())
    proposed['excluded_unbound_proposal_rows'] = len(set(candidate) - {a['description'] for a in inventory.values()})
    direct = incumbent
    if family == 'EV':
        guard = amount_guard(public)
        assert guard is not None
        direct, changed = clip_claims(incumbent,guard)
        proposed['direct_amount_changes'] = changed
    return dict(zip(MODES,(incumbent,candidate,scoped,fixed,added,direct),strict=True)),dict(proposed)


def verify_native(db, source, prediction, program_sha, ready):
    key = source['key']
    ids = physical_native(db,key,prediction)
    by_task = {view['id']:view for view in source['views']}
    assert len(ids)==len(by_task)==2 and set(by_task)==set(FAMILIES)
    for call,readout in zip(ids,prediction['reads'],strict=True):
        trace, = (r for r in readout['execution']['traces'] if 'physical_call_id' in r)
        family, = readout['native']
        assert trace['physical_call_id']==call and readout['native'][family]==prediction['native'][family]
        assert readout['execution']['program_sha256']==program_sha
        if call in ready:
            continue
        physical_wire(db,{key},call,key)
        result = json.loads(db.execute('select result from calls where id=?',(call,)).fetchone()[0])
        payload = read(Path(result['artifact_directory'])/'request.json')['payload']
        user, = (m['content'] for m in payload['messages'] if m['role']=='user')
        literal = by_task[family]['public']['original_input']
        assert any(json.dumps(literal,ensure_ascii=mode) in user for mode in (True,False))
        ready.add(call)


def run():
    bound,_,base_library,_,sources,_,context,_ = initial.materials()
    first = ROOT/read(initial.POINTER)['artifact_root']
    later = ROOT/read(corrective.POINTER)['artifact_root']
    p,q = [read(stage/'binding.json') for stage in (first,later)]
    p_end,q_end = [read(stage/'terminal.json') for stage in (first,later)]
    assert first.name==digest(p)==digest(bound) and later.name==digest(q)
    assert not p_end['TEST_opened'] and q['postfreeze_TRAIN_only'] and not q['original_TEST_content_or_labels_used']
    assert q['parent_feedback_terminal_sha256']==sha(first/'terminal.json')
    assert all(s['dataset']==OE and s['project_split']=='train' for s in sources)
    expected_keys = {src['key'] for src in sources}
    assert len(expected_keys)==4
    # Original archives remain unchanged. Bind stage receipts before using saved outputs.
    for stage,config in ((first,p),(later,q)):
        assert all(sha(stage/'source_snapshot'/path)==h for path,h in config['source_sha256'].items())
    base = read(first/'incumbent.json')
    rows, program_hashes = {}, {}
    for role in initial.ROLES:
        first_record = read(first/f'{role}.json')
        fixed_record = read(later/f'{role}_native.json')
        program_hashes['initial',role] = digest(first_record['candidate'])
        assert program_hashes['initial',role]==p_end['outcome']['condition_results'][role]['program_sha256']
        assert fixed_record['program_sha256']==q_end['outcomes'][role]['candidate_sha256']
        program_hashes['corrective',role] = fixed_record['program_sha256']
        rows['initial',role]=first_record['measurements']
        rows['corrective',role]=fixed_record['predictions']
    assert set(base['predictions'])==expected_keys and all(set(r)==expected_keys for r in rows.values())
    records = []
    native_ids = set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for position,source in enumerate(sources):
            key = source['key']
            old = base['predictions'][key]
            verify_native(db,source,old,digest(base_library['programs'][OE]),native_ids)
            for (stage,role),proposal in rows.items():
                change = proposal[key]
                verify_native(db,source,change,program_hashes[stage,role],native_ids)
                for view in source['views']:
                    family = view['id']
                    text = view['public']['original_input']
                    _,assets,_ = title_inventory(text)
                    scope = supplied_jurisdiction_scope(text)
                    assert scope and len(assets)>0
                    args = (old['native'][family]['answer'],change['native'][family]['answer'],
                            assets,set(scope['citations']),family,view['public'])
                    projected,counts = merge(*args)
                    records.append({'source':key,'pilot_position':position,'stage':stage,'role':role,
                                    'family':family,'outputs':projected,'routing':counts})
        stage = read(first/'shared_explanation.json')
        typed = stage['audit']['typed_reads']
        assert stage['controls']['literal_only'] and stage['controls']['native_only']
        for case,row in zip(context['cases'],typed,strict=True):
            assert row['case']==case.source_id and row['source_sha256']==digest(case.public) and row['failure'] is None
            physical_wire(db,{case.root_id},row['physical_call_id'],case.root_id)
        support = initial.support(context,typed)
        assert support['shared']['retained']==0 and support['independent_completions']['retained']>0
    grade_path = ROOT/p['native_TRAIN_grade_path']
    assert 'train' in grade_path.parts
    binding = {'study':'OpenExempt_same_scope_for_independent_and_shared_teacher_updates','partition':'TRAIN',
               'frozen_feedback_terminal_sha256':sha(first/'terminal.json'),
               'frozen_corrective_terminal_sha256':sha(later/'terminal.json'),
               'fixed_pilot_sha256':digest(sources),'native_grade_sha256':p['native_TRAIN_grade_sha256'],
               'runner_sha256':sha(Path(__file__)),'modes':list(MODES),
               'amount_bound_runner_sha256':sha(Path(__file__).with_name('convergence_revision5_oe_native_amount_bound.py')),
               'primary':'Replace proposal citations only in the exact unresolved title scope and retain old EV amounts for common citations.'}
    out = HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    immutable_json(out/'predictions.json',records)
    assert sha(grade_path)==binding['native_grade_sha256']
    annotations = read(grade_path)
    views = {s['key']:{v['id']:v for v in s['views']} for s in sources}
    results = {}
    side = []
    for row in records:
        key,family = row['source'],row['family']
        gold = annotations[key][family]
        scores = {m:grade_view(OE,views[key][family],gold,o)['grade'] for m,o in row['outputs'].items()}
        assert all(v is not None for v in scores.values())
        label = row['stage']+'_'+row['role']
        body = results.setdefault(label,{f:{m:[] for m in MODES} for f in FAMILIES})
        for mode,value in scores.items():
            body[family][mode].append(value)
        side.append({**{k:row[k] for k in ('pilot_position','stage','role','family','routing')},
                    'F1':scores,'is_original_shared_conflict_source':key==p['pilot_root'],
                    'scoped_output_matches_direct_bound':row['outputs']['title_scope']==row['outputs']['direct_amount_bound']})
    aggregates = {r:{f:{m:mean(xs) for m,xs in g.items()} for f,g in fs.items()} for r,fs in results.items()}
    terminal = {'status':'settled_OE_ownership_update_scope_TRAIN_replay',
                'new_calls':0,'partition':'TRAIN','ledger':ledger,'original_libraries_preserved':True,
                'native_physical_responses_verified':len(native_ids),'projection_responses_verified':len(typed),
                'aggregate_F1':aggregates,'source_results':side,'retained_shared_support':support,
                'shared_projection_gate_rejection_remains':True,
                'runner_sha256':binding['runner_sha256'],'amount_bound_runner_sha256':binding['amount_bound_runner_sha256'],
                'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',terminal)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**terminal},sort_keys=True),flush=True)


if __name__=='__main__':
    run()
