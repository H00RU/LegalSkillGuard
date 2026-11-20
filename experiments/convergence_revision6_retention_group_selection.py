"""Replay budget-matched candidate-driven group selection on the actual B5 CNI fit."""

from pathlib import Path
import sqlite3

from experiments import convergence_revision5_m2_cni_disposition_retention as retention
from experiments.convergence_formal_train_fit import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE/'revision6_retention_group_selection'
POINTER = HANDOFF/'revision6_retention_group_selection_current.json'
SIGNED = {retention.ENTAIL, retention.DENY}


def rank(before, after):
    changes = [(a,b) for a,b in zip(before,after,strict=True) if a != b]
    return (sum(a in SIGNED and b in SIGNED for a,b in changes),
            sum(a is not None and b is not None for a,b in changes))


def choose(pool):
    if not pool:
        raise ValueError('Both policies need the same audited TRAIN group pool')
    latest = max(pool,key=lambda row:row['position'])
    active = max(pool,key=lambda row:(rank(row['before'],row['after']),row['position']))
    return {'chronological':latest,'candidate_driven':active}


def select(row):
    facts = row['facts']
    before, after = row['before'],row['after']
    direct = [all(x is None or x == y for x,y in zip(current,facts,strict=True))
              for current in (before,after)]
    shared = [retention.supports(row['shared'],current) for current in (before,after)]
    independent = [retention.supports(row['independent'],current) for current in (before,after)]
    if direct != shared or independent != shared:
        raise ValueError('Both screening controls must receive the same selected source assertions')
    return {
        'selected_position':row['position'],'physical_comparison_count':len(set(row['request_ids'])),
        'observed_polarity_changes':list(rank(before,after)),
        'compatible_entering':shared[0], 'compatible_proposal':shared[1],
        'decision':'proposal' if shared[1] and all(x is not None for x in after) else 'incumbent',
        'same_information_direct_matches':True,
    }


def run():
    batch, arm = 5, retention.EXTERNAL_ARM
    checkpoint = ROOT/read(retention.BOOTSTRAP)['artifact_root']
    study = read(checkpoint/'binding.json')
    roster = retention.load_roster(study)
    journal = TrainingJournal(checkpoint,study,roster)
    fit = ROOT/read(pointer(batch))['artifact_root']
    spec, terminal, decisions = (read(fit/n) for n in ('binding.json','terminal.json','matched_decisions.json'))
    if fit.name != digest(spec) or terminal['TEST_opened'] or digest(decisions) != terminal['matched_decisions_sha256']:
        raise ValueError('Require the original sealed B5 training fit')
    if any(sha(fit/'source_snapshot'/n) != h for n,h in spec['source_sha256'].items()):
        raise ValueError('The original B5 fitting sources must be preserved')
    directory = fit/'candidates'/arm/retention.DATASET
    candidate, earlier = (read(directory/n) for n in ('measurements.json','prior_TRAIN_regression.json'))
    decision = decisions['teacher'][arm][retention.DATASET]
    if (digest(candidate['predictions']) != decision['predictions_sha256']
            or digest(earlier) != decision['earlier_TRAIN_regression']['evidence_sha256']
            or decision['selected'] != 'candidate' or decision['native_utility_delta'] <= 0
            or decision['earlier_TRAIN_regression']['native_utility_delta'] <= 0):
        raise ValueError('Keep the exact native-positive teacher proposal and prior-source reads')
    entering = journal.library(arm,batch-1)
    adopted = journal.library(arm,batch)
    original_reader = entering.get('schema_proposals',{}).get(retention.DATASET)
    native_consumer = entering['programs'][retention.DATASET]
    candidate_reader = candidate['candidate']
    if (candidate_reader != adopted['schema_proposals'][retention.DATASET]
            or native_consumer != adopted['programs'][retention.DATASET]):
        raise ValueError('Require the original teacher proposal and actual B5 adopted version')
    observation = journal._observations(arm,batch)
    pool = []
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for key,(position,view,audit) in retention.source_material(roster).items():
            if position[0] > batch:
                continue
            if position[0] == batch:
                saved = read(journal.directory(arm,batch)/'predictions'/(digest(key)+'.json'))
                if digest(saved) != observation['predictions'][key]:
                    raise ValueError('Use the original entering B5 response')
                a,b = saved['result'],candidate['predictions'][key]
            else:
                a,b = earlier['before'][key],earlier['candidate'][key]
            trace, = b['schema_reads']
            if trace['proposal_sha256'] != digest(candidate_reader):
                raise ValueError('The candidate response must execute the adopted schema proposal')
            calls = [retention.verify_prediction(db,key,result) for result in (a,b)]
            if len(set(calls)) != 2:
                raise ValueError('Use two measured responses per candidate group')
            before,after = ([x['native'][t]['answer'] for t in retention.TASKS] for x in (a,b))
            facts,shared,independent = retention.local_pair(key,(position,audit),view)
            pool.append({'position':position,'before':before,'after':after,'facts':list(facts.values()),
                         'shared':shared,'independent':independent,'request_ids':calls})
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    layout = {'stage':'revision6_retention_group_selection','TRAIN_only':True,'TEST_opened':False,
              'original_fit_terminal_sha256':sha(fit/'terminal.json'),'native_comparison_sha256':digest(decision),
              'group_pool_sha256':digest(pool),'original_fit_readers':{
                  'incumbent':digest(original_reader),'proposal':digest(candidate_reader)},
              'consumer_sha256':digest(native_consumer),
              'source_sha256':{str(Path(p).relative_to(ROOT)):sha(Path(p)) for p in (__file__,retention.__file__)}}
    out = HOME/digest(layout)
    immutable_json(out/'binding.json',layout)
    choices = {policy:select(row) for policy,row in choose(pool).items()}
    libraries = {}
    for policy,record in choices.items():
        reader = original_reader if record['decision']=='incumbent' else candidate_reader
        fitted = sealed({'batch':batch,'binding_sha256':out.name,'decision':record,
                         'schema_proposal':reader,'program':native_consumer},'snapshot_sha256')
        immutable_json(out/'TRAIN_batch_libraries'/f'{policy}.json',fitted)
        libraries[policy] = fitted['snapshot_sha256']
    result = sealed({
        'status':'settled_revision6_retention_group_selection','binding_sha256':out.name,
        'scope':'B5 original PARSE-style ContractNLI candidate and original reviewed disposition/retention groups',
        'source_group_pool':len(pool),'verified_archived_reads':len({i for row in pool for i in row['request_ids']}),
        'evaluation_budget_per_policy':2,'same_pool_used_to_rank_both_policies':True,
        'library_sha256':libraries,'choices':choices,'native_TRAIN_proposal_delta':decision['native_utility_delta'],
        'new_executor_requests':0,'forward_native_effect_measured':False,'TEST_opened':False,'ledger':ledger,
    },'terminal_sha256')
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':result['status'],'terminal_sha256':result['terminal_sha256']},POINTER)
    print(out)


if __name__ == '__main__':
    run()
