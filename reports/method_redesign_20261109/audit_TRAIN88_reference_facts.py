"""Read one fixed TRAIN factual annotation projection; no test reference access.

The native answer/query directive and unrelated reference cases are not emitted
or supplied to models. This is additional TRAIN diagnostic supervision, not a
repair or recovered reading of a previous model output.
"""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,re,sqlite3,tarfile
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_TRAIN88_reference_facts_v1_20261110'
RUN=STAGE.name
DB=ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3'
BEFORE=Path('/media/sangfor/vdb/legal-skill-backups/legal_temporal13_20261110/ledger.after.sqlite3')
OLD=BASE/'redesign_source_roles_v1_20261109/seal.json'


def read(p):return json.loads(p.read_text())


def snapshot(p):
 with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
  return {t:c.execute('select * from '+t+' order by 1').fetchall() for t in ['calls','meta','oracle_views']}


def main():
 out=STAGE/'reference_fact_projection.json'
 if out.exists():print(out.read_text());return
 old=read(OLD);source=old['sources']['train'][87]
 row=next(r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources'] if r['key']==source)
 assert row['dataset']=='SARA_v2_Binary' and row['native_split']=='train'
 original_id=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources'][source]['original_id']
 assert isinstance(original_id,str) and re.fullmatch(r'[a-zA-Z0-9_]+',original_id)
 # Inspect archive filenames only to choose the exact existing training item.
 with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as archive:
  matches=[m for m in archive.getmembers() if m.isfile() and Path(m.name).stem==original_id and '/cases/' in m.name]
  assert len(matches)==1,('Expected one exact fixed TRAIN case',len(matches))
  member=matches[0]
  question='Diagnose the already selected TRAIN88 annotation versus public text for payment dates and medium. Emit factual predicates only, do not change old model frames, not an independent test or source-only method success.'
  file_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
  view={'kind':'SARA_TRAIN_reference_factual_projection','source':source,
        'projection':['payment_','service_','agent_','patient_','purpose_','start_','end_','amount_','means_'],
        'goal_directives_or_native_label_emitted':False}
  l=MethodLedger(DB,run_id=RUN,binding={'code_hash':file_hash,'config_hash':digest(old['config'])},sources=old['sources'],
    authorization_hash=digest({'authority':'docs/CURRENT_GOAL.md','existing_fixed_TRAIN_diagnostic':True,'view':view}),question=question)
  l.reserve_oracle(source,digest(view))
  raw=archive.extractfile(member).read();text=raw.decode()
 # Only simple ground facts from an explicit whitelist reach the evidence file.
 # Do not print original_id (its suffix can encode the native answer).
 whitelist=set(view['projection']);facts=[]
 for line in text.splitlines():
  line=line.strip()
  m=re.fullmatch(r'([a-z][a-z0-9_]*)\((.*)\)\.',line)
  if m and m[1] in whitelist:
   assert ':-' not in line
   facts.append(line)
 assert facts
 result={'source':source,'original_TRAIN_ordinal':88,'public_facts':row['public']['facts'],
  'reference_member_name_not_emitted_because_it_may_encode_label':True,
  'reference_case_sha256':hashlib.sha256(raw).hexdigest(),'factual_projection':facts,
  'annotation_supervision_not_public_text_entailment':True,'old_model_frames_not_modified':True,
  'native_query_answer_not_emitted_or_graded':True,'only_exact_existing_TRAIN_member_opened':True,
  'unrelated_cases_DEV_TEST_references_read':False,'new_model_calls':0,'new_oracle_views':1,'goal_complete':False}
 immutable_json(out,result)
 before=snapshot(BEFORE);current=snapshot(DB);historic=deepcopy(current)
 historic['meta']=[r for r in historic['meta'] if r[0]!='method_runtime_policy:'+RUN]
 historic['oracle_views']=[r for r in historic['oracle_views'] if (r[0],r[1])!=(source,digest(view))]
 assert historic==before
 immutable_json(STAGE/'preservation.json',{'all_old_calls_meta_oracle_rows_equal_backup':True,
  'calls_unchanged':len(current['calls']),'meta_count':len(current['meta']),'oracle_count':len(current['oracle_views']),
  'new_model_calls':0,'new_oracle_views':1,'old_ledger_logical_sha256':digest(historic),'current_ledger_logical_sha256':digest(current)})
 dst=Path('/media/sangfor/vdb/legal-skill-backups/legal_TRAIN88_reference_facts_20261110/ledger.after.sqlite3');dst.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(DB) as a,sqlite3.connect(dst) as b:a.backup(b)
 assert snapshot(dst)==current
 print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
