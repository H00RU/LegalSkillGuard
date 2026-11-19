"""Test whether a synthesized signed-scope interface repairs two paired native labels."""

import argparse
from collections import Counter
import fcntl
from functools import lru_cache
import inspect
import json
from pathlib import Path
import sqlite3
from statistics import mean

import jsonschema

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_fit import ORDINARY
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_disclosure_objects import clean
from experiments.convergence_revision5_cni_linked_evidence import DATASET, span_inventory
from experiments.convergence_revision5_cni_oral_scope import verify_prediction
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_CNI_signed_scope_20261119'
POINTER = HANDOFF / 'revision5_CNI_signed_scope_current.json'
DONE = 'settled_CNI_paired_signed_scope_TRAIN'
TASKS = {'external_disclosure': 'nda-7', 'agreement_fact': 'nda-10'}
ROLES = ('fixed', 'synthesized')
YES, NO, ABSENT = 'Entailment', 'Contradiction', 'NotMentioned'
# Source-only witnesses used by the direct check and evaluation. Neither reader sees them.
REVIEWS = {
    (1, 1): ((NO, (25,), 'divulge any Confidential Information to third parties'), (ABSENT, (), '')),
    (7, 2): ((NO, (14,), 'shall not disclose said information to third parties'), (ABSENT, (), '')),
    (8, 0): ((NO, (14,), 'shall not disclose, allow access to'), (ABSENT, (), '')),
    (8, 1): ((YES, (49,), 'legal advisors, financial advisors and accountants'),
             (YES, (55, 58, 60), 'shall not disclose the existence of this Agreement')),
}
MEANINGS = {
    'external_grant_is_operative': 'an operative ordinary-disclosure permission covers confidential information',
    'external_grant_reaches_external_recipient': (
        'the same permission reaches an external consultant, agent, advisor or other external recipient'),
    'external_bar_applies': 'an operative rule bars onward disclosure of protected information to external recipients',
    'fact_bar_is_operative': 'an operative restriction governs disclosure rather than use, retention or license',
    'fact_is_the_restricted_object': (
        'that same restriction covers the fact that this agreement was made or negotiated, directly or by definition'),
    'fact_has_unrestricted_public_grant': (
        'an operative rule affirmatively authorizes public disclosure of the fact of this agreement or negotiation'),
}
COMMON = (
    'Read the complete agreement and both native questions. Analyze the subject, act, object, recipient and '
    'exceptions of each operative source clause. For ordinary confidential information, check an express grant '
    'to external recipients and an express bar to external recipients. Permission for employees alone is '
    'internal. A requirement to get written consent is a bar absent consent, not an already operative grant. '
    'For the fact of agreeing or negotiating, trace the precise protected object through any named definition. '
    'A special restriction with listed exceptions can still govern the existence of the agreement. A grant to '
    'some advisors for another object does not authorize public disclosure of the existence of the agreement. '
    'License language and survival language alone establish neither disclosure conclusion. '
    'Check the full source for an alternative applicable clause. Set a coordinate false for a checked absence '
    'and null for unresolved scope. For an established grant or bar, cite its original IDs and any governing '
    'definition or exception. Use an empty list if neither signed conclusion is established.'
)


def consume(v, _):
    external, agreement = None, None
    if v['external_grant_is_operative'] == True and v['external_grant_reaches_external_recipient'] == True:
        external = YES
    elif v['external_grant_is_operative'] == False or v['external_grant_reaches_external_recipient'] == False:
        if v['external_bar_applies'] is not None:
            external = NO if v['external_bar_applies'] else ABSENT
    if v['fact_bar_is_operative'] == True and v['fact_is_the_restricted_object'] == True:
        agreement = YES
    elif v['fact_bar_is_operative'] == False or v['fact_is_the_restricted_object'] == False:
        if v['fact_has_unrestricted_public_grant'] is not None:
            agreement = NO if v['fact_has_unrestricted_public_grant'] else ABSENT
    return {'external_disclosure': external, 'agreement_fact': agreement}


@lru_cache(maxsize=1)
def layouts():
    procedure = inspect.getsource(consume)
    module = residual.FiniteModule.build(
        'signed_disclosure_scope', {field: [True, False, None] for field in MEANINGS},
        [{}], consume, consumer_sha256=digest(procedure), program_source=procedure,
        protected_status_fields=('external_bar_applies', 'fact_has_unrestricted_public_grant'),
        source_scope={'source_fields': ['source_text'], 'local_unit': 'operative disclosure proposition',
                      'field_meanings': MEANINGS})
    fixed = [{'name': field, 'operation': 'field', 'field': field} for field in MEANINGS]
    features = []
    for start, name in ((0, 'grant_to_external_recipients'), (3, 'restriction_on_agreement_fact')):
        deps = set(list(MEANINGS)[start:start+2])
        relation, = (r for r in residual.consumer_relations(module)
                     if r['expression']['op'] == 'and' and set(r['consumer_dependencies']) == deps)
        features.extend(({**relation, 'name': name}, fixed[start+2]))
    pair = (residual.compile_pair(module, fixed, operation='fixed_coordinates', layout='anchored'),
            residual.compile_pair(module, features, operation='consumer_relational_projection', layout='anchored'))
    for state in module.states:
        for asset in pair:
            observed = residual.encode(asset['features'], state)
            receipt = residual.decode(asset, observed, {}, module_binding=module.binding)
            assert receipt['valid'] and receipt['outputs'] == consume(state, {})
    return module, pair


