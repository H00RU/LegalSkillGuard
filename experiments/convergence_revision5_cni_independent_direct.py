"""Attribute the paired independent-route reads against an explicit clause control."""

import json
from pathlib import Path
import re
from statistics import mean

from experiments.convergence_pilot_b0 import ROOT, read, sha
from experiments.convergence_revision5_cni_independent_routes import (
    DATASET, DONE, POINTER, TASKS, UNKNOWN, YES, materials, spans_for,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


ITEM = re.compile(r'^\((?:[A-Za-z]+|\d+)\)\s')
HEADER = re.compile(
    r'(?:not have breached any obligation|obligations? .{0,90}shall not (?:apply|extend)|'
    r'confidential information.{0,280}(?:does not include|except information which)|shall exclude)',re.I)
DEVELOPMENT = re.compile(r'\bindependent(?:ly| development)\b',re.I)
NON_USE = re.compile(r'\b(?:without (?:use|reference)|independently (?:of|developed)|developed independently|independently develop)\b',re.I)
RECEIPT = re.compile(
    r'\b(?:received|obtained|available|revealed|disclosed|furnished|acquir\w*)\b.{0,200}'
    r'\b(?:third[- ]party|another source|a source not known|source other than|other persons)\b',re.I)
LAWFUL = re.compile(r'\b(?:lawful\w*|rightful\w*|free (?:of|to disclose)|without (?:breach|restriction)|'
                    r'not known|unless such party|who did not receive)\b',re.I)
PAST_ONLY = re.compile(r'\b(?:at or prior to|before|prior to) (?:the time of )?(?:disclosure|receipt)\b',re.I)
EXPRESS_RIGHT = re.compile(r'\b(?:shall not (?:be construed to limit|preclude or limit)|right to independently)\b',re.I)


def direct(case):
    """Scope the active item before checking time and independent source."""
    clauses = [' '.join(t.split()) for t in spans_for(case['views']['development'])]
    paths = {kind:[] for kind in TASKS}
    earlier = []
    heading = None
    parent = None
    for i,text in enumerate(clauses):
        if HEADER.search(text) and text.rstrip().endswith((':','cases:')):
            heading, parent = i,None
        elif heading is not None and not ITEM.search(text):
            if re.fullmatch(r'the receiving party can show',text,re.I):
                parent = i
            elif text:
                heading,parent=None,None
        elif ITEM.search(text):
            if parent is not None and re.match(r'^\([ivx]+\)',text):
                parent = None
            if re.search(r'\bthe receiving party can show\b',text,re.I):
                parent = i
        if not text:
            continue
        if ITEM.search(text) and heading is not None:
            anchors = [heading,*([parent] if parent is not None and parent!=i else []),i]
            if DEVELOPMENT.search(text) and NON_USE.search(text):
                (earlier if PAST_ONLY.search(text) else paths['development']).append(anchors)
            if RECEIPT.search(text) and LAWFUL.search(text) and not PAST_ONLY.search(text):
                if not re.search(r'\bcommunicated by such Discloser to an unaffiliated third party\b',text,re.I):
                    paths['receipt'].append(anchors)
        if EXPRESS_RIGHT.search(text) and DEVELOPMENT.search(text) and NON_USE.search(text):
            paths['development'].append([i])
    result={}
    for kind,groups in paths.items():
        if groups:
            result[kind]={'answer':YES,'evidence':sorted({i for group in groups for i in group}),
                          'witnesses':groups}
        else:
            closed = kind=='development' and (earlier or not any(DEVELOPMENT.search(t) for t in clauses))
            result[kind]={'answer':UNKNOWN if closed else None,'evidence':[],'witnesses':earlier if closed else []}
    return result


def has_scope_evidence(case, kind, observed, direct):
    if observed['answer']!=case['independent_expected'][kind]:
        return False
    if observed['answer']==UNKNOWN:
        if case['stratum']=='prior_only_development_then_third_party_receipt':
            raw = {26,28}<=set(observed.get('raw_evidence',()))
            return raw or any({26,28}<=set(w) for w in observed.get('witnesses',()))
        return True
    witnesses = direct[kind]['witnesses'] if direct[kind]['answer']==YES else []
    # The independent review supplies a separate conservative backup path.
    full_witness = case['independent_witnesses'][list(TASKS).index(kind)]
    if full_witness:
        witnesses = [*witnesses,full_witness]
    return any(set(w)<=set(observed['evidence']) for w in witnesses)


def run():
    stage=ROOT/read(POINTER)['artifact_root']
    terminal=read(stage/'terminal.json')
    assert terminal['status']==DONE
    binding,cases,bank=materials()
    assert digest(binding)==stage.name and read(stage/'binding.json')==binding and read(stage/'cases.json')==cases
    assert all(sha(stage/'source_snapshot'/f)==h for f,h in binding['sources_sha256'].items())
    records=read(stage/'predictions.json')
    measurements=[]
    for case,pair in zip(cases,records,strict=True):
        direct_scope=direct(case)
        data={'stratum':case['stratum'],'source':case['source'],'observations':{}}
        for role in ('original','fixed','synthesized','retrospective_direct'):
            if role=='original':
                raw={kind:bank[case['source']]['native'][task] for kind,task in TASKS.items()}
                observations={kind:{'answer':x['answer'],'evidence':x['evidence_sentence_ids'],
                                    'raw_evidence':x['evidence_sentence_ids']} for kind,x in raw.items()}
            elif role=='retrospective_direct':
                observations=direct_scope
            else:
                observations=pair[role]['observation']
            data['observations'][role] = {
                kind:{**x,'source_witness':has_scope_evidence(case,kind,x,direct_scope)} for kind,x in observations.items()}
        measurements.append(data)
    params={'TRAIN_binding':stage.name,'TRAIN_terminal_sha256':sha(stage/'terminal.json'),
            'comparison_source_sha256':sha(Path(__file__)),
            'direct_policy':'Retrospective scope-bound literal clause scanner'}
    out=stage/'attribution'/digest(params)
    immutable_json(out/'prediction_attribution.json',measurements)
    path=ROOT/binding['grade_path']
    assert sha(path)==binding['grade_sha256']
    grades=read(path)
    metrics={role:{k:[] for k in TASKS} for role in ('original','fixed','synthesized','retrospective_direct')}
    cases_by_stratum={c['stratum']:c for c in cases}
    rows=[]
    for row in measurements:
        source=row['source']
        case=cases_by_stratum[row['stratum']]
        public={'stratum':row['stratum'],'scores':{}}
        for role,outputs in row['observations'].items():
            public['scores'][role]={}
            for kind,result in outputs.items():
                score=grade_view(DATASET,case['views'][kind],grades[source][TASKS[kind]],result['answer'],result['evidence'])
                measures={'exact':score['grade'],'joint_evidence':score['grade']*score['evidence_f1'],
                          'source_witness':result['source_witness'],'emitted':result['answer'] is not None}
                metrics[role][kind].append(measures)
                public['scores'][role][kind]=measures
        rows.append(public)
    summary={'matched_scope_scores':{role:{kind:{k:mean(r[k] for r in data) for k in data[0]}
                                           for kind,data in groups.items()} for role,groups in metrics.items()},
             'per_source_structure':rows,
             'live_comparison':terminal,
             'retrospective_control_runner_sha256':params['comparison_source_sha256'],
             'no_additional_requests':True}
    immutable_json(out/'summary.json',summary)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),'matched_scope_scores':summary['matched_scope_scores']},
                     sort_keys=True),flush=True)


if __name__=='__main__':
    run()
