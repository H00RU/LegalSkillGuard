"""Check exact TRAIN candidate claims under two established statutory amount rules."""

from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from experiments import convergence_revision5_oe_wildcard_replay as wildcard
from experiments import convergence_revision6_candidate_fit as formal
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import convergence_oe_pa_monetary as pennsylvania
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision6_candidate_archive_coverage'
POINTER = HANDOFF / 'revision6_candidate_archive_coverage_current.json'
RULES = (wildcard.CITATION, pennsylvania.CITATION)
ROLES = ('incumbent','candidate')


def expected_amounts(view):
    bounds = wildcard.native_bounds(view)
    federal = {} if not bounds else {
        asset:Decimal(wildcard.direct_claim(value,bounds['limits'])) / 100
        for asset,value in bounds['assets'].items()
    }
    return {wildcard.CITATION:federal, pennsylvania.CITATION:{
        asset:Decimal(str(value)) for asset,value in pennsylvania.claims(view).items()
    }}


def amount_state(predictions, asset, citation, expected):
    if predictions is None:
        return 'unread'
    positive = [Decimal(str(row['claim_value'])) for row in predictions.get(asset,[])
                if row['citation'] == citation and row['claim_value'] > 0]
    if not positive:
        return 'missing'
    if len(set(positive)) != 1:
        return 'ambiguous_amounts'
    return 'exact' if positive[0] == expected else 'wrong_amount'


def verified_ev(db, source, view, result, program):
    row, = (obs for obs in result['reads'] if set(obs['native']) == {'EV'})
    if row['native']['EV'] != result['native']['EV'] or row['execution']['program_sha256'] != program:
        raise ValueError('Require the original program and matching native EV response')
    trace, = (r for r in row['execution']['traces'] if 'physical_call_id' in r)
    identity = trace['physical_call_id']
    physical_wire(db,{source['key']},identity,source['key'])
    raw = json.loads(db.execute('select result from calls where id=?',(identity,)).fetchone()[0])
    request = read(Path(raw['artifact_directory'])/'request.json')['payload']
    user, = (m['content'] for m in request['messages'] if m['role']=='user')
    literal = view['public']['original_input']
    if raw['content'] != trace['raw_content'] or not any(
            json.dumps(literal,ensure_ascii=f) in user for f in (False,True)):
        raise ValueError('The original EV request must bind that exact TRAIN asset and response')
    native = row['native']['EV']
    answer = native['answer'] if (native['handled'] and not native['fallback_executed']
                                 and raw['finish_reason']=='stop') else None
    return identity,answer


def audit_batch(db, batch):
    fit = ROOT/read(formal.pointer(batch))['artifact_root']
    binding, terminal, decisions = (read(fit/name) for name in (
        'binding.json','terminal.json','matched_decisions.json'))
    if (digest(binding) != fit.name or digest(decisions) != terminal['matched_decisions_sha256']
            or terminal['batch'] != batch or terminal['TEST_opened']):
        raise ValueError('Only reuse the settled fit from the original TRAIN batch')
    checkpoint = ROOT/binding['checkpoint_root']
    study = read(checkpoint/'binding.json')
    roster = formal.load_roster(study)
    journal = TrainingJournal(checkpoint,study,roster)
    proposal = read(fit/'candidates'/formal.ORDINARY/formal.OE/'measurements.json')
    teacher = decisions['teacher'][formal.ORDINARY][formal.OE]
    lead = digest(journal.library(formal.M2,batch-1)['programs'][formal.OE])
    patch = digest(proposal['candidate'])
    if (patch != decisions['relation'][formal.OE]['matched_proposal_sha256']
            or digest(proposal['predictions']) != teacher['predictions_sha256']):
        raise ValueError('Bind the exact archived B2–B8 native candidate')
    observation = journal._observations(formal.M2,batch)
    sources = [s for s in roster[batch-1] if s['dataset']==formal.OE and s['project_split']=='train']
    if {s['key'] for s in sources} != set(proposal['predictions']):
        raise ValueError('Keep all four TRAIN mothers and both actual response conditions')
    counts = {rule:Counter() for rule in RULES}
    physical = set()
    headers = Counter()
    for source in sources:
        key = source['key']
        view, = (v for v in source['views'] if v['id']=='EV')
        original = read(journal.directory(formal.M2,batch)/'predictions'/(digest(key)+'.json'))
        if digest(original) != observation['predictions'][key]:
            raise ValueError('The entering prediction no longer matches the archived receipt')
        base, update = (verified_ev(db,source,view,result,program) for result,program in (
            (original['result'],lead),(proposal['predictions'][key],patch)))
        physical.update((base[0],update[0]))
        headers['paired_decoded_mothers'] += base[1] is not None and update[1] is not None
        for rule, slots in expected_amounts(view).items():
            counts[rule]['source_bound_mothers'] += bool(slots)
            for asset, expected in slots.items():
                a,b = (amount_state(x[1],asset,rule,expected) for x in (base,update))
                counts[rule][f'{a}_to_{b}'] += 1
    return {'batch':batch,'TRAIN_mothers':len(sources),'original_fit_terminal_sha256':sha(fit/'terminal.json'),
            'original_M2_decision':decisions['relation'][formal.OE]['status'],
            'verified_EV_requests':len(physical),'response_coverage':dict(headers),
            'amount_states':{rule:dict(data) for rule,data in counts.items()}}, physical


def run():
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        verified = [audit_batch(db,batch) for batch in range(2,9)]
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    data = [row for row,_ in verified]
    binding = {'stage':'revision6_candidate_archive_coverage','partition':'TRAIN','TEST_opened':False,
               'fit_hashes':[row['original_fit_terminal_sha256'] for row in data],
               'source_sha256':{str(Path(p).relative_to(ROOT)):sha(Path(p)) for p in (
                   __file__, formal.__file__, wildcard.__file__, pennsylvania.__file__)}}
    out = HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    result = sealed({'status':'settled_revision6_candidate_archive_coverage','binding_sha256':out.name,
                     'by_batch':data,'verified_EV_requests':len(set.union(*(p for _,p in verified))),
                     'ledger':ledger,'new_executor_requests':0,'TEST_opened':False},'terminal_sha256')
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':result['status'],'terminal_sha256':result['terminal_sha256']},POINTER)
    print(out)


if __name__ == '__main__':
    run()
