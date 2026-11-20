"""Replay source-bound employee-disclosure witnesses on the original TRAIN and DEV."""

from collections import Counter
from pathlib import Path
import re
from statistics import mean

from experiments import convergence_revision6_contract_citation_roles as citations
from experiments import convergence_revision6_contract_links as links
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision6_contract_employee_witnesses'
POINTER = HANDOFF / 'revision6_contract_employee_witnesses_current.json'
TASK = links.linked.TASK
EXCEPT = re.compile(
    r'\bneither\s+party\s+shall\s+disclose\s+the\s+confidential\s+information\s+'
    r'received\s+from\s+the\s+other\b[^.;]{0,150}\bexcept\s+its\s+employees\b', re.I)
RECEIVER = re.compile(
    r'\b(?:the\s+receiving\s+party\s+may\s+disclose\s+the\s+confidential\s+information|'
    r'each\s+party\s+may\s+disclose\s+the\s+other\s+party[’\']s\s+confidential\s+information)'
    r'\s+to\s+(?:those\s+of\s+)?its\s+(?:directors,\s*officers\s*(?:,\s*|and\s+))?employees\b',
    re.I)


def witness(view):
    """The permission, receiving role and employee membership must share a source path."""
    linked = links.direct_source(view)
    spans = [' '.join(s.split()) for s in links.linked.span_inventory(view)]
    local = [i for i,s in enumerate(spans) if EXCEPT.search(s) or RECEIVER.search(s)]
    if linked is not None:
        return linked if not local else None
    if len(local) == 1:
        return {'answer':'Entailment','evidence_sentence_ids':local}
    return None


def project(native, proof):
    if proof is None:
        return native
    if (native['answer'] == proof['answer']
            and set(proof['evidence_sentence_ids']) <= set(native['evidence_sentence_ids'])):
        return native
    return proof


def compare(sources, old, new, labels):
    rows = [[{'source':s['key'], 'view':TASK, **links.first.native_score(s, bank[s['key']], labels)}
             for s in sources] for bank in (old,new)]
    a,b = rows
    return {
        'correct':[sum(r['grade'] for r in arm) for arm in rows],
        'evidence_f1':[mean(r['evidence_f1'] for r in arm) for arm in rows],
        'accuracy_increases':sum(y['grade'] > x['grade'] for x,y in zip(a,b,strict=True)),
        'accuracy_regressions':sum(y['grade'] < x['grade'] for x,y in zip(a,b,strict=True)),
        'effects':{metric:paired_source_effect(*[
            [{**r,'grade':r[metric]} for r in arm] for arm in rows
        ]) for metric in ('grade','evidence_f1')},
    }


def materials():
    spec, audited, _, _, study, batches, dev, parent, base_terminal = links.materials()
    training = [s for batch in batches for s in batch if s['dataset']==links.linked.DATASET]
    if any(s['project_split']!='train' for s in training) or any(s['project_split']!='dev' for s in dev):
        raise ValueError('Use only original ContractNLI TRAIN and DEV')
    proof_bank = {s['key']:witness(next(v for v in s['views'] if v['id']==TASK)) for s in training+dev}
    audit = Counter()
    for pos,item in audited.items():
        _, definition, required, _ = links.linked.REVIEWS[pos]
        proof = proof_bank[item['source']['key']]
        expect = required | ({definition} if definition is not None else set())
        if expect != (set(proof['evidence_sentence_ids']) if proof else set()):
            raise ValueError('The compiler must preserve the independently reviewed TRAIN provenance')
        audit['source_reviewed_mothers'] += 1
        audit['exact_nonempty_source_witness'] += bool(proof)
    return spec, study, training, dev, proof_bank, parent, base_terminal, dict(audit), batches


def original_training(spec, training, batches):
    linked = links.linked
    root = ROOT/read(linked.BOOTSTRAP)['artifact_root']
    original = read(root/'binding.json')
    journal = linked.TrainingJournal(root,original,batches)
    banks = {}
    for arm in (linked.ARM,links.first.release.formal.common.EXTERNAL_ARM):
        by_source = {}
        for batch,members in enumerate(batches,1):
            merged = journal._observations(arm,batch)
            for source in (s for s in members if s['dataset']==linked.DATASET):
                key = source['key']
                path = journal.directory(arm,batch)/'predictions'/(digest(key)+'.json')
                record = read(path)
                if digest(record) != merged['predictions'][key]:
                    raise ValueError('An original TRAIN prediction no longer matches its receipt')
                native = record['result']['native'][TASK]
                by_source[key] = {'answer':native['answer'],'evidence_sentence_ids':native['evidence_sentence_ids']}
        if len(training) != len(by_source):
            raise ValueError('Keep the full original TRAIN denominator for each arm')
        banks[arm] = by_source
    return banks


def run():
    spec, study, training, dev, proof_bank, parent, base_terminal, audit, batches = materials()
    release = links.first.release
    actor = release.ReleaseActor(parent,release.parent_cells(parent,base_terminal),{})
    raw = {'train':original_training(spec,training,batches),'dev':{}}
    for arm in release.ARMS:
        data = {}
        for source in dev:
            result = actor.original(arm,source['key'])['result']['native'][TASK]
            data[source['key']] = {'answer':result['answer'],'evidence_sentence_ids':result['evidence_sentence_ids']}
        raw['dev'][arm] = data
    binding = {'stage':'revision6_contract_employee_witnesses','base_DEV_terminal':base_terminal['terminal_sha256'],
               'provenance_TRAIN_sha256':spec['original_linked_TRAIN_terminal_sha256'],
               'original_native_cells_sha256':digest(raw),'proofs_sha256':digest(proof_bank),'TEST_opened':False,
               'source_sha256':{str(Path(p).relative_to(ROOT)):sha(Path(p)) for p in (
                   __file__,links.__file__,citations.__file__)}}
    out = HOME/digest(binding)
    immutable_json(out/'binding.json',binding)
    new = {split:{arm:{k:project(v,proof_bank[k]) for k,v in cells.items()} for arm,cells in bank.items()}
           for split,bank in raw.items()}
    output_hash = immutable_json(out/'predictions.json',{'original':raw,'common_witness':new})
    path = {'train':(spec['TRAIN_grading_file'],spec['TRAIN_grade_sha256']),
            'dev':(study['grading_paths'][links.linked.DATASET],None)}
    reports = {}
    for split,cohort in (('train',training),('dev',dev)):
        name,known = path[split]
        if split not in Path(name).parts or sha(ROOT/name) != (known or study['grading_file_sha256'][name]):
            raise ValueError('Use the original split grading file after sealing all predictions')
        labels = read(ROOT/name)
        reports[split] = {'mothers':len(cohort),'eligible_witnesses':sum(bool(proof_bank[s['key']]) for s in cohort),
                          'arms':{arm:compare(cohort,old,new[split][arm],labels) for arm,old in raw[split].items()}}
    terminal = sealed({'status':'settled_revision6_contract_employee_witnesses','binding_sha256':out.name,
                       'source_audit':audit,'reports':reports,'predictions_sha256':output_hash,
                       'shared_control':True,'new_executor_requests':0,'TEST_opened':False},'terminal_sha256')
    immutable_json(out/'terminal.json',terminal)
    write_status(out,{'status':terminal['status'],'terminal_sha256':terminal['terminal_sha256']},POINTER)
    print(out)


if __name__ == '__main__':
    run()
