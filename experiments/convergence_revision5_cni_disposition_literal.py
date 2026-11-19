"""Replay a literal trigger check against measured NDA disposition citations."""

from collections import Counter
from pathlib import Path
import re
from statistics import mean

from experiments.convergence_revision5_cni_disposition_scope import (
    BOOTSTRAP, DATASET, DONE, HOME, POINTER, REVIEWS, ROOT, TASK, load_roster, materials, spans_for,
)
from experiments.convergence_pilot_b0 import read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


# Limited to explicit linked trigger forms in the reviewed TRAIN comparison.
CLOSURE = re.compile(
    r'\b(?:expir(?:ation|y)(?:\s*(?:/|or)\s*(?:other\s+)?termination)?|'
    r'termination(?:\s*(?:/|or)\s*expir(?:ation|y))?)\s+of\s*'
    r'(?:this|the)\s+(?:(?:confidentiality|non-disclosure)\s+agreement|agreement|project|business relationship)\b',
    re.I,
)
DISPOSITION = re.compile(r'\b(?:return(?:s|ed)?|destroy(?:s|ed)?|erase(?:s|d)?)\b', re.I)
INFORMATION = re.compile(r'\b(?:information|copies|materials?)\b', re.I)
LEAD_IN = re.compile(r'\b(?:upon|on|within|automatically upon|after|immediately on)\b', re.I)
CONTINUED_TRIGGER = re.compile(r'\b(?:immediately|promptly)\s+(?:on|upon)\s*$', re.I)


def positive_citations(spans):
    """Match a disposition and its own explicit timing phrase, including an adjacent list item."""
    text = [' '.join(s.split()).replace('relation- ship','relationship') for s in spans]
    support=[]
    for index,clause in enumerate(text):
        if not DISPOSITION.search(clause) or not INFORMATION.search(clause):
            continue
        if any(LEAD_IN.search(clause[max(0,m.start()-72):m.start()]) for m in CLOSURE.finditer(clause)):
            support.append({index})
        if (index+1 < len(text) and CONTINUED_TRIGGER.search(clause)
                and CLOSURE.search(text[index+1])):
            support.append({index,index+1})
    return support


def completed_source(citations, literal):
    """A recorded positive must already include the source-linked trigger or its list continuation."""
    return any(ids <= set(citations) for ids in literal)


def run():
    bound,cases=materials()
    live=read(POINTER)
    stage=ROOT/live['artifact_root']
    assert stage.name==digest(bound) and live['status']==DONE
    assert read(stage/'binding.json')==bound
    roster=load_roster(read(ROOT/read(BOOTSTRAP)['artifact_root']/'binding.json'))
    train=[s for batch in roster for s in batch if s['dataset']==DATASET]
    support_count=Counter(len(positive_citations(spans_for(next(v for v in s['views'] if v['id']==TASK))))
                          for s in train)
    grade_path=ROOT/bound['grade_path']
    assert sha(grade_path)==bound['grade_sha256']
    labels=read(grade_path)
    audit=[]
    for case,pair in zip(cases,read(stage/'paired_reads.json'),strict=True):
        kind, reviewed_positive, reviewed_spans=REVIEWS[tuple(case['pos'])]
        support=positive_citations(spans_for(case['view']))
        assert bool(support)==reviewed_positive
        assert all(ids<=set(reviewed_spans) for ids in support)
        literal_citations=sorted(set.union(*support)) if support else []
        # Only these six contracts have a separate scope review. With no positive
        # support, the narrow reader leaves contracts outside that scope unscored.
        prediction='Entailment' if support else 'NotMentioned'
        scored=grade_view(DATASET,case['view'],labels[case['source']][TASK],prediction,literal_citations)
        audit.append({
            'structure':kind, 'literal_exact':bool(scored['grade']),'literal_evidence_f1':scored['evidence_f1'],
            'literal_support_spans':len(literal_citations),
            'recorded_entailments_citing_linked_trigger':{role:
                value['answer']=='Entailment' and completed_source(value['evidence'],support)
                for role,value in pair.items()},
        })
    terminal = {'source_cue_TRAIN_mothers':len(train), 'candidate_lexical_row_count_histogram':dict(support_count),
                'scope_reviewed_mothers':len(audit),'literal_correct':sum(row['literal_exact'] for row in audit),
                'literal_evidence_f1':mean(row['literal_evidence_f1'] for row in audit),'cases':audit,
                'new_generation_calls':0,'DEV_or_TEST_opened':False,
                'retrospective_scope':'Rule derived on six inspected forms. Cases outside the independently reviewed six are unscored.',
                'bound_experiment_source_sha256':sha(Path(__file__)),'paired_terminal_sha256':sha(stage/'terminal.json')}
    immutable_json(HOME/'literal_audit.json',terminal)
    print(terminal,flush=True)


if __name__=='__main__':
    run()
