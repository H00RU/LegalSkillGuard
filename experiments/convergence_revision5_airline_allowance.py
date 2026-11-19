"""Compare complimentary-bag assignment policies under the pinned public rules."""

import base64
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_airline_joint_relation import BAG, LOCAL_RULES
from experiments.convergence_formal_b1_observe import POINTER as B1_OBSERVATION
from experiments.convergence_formal_train_observe import load_roster, pointer
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_disposition_scope import ARM, TrainingJournal
from legal_skill_guard.paired_interfaces.airline_public_fees import DOMESTIC, section
from legal_skill_guard.paired_interfaces.native_adapters import public_geography
from legal_skill_guard.paired_interfaces.shared_semantics import SourceCase, Theory, allowed_relation, source_variant
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_Airline_allowance_20261119'
DATASET = 'RuleArena_Airline'
BENCHMARK = LOCAL_RULES/'compute_answer.py'
TRIP = re.compile(r'^(.+?) is an? (.+?) Class passenger flying from (.+?) to (.+?) with the following items:')
BAG_HEADINGS = ('### First Bag','### Second Bag','### Third Bag','### Fourth Bag +')
WEIGHT_HEADINGS = ('##### Over 50 lbs / 23 kgs to 53 lbs / 24 kgs',
                   '##### Over 53 lbs / 24 kgs to 70 lbs / 32 kgs',
                   '##### Over 70 lbs / 32kgs to 100 lbs / 45 kgs')
SIZE_COLUMNS = ('Over 62 in / 158 cm – 65 in / 165 cm','Over 65 in / 165 cm – 115 in / 292 cm')
PACIFIC_BASE = 'To or from India, China, Japan, South Korea, Hong Kong, Australia and New Zealand'
EAST_WEIGHT = 'To or from India, China, Japan, South Korea and Hong Kong'
PACIFIC_SIZE = 'China, Japan, South Korea, Hong Kong, India, Australia, and New Zealand'
ATLANTIC = 'Between Europe, Israel, Qatar and U.S., Puerto Rico, U.S. Virgin Islands'
LATIN_THIRD = 'Between Mexico, Caribbean, Central America, South America and U.S.'
LATIN_FOURTH = 'Between Mexico, Caribbean or Central America, South America and U.S.'
LATIN_WEIGHT = 'Between Mexico, Caribbean or Central America, South America and U.S.'
LATIN_HEAVY = 'Between Mexico, Caribbean, Central America, South America and U.S.'
ROUTE_SELECTORS = {
    'U.S.':(('Within and between U.S., Puerto Rico',DOMESTIC,DOMESTIC,DOMESTIC),
             (DOMESTIC,DOMESTIC),'Between U.S., Puerto Rico, U.S. Virgin Islands and Canada'),
    'Mexico':(('Between Mexico, Caribbean (excluding Cuba/Haiti),',
               'Between Mexico, Caribbean (excluding Cuba/Haiti) or',LATIN_THIRD,LATIN_FOURTH),
              (LATIN_WEIGHT,LATIN_HEAVY),'Mexico / Caribbean / Central America (except Panama) / Guyana / Suriname'),
    'Peru':(('Between Panama, Colombia, Ecuador, Peru','Between South America (excluding Guyana, Suriname)',
              LATIN_THIRD,LATIN_FOURTH),(LATIN_WEIGHT,LATIN_HEAVY),'Panama / South America (except Guyana / Suriname)'),
    'South America':(('Between South America (excluding Colombia','Between South America (excluding Guyana, Suriname)',
                       LATIN_THIRD,LATIN_FOURTH),(LATIN_WEIGHT,LATIN_HEAVY),'Panama / South America (except Guyana / Suriname)'),
    **{place:((PACIFIC_BASE,)*4,(EAST_WEIGHT,EAST_WEIGHT),PACIFIC_SIZE) for place in
       ('India','China','Japan','South Korea','Hong Kong')},
    **{place:((PACIFIC_BASE,)*4,('To or from Australia and New Zealand',)*2,PACIFIC_SIZE)
       for place in ('Australia','New Zealand')},
    **{place:((first,ATLANTIC,ATLANTIC,ATLANTIC),(ATLANTIC,ATLANTIC),'Europe, Israel, Qatar')
       for place,first in (('Europe','Between Europe and U.S.'),('Israel','Between Israel and U.S.'),
                           ('Qatar','Between Qatar and U.S.'))},
}


