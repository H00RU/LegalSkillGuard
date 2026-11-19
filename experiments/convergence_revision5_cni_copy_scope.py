"""Compare anchored creation-permission interfaces on original ContractNLI TRAIN."""

import argparse
import inspect
from itertools import product
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

import jsonschema

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_linked_evidence import span_inventory
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_scoped_update import verify_public_wire
from experiments.convergence_revision5_m2_cni_disposition_retention import verify_prediction
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


DATASET, TASK = 'ContractNLI', 'nda-17'
HOME = BASE / 'revision5_CNI_copy_scope_20261119'
POINTER = HANDOFF / 'revision5_CNI_copy_scope_current.json'
DONE = 'settled_CNI_copy_creation_permission_TRAIN'
ENTAIL, CONTRADICT, ABSENT = 'Entailment', 'Contradiction', 'NotMentioned'
ROLES = ('fixed', 'synthesized')
PAIRS = ((1, 2), (2, 1), (3, 2), (4, 1), (6, 1), (8, 2))
APPLIES = 'addresses_creation_under_confidentiality_rule'
GRANT = 'operative_permission_under_contract_terms'
BAR = 'ordinary_creation_restricted'
MEANINGS = {
    APPLIES: 'the group regulates the Receiving Party making new copies or recordings of the other party\'s Confidential Information '
             'as such. Disregard keeping, returning or destroying existing copies, copying signatures or notices, '
             'and conditions merely restricting removal of particular physical materials unless they govern copying Confidential Information generally',
    GRANT: 'the same rule itself permits creation in an identified situation, such as what is necessary for the permitted purpose. '
           'Future approval only or an undertaking to consider consent supplies no present copying permission',
    BAR: 'the same rule bars ordinary creation, either outright or unless further discretionary approval is secured',
}
COMMON_PROMPT = (
    'Read the entire NDA and the indexed candidate groups. A group shows a source clause and any nearby lead-in. '
    'Use the lead-in only when the source makes it govern that clause. Report each group independently and preserve its ID. '
    'Check whether the operative object and action are making new copies of the other party\'s Confidential Information. '
    'Distinguish a purpose-based right from something that needs further approval. '
    'Do not infer a copying permission from a statement about handling existing copies. '
    'Use null when available text cannot resolve a field. Return the specified structure only.'
)
COPY = re.compile(r'\b(?:cop(?:y|ies|ied|ying)|reproduc\w*|duplicat\w*|photograph\w*|videotap\w*|transcrib\w*)\b', re.I)
CREATE = re.compile(r'\b(?:mak(?:e|es|ing) (?:any |such |new |or retain )?(?:a )?cop(?:y|ies)|'
                    r'(?:copy|reproduce) (?=any |documents|confidential |the |it\b)|copy(?=\s*,| reproduce\b)|shall not be (?:copied|reproduced)|'
                    r'no reproductions may be made|photograph|videotape|copies .{0,90} are to be made)\b', re.I)
PURPOSE = re.compile(r'(?:except (?:as |for |to )|other than |may only ).{0,125}'
                     r'(?:required|necessary|needed|to further|for use by).{0,110}(?:purpose|intent|project|this agreement)', re.I)
RESTRICTION = re.compile(r'\b(?:not|no|nor|neither|only)\b', re.I)
CONSENT = re.compile(r'\b(?:prior|express(?:ly)?|written)\b.{0,80}\b(?:consent|approval|authori[zs]\w*)\b|'
                     r'\bwithout\b.{0,75}\b(?:consent|approval)\b', re.I)
SCOPE = re.compile(r'\b(?:confidential information|information disclosed|details of products|information in any manner)\b', re.I)
HANDLING = re.compile(r'\b(?:return\w*|destroy\w*|retain\w*|signatures?|legends?|counterparts?|label\w*|'
                      r'hard copy|enclosed copy|security measures|reverse.engineer\w*|'
                      r'copies? of this agreement|fax|copies? thereof|define\w*|shall mean|information includes all copies)\b', re.I)
