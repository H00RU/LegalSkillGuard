"""Replay settled TRAIN reads only; no client, model, ledger write or grading input."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
parser.add_argument('--implementation-root',type=Path)
args=parser.parse_args()
ROOT=args.root.resolve()
WORK=(args.implementation_root or ROOT).resolve()
sys.path.insert(0,str(WORK))
from legal_skill_guard.skill_evolution.objects import Library, apply_revision_package, digest
from legal_skill_guard.skill_evolution.runtime import SkillRuntime, typed
from legal_skill_guard.skill_evolution.answer_domain import incompatible_native_enum
FOLDER=ROOT/'artifacts/legal_skill_evolution_20261111/formal_v3'
spec=importlib.util.spec_from_file_location('legal_skill_guard.skill_evolution.runtime_before_enum_skip', FOLDER/'source_snapshot/legal_skill_guard/skill_evolution/runtime.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
records={r['key']:r for r in json.loads((ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json').read_text())}

def denied(*args,**kwargs):raise AssertionError('Network disabled in actual-TRAIN trace replay')
socket.socket=denied
libraries={}
parents=[]
for arm in json.loads((ROOT/'configs/legal_skill_evolution_formal_v3_20261111.json').read_text())['arms']:
    for p in (FOLDER/arm).glob('B[0-8].json'):
        lib=Library.load(p);libraries[lib.hash]=lib
    for p in (FOLDER/arm).glob('initial_B[1-8].json'):
        blob=json.loads(p.read_text());parents.extend((str(p.relative_to(ROOT)),r) for r in blob['results'])
    for p in (FOLDER/arm).glob('B[1-8]_candidates/*.json'):
        blob=json.loads(p.read_text());n=int(p.parent.name.split('_')[0][1:]);base=Library.load(FOLDER/arm/f'B{n-1}.json')
        revisions=blob.get('revisions',[])
        for cell in blob.get('table',{}).get('mixed_version_table',[]):
            lib=apply_revision_package(base,[r for i,r in enumerate(revisions) if cell['mask'] & (1<<i)],base.hash)
            libraries[lib.hash]=lib
            if isinstance(cell.get('trace'),dict):parents.append((str(p.relative_to(ROOT)),cell['trace']))

class RecordedReads:
    def __init__(self, execution):
        self.execution=execution;self.calls=[];self.keys=defaultdict(list);self.positions=Counter()
        for event in execution.get('events',[]):
            if event.get('kind')=='READ_LOCAL':
                self.keys[self.key(event['question'],event['locator'],event['fields'])].append(deepcopy(event))
    @staticmethod
    def key(question,locator,fields):return (question,locator,tuple(sorted(fields)))
    def read(self,source,view,*,question,fields,locator,purpose,allow_unresolved=False,**kwargs):
        key=self.key(question,locator,fields);pos=self.positions[key]
        if key not in self.keys:raise RuntimeError('No recorded matching READ_LOCAL; no response invented')
        events=self.keys[key]
        # Multiple identical requests must have identical semantic records before
        # skipping any prefix can reuse one. Keep ambiguity out of passed cases.
        if len({digest(e['fields']) for e in events}) != 1:raise RuntimeError('Ambiguous same-query recorded responses')
        event=deepcopy(events[min(pos,len(events)-1)]);self.positions[key]+=1
        self.calls.append(event)
        values={}
        for name,item in event['fields'].items():
            if item['status']=='unknown' and item['value'] is None and allow_unresolved:continue
            if item['status']!='known' or item['value'] is None or not item['support_ids']:raise RuntimeError('Unreplayable invalid read record')
            typed(item['value'],fields[name]['type']);values[name]=item['value']
        return values,event
    def direct(self,source,view,purpose):
        if not self.execution.get('fallback'):raise RuntimeError('A new fallback was not in the actual settled trace')
        events=[deepcopy(e) for e in self.execution['events'] if e.get('kind') not in ('READ_LOCAL','APPLY','USE')]
        return {'answer':deepcopy(self.execution['answer']),'evidence_sentence_ids':deepcopy(self.execution.get('evidence_sentence_ids',[])),
                'events':events,'core_executed':False,'fallback':True}

def semantic(result):return {k:result.get(k) for k in ('answer','evidence_sentence_ids','core_executed','fallback','terminal_skill','retrieved')}
seen=set();passed=[];unresolved=[];ineligible=Counter();physical=set();scanned=0
for artifact,parent in parents:
    if parent['source'] not in records:raise AssertionError('Non-TRAIN parent reached replay')
    lib=libraries.get(parent['library_hash'])
    if lib is None:ineligible['unknown_library']+=1;continue
    source=records[parent['source']];views={v['id']:v for v in source['views']}
    for item in parent.get('views',[]):
        execution=item['execution'];view=views[item['view']];selected=execution.get('retrieved')
        if selected is None:ineligible['no_settled_retrieval']+=1;continue
        key=(source['key'],view['id'],lib.hash,tuple(selected))
        if key in seen:continue
        seen.add(key);scanned+=1
        rejected=[identity for identity in selected if identity in lib.skills and incompatible_native_enum(lib.skills[identity].procedure,view['answer_schema'])]
        if not rejected:continue
        try:
            before_reads=RecordedReads(execution);after_reads=RecordedReads(execution)
            before=old.SkillRuntime(before_reads).run(source,view,lib,retrieved=selected)
            after=SkillRuntime(after_reads).run(source,view,lib,retrieved=selected)
            if semantic(before)!=semantic(execution):raise AssertionError('Old replay does not reproduce recorded final answer/path')
            if semantic(after)!=semantic(before):raise AssertionError('Optimized replay changes final answer/path')
            if [e.get('kind') for e in before['events']] != [e.get('kind') for e in execution['events']]:raise AssertionError('Old event sequence differs from actual trace')
            removed=max(0,len(before_reads.calls)-len(after_reads.calls))
            after_ids={e.get('physical_call_id') for e in after_reads.calls}
            removed_ids={e.get('physical_call_id') for e in before_reads.calls}-after_ids
            physical.update(i for i in removed_ids if i)
            passed.append({'source':source['key'],'dataset':source['dataset'],'view':view['id'],'library_hash':lib.hash,
                           'artifact':artifact,'proved_incompatible_terminal_roots':rejected,'actual_read_occurrences_before':len(before_reads.calls),
                           'actual_read_occurrences_after':len(after_reads.calls),'removed_read_occurrences':removed,'physical_ids_referenced_only_by_removed_reads':sorted(i for i in removed_ids if i),
                           'final_answer_and_core_fallback_terminal_and_retrieval_unchanged':True})
        except Exception as error:
            unresolved.append({'source':source['key'],'view':view['id'],'library_hash':lib.hash,'artifact':artifact,'error':type(error).__name__+': '+str(error)})
result={'captured_utc':datetime.now(timezone.utc).isoformat(),'scope':'Settled formal TRAIN initial and candidate traces; no DEV grading or TEST files read',
        'new_model_calls':0,'ledger_writes':0,'network_disabled':True,'unique_TRAIN_view_library_retrieval_cases_scanned':scanned,
        'affected_cases_reproduced':len(passed),'unresolved_replays':unresolved,'ineligible':dict(ineligible),
        'actual_read_occurrences_before':sum(x['actual_read_occurrences_before'] for x in passed),
        'actual_read_occurrences_after':sum(x['actual_read_occurrences_after'] for x in passed),
        'distinct_historical_physical_ids_referenced_only_by_removed_reads':len(physical),
        'dataset_counts':dict(Counter(x['dataset'] for x in passed)),'rows':passed,
        'interpretation':'Actual recorded READ_LOCAL values were replayed, with exact old final-answer and core/fallback/terminal/retrieval reproduction. Not a new model experiment or universal response-distribution equivalence. Historical physical cost is unchanged; removed logical reads are prospective savings, not an additional method contribution.'}
result['implementation_sha256']={name:hashlib.sha256((WORK/name).read_bytes()).hexdigest() for name in ('legal_skill_guard/skill_evolution/runtime.py','legal_skill_guard/skill_evolution/answer_domain.py')}
result['before_runtime_sha256']=hashlib.sha256((FOLDER/'source_snapshot/legal_skill_guard/skill_evolution/runtime.py').read_bytes()).hexdigest()
out=ROOT/'reports/legal_skill_evolution_run_20261111/actual_TRAIN_enum_skip_regression.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('rows','ineligible')},ensure_ascii=False),flush=True)