def materials():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    spec = read(root / 'binding.json')
    assert digest(spec) == root.name
    roster = load_roster(spec)
    journal = TrainingJournal(root, spec, roster)
    train = {s['key'] for batch in roster for s in batch if s['dataset'] == DATASET and s['project_split']=='train'}
    cases, settled, grade_files, physical = [], [], set(), set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        for batch, sources in enumerate(roster, 1):
            if not any(b == batch for b, _ in REVIEWS):
                continue
            stage = ROOT / read(FIRST if batch == 1 else observe_pointer(batch))['artifact_root']
            bound, end = (read(stage / p) for p in ('binding.json', 'terminal.json'))
            assert digest(bound) == stage.name and not end['TEST_opened']
            assert all(sha(stage/'source_snapshot'/n) == h for n, h in bound['source_sha256'].items())
            receipt = journal._observations(ORDINARY, batch)
            assert end['observation_receipts'][ORDINARY] == receipt['train_observation_sha256']
            settled.append(sha(stage / 'terminal.json'))
            grade = bound['native_grade_paths'][DATASET]
            grade_files.add((grade, bound['native_grade_sha256'][grade]))
            for n, source in enumerate(s for s in sources if s['dataset'] == DATASET):
                pos = (batch, n)
                if pos not in REVIEWS:
                    continue
                key = source['key']
                views = {k: next(v for v in source['views'] if v['id']==t) for k,t in TASKS.items()}
                anchor = views['external_disclosure']
                spans = span_inventory(anchor)
                saved = read(journal.directory(ORDINARY,batch)/'predictions'/(digest(key)+'.json'))
                assert digest(saved) == receipt['predictions'][key]
                skill = digest(journal.library(ORDINARY,batch-1)['programs'][DATASET])
                native = verify_prediction(db, train, key, anchor, saved['result'], physical, skill)
                raw = json.loads(saved['result']['reads'][0]['execution']['traces'][0]['raw_content'])['value']
                direct = {}
                for (k,t), (label, ids, cue) in zip(TASKS.items(), REVIEWS[pos], strict=True):
                    assert all(cue in clean(spans[i]) for i in ids)
                    output = native[t]
                    assert all(output[field] == raw[t][field] for field in ('answer','evidence_sentence_ids'))
                    direct[k] = {'answer': label, 'evidence': list(ids)}
                payload = {'complete_document': anchor['public']['source_text'],
                           'native_hypotheses': {k: v['public']['question'] for k,v in views.items()},
                           'evidence_units': [{'id': j, 'text': s} for j,s in enumerate(spans)]}
                cases.append({'source':key, 'views':views, 'payload':payload, 'direct':direct,
                              'original':{k:{'answer':native[t]['answer'],
                                            'evidence':native[t]['evidence_sentence_ids']} for k,t in TASKS.items()}})
    assert len(cases) == len(REVIEWS) == len(physical)
    (grade_path, grade_hash), = grade_files
    assert 'train' in Path(grade_path).parts
    files = [Path(__file__).resolve().relative_to(ROOT), 'experiments/convergence_revision5_cni_disclosure_objects.py',
             'experiments/convergence_revision5_cni_linked_evidence.py','experiments/convergence_revision5_cni_oral_scope.py',
             'experiments/convergence_revision5_m2_cumulative_audit.py',
             'legal_skill_guard/paired_interfaces/residual.py','legal_skill_guard/skill_evolution/clients.py',
             'legal_skill_guard/skill_evolution/ledger.py','legal_skill_guard/rr/client.py']
    binding = {'study': 'CNI_native_signed_disclosure_scope', 'TRAIN_only': True, 'executor': spec['executor'],
               'cases_sha256': digest(cases), 'original_terminals': settled,
               'grade_path': grade_path, 'grade_sha256': grade_hash, 'sources_sha256': {str(p): sha(ROOT/p) for p in files},
               'states': len(layouts()[0].states), 'assets': [a['version'] for a in layouts()[1]],
               'forecast': 'Linking the legal effect to the same recipient and information object reduces polarity swaps '
                           'relative to fixed fields, while preserving the narrow-agreement-fact restriction.',
               'controls': 'Fixed fields use identical source and consumer; a reviewed clause-level direct check bounds the mechanism.',
               'planned_calls': 2*len(cases)}
    return binding, cases


def contract(asset, case):
    span = {'type':'integer','minimum':0,'maximum':len(case['payload']['evidence_units'])-1}
    evidence = {'type':'array','maxItems':12,'items':span}
    coords = {f['name']:{'enum':asset['domains'][f['name']]} for f in asset['features']}
    schema = record_schema({'relations':record_schema(coords),'evidence':record_schema(dict.fromkeys(TASKS,evidence))})
    prompts = '\n'.join(residual.reader_prompt(asset,verbalize_relations=True).splitlines()[4:])
    return [{'role':'system','content':COMMON+'\n'+prompts},
            {'role':'user','content':json.dumps(case['payload'],ensure_ascii=False,sort_keys=True)}], schema