EXCEPTION = re.compile(r'\b(?:except|other than|unless|without|only)\b', re.I)
REMOVAL = re.compile(r'\b(?:removed (?:materials|items)|approved removal)\b', re.I)
FUTURE_CONSENT = re.compile(r'\b(?:will|may) consider\b.{0,95}\bconsent\b', re.I)
HEADING = re.compile(r'^\s*(?:[\d().]+\s*)?(?:proprietary information,?\s+|returning\s+)?'
                     r'(?:reproductions?|copies|duplicate)[.:]?$', re.I)
MIXED_RECIPIENT_SCOPE = re.compile(r'\b(?:copy|copied)\b.{0,170}\b(?:disclose|disclosed|communicate|communicated)\b'
                                   r'.{0,100}\b(?:to anyone|to any other person)\b', re.I)
DEFINITION = re.compile(r'\bConfidential Information["”]?\s+(?:shall\s+)?means?\b',re.I)


def local_consumer(v, _):
    return {
        'direct_permission': v["addresses_creation_under_confidentiality_rule"] == True and v["operative_permission_under_contract_terms"] == True,
        'creation_bar': v["addresses_creation_under_confidentiality_rule"] == True and v["ordinary_creation_restricted"] == True,
    }


def local_possible(v, context):
    slots = list(MEANINGS)
    completions = product(*((True, False) if v[field] is None else (v[field],) for field in slots))
    readings = [local_consumer(dict(zip(slots, row, strict=True)), context) for row in completions]
    return {key: readings[0][key] if all(r[key] == readings[0][key] for r in readings) else None for key in readings[0]}


def layouts():
    source = inspect.getsource(local_consumer)
    scope = {'source_fields': ['source_text'], 'local_unit': 'one creation or handling clause', 'field_meanings': MEANINGS}
    domains = {name: [False, True, None] for name in MEANINGS}
    module = residual.FiniteModule.build('ContractNLI_copy_creation_scope', domains, [{}], local_possible,
                                         consumer_sha256=digest([source, inspect.getsource(local_possible)]),
                                         program_source=source, source_scope=scope)
    joint = [r for r in residual.consumer_relations(module) if r['expression']['op']=='and']
    for item in joint:
        item['name'] = 'direct_permission' if GRANT in item['consumer_dependencies'] else 'creation_bar'
    assert {r['name'] for r in joint} == {'direct_permission', 'creation_bar'} and len(joint) == 2
    assets = {
        'fixed': residual.compile_pair(module, [{'name': f, 'field': f, 'operation': 'field'} for f in domains],
                                       operation='fixed_coordinates', layout='anchored'),
        'synthesized': residual.compile_pair(module, sorted(joint,key=lambda r:r['name']),
                                             operation='consumer_relational_projection', layout='anchored'),
    }
    for asset in assets.values():
        for state in module.states:
            derived = residual.decode(asset,residual.encode(asset['features'], state),{},module_binding=module.binding)
            assert derived['valid'] and derived['outputs'] == local_possible(state,{})
    return module,assets


def source_groups(view):
    spans = [' '.join(x.split()) for x in span_inventory(view)]
    groups = []
    for i, clause in enumerate(spans):
        if not COPY.search(clause):
            continue
        lead = i
        if i and re.search(r'\bneither (?:it|they) nor (?:its|their)$',spans[i-1],re.I):
            lead = i-1
        elif re.match(r'^\(?[a-z0-9]+[.)]', clause, re.I):
            headers = [j for j in range(max(0,i-5),i) if spans[j].endswith((':',';'))
                       and (re.search(r'\b(?:assures|affirms|undertakes|promises|agrees|shall)\b',spans[j],re.I)
                            or SCOPE.search(spans[j]))]
            if headers:
                lead = headers[-1]
        suffix = i
        if i+1<len(spans) and re.search(r'^.{0,32}\b(?:will consider|may consider)\b', spans[i+1], re.I) and COPY.search(spans[i+1]):
            suffix = i+1
        ids = sorted({lead,i,suffix})
        groups.append({'clause_id':i,'span_ids':ids,'source_spans':[spans[j] for j in ids],
                       'operative_text':clause})
    return groups


