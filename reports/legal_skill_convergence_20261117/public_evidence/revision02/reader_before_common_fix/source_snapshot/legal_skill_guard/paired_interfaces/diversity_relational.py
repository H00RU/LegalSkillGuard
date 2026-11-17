"""Real-source Diversity adapter over the existing residual synthesizer.

The common locator identifies named parties, role slots and sentence scope.
It never places a source citizenship, amount, native target or reference output
in the model's read input. Every control receives the same locator information.
TRAIN source-fidelity checks use the separate audit_source reference adapter.
"""
from functools import lru_cache
import hashlib
import inspect
from itertools import product
import re
from textwrap import dedent

from legal_skill_guard.paired_interfaces import residual,relational_program
from legal_skill_guard.paired_interfaces.diversity import TASK_RULES
from legal_skill_guard.skill_evolution.objects import digest

STATES=('Alabama','Alaska','Arizona','Arkansas','California','Colorado','Connecticut','Delaware',
    'Florida','Georgia','Hawaii','Idaho','Illinois','Indiana','Iowa','Kansas','Kentucky','Louisiana',
    'Maine','Maryland','Massachusetts','Michigan','Minnesota','Mississippi','Missouri','Montana',
    'Nebraska','Nevada','New Hampshire','New Jersey','New Mexico','New York','North Carolina',
    'North Dakota','Ohio','Oklahoma','Oregon','Pennsylvania','Rhode Island','South Carolina',
    'South Dakota','Tennessee','Texas','Utah','Vermont','Virginia','Washington','West Virginia',
    'Wisconsin','Wyoming',None)


def citizenship(u,c):
    return {'different':None if u['plaintiff_state'] is None or u['defendant_state'] is None
            else u['plaintiff_state']!=u['defendant_state']}


def single_claim(u,c):
    return {'enough':None if u['claim0'] is None else u['claim0']>75}


def same_pair_claims(u,c):
    return {'enough':None if u['claim0'] is None or u['claim1'] is None
            else u['claim0']+u['claim1']>75}


@lru_cache(maxsize=3)
def module(kind):
    if kind=='citizenship':
        fn=citizenship;domains={'plaintiff_state':STATES,'defendant_state':STATES}
        meanings={'plaintiff_state':'citizenship state of the named plaintiff',
                  'defendant_state':'citizenship state of the named defendant'}
    elif kind in ('single_claim','same_pair_claims'):
        fn=single_claim if kind=='single_claim' else same_pair_claims
        # Exact coordinate abstraction for nonnegative whole-thousand amounts:
        # min(a,76)+min(b,76)>75 iff a+b>75. If either exceeds75,
        # nonnegativity makes both comparisons true; otherwise neither changes.
        # This explicit theorem, not extrapolation of a finite truth table,
        # covers arbitrarily large amounts. Fractions must be unread, not round.
        domains={'claim'+str(i):[*range(77),None] for i in range(1 if kind=='single_claim' else 2)}
        meanings={k:'amount in whole thousands of dollars of claim '+k[-1]+' asserted by this same plaintiff against this same defendant, in textual order; cap at76 (76 means at least $76,000). Do not round a fractional thousand; use unread instead' for k in domains}
    else:raise ValueError('Unsupported audited local module')
    code=dedent(inspect.getsource(fn))
    return residual.FiniteModule.build(kind,domains,[{}],fn,
        consumer_sha256=hashlib.sha256(code.encode()).hexdigest(),
        source_scope={'source_fields':['source_text'],'local_unit':kind+' for the named source-local party pair',
                      'field_meanings':meanings,**({'source_abstraction':{
                          'kind':'nonnegative_integer_thousand_cap','cap':76,'comparison_threshold':75,
                          'proof':'for nonnegative a,b: if either>75 both sums>75; otherwise clipping changes neither',
                          'fractional_thousand_inputs_supported':False}} if kind!='citizenship' else {})},program_source=code)


@lru_cache(maxsize=3)
def candidates(kind):
    spec=module(kind);pool=residual.propose(spec,relational=True,max_new=8)
    # No static candidate is called learned. The raw correct interface remains
    # a strong control; actual TRAIN reads choose among generated candidates.
    return [pool['baseline'],*pool['candidates']]


