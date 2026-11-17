"""Metadata-only audit of official MAUD full-document template overlap.

The threshold/rule are fixed in source before any similarity is computed.
No target annotations, model outputs or task-specific keywords are read.
Failing candidates remain recorded; this audit never silently reselects TEST.
"""
from collections import defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import sqlite3
import zipfile

from experiments.two_method_heldout_exposure_gate import KNOWN_INCIDENT
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'
OLD=ROOT/'artifacts/two_method_followthrough_20261116'
ARCHIVE=Path('/media/sangfor/vdb/legal-skill-data/legal_skill_evolution_20261111/maud_data.zip')
MIN_JACCARD=0.90
NGRAM=5


def read(p):return json.loads(p.read_text())
def shingles(text):
    text=re.sub(r'["“][A-Z][A-Za-z0-9 .,&\'-]{2,80}["”]',' ENTITY ',text)
    text=re.sub(r'\d+',' NUMBER ',text.casefold())
    words=re.findall(r'[a-z_]+',text)
    return {tuple(words[i:i+NGRAM]) for i in range(len(words)-NGRAM+1)}


def run():
    summary=read(BASE/'handoff/normalized_inputs_current.json');data=ROOT/summary['artifact_root']
    identities=read(data/'identity_metadata.json')
    selected={r['original_id'] for r in identities if r['dataset']=='MAUD' and r['project_split']=='test'}
    exposure=read(OLD/'exposure/historical_exposure_index.json')
    if exposure['failures']:raise ValueError('Historical exposure gaps remain')
    keys=set(exposure['source_keys'])
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        keys.update(r[0] for r in db.execute('select distinct source from calls'))
        ledger_rows=db.execute('select count(*) from calls').fetchone()[0]
    for path in [Path(KNOWN_INCIDENT),*sorted((OLD/'exposure/incidents').glob('*.json'))]:
        for cohort in read(path)['conservative_affected_cohorts'].values():keys.update(cohort['sources'])
    keys.update(r['source'] for r in identities if r['project_split'] in ('train','dev'))
    with zipfile.ZipFile(ARCHIVE) as archive:
        texts={Path(n).stem:archive.read(n).decode('utf-8-sig') for n in archive.namelist()
            if n.startswith('data/contracts/') and n.endswith('.txt')}
    exposed={c for c in texts if 'MAUD:'+digest(c) in keys}
    features={c:shingles(text) for c,text in texts.items()}
    parent={c:c for c in texts}
    def find(c):
        while parent[c]!=c:
            parent[c]=parent[parent[c]];c=parent[c]
        return c
    edges=[]
    for a,b in combinations(sorted(texts),2):
        x,y=features[a],features[b]
        if not x or not y:raise ValueError('Empty full-document template')
        if min(len(x),len(y))/max(len(x),len(y))<MIN_JACCARD:continue
        intersection=len(x&y);similarity=intersection/(len(x)+len(y)-intersection)
        if similarity>=MIN_JACCARD:
            edges.append({'left':a,'right':b,'jaccard':similarity})
            ra,rb=find(a),find(b)
            if ra!=rb:parent[max(ra,rb)]=min(ra,rb)
    groups=defaultdict(list)
    for c in texts:groups[find(c)].append(c)
    exposed_roots={find(c) for c in exposed};violations=[]
    for c in sorted(selected):
        if find(c) in exposed_roots:
            violations.append({'candidate_original_id':c,'group':sorted(groups[find(c)]),
                'reason':'same_90percent_fulltext_template_component_as_known_exposed_or_TRAIN_DEV'})
    internal=[sorted(set(group)&selected) for group in groups.values() if len(set(group)&selected)>1]
    protocol={'name':'convergence_MAUD_full_document_nearduplicate_audit_v1','token_ngram':NGRAM,
        'jaccard_at_least':MIN_JACCARD,'normalization':'casefold; numbers; bounded quoted entities',
        'threshold_fixed_before_results':True,'transitive_components':True,
        'input_root':summary['artifact_root'],'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ledger_rows':ledger_rows,'exposed_keys_sha256':digest(sorted(keys)),
        'labels_or_scores_read':False,'TEST_source_text_displayed':False,'no_silent_reselection':True}
    out=BASE/'nearduplicate_audit_v1'/digest(protocol)
    immutable_json(out/'protocol.json',protocol);immutable_json(out/'similarity_edges.json',edges)
    immutable_json(out/'TEST_candidate_violations.json',{'historical_or_partition_overlap':violations,'internal_components':internal})
    result={'artifact_root':str(out.relative_to(ROOT)),'official_parent_documents':len(texts),
        'template_components':len(groups),'near_duplicate_edges':len(edges),
        'selected_TEST_candidates':len(selected),'selected_exposure_overlap':len(violations),
        'selected_internal_overlap_components':len(internal),'candidate_pass':not violations and not internal,
        'no_TEST_labels_or_text_displayed':True,'new_model_calls':0}
    immutable_json(out/'summary.json',result)
    (BASE/'handoff/contract_nearduplicate_current.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':run()