def collect(ports, groups):
    permitted, prohibited = [], []
    uncertain = False
    for row, group in zip(ports, groups, strict=True):
        if row['direct_permission'] is True:
            permitted.append(group['span_ids'])
        elif row['creation_bar'] is True and row['direct_permission'] is False:
            prohibited.append(group['span_ids'])
        elif None in row.values():
            uncertain = True
    if permitted:
        return {'answer':ENTAIL,'evidence_sentence_ids':sorted({i for ids in permitted for i in ids})}
    if uncertain:
        return {'answer':None,'evidence_sentence_ids':[]}
    if prohibited:
        return {'answer':CONTRADICT,'evidence_sentence_ids':sorted({i for ids in prohibited for i in ids})}
    return {'answer':ABSENT,'evidence_sentence_ids':[]}


def literal(group):
    clause = group['operative_text']
    full = ' '.join(group['source_spans'])
    if HEADING.search(clause) or DEFINITION.search(clause) or REMOVAL.search(clause) or FUTURE_CONSENT.search(clause) or (
            not CREATE.search(clause) and HANDLING.search(clause)):
        return {'direct_permission':False,'creation_bar':False}
    if CREATE.search(clause) and SCOPE.search(full):
        if MIXED_RECIPIENT_SCOPE.search(clause) and EXCEPTION.search(clause):
            return {'direct_permission':None,'creation_bar':None}
        if PURPOSE.search(clause) and not ('may only' in clause.lower() and CONSENT.search(clause)):
            return {'direct_permission':True,'creation_bar':False}
        if RESTRICTION.search(clause) and not (EXCEPTION.search(clause) and not CONSENT.search(clause)):
            return {'direct_permission':False,'creation_bar':True}
    return {'direct_permission':None,'creation_bar':None}


def matched_direct(groups):
    return collect([literal(g) for g in groups],groups)


def estimate(views, predictions, annotations):
    modes = next(iter(predictions.values()))
    scores = {role:{metric:[] for metric in ('grade','evidence_f1','grounded')} for role in modes}
    unhandled = dict.fromkeys(modes,0)
    for key, alternatives in predictions.items():
        for role, value in alternatives.items():
            grade = grade_view(DATASET,views[key],annotations[key][TASK],value['answer'],value['evidence_sentence_ids'])
            unhandled[role] += value['answer'] is None
            for metric, number in {**grade,'grounded':grade['grade']*grade['evidence_f1']}.items():
                if metric in scores[role]:
                    scores[role][metric].append({'source':key,'view':TASK,'grade':number})
    summary={role:{'native_correct':int(sum(r['grade'] for r in m['grade'])),'sources':len(m['grade']),
                   'unhandled':unhandled[role],
                   **{metric:mean(r['grade'] for r in m[metric]) for metric in ('evidence_f1','grounded')}}
             for role,m in scores.items()}
    paired={}
    if 'synthesized' in modes:
        for other in ('fixed','direct'):
            paired[other]={m:paired_source_effect(scores[other][m],scores['synthesized'][m]) for m in scores[other]}
    return {'metrics':summary,'synthesized_vs':paired}


def wire(asset, view, groups):
    signals = record_schema({f['name']:{'enum':asset['domains'][f['name']]} for f in asset['features']})
    schema = record_schema({'clauses':record_schema({str(g['clause_id']):signals for g in groups})})
    payload = {'complete_document':view['public']['source_text'], 'candidate_groups':{
        str(g['clause_id']):dict(zip(map(str,g['span_ids']), g['source_spans'],strict=True)) for g in groups}}
    prompt = '\n'.join(residual.reader_prompt(asset,verbalize_relations=True).splitlines()[4:])
    return [{'role':'system','content':COMMON_PROMPT+'\n'+prompt},
            {'role':'user','content':json.dumps(payload,ensure_ascii=False)}], schema


