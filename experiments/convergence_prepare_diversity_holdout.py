"""Isolated Diversity partition preparation; prints only counts and hashes.

The development agent must not inspect raw native TEST or sealed_test files.
Native annotations are copied to sealed scoring storage without model use,
reference-score filtering or display. DEV is explicitly a project split of
native TEST; TEST remains closed until the B8 library/model freeze.
"""
from collections import Counter
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from legal_skill_guard.paired_interfaces.diversity import (
    REVISION, annotation, audit_source, public_source, structural_group)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'
DEV=(2,2,3,3,3,3)
TEST=(5,5,5,5,6,6)


def read(path):return json.loads(path.read_text())
def sha(body):return hashlib.sha256(body).hexdigest()
def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'LegalSkillGuard-source-preparation'}),timeout=60) as r:
        return r.read()


def official_design():
    """Pin official source once, quarantine all already-read v6 examples."""
    path=BASE/'handoff/diversity_official_design_receipt.json'
    if path.exists():return read(path)
    commit=json.loads(fetch('https://api.github.com/repos/HazyResearch/legalbench/commits/main'))['sha']
    files=[];groups=set();examples=0;malformed=[]
    for name in ('README.md','base_prompt.txt','application_prompt.txt'):
        url=f'https://raw.githubusercontent.com/HazyResearch/legalbench/{commit}/tasks/diversity_6/{name}'
        body=fetch(url)
        target=BASE/'design_exposure/LegalBench_Diversity'/commit/name
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
        files.append({'path':str(target.relative_to(ROOT)),'url':url,'sha256':sha(body),'bytes':len(body)})
        if name=='README.md':continue
        # Q facts precede the fixed native question. Never read native TEST here.
        for m in re.finditer(r'Q:\s*(.*?)\s*Is there diversity jurisdiction\?',body.decode(),re.S):
            text=m.group(1).strip()
            if '{{' in text:continue
            try:records=[audit_source(text)]
            except ValueError as error:
                # The official application prompt repeats a defendant's name
                # in citizenship assertions while omitting another defendant.
                # Do not repair it into training truth. Conservatively exclude
                # both possible name-to-citizenship assignments from TEST.
                citizens=re.findall(r'(\w+) is from ([^.]+)\.',text)
                names=[n for n,_ in citizens]
                repeated={n for n in names if names.count(n)>1}
                claim_names=set()
                for match in re.finditer(r'(?:^|\. )([^.\n]+?) (?:both sue|sues|sue) (.+?)(?: each)? for ',text):
                    claim_names.update(match[1].split(' and '));claim_names.update(match[2].split(' and '))
                missing=claim_names-set(names)
                if len(repeated)!=1 or len(missing)!=1:raise
                duplicate=next(iter(repeated));absent=next(iter(missing));records=[]
                occurrences=list(re.finditer(r'\b'+re.escape(duplicate)+r'(?= is from )',text))
                for hit in occurrences:
                    replacement=text[:hit.start()]+absent+text[hit.end():]
                    records.append(audit_source(replacement))
                malformed.append({'text_sha256':sha(text.encode()),'reason':str(error),
                    'action':'exclude all possible duplicate-name assignments; never use as supervision'})
            groups.update(structural_group(record) for record in records);examples+=1
    result={'official_repository_commit':commit,'files':files,'design_exposure_examples':examples,
        'quarantined_group_hashes':sorted(groups),'malformed_official_design_examples':malformed,
        'common_public_rules_no_examples':True,
        'original_plan_already_registers_diversity6_base_and_application_as_design_exposure':True}
    immutable_json(path,result)
    return result