def row(lines, prefix):
    header = None
    found = []
    for line in lines:
        if not line.startswith('|'):
            continue
        values = [v.strip().rstrip('^') for v in line.strip().strip('|').split('|')]
        if values[0] in ('Region','Regions'):
            header = values[1:]
        elif values[0].startswith(prefix):
            if header is None or len(values[1:])!=len(header):
                raise ValueError('Unbound public table row')
            found.append(dict(zip(header,values[1:],strict=True)))
    if len(found)!=1:
        raise ValueError('No unique public fare-table route')
    return found[0]


def usd(value):
    if value=='Not accepted':
        return None
    if not re.fullmatch(r'\$[0-9]+',value):
        raise ValueError('No exact public fee for this fare')
    return int(value[1:])


def policy(public, geo):
    fact, source = public['facts'], public['source_text']
    match = TRIP.match(fact)
    if match is None:
        raise ValueError('No explicit itinerary')
    traveler,cabin,start,end = match.groups()
    if cabin not in ('Main Cabin','Main Plus','Basic Economy','Premium Economy','Business','First'):
        raise ValueError('Cabin outside the scoped published table')
    places = [geo.get(start),geo.get(end)]
    if 'U.S.' not in places:
        raise ValueError('Outside the U.S. leg scope')
    routine = next((region for region in places if region!='U.S.'),'U.S.')
    if routine not in ROUTE_SELECTORS:
        raise ValueError('Route outside the declared table selectors')
    base_rows, heavy_rows, size_row = ROUTE_SELECTORS[routine]
    column = 'Main Cabin' if cabin=='Main Plus' else cabin
    base = [usd(row(section(source,h),selector)[column])
            for h,selector in zip(BAG_HEADINGS,base_rows,strict=True)]
    if any(fee is None for fee in base):
        raise ValueError('Unsupported base fare')
    if cabin=='Main Plus':
        sentence = '^Main Plus includes 1 extra free checked bag in addition to the Main Cabin allowance (max of 2).'
        if any(sentence not in section(source,h) for h in BAG_HEADINGS[:2]):
            raise ValueError('Main Plus allowance changed')
        free = min(2,next((i for i,fee in enumerate(base) if fee),len(base))+1)
        base[:free] = [0]*free
    if base[-1]<=0 or list(sorted(base))!=base:
        raise ValueError('Only prefix complimentary slots are supported')
    raw_weight = [usd(row(section(source,h),selector)[column])
                  for h,selector in zip(WEIGHT_HEADINGS,('All Regions',*heavy_rows),strict=True)]
    oversize = row(section(source,'#### Oversize Bags'),size_row)
    size = [usd(oversize[v]) for v in SIZE_COLUMNS]
    quoted, = re.findall(r'cannot exceed (\d+) x (\d+) x (\d+) inches',source)
    if 'The higher fee between oversize and overweight applies, in addition to the checked bag fee.' not in source:
        raise ValueError('No published same-bag fee combiner')
    special = cabin in ('Business','First') or routine in ('Australia','New Zealand')
    if special and '70 lbs / 32 kgs for complimentary bags and 50 lbs / 23 kgs for excess charged bags' not in source:
        raise ValueError('No published complimentary weight rule')
    ticket, = re.findall(rf'^{re.escape(traveler)}\x27s flight ticket is \$(\d+)\.$',fact,re.M)
    return {'base':base,'standard_weight':[[50,0],[53,raw_weight[0]],[70,raw_weight[1]],[100,raw_weight[2]]],
            'size':[[62,0],[65,size[0]],[115,size[1]]],'carry':sorted(map(int,quoted)),
            'complimentary_cutoff':70 if special else 50,'ticket':int(ticket),
            'route':routine,'cabin':cabin,'policy_sha256':digest(source)}


def inventory(facts, rule):
    rows = list(BAG.finditer(facts))
    if len(rows)!=facts.count(' lbs;') or [int(r[1]) for r in rows]!=list(range(1,len(rows)+1)):
        raise ValueError('The original public inventory is incomplete')
    dims = [sorted(map(int,r.groups()[1:4])) for r in rows]
    carries = [i for i,d in enumerate(dims) if all(a<=b for a,b in zip(d,rule['carry'],strict=True))]
    if len(rows)<2 or carries!=[0]:
        raise ValueError('The benchmark carry-on anchor is outside the supported public scope')
    return rows,[(sum(d),int(r[5])) for d,r in zip(dims[1:],rows[1:],strict=True)]