def locator(text):
    names=re.findall(r'\b(\w+) is from [^.]+\.',text)
    if len(names)!=len(set(names)):raise ValueError('Ambiguous public party identity')
    claims=[];plaintiffs=set();defendants=set()
    for sentence in text.split('. '):
        if ' sue' not in sentence:continue
        match=re.match(r'(.+?) (?:both sue|sues|sue) (.+?)(?: each)? for (.+)',sentence)
        if not match:raise ValueError('Unsupported claim attachment syntax')
        ps,ds,tail=match.groups();ps=ps.split(' and ');ds=ds.split(' and ')
        # Counting visible amount mentions specifies local arity. Their actual
        # values are deliberately not extracted or supplied to the reader.
        count=len(re.findall(r'\$[\d,]+',tail))
        if count not in (1,2):raise ValueError('Consumer covers one or two claims per represented pair')
        plaintiffs.update(ps);defendants.update(ds)
        claims.extend({'plaintiff':p,'defendant':d,'claim_count':count} for p in ps for d in ds)
    if not claims or not plaintiffs|defendants<=set(names) or plaintiffs&defendants:
        raise ValueError('Source role/identity scope is unresolved')
    if len({(r['plaintiff'],r['defendant']) for r in claims})!=len(claims):
        raise ValueError('Multiple sentences for one pair require a recertified aggregation module')
    return {'plaintiffs':sorted(plaintiffs),'defendants':sorted(defendants),'claim_groups':claims,
        'locator_is_shared_with_all_controls':True,'source_values_or_native_labels_supplied':False}


def program(source,choices):
    view=source['views'][0];public=view['public'];scope=locator(public['source_text'])
    units={};different=[];sufficient=[]
    def unit(name,kind,context):
        asset=candidates(kind)[choices[kind]]
        units[name]={'asset':asset,'asset_sha256':digest(asset),'module_binding':asset['module_binding'],
            'context':{},'template_key':kind+':'+asset['version'],'entity_context':context}
    for i,(p,d) in enumerate(product(scope['plaintiffs'],scope['defendants'])):
        name='citizenship_pair_'+str(i);unit(name,'citizenship',{'plaintiff':p,'defendant':d})
        different.append({'local':[name,'different']})
    for i,row in enumerate(scope['claim_groups']):
        kind='single_claim' if row['claim_count']==1 else 'same_pair_claims'
        name='claim_pair_'+str(i);unit(name,kind,row);sufficient.append({'local':[name,'enough']})
    guard={'all':[{'all':different},{'all':sufficient}]}
    return relational_program.sealed({'units':units,
        'outputs':{view['id']:{'if':guard,'then':{'constant':'Yes'},'else':{'constant':'No'}}},
        'diagnostics':{'parties_are_diverse':{'all':different},'aic_is_met':{'all':sufficient}},
        'composition_certificate':{'local_certificates_preserved':True,
            'claim_aggregation_cannot_exchange_plaintiff_defendant_pairs':True,
            'source_English_or_benchmark_legal_correctness_certified':False}})


def views(source):
    if source['dataset']!='LegalBench_Diversity' or len(source['views'])!=1:raise ValueError('Explicit Diversity native task required')
    public=source['views'][0]['public'];scope=locator(public['source_text'])
    kinds=['citizenship',*sorted({'single_claim' if r['claim_count']==1 else 'same_pair_claims' for r in scope['claim_groups']})]
    plans=[]
    for indices in product(*(range(len(candidates(k))) for k in kinds)):
        choices=dict(zip(kinds,indices));p=program(source,choices)
        plan={'name':'synthesized:'+digest(choices)[:16],'reader_kind':'consumer_relational_program',
            'relational_program':p,'source_public_sha256':digest(source),
            'schema':relational_program.schema(p),'system':relational_program.prompt(p),
            'choices':choices,'candidate_origin':'existing_residual.propose_from_audited_local_consumer_AST',
            'is_correct_fixed_raw_control':all(i==0 for i in indices)}
        plan['version']=digest(plan);plans.append(plan)
    return [{'source':source['key'],'dataset':source['dataset'],'view':'native',
        'native_tasks':[source['views'][0]['id']],'native_public':{source['views'][0]['id']:public},
        'source_units':[],'plans':plans,'scope':{'schema':'diversity_relational_program_v1','context':'fixed_native_rules'},
        'relational_public_source':{'source_text':public['source_text']},
        'read_input':{'source_text':public['source_text'],'rules':public.get('rules',TASK_RULES)},
        'pre_generation_domain_refusal':False}]


class Provider:
    def views(self,source):return views(source)
    def verify_plan(self,source,view,plan):
        if (plan['source_public_sha256']!=digest(source) or plan['version']!=digest({k:v for k,v in plan.items() if k!='version'})):
            raise ValueError('Source-bound synthesized program changed')
        relational_program.verify(plan['relational_program'])