def decode(module,asset,groups,schema,raw):
    try:
        if raw['finish_reason']!='stop':
            raise ValueError('Incomplete response')
        reported = json.loads(raw['content'])
        jsonschema.validate(reported,schema)
        ports = [residual.decode(asset,reported['clauses'][str(group['clause_id'])],{},module_binding=module.binding)
                 for group in groups]
        if any(not port['valid'] for port in ports):
            raise ValueError('The local signature is outside the proof domain')
        observed = [port['outputs'] for port in ports]
        return {**collect(observed,groups),'relations':observed,'valid':True}
    except (ValueError,jsonschema.ValidationError):
        return {'answer':None,'evidence_sentence_ids':[],'relations':[],'valid':False}


def materials():
    root = ROOT/read(BOOTSTRAP)['artifact_root']
    study = read(root/'binding.json')
    assert root.name==digest(study)
    roster = load_roster(study)
    journal = TrainingJournal(root,study,roster)
    arms = (ORDINARY,EXTERNAL_ARM)
    bank, cases, physical, archived = {arm:{} for arm in arms}, {},set(),{}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        for batch,rows in enumerate(roster,1):
            stage,observation_binding,terminal = bound_stage(FIRST if batch==1 else observe_pointer(batch))
            archived[str(batch)] = sha(stage/'terminal.json')
            receipts = {arm:journal._observations(arm,batch) for arm in arms}
            assert all(terminal['observation_receipts'][a]==r['train_observation_sha256'] for a,r in receipts.items())
            for position, source in enumerate(r for r in rows if r['dataset']==DATASET):
                assert source['project_split']=='train'
                view, = (v for v in source['views'] if v['id']==TASK)
                key = source['key']
                groups = source_groups(view)
                cases[key] = {'position':[batch,position],'view':view,'groups':groups}
                decision = matched_direct(groups)
                for arm in arms:
                    saved = read(journal.directory(arm,batch)/'predictions'/(digest(key)+'.json'))
                    assert digest(saved)==receipts[arm]['predictions'][key]
                    result = saved['result']
                    pid = verify_prediction(db,key,result)
                    if pid not in physical:
                        verify_public_wire(db,source,pid)
                        physical.add(pid)
                    native = result['native'][TASK]
                    bank[arm][key] = {'original':native,'matched_direct':decision if decision['answer'] is not None else native}
    grade = observation_binding['native_grade_paths'][DATASET]
    assert 'train' in Path(grade).parts
    return cases,bank,physical,archived,grade,observation_binding['native_grade_sha256'][grade],study['executor']


def execute(stage,binding,cases,keys,module,assets,bank):
    run_id = 'convergence-revision5-cni-copy-scope-'+stage.name[:16]
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':keys,'dev':[],'test':[]},binding=binding)
    executor = FrozenExecutor(ledger,stage,binding['executor'])
    executor.readiness()
    for path,h in binding['source_sha256'].items():
        saved = stage/'source_snapshot'/path
        saved.parent.mkdir(parents=True,exist_ok=True)
        if not saved.exists():
            with saved.open('xb') as stream:
                stream.write((ROOT/path).read_bytes())
        assert sha(saved)==h
    write_status(stage, {'status':'running','completed_pairs':0},POINTER)
    records, phys, params = {}, set(), None
    tokens = 0
    for key in keys:
        case = cases[key]
        pair = {'direct':matched_direct(case['groups']), **{'original_'+a:bank[a][key]['original'] for a in bank}}
        for role, asset in assets.items():
            message,schema = wire(asset,case['view'],case['groups'])
            identity = f'{run_id}:{digest(key)}:{role}'
            result = executor.generate(identity,source=key,purpose='skill_actor',messages=message,thinking=False,schema=schema)
            pair[role] = {**decode(module,asset,case['groups'],schema,result),'physical_call_id':identity}
            tokens += result['usage']['total_tokens']
            with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
                physical_wire(db,set(keys),identity,key)
            payload = read(Path(result['artifact_directory'])/'request.json')['payload']
            assert payload['messages']==message and payload['response_format']['json_schema']['schema']==schema
            settings={k:v for k,v in payload.items() if k not in ('messages','response_format')}
            assert params is None or params==settings
            params=settings
            phys.add(identity)
        records[key]=pair
        immutable_json(stage/'pairs'/(digest(key)+'.json'),pair)
        write_status(stage,{'status':'running','completed_pairs':len(records)},POINTER)
        print(json.dumps({'completed_pairs':len(records)}),flush=True)
    assert len(phys)==2*len(keys)
    return records,tokens


