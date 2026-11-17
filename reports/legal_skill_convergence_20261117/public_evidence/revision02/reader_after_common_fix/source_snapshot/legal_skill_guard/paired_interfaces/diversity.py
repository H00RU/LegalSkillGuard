"""LegalBench Diversity source/score adapter for the fixed convergence study.

The deterministic parser is an independent TRAIN audit/reference capability,
not the weak reader or an inference shortcut unique to either method. Public
inputs contain the original text and never the three native annotation fields.
Task conventions here are those audited by the pinned study configuration,
not a general statement of civil procedure.
"""
from collections import defaultdict
import hashlib
import re


GOLD_FIELDS=frozenset({'answer','parties_are_diverse','aic_is_met'})
REVISION='daec8237410aa23e3faf4bc41ad8b3a7e1696826'
# Common public task convention, supplied identically to every arm. These are
# rules, not a solved example or any row's native annotation. README provenance
# is pinned separately by the study's source-preparation receipt.
TASK_RULES=(
    'For this benchmark, diversity jurisdiction requires both complete diversity '
    'and a sufficient amount in controversy. No plaintiff may share citizenship '
    'with any defendant; citizenship may be shared within either side. For each '
    'plaintiff-defendant pair asserted in the facts, add only that same pair\'s '
    'claims. Do not combine different plaintiffs or different defendants. Each '
    'asserted pair must exceed $75,000. Equality to $75,000 is insufficient.'
)
TASK_QUESTION='Is there diversity jurisdiction?'


def audit_source(text):
    citizens=re.findall(r'(\w+) is from ([^.]+)\.',text)
    citizenship=dict(citizens)
    if len(citizens)!=len(citizenship):raise ValueError('Duplicate named citizenship assertion')
    claims=[]
    for sentence in text.split('. '):
        if ' sue' not in sentence:continue
        match=re.search(r'^(.+?) (?:both sue|sues|sue) (.+?)(?: each)? for (.+)',sentence)
        if not match:raise ValueError('Unsupported claim sentence; repair the adapter, not the source roster')
        plaintiffs,defendants,tail=match.groups()
        amounts=[int(v.replace(',','')) for v in re.findall(r'\$([\d,]+)',tail)]
        if not amounts:raise ValueError('An asserted claim lacks an explicit amount')
        for plaintiff in plaintiffs.split(' and '):
            for defendant in defendants.split(' and '):
                for amount in amounts:claims.append({'plaintiff':plaintiff,'defendant':defendant,'amount':amount})
    if not claims:raise ValueError('No supported plaintiff/defendant claim structure')
    parties={c[k] for c in claims for k in ('plaintiff','defendant')}
    if not parties<=set(citizenship):raise ValueError('A claim participant lacks source citizenship')
    return {'citizenship':citizenship,'claims':claims,'source_text_sha256':hashlib.sha256(text.encode()).hexdigest()}


def reference_outputs(record):
    citizens=record['citizenship'];claims=record['claims']
    plaintiffs={c['plaintiff'] for c in claims};defendants={c['defendant'] for c in claims}
    diverse=all(citizens[p]!=citizens[d] for p in plaintiffs for d in defendants)
    totals=defaultdict(int)
    for c in claims:totals[c['plaintiff'],c['defendant']]+=c['amount']
    amount=all(v>75000 for v in totals.values())
    return {'answer':'Yes' if diverse and amount else 'No',
            'parties_are_diverse':diverse,'aic_is_met':amount}


def structural_group(record):
    """Name-invariant same-state, role/claim and exact-amount grouping.

    Canonicalize by every role-preserving party renaming; a textual name or
    variant index never creates a new independent mother source. This key is
    metadata for the isolated splitter, never a model input or an answer field.
    """
    from itertools import permutations
    from legal_skill_guard.skill_evolution.objects import digest
    claims=record['claims'];ps=sorted({c['plaintiff'] for c in claims});ds=sorted({c['defendant'] for c in claims})
    if set(ps)&set(ds):raise ValueError('This adapter requires disjoint plaintiff and defendant role sets')
    representations=[]
    for plaintiffs in permutations(ps):
        for defendants in permutations(ds):
            names={**{name:'p'+str(i) for i,name in enumerate(plaintiffs)},
                   **{name:'d'+str(i) for i,name in enumerate(defendants)}}
            ordered=[*plaintiffs,*defendants];states={};pattern=[]
            for name in ordered:
                state=record['citizenship'][name]
                if state not in states:states[state]=len(states)
                pattern.append(states[state])
            edges=sorted((names[c['plaintiff']],names[c['defendant']],c['amount']) for c in claims)
            representations.append((tuple(pattern),tuple(edges)))
    return digest({'role_sizes':[len(ps),len(ds)],'name_invariant_structure':min(representations)})


def public_source(row,variant,*,project_split):
    from legal_skill_guard.skill_evolution.objects import digest
    if project_split not in ('train','dev','test'):raise ValueError('Explicit project partition required')
    native_split='train' if project_split=='train' else 'test'
    # Native row indices restart in each split. Omitting native_split aliases
    # unrelated TRAIN/TEST cases even though their source texts differ.
    source_id='LegalBench_Diversity:'+digest({'revision':REVISION,'variant':variant,
        'native_split':native_split,'native_index':str(row['index'])})
    return {'key':source_id,'dataset':'LegalBench_Diversity','dataset_revision':REVISION,
        'native_config':variant,'native_id':str(row['index']),'native_split':native_split,'project_split':project_split,
        'split':project_split,'parent_id':source_id,
        'views':[{'id':'native','public':{'source_text':row['text'],
            'question':TASK_QUESTION,'rules':TASK_RULES},
            'answer_schema':{'type':'string','enum':['Yes','No']}}]}


def annotation(row):
    def boolean(value):
        if str(value).lower() not in ('true','false'):raise ValueError('Invalid native intermediate label')
        return str(value).lower()=='true'
    if row['answer'] not in ('Yes','No'):raise ValueError('Invalid native final label')
    return {'native':{'answer':row['answer'],'diagnostics':{
        'parties_are_diverse':boolean(row['parties_are_diverse']),'aic_is_met':boolean(row['aic_is_met'])}}}


def score(predictions,annotations):
    """Native balanced accuracy plus accuracy; no mixed-unit five-way average."""
    if set(predictions)!=set(annotations) or not predictions:raise ValueError('Score the full fixed source denominator')
    by_class=defaultdict(list)
    for source,prediction in predictions.items():
        target=annotations[source]['native']['answer']
        if target not in ('Yes','No'):raise ValueError('Invalid native class')
        by_class[target].append(int(prediction==target))
    accuracy=sum(sum(v) for v in by_class.values())/len(predictions)
    balanced=sum(sum(v)/len(v) for v in by_class.values())/len(by_class)
    return {'accuracy':accuracy,'balanced_accuracy':balanced,'sources':len(predictions),
            'class_counts':{k:len(v) for k,v in by_class.items()},'invalid_or_abstained':sum(v not in ('Yes','No') for v in predictions.values())}