def decode(asset, case, response):
    _, schema = contract(asset, case)
    try:
        if response['finish_reason'] != 'stop':
            raise ValueError('Incomplete read')
        value = json.loads(response['content'])
        jsonschema.validate(value, schema)
        result = residual.decode(asset,value['relations'],{},module_binding=layouts()[0].binding)
        if not result['valid']:
            raise ValueError('Read outside the certified domain')
        for ids in value['evidence'].values():
            if len(set(ids)) != len(ids) or any(not case['payload']['evidence_units'][i]['text'].strip() for i in ids):
                raise ValueError('Evidence must have distinct nonempty spans')
        output = {}
        for task,label in result['outputs'].items():
            ids = sorted(value['evidence'][task])
            if label in (YES, NO) and not ids:
                label = None
            output[task] = {'answer':label,'evidence':ids if label in (YES,NO) else [],'raw_evidence':ids}
        return output
    except (ValueError, jsonschema.ValidationError) as error:
        return {k:{'answer':None,'evidence':[],'error':type(error).__name__} for k in TASKS}


def score(cases, reads, grades):
    metrics = {arm: {k: [] for k in TASKS} for arm in ('original', *ROLES, 'direct')}
    for case, pair in zip(cases, reads, strict=True):
        native = grades[case['source']]
        arms = {'original': case['original'], 'direct': case['direct'],
                **{arm: pair[arm]['answer'] for arm in ROLES}}
        for arm, predictions in arms.items():
            for k,t in TASKS.items():
                pred, direct = predictions[k], case['direct'][k]
                result = grade_view(DATASET,case['views'][k],native[t],pred['answer'],pred['evidence'])
                supports = pred['answer'] == direct['answer'] and set(direct['evidence']) <= set(pred['evidence'])
                metrics[arm][k].append({'native_correct':result['grade'],'official_evidence_f1':result['evidence_f1'],
                                        'reviewed_witness_complete':supports})
    return {arm:{k:{metric:mean(row[metric] for row in rows) for metric in rows[0]} for k,rows in tasks.items()}
            for arm,tasks in metrics.items()}


def run(execute):
    binding, cases = materials()
    out = HOME / digest(binding)
    immutable_json(out/'binding.json', binding)
    if (out/'terminal.json').exists():
        print(json.dumps(read(out/'terminal.json'),sort_keys=True),flush=True)
        return
    if not execute:
        write_status(out, {'status':'prepared','planned_calls':binding['planned_calls']}, POINTER)
        print(str(out.relative_to(ROOT)),flush=True)
        return
    assert ROOT/read(POINTER)['artifact_root'] == out
    lock = (out/'driver.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for name, expected in binding['sources_sha256'].items():
        path = out/'source_snapshot'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        assert sha(path) == expected
    run_id = 'convergence-revision5-CNI-signed-scope-'+out.name[:16]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':[c['source'] for c in cases],'dev':[],'test':[]},
                             binding=binding)
    reader = FrozenExecutor(ledger,out,binding['executor'])
    reader.readiness()
    answers, tokens = [], Counter()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        roles = tuple(zip(ROLES,layouts()[1],strict=True))
        for n,case in enumerate(cases):
            pair = {}
            for role,asset in (roles if n%2==0 else roles[::-1]):
                identity = f'{run_id}:{n}:{role}'
                messages,schema = contract(asset,case)
                write_status(out, {'status':'running','settled_pairs':n,'current_call':identity}, POINTER)
                result = reader.generate(identity,source=case['source'],purpose='skill_actor',messages=messages,
                                         thinking=False,schema=schema)
                answer = decode(asset,case,result)
                physical_wire(db, {case['source']}, identity, case['source'])
                request = read(Path(result['artifact_directory'])/'request.json')['payload']
                assert request == reader.payload(messages=messages,thinking=False,schema=schema)
                tokens[role] += result['usage']['total_tokens']
                pair[role] = {'id':identity,'answer':answer}
                immutable_json(out/'reads'/f'{n}_{role}.json',pair[role])
                print(json.dumps({'completed':n,'role':role}),flush=True)
            answers.append(pair)
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
    immutable_json(out/'predictions.json',answers)
    path = ROOT/binding['grade_path']
    assert sha(path) == binding['grade_sha256']
    terminal = {'status':DONE,'partition':'TRAIN','new_executor_requests':binding['planned_calls'],'new_teacher_requests':0,
                'pairs':len(cases),'states_preserved':binding['states'],'verified_archived_reads':len(cases),
                'tokens_by_role':dict(tokens),'ledger':counts,'native_results':score(cases,answers,read(path)),
                'runner_sha256':sha(Path(__file__)),'predictions_sha256':sha(out/'predictions.json')}
    immutable_json(out/'terminal.json',terminal)
    write_status(out, {'status':DONE,'settled_pairs':len(answers)}, POINTER)
    print(json.dumps(terminal,sort_keys=True),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