def prepare():
    design=official_design();excluded=set(design['quarantined_group_hashes'])
    # All36 native TRAIN rows are conservatively excluded, including the12 not
    # selected for learning. They cannot become hidden extra few-shot sources.
    train_receipt=read(BASE/'handoff/diversity_train_download_receipt.json')
    for item in train_receipt['files']:
        for row in csv.DictReader(StringIO((ROOT/item['path']).read_text(encoding='utf-8-sig')),delimiter='\t'):
            excluded.add(structural_group(audit_source(row['text'])))
    train=read(BASE/'handoff/diversity_train_current.json')
    raw_receipts=[];pools={};parser_failures=[]
    for number in range(1,7):
        variant=f'diversity_{number}'
        url=f'https://huggingface.co/datasets/nguha/legalbench/raw/{REVISION}/data/{variant}/test.tsv'
        path=BASE/'sealed_native/LegalBench_Diversity'/variant/'test.tsv'
        if path.exists():body=path.read_bytes()
        else:
            body=fetch(url);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        rows=list(csv.DictReader(StringIO(body.decode('utf-8-sig')),delimiter='\t'))
        if len(rows)!=300:raise ValueError('Pinned native row count mismatch')
        raw_receipts.append({'path':str(path.relative_to(ROOT)),'url':url,'sha256':sha(body),'bytes':len(body),'rows':len(rows)})
        pool=[]
        for row in rows:
            try:group=structural_group(audit_source(row['text']))
            except ValueError as error:
                # No silent deletion of difficult cases; stop whole preparation.
                parser_failures.append({'variant':variant,'native_id':row['index'],'reason':str(error)})
                continue
            if group not in excluded:pool.append((group,row))
        pools[variant]=sorted(pool,key=lambda x:digest({'seed':45,'group':x[0],'variant':variant,'index':str(x[1]['index'])}))
    if parser_failures:
        immutable_json(BASE/'handoff/diversity_grouping_failures.json',parser_failures)
        raise ValueError('Grouping parser has uncovered native structures; repair it before selecting any cohort')
    used=set(excluded);public={'dev':[],'test':[]};grading={'dev':{},'test':{}};metadata=[]
    inventory={v:len({g for g,_ in pool}) for v,pool in pools.items()}
    for split,quotas in (('dev',DEV),('test',TEST)):
        for number,quota in enumerate(quotas,1):
            variant=f'diversity_{number}';selected=0
            for group,row in pools[variant]:
                if group in used:continue
                used.add(group);s=public_source(row,variant,project_split=split)
                public[split].append(s);grading[split][s['key']]=annotation(row)
                metadata.append({'original_dataset':'nguha/legalbench','revision':REVISION,
                    'native_split':'test','native_config':variant,'native_id':str(row['index']),
                    'source':s['key'],'mother_group':group,'project_split':split,
                    'exposure_status':'project_DEV_source' if split=='dev' else 'sealed_fresh_candidate',
                    'public_content_sha256':digest(s),'development_agent_read_source':False})
                selected+=1
                if selected==quota:break
            if selected!=quota:raise ValueError('Pinned independent group stock deficit: '+variant+' '+split)
    protocol={'name':'convergence_Diversity_group_split_v1','seed':45,'revision':REVISION,
        'DEV_quotas':DEV,'TEST_quotas':TEST,'raw_native_receipts':raw_receipts,
        'TRAIN_preparation_root':train['artifact_root'],'design_receipt_sha256':sha((BASE/'handoff/diversity_official_design_receipt.json').read_bytes()),
        'excluded_train_design_group_hashes':sorted(excluded),
        'code_sha256':{p:sha((ROOT/p).read_bytes()) for p in (
            'experiments/convergence_prepare_diversity_holdout.py','legal_skill_guard/paired_interfaces/diversity.py')},
        'label_or_reference_accuracy_used_for_selection':False,'development_agent_receives_TEST_content':False,
        'model_calls':0,'global_five_library_freeze_complete':False}
    out=BASE/'diversity_holdout_v1'/digest(protocol)
    immutable_json(out/'protocol.json',protocol);immutable_json(out/'identity_metadata.json',metadata)
    for split in ('dev','test'):
        sub='dev' if split=='dev' else 'sealed_test'
        immutable_json(out/sub/'public.json',public[split]);immutable_json(out/sub/'grading.json',grading[split])
    summary={'artifact_root':str(out.relative_to(ROOT)),'DEV_mothers':16,'TEST_candidate_mothers':32,
        'by_variant':{split:dict(Counter(s['native_config'] for s in public[split])) for split in public},
        'remaining_eligible_groups_before_selection':inventory,'excluded_train_design_groups':len(excluded),
        'all_selected_groups_distinct':len({m['mother_group'] for m in metadata})==48,
        'TEST_scoring_performed':False,'TEST_content_or_labels_displayed':False,'new_model_calls':0}
    immutable_json(out/'summary.json',summary)
    (BASE/'handoff/diversity_holdout_current.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':prepare()