def band(value, schedule):
    fee = next((fee for bound,fee in schedule if value<=bound),None)
    if fee is None:
        raise ValueError('At least one item is not accepted by the scoped published table')
    return fee


def totals(bags, rule):
    base = [rule['base'][min(i,3)] for i in range(len(bags))]
    slots = base.count(0)
    paid, savings, overweight_savings = [], [], []
    for size,weight in bags:
        oversize = band(size,rule['size'])
        standard = band(weight,rule['standard_weight'])
        discount = standard if weight>rule['complimentary_cutoff'] else 0
        paid.append(max(oversize,standard))
        savings.append(paid[-1]-max(oversize,discount))
        overweight_savings.append(standard-discount)
    initial=rule['ticket']+sum(base)+sum(paid)
    sets = combinations(range(len(savings)),slots)
    exhaustive = min(initial-sum(savings[i] for i in ids) for ids in sets)
    joint = initial-sum(sorted(savings,reverse=True)[:slots])
    if joint!=exhaustive:
        raise ValueError('Local gains must reproduce exhaustive assignment')
    over_sort=sorted(range(len(savings)),key=lambda i:(-overweight_savings[i],i))
    return {'joint_assignment':joint,'exact_enumeration':exhaustive,
            'source_order':initial-sum(savings[:slots]),
            'overweight_only_order':initial-sum(savings[i] for i in over_sort[:slots]),
            'positive_savings':sum(v>0 for v in savings),'slots':slots}


def edit_witness(source, rule, original):
    public = source['views'][0]['public']
    rows,bags = inventory(public['facts'],rule)
    start,end=rows[1].start(),rows[-1].end()
    lines = [r[0].partition('. ')[2] for r in rows[1:]]

    def render(order):
        return '\n'.join(f'{i+2}. {lines[old]}' for i,old in enumerate(order))

    def reference(values, _):
        return totals([bags[i] for i in values['order']],rule)['joint_assignment']

    key=source['key']
    law=rule['policy_sha256']
    theory=Theory({law:[{}]},{key:[{}]},reference,sha(Path(__file__)),
                  provenance=({'kind':'explicit_source','evidence_sha256':digest(public)},
                              {'kind':'official_task_assumption','evidence_sha256':sha(BENCHMARK)}),
                  allowed_edits=frozenset({'order'}))
    order=list(range(len(bags)))
    case=SourceCase(key,key,law,public,{'order':order},spans={'order':('facts',start,end)})
    for i,j in combinations(order,2):
        permutation=order.copy()
        permutation[i],permutation[j]=permutation[j],permutation[i]
        target=totals([bags[k] for k in permutation],rule)
        if target['source_order']==original['source_order']:
            continue
        edited=source_variant(case,theory,{'order':permutation},{'order':render})
        if edited['status']!='REALIZABLE':
            raise ValueError('The checked-item order edit must bind the exact facts')
        parsed=inventory(edited['case'].public['facts'],rule)[1]
        assert parsed==[bags[k] for k in permutation]
        pair=allowed_relation(theory,[case,edited['case']])['signatures']
        assert list(pair.values())==[[original['joint_assignment']]*2]
        return {'source_edit_sha256':digest(edited['receipt']),
                'same_minimum_fee_after_order_edit':True,
                'source_order_fee_delta':target['source_order']-original['source_order'],
                'actual_executor_responses_to_edited_variant':0}
    return None


