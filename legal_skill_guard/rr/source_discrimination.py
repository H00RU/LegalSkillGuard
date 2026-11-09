"""Source-bound finite programs learned from TRAIN frame/contrast supervision.

Ordered-span matching, a phrase dictionary and finite constraint execution are
shared baseline machinery. A match is not a proof of natural-language meaning.
"""
from itertools import product
import re
from .semantic_frames import occurrences, label

ROLES = ('payer', 'payee', 'work_activity', 'payment_medium')
CLASS_FIELDS = {'work_activity': 'work_is_agricultural',
                'payment_medium': 'payment_is_agricultural_product'}


def find_spans(text,value):
    return occurrences(text,value) if value is not None and value in text else []


def sentence_spans(text):
    # Numeric decimal points do not split a unit. A sentence is only a lexical
    # locality guard, not an assertion that all its entities form one event.
    start = 0
    for match in re.finditer(r'[.!?](?=\s|$)', text):
        yield start, match.end()
        start = match.end()
    if start < len(text): yield start, len(text)


def _positions(text, frame):
    result = {}
    for role in ROLES:
        value = frame[role]
        positions = occurrences(text, value)
        if len(positions) > 1: raise ValueError('Induction needs an unambiguous annotated occurrence')
        result[role] = positions[0] if positions else None
    return result


def learn_selector(examples):
    """Ordinary same-information wrapper learner; no confusion-pair objective."""
    if not examples: raise ValueError('Need actual verified source annotations')
    lexicon = {role: {} for role in CLASS_FIELDS}
    positions = []; left_cues={r:[] for r in ROLES}
    for e in examples:
        pos = _positions(e['facts'], e['frame']); positions.append(pos)
        for role,span in pos.items():
            if span is None:continue
            tokens=re.findall(r'\b[A-Za-z]+\b|[^\w\s]',e['facts'][:span[0]])
            # This operator is a lexical word cue. Punctuation belongs to unit
            # segmentation, and must not become a required semantic-role token.
            left_cues[role].append(tokens[-1] if tokens and tokens[-1].isalpha() else None)
        for role, field in CLASS_FIELDS.items():
            phrase = e['frame'][role]
            if phrase is None: continue
            value = label(e['frame'][field])
            lexicon[role].setdefault(phrase, set()).add(value)
    precedence = []
    for left in ROLES:
        for right in ROLES:
            if left == right: continue
            observed = [(p[left], p[right]) for p in positions if p[left] and p[right]]
            if observed and all(a[1] <= b[0] for a, b in observed): precedence.append([left, right])
    local = all(any(all(p is None or a <= p[0] < p[1] <= b for p in positions[i].values())
                        for a,b in sentence_spans(e['facts'])) for i,e in enumerate(examples))
    return {'lexicon': {r: {p: sorted(v) for p,v in words.items()} for r,words in lexicon.items()},
            'precedence': precedence, 'same_sentence': local,
            'left_cues': {r:v[0] if v and v[0] is not None and len(set(v))==1 else None for r,v in left_cues.items()},
            'training_mothers': sorted({e['mother'] for e in examples}),
            'training_cases': [e['case_id'] for e in examples],
            'unknown_on_unseen_phrase': True, 'semantic_certificate': False}


def execute_selector(program, text, focus):
    units = list(sentence_spans(text)) if program['same_sentence'] else [(0,len(text))]
    candidates = []
    for start, end in units:
        source = text[start:end]
        options = {r: [(focus[r], [start+a,start+b]) for a,b in find_spans(source, focus[r])]
                   for r in ('payer','payee')}
        if not options['payer'] or not options['payee']: continue
        for role in CLASS_FIELDS:
            options[role] = [(phrase,[start+a,start+b]) for phrase in program['lexicon'][role]
                             for a,b in find_spans(source,phrase)]
            # Null means unrecognized/unsupported by this finite learned lexicon.
            # It does not assert that no medium or activity exists in the text.
            options[role].append((None,None))
        for role,cue in program['left_cues'].items():
            if cue is None:continue
            def matches_cue(value):
                if value[1] is None:return True
                tokens=re.findall(r'\b[A-Za-z]+\b|[^\w\s]',text[start:value[1][0]])
                return bool(tokens) and tokens[-1]==cue
            options[role]=[v for v in options[role] if matches_cue(v)]
        for values in product(*(options[r] for r in ROLES)):
            binding=dict(zip(ROLES,values))
            if any(binding[a][1] and binding[b][1] and binding[a][1][1] > binding[b][1][0]
                   for a,b in program['precedence']):continue
            candidates.append({'spans':{r:v[1] for r,v in binding.items()},
                               'values':{r:v[0] for r,v in binding.items()}, 'unit':[start,end]})
    # Keep all maximal compatible bindings; no first-match hidden default.
    maximal=[]
    for c in candidates:
        if not any(all(c['spans'][r] is None or c['spans'][r]==other['spans'][r] for r in ROLES)
                   and sum(v is not None for v in other['spans'].values()) > sum(v is not None for v in c['spans'].values())
                   for other in candidates if other['unit']==c['unit']):maximal.append(c)
    classifications=[]
    for c in maximal:
        values={**c['values']}
        h=[]
        for role,field in CLASS_FIELDS.items():
            labels=program['lexicon'][role].get(values[role],[])
            v=labels[0] if len(labels)==1 else 2
            values[field]=None if v==2 else bool(v);h.append(v)
        c['values']=values;c['h']=h;classifications.append(h)
    unanimous=classifications[0] if classifications and all(x==classifications[0] for x in classifications) else [2,2]
    return {'candidates':maximal,'prediction':unanimous,'unresolved':not classifications or unanimous==[2,2],
            'new_model_calls':0,'source_meaning_proved':False,'classification_source':'TRAIN verified role/phrase labels only'}


