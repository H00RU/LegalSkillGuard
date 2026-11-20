"""Evaluate the group-selected EV skill at its declared task scope on fixed DEV."""

import argparse
from collections import Counter
from functools import lru_cache
import inspect
from pathlib import Path

from experiments import convergence_revision6_candidate_edits as fit
from experiments import convergence_revision5_oe_assertion_coverage as common
from experiments import convergence_revision5_release_dev as release
from experiments.convergence_pilot_b0 import BASE,HANDOFF,LEDGER,ROOT,read,sha,write_status
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import with_ev_inventory
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed,verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE/'revision6_candidate_M2_DEV'
POINTER = HANDOFF/'revision6_candidate_M2_DEV_current.json'
POLICIES = ('source_context','native_disagreement')


def materials():
    parent = ROOT/read(fit.POINTER)['artifact_root']
    end = verify(read(parent/'terminal.json'),'terminal_sha256')
    if end['binding_sha256'] != parent.name or end['TEST_opened']:
        raise ValueError('Require the settled candidate-driven TRAIN acquisition')
    libraries = {p:verify(read(parent/'TRAIN_batch_libraries'/f'{p}.json'),'snapshot_sha256') for p in POLICIES}
    if any(libraries[p]['snapshot_sha256']!=end['decisions'][p]['snapshot_sha256'] for p in POLICIES):
        raise ValueError('The DEV skill must be the exact adopted TRAIN program')
    root, latest, _ = release.stage(release.POINTER)
    cohort, original, study, _ = release.formal.common.archive()
    sources = [s for s in cohort if s['dataset']=='OpenExempt']
    files = [Path(__file__).resolve(),Path(common.__file__).resolve(),Path(inspect.getfile(ProgramActor)),
             Path(inspect.getfile(with_ev_inventory)),Path(inspect.getfile(FrozenExecutor))]
    binding = {'stage':'revision6_group_selected_EV_fixed_DEV','TRAIN_fit_terminal_sha256':end['terminal_sha256'],
               'adopted_EV_libraries':{p:libraries[p]['snapshot_sha256'] for p in POLICIES},
               'shared_EC_DEV_terminal_sha256':latest['terminal_sha256'],
               'public_DEV_sha256':digest(sources),'executor':study['executor'],
               'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},
               'native_scope':'EV only. EC comes from the same verified B8 DEV arm in both conditions.',
               'unchanged_grade_and_DEV_population':True,'TEST_opened':False}
    return binding,libraries,root,latest,sources,original,study


def run(execute=False):
    binding,libraries,root,latest,sources,original,study = materials()
    out = HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    if (out/'terminal.json').exists():
        print(out,flush=True)
        return
    if not execute:
        write_status(out,{'status':'prepared','DEV_mothers':len(sources),'max_new_wire_requests':len(sources)*2},POINTER)
        print(out,flush=True)
        return
    if ROOT/read(POINTER)['artifact_root'] != out:
        raise ValueError('Prepare exact DEV cohort and adopted TRAIN checkpoints')
    for name,expected in binding['source_sha256'].items():
        p=out/'source_snapshot'/name
        p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            with p.open('xb') as f:
                f.write((ROOT/name).read_bytes())
        if sha(p)!=expected:
            raise ValueError('The versioned DEV runner changed')
    cells = release.parent_cells(root,latest)
    baseline = release.ReleaseActor(root,cells,{})
    keys = [s['key'] for s in sources]
    ledger = EvolutionLedger(LEDGER,run_id='revision6-M2-EV-DEV-'+out.name[:12],
        sources={'train':[],'dev':keys,'test':[]},binding=binding)
    reader = FrozenExecutor(ledger,out,binding['executor'])
    reader.exact_replay_roots = [x[0] for x in original.values()]
    actor = ProgramActor(reader,out,max_calls=1)
    board = {'original_views':{},'raw':{p:{} for p in POLICIES}}
    completion = Counter()
    traces = {}
    @lru_cache(maxsize=None)
    def measure(program_hash, source_key):
        source = next(s for s in sources if s['key']==source_key)
        program = next(row['program'] for row in libraries.values() if digest(row['program'])==program_hash)
        ev = next(v for v in source['views'] if v['id']=='EV')
        public = with_ev_inventory({**source,'views':[ev]},jurisdiction_scope=True)
        row = actor.execute(program,public,'skill_dev')
        actor.verify_program_result(public,program,'skill_dev',row)
        return row
    for source in sources:
        k=source['key']
        board['original_views'][k]={v['id']:v for v in source['views']}
        fixed=baseline.original(release.formal.common.ORDINARY,k)['result']['native']['EC']['answer']
        for policy,library in libraries.items():
            row=measure(digest(library['program']),k)
            completion[policy]+=row['native']['EV']['handled']
            board['raw'][policy][k]={'EC':fixed,'EV':row['native']['EV']['answer']}
            traces[policy,k] = digest(row)
        write_status(out,{'status':'running','completed_mothers':len(board['original_views'])},POINTER)
    common.replay(board)
    # Retain exact inherited EC outputs when applying shared controls to the EV route.
    for policy in POLICIES:
        for key in keys:
            board['common_controls'][policy][key]['EC']=board['raw'][policy][key]['EC']
    seals = {mode:immutable_json(out/f'{mode}_predictions.json',board[mode]) for mode in ('raw','common_controls')}
    proof = immutable_json(out/'verified_native_reads.json',[[p,k,h] for (p,k),h in traces.items()])
    path=study['grading_paths']['OpenExempt']
    if 'dev' not in Path(path).parts or sha(ROOT/path)!=study['grading_file_sha256'][path]:
        raise ValueError('Use the original sealed development scorer')
    labels=read(ROOT/path)
    scores={}
    counts={}
    for mode in seals:
        answers=dict(zip(common.CHOICES,(board[mode][p] for p in POLICIES),strict=True))
        scores[mode]=common.score(board['original_views'],answers,labels)
        graded={p:{} for p in POLICIES}
        for p in POLICIES:
            for k in keys:
                graded[p][k]=grade_view('OpenExempt',board['original_views'][k]['EV'],labels[k]['EV'],
                                        board[mode][p][k]['EV'])['grade']
        counts[mode]={'improvements':sum(graded[POLICIES[1]][k]>graded[POLICIES[0]][k] for k in keys),
                      'regressions':sum(graded[POLICIES[1]][k]<graded[POLICIES[0]][k] for k in keys)}
    with ledger.transaction() as db:
        physical=dict(db.execute('select status,count(*) from calls where id like ? group by status',(ledger.run_id+':%',)))
    if physical.get('reserved'):
        raise ValueError('Reconcile only actually dispatched DEV calls before sealing')
    report=sealed({'status':'settled_revision6_group_selected_EV_DEV','binding_sha256':out.name,
                   'fixed_EC_shared':True,'DEV_mothers':len(keys),'scores':scores,'EV_source_changes':counts,
                   'EV_handled_counts':dict(completion),'prediction_sha256':seals,'verified_native_reads_sha256':proof,
                   'new_physical_calls':physical,'TEST_opened':False},'terminal_sha256')
    immutable_json(out/'terminal.json',report)
    write_status(out,{'status':report['status'],'terminal_sha256':report['terminal_sha256']},POINTER)
    print(out,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