def run(phase):
    module,assets = layouts()
    cases,bank,physical,archived,grade,grade_sha,executor = materials()
    keys = [k for k,s in cases.items() if tuple(s['position']) in PAIRS]
    assert len(cases)==24 and len(keys)==len(PAIRS) and all(cases[k]['groups'] for k in keys)
    files = (Path(__file__).resolve().relative_to(ROOT), 'legal_skill_guard/paired_interfaces/residual.py',
             'legal_skill_guard/skill_evolution/clients.py','legal_skill_guard/skill_evolution/ledger.py',
             'legal_skill_guard/rr/client.py','experiments/convergence_revision5_cni_scoped_update.py',
             'experiments/convergence_revision5_cni_nonsolicitation.py','experiments/convergence_revision5_m2_cumulative_audit.py')
    binding={'study':'copy_creation_vs_retention_in_CNI_TRAIN','partition':'TRAIN','native_grade_sha256':grade_sha,
             'executor':executor,'requests':2*len(keys),'original_read_refs':archived,'source_sha256':{str(f):sha(ROOT/f) for f in files},
             'cases_sha256':digest(cases),'original_and_direct_predictions_sha256':digest(bank),
             'pair_positions':[cases[k]['position'] for k in keys], 'local_proof_states':len(module.states),
             'layouts':{r:a['version'] for r,a in assets.items()}}
    stage = HOME/digest(binding)
    immutable_json(stage/'binding.json',binding)
    immutable_json(stage/'cases.json',cases)
    immutable_json(stage/'TRAIN_original_and_direct.json',bank)
    if (stage/'terminal.json').exists():
        print(json.dumps({'artifact_root':str(stage.relative_to(ROOT)),**read(stage/'terminal.json')},sort_keys=True),flush=True)
        return
    if phase=='run':
        assert ROOT/read(POINTER)['artifact_root']==stage
        records,tokens = execute(stage,binding,cases,keys,module,assets,bank)
        immutable_json(stage/'paired_predictions.json',records)
    assert sha(ROOT/grade)==grade_sha
    annotations=read(ROOT/grade)
    views={k:c['view'] for k,c in cases.items()}
    direct_summary={a:estimate(views,rows,annotations) for a,rows in bank.items()}
    diagnostic=[]
    for key in keys:
        native=annotations[key][TASK]
        direct=matched_direct(cases[key]['groups'])
        row={'position':cases[key]['position'],'benchmark':native['answer'],'direct':direct['answer'],
             'group_count':len(cases[key]['groups']),'direct_evidence_F1':grade_view(
                 DATASET,views[key],native,direct['answer'],direct['evidence_sentence_ids'])['evidence_f1']}
        diagnostic.append(row)
    preflight={'artifact_root':str(stage.relative_to(ROOT)),'native_TRAIN':direct_summary,'pair_diagnostic':diagnostic,
               'archived_physical_responses_verified':len(physical),'source_groups':sum(len(c['groups']) for c in cases.values())}
    immutable_json(stage/'direct_preflight.json',preflight)
    if phase=='prepare':
        assert not POINTER.exists() or read(POINTER)['status']!='running'
        write_status(stage,{'status':'prepared','requests':binding['requests']},POINTER)
        print(json.dumps(preflight,sort_keys=True),flush=True)
        return
    by_role = estimate(views,records,annotations)
    terminal = {**preflight,'status':DONE,'paired_TRAIN':by_role,'new_executor_calls':binding['requests'],
                'new_executor_tokens':tokens,'new_teacher_calls':0,'original_TEST_opened':False,
                'predictions_sha256':sha(stage/'paired_predictions.json')}
    immutable_json(stage/'terminal.json',terminal)
    write_status(stage,{'status':DONE,'requests':binding['requests']},POINTER)
    print(json.dumps(terminal,sort_keys=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase)