def path_value(path,features):
    if path['operator']=='constant':return path['value']
    value=features[path['role']]
    return 1-value if path['operator']=='negate' and value!=2 else value


def learn_evidence_paths(examples,*,contrast=True):
    """Enumerate a finite evidence grammar; never assign an output its own role.

    The target IDs are opaque. Features use one shared TRAIN phrase lexicon;
    source role names do not determine target-to-path correspondence.
    All consistent paths survive, including indistinguishable constants.
    """
    lexicon={}
    for e in examples:
        for role,field in CLASS_FIELDS.items():
            phrase=e['frame'][role]
            if phrase is not None:lexicon.setdefault(phrase,set()).add(label(e['frame'][field]))
    lexicon={phrase:sorted(values) for phrase,values in lexicon.items()}
    rows=[]
    for e in examples:
        features={}
        for role in CLASS_FIELDS:
            values=lexicon.get(e['frame'][role],[])
            features[role]=values[0] if len(values)==1 else 2
        targets=e.get('targets',[label(e['frame'][f]) for f in CLASS_FIELDS.values()])
        rows.append({'case_id':e['case_id'],'mother':e['mother'],'features':features,'targets':targets})
    pairs=[(a,b) for i,a in enumerate(rows) for b in rows[:i] if a['mother']==b['mother']]
    grammar=[{'operator':operator,'role':role} for role in CLASS_FIELDS for operator in ('read','negate')]
    grammar += [{'operator':'constant','value':value} for value in range(3)]
    targets=[]
    for target in range(2):
        candidates=[]
        for path in grammar:
            mismatch=[r['case_id'] for r in rows if path_value(path,r['features'])!=r['targets'][target]]
            contrast_mismatch=[]
            for a,b in pairs:
                predicted=(path_value(path,a['features']),path_value(path,b['features']))
                required=(a['targets'][target],b['targets'][target])
                if (predicted[0]!=predicted[1]) != (required[0]!=required[1]):
                    contrast_mismatch.append([a['case_id'],b['case_id']])
            candidates.append({'path':path,'point_mismatch_cases':mismatch,'contrast_mismatch_pairs':contrast_mismatch,
                               'consistent':not mismatch and (not contrast or not contrast_mismatch)})
        point_version=[c['path'] for c in candidates if not c['point_mismatch_cases']]
        version=[c['path'] for c in candidates if c['consistent']]
        targets.append({'target_index':target,'candidates':candidates,'consistent_paths':version,
                        'point_supervision_alone_paths':point_version,
                        'contrast_removes_point_consistent_paths':len(point_version)-len(version),
                        'identified_on_this_grammar':len(version)==1})
    return {'phrase_lexicon':lexicon,'training_rows':rows,'paired_source_cases':[
                [a['case_id'],b['case_id']] for a,b in pairs],
            'grammar':grammar,'targets':targets,'contrast_enabled':contrast,
            'target_role_mapping_hardcoded':False,'semantic_certificate':False,
            'unknown_branch':'No consistent program or disagreeing consistent outputs returns unknown',
            'full_point_labels_make_observed_pair_changes_redundant':True}


def execute_paths(learning,binding_candidates):
    predictions=[]
    for candidate in binding_candidates:
        features={}
        for role in CLASS_FIELDS:
            values=learning['phrase_lexicon'].get(candidate['values'][role],[])
            features[role]=values[0] if len(values)==1 else 2
        outputs=[]
        for target in learning['targets']:
            answers={path_value(p,features) for p in target['consistent_paths']}
            outputs.append(next(iter(answers)) if len(answers)==1 else 2)
        predictions.append(outputs)
    return predictions[0] if predictions and all(p==predictions[0] for p in predictions) else [2,2]