def paid_answer(db, source, result, ids, expected_purpose='skill_actor'):
    key=source['key']
    if 'measured' in result:
        measured=result['measured']
        identity=measured['physical_call_id']
        content_match=lambda actual: actual['usage']==measured['usage']
    else:
        entry, = result['reads']
        trace, = entry['execution']['traces']
        identity=trace['physical_call_id']
        content_match=lambda actual: actual['content']==trace['raw_content']
    status,role,parent,purpose,fingerprint,payload=db.execute(
        'select status,role,source,purpose,request_hash,result from calls where id=?',(identity,)).fetchone()
    assert (status,role,parent,purpose)==('completed','executor',key,expected_purpose)
    actual=json.loads(payload)
    path=Path(actual['artifact_directory'])
    original, wire=(read(path/p) for p in ('request.json','wire_request.json'))
    raw=base64.b64decode(wire['body_b64'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==wire['body_sha256'] and json.loads(raw)==original['payload']
    assert original['request_hash']==actual['request_hash']==fingerprint and original['id']==identity
    assert read(path/'result.json')==actual and actual['thinking_requested'] is False and content_match(actual)
    assert original['payload']['model']=='Qwen/Qwen3-8B'
    ids.add(identity)
    return result['native']['native']['answer']


def run():
    observation=ROOT/read(pointer(8))['artifact_root']
    runtime=read(observation/'binding.json')
    cp=ROOT/runtime['checkpoint_root']
    study=read(cp/'binding.json')
    roster=load_roster(study)
    journal=TrainingJournal(cp,study,roster)
    geo=public_geography()
    grade=runtime['native_grade_paths'][DATASET]
    assert 'train' in Path(grade).parts
    binding={'study':'Airline_rule_bound_complimentary_assignment','TRAIN_roster_sha256':digest(roster),
             'route_selectors_sha256':digest(ROUTE_SELECTORS),'runner_sha256':sha(Path(__file__)),
             'benchmark_assignment_reference_sha256':sha(BENCHMARK),
             'native_TRAIN_grading_sha256':runtime['native_grade_sha256'][grade],
             'original_DEV_or_TEST_paths_used':False}
    out=HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    results,ids,sources = [],set(),{}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        ledger=dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for n,cells in enumerate(roster,1):
            stage=ROOT/read(B1_OBSERVATION if n==1 else pointer(n))['artifact_root']
            observation_end=read(stage/'terminal.json')
            assert not observation_end['TEST_opened']
            observation_binding=read(stage/'binding.json')
            assert stage.name==digest(observation_binding)
            assert all(sha(stage/'source_snapshot'/p)==h for p,h in observation_binding['source_sha256'].items())
            seal=journal._observations(ARM,n)
            assert seal['train_observation_sha256']==observation_end['observation_receipts'][ARM]
            for source in (x for x in cells if x['dataset']==DATASET):
                key=source['key']
                assert source['project_split']=='train'
                sources[key]=source
                archive=read(journal.directory(ARM,n)/'predictions'/(digest(key)+'.json'))
                assert digest(archive)==seal['predictions'][key]
                before=paid_answer(db,source,archive['result'],ids)
                result={'source':key,'batch':n,'original':before}
                public=source['views'][0]['public']
                try:
                    rule=policy(public,geo)
                    _,bags=inventory(public['facts'],rule)
                    result.update(totals(bags,rule))
                    result['route']=rule['route']
                    result['cabin']=rule['cabin']
                    result['permutation_witness']=edit_witness(source,rule,result)
                except ValueError as error:
                    result['unresolved']=str(error)
                results.append(result)
    assert len(results)==len(ids)==24
    immutable_json(out/'predictions.json',results)
    assert sha(ROOT/grade)==binding['native_TRAIN_grading_sha256']
    labels=read(ROOT/grade)
    modes=('original','joint_assignment','source_order','overweight_only_order','exact_enumeration')
    score={}
    for row_ in results:
        key=row_['source']
        source=sources[key]
        score[key]={m:grade_view(DATASET,source['views'][0],labels[key]['native'],row_.get(m))['grade'] for m in modes}
    supported=[r for r in results if 'unresolved' not in r]
    summary={'TRAIN_mothers':len(results),'physical_original_responses_verified':len(ids),
             'source_only_supported_mothers':len(supported),
             'source_only_unresolved_reasons':dict(Counter(r['unresolved'] for r in results if 'unresolved' in r)),
             'source_only_supported_routes':dict(Counter(r['route'] for r in supported)),
             'correct_supported':{m:sum(score[r['source']][m] for r in supported) for m in modes},
             'original_correct_all_TRAIN':sum(r['original'] for r in score.values()),
             'joint_and_source_order_different':sum(r['joint_assignment']!=r['source_order'] for r in supported),
             'joint_and_overweight_sort_different':sum(r['joint_assignment']!=r['overweight_only_order'] for r in supported),
             'source_order_edit_witnesses':sum(r['permutation_witness'] is not None for r in supported),
             'source_order_edit_fee_deltas':[r['permutation_witness']['source_order_fee_delta']
                                            for r in supported if r['permutation_witness'] is not None],
             'new_model_requests':0,'ledger':ledger,'runner_sha256':binding['runner_sha256']}
    immutable_json(out/'scores.json',score)
    immutable_json(out/'summary.json',summary)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**summary},sort_keys=True))


if __name__=='__main__':
    run()