def compile_discrimination(examples):
    selector=learn_selector(examples);confusions=[];invariance=[]
    dependencies=learn_evidence_paths(examples)
    constraints=[{'kind':'target_reads_learned_source_paths','target_index':t['target_index'],
                  'paths':t['consistent_paths'],'identified':t['identified_on_this_grammar']}
                 for t in dependencies['targets']]
    for e in examples:
        truth=[label(e['frame'][f]) for f in CLASS_FIELDS.values()]
        for mode in ('direct','reader'):
            observed=e[mode]
            for i,role in enumerate(CLASS_FIELDS):
                if observed[i]!=truth[i]:confusions.append({'case_id':e['case_id'],'mother':e['mother'],
                    'output_role':role,'observed':observed[i],'verified':truth[i],
                    'binding_constraint':constraints[i], 'reader':mode})
    for e in examples:
        for other in examples:
            if e['mother']!=other['mother'] or e['case_id']>=other['case_id']:continue
            changed=[r for r in CLASS_FIELDS if e['frame'][r]!=other['frame'][r]]
            invariant=[r for r in CLASS_FIELDS if e['frame'][r]==other['frame'][r]]
            invariance.append({'cases':[e['case_id'],other['case_id']], 'changed_source_roles':changed,
                               'invariant_source_roles':invariant, 'evidence':'Verified real TRAIN controlled span edit'})
    questions=sorted({q for e in examples for q in e['questions']})
    actions=[];uncompiled=[]
    for q in questions:
        supported_roles=[role for role,phrases in selector['lexicon'].items() if any(p in q for p in phrases)]
        if len(supported_roles)!=1:
            uncompiled.append({'question':q,'reason':'Question has no unique TRAIN phrase-to-role mapping'});continue
        actions.append({'role':supported_roles[0],'question_template':q,
            'output_schema':{'type':'object','properties':{'span':{'anyOf':[{'type':'string'},{'type':'null'}]}},
                             'required':['span'],'additionalProperties':False},
            'answer_map':'Keep candidates whose stated role span equals the returned exact source span; null keeps all',
            'answer_is_fallible':True,'cache_identity':'Exact dispatched prompt/schema only'})
    return {'selector':selector,'confusions':confusions,'source_role_invariance':invariance,
            'learned_evidence_paths':dependencies,'answer_constraints':constraints,
            'question_templates':questions,'question_actions':actions,'uncompiled_questions':uncompiled,
            'unknown_branch':'Keep every compatible binding; unseen role phrases stay unknown',
            'semantic_certificate':False,'empty':not confusions}


def plan_questions(skill,candidates,focus):
    if not candidates:return {'actions':[],'status':'candidate_not_covered','none_of_the_above':True}
    actions=[]
    for action in skill['question_actions']:
        role=action['role']
        if len({c['values'][role] for c in candidates})<2:continue
        question=action['question_template'].format(**focus)
        actions.append({**action,'question':question,'necessary_role':role})
    return {'actions':actions,'status':'ambiguous' if actions else 'no_distinguishing_question_needed_or_available',
            'none_of_the_above':True,'all_unissued_questions_unobserved':True}


def constrain_bindings(candidates,role,answer,text):
    if role not in CLASS_FIELDS:raise ValueError('Question role is not in the compiled local interface')
    if set(answer)!={'span'}:raise ValueError('Question answer must match its exact schema')
    if answer['span'] is None:return {'retained':candidates,'status':'unknown','semantic_certificate':False}
    occurrences(text,answer['span'])
    kept=[c for c in candidates if c['values'][role]==answer['span']]
    return {'retained':kept,'status':'proposed_constraint' if kept else 'answer_outside_candidate_set',
            'none_of_the_above':True,'semantic_certificate':False,
            'may_drop_correct_interpretation_if_reader_is_wrong':True}


def apply_constraints(skill, text, focus, observed):
    actual=execute_selector(skill['selector'],text,focus)
    actual['source_role_predictions']=actual['prediction']
    actual['prediction']=execute_paths(skill['learned_evidence_paths'],actual['candidates'])
    actual['unresolved']=not actual['candidates'] or actual['prediction']==[2,2]
    # These are new predictions from a learned source program. The received
    # model answer and any rejected frame remain unchanged in their records.
    return {**actual, 'actual_reader_answer':observed,
            'disagreements': [i for i,(a,b) in enumerate(zip(actual['prediction'],observed)) if a!=b],
            'constraints_executed':skill['answer_constraints'],
            'question_plan':plan_questions(skill,actual['candidates'],focus),
            'questions_executed_from_cache':[],
            'not_previously_asked_questions_must_be_dispatched':True}
