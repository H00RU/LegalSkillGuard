"""Finite empirical, source-clustered channel prototype. No model calls."""
from dataclasses import dataclass, replace
from collections import defaultdict
import math
import numpy as np
from scipy.optimize import linprog

@dataclass(frozen=True, order=True)
class Graph:
    # Fixed typed nodes: persons claimant/respondent, events 0/1. Anchors persist.
    claimant: int
    respondent: int
    exception_event: int
    anchor: str = 'TRAIN-schema-v1'
    def __post_init__(self):
        if any(x not in (0, 1) for x in (self.claimant, self.respondent, self.exception_event)):
            raise ValueError('outside finite typed domain')

EDITS = {
    'identity': lambda g: g,
    'role_swap': lambda g: replace(g, claimant=g.respondent, respondent=g.claimant),
    'reattach_exception': lambda g: replace(g, exception_event=1-g.exception_event),
    'joint_swap_reattach': lambda g: replace(g, claimant=g.respondent, respondent=g.claimant,
                                          exception_event=1-g.exception_event),
}

@dataclass(frozen=True)
class Pair:
    source_id: str
    reference: Graph
    observed: Graph
    plan_version: str
    context: str = 'two-person-two-event'
    split: str = 'calibration'
    provenance: str = 'synthetic fixture; not legal evidence'

def canonicalize_pair(pair):
    candidates = [name for name, edit in EDITS.items() if edit(pair.reference) == pair.observed]
    return {'candidate_joint_edits': candidates, 'ambiguous': len(candidates)>1,
            'unmatched': not candidates, 'source_id': pair.source_id,
            'reference_anchor': pair.reference.anchor, 'observed_anchor': pair.observed.anchor}

@dataclass
class Channel:
    version: str
    context: str
    support: frozenset
    A: np.ndarray
    b: np.ndarray
    sources: frozenset
    alpha: float
    unknown_mode: str
    diagnostics: dict
    def bounds(self, coefficients, unknown_upper=1.):
        low = np.array(list(coefficients)+[0.])
        high = np.array(list(coefficients)+[unknown_upper])
        args = dict(A_ub=self.A, b_ub=self.b, A_eq=np.ones((1,len(low))),
                    b_eq=[1.], bounds=(0,1), method='highs')
        lo, hi = linprog(low, **args), linprog(-high, **args)
        if not lo.success or not hi.success:
            raise ValueError('incompatible channel: shared mixture assumption rejected')
        return [max(0.,float(lo.fun)), min(1.,float(-hi.fun))]

def fit_channel(pairs, version, context='two-person-two-event', alpha=.05,
                unknown_mode='unrestricted', development_sources=()):
    if not pairs or not 0<alpha<1: raise ValueError('empty calibration or invalid alpha')
    for pair in pairs: require_complete_pair(pair)
    if unknown_mode not in ('unrestricted','detectable_residual'): raise ValueError('unknown mode')
    if any(p.plan_version!=version or p.context!=context or p.split!='calibration' for p in pairs):
        raise ValueError('version/context/calibration split mismatch')
    sources = frozenset(p.source_id for p in pairs)
    if sources.intersection(development_sources): raise ValueError('source leakage across split')
    strata = defaultdict(lambda: defaultdict(list))
    for p in pairs: strata[p.reference][p.source_id].append(p)
    # Category set is dictionary-generated plus OTHER; fixed before seeing outputs.
    cells = sum(len(set(f(g) for f in EDITS.values()))+1 for g in strata)
    A,b,counts = [],[],{}
    for g, groups in strata.items():
        outputs = sorted(set(f(g) for f in EDITS.values()))
        n=len(groups); counts[str(g)]=n
        radius=math.sqrt(math.log(2*cells/alpha)/(2*n))
        for output in outputs+[None]:
            means=[]
            for ps in groups.values():
                means.append(sum((p.observed==output if output is not None else p.observed not in outputs)
                                 for p in ps)/len(ps))
            freq=float(np.mean(means)); lower=max(0.,freq-radius); upper=min(1.,freq+radius)
            known=np.array([float(f(g)==output) for f in EDITS.values()])
            if unknown_mode=='detectable_residual':
                row=np.r_[known, float(output is None)]
                A.extend([row,-row]); b.extend([upper,-lower])
            else:
                # Unknown may generate any category, including a known output.
                A.extend([np.r_[known,0.], -np.r_[known,1.]])
                b.extend([upper,-lower])
    channel=Channel(version,context,frozenset(strata),np.array(A),np.array(b),sources,
                    alpha,unknown_mode,{'independent_source_counts_by_reference':counts,
                    'pair_count':len(pairs),'simultaneous_cells':cells,
                    'ambiguous_pairs':sum(canonicalize_pair(p)['ambiguous'] for p in pairs),
                    'unmatched_pairs':sum(canonicalize_pair(p)['unmatched'] for p in pairs)})
    channel.bounds([0.]*len(EDITS)) # Feasibility, including finite sample constraints.
    return channel

@dataclass(frozen=True)
class Program:
    name: str
    evaluate: object
    context: str = 'two-person-two-event'

def risk(channel, program, train_world_weights, requested_version, allow_stationary_transfer=False):
    if requested_version!=channel.version: return {'status':'unsupported','reason':'version mismatch'}
    if program.context!=channel.context: return {'status':'unsupported','reason':'domain mismatch'}
    missing = [w for w in train_world_weights if w not in channel.support]
    if not train_world_weights or (missing and not allow_stationary_transfer):
        return {'status':'unsupported','reason':'reference support gap'}
    if any(not isinstance(w,Graph) or w.anchor not in {g.anchor for g in channel.support}
           for w in train_world_weights):
        return {'status':'unsupported','reason':'typed schema or anchor mismatch'}
    if any(v<0 for v in train_world_weights.values()) or abs(sum(train_world_weights.values())-1)>1e-8:
        raise ValueError('reference weights must be probability weights')
    L=[sum(weight*(program.evaluate(f(w))!=program.evaluate(w))
           for w,weight in train_world_weights.items()) for f in EDITS.values()]
    return {'status':'supported_conditional','interval':channel.bounds(L), 'loss_coefficients':L,
            'unknown_mode':channel.unknown_mode, 'alpha':channel.alpha,
            'extrapolated_worlds':len(missing),
            'stationary_transfer_assumption':bool(missing and allow_stationary_transfer)}

def robust_select(channels, program, train_world_weights, versions, costs, baseline,
                  selection_mode='minimax', allow_stationary_transfer=False):
    if selection_mode not in ('minimax','strict'): raise ValueError('invalid selection mode')
    results={k:risk(v,program,train_world_weights,versions[k],allow_stationary_transfer) for k,v in channels.items()}
    if any(r['status']=='unsupported' for r in results.values()):
        return {'status':'unsupported','plan':baseline,'reason':'missing comparable support','risks':results}
    best=min(results,key=lambda k:results[k]['interval'][1]+costs[k])
    separated=all(results[best]['interval'][1]+costs[best] < r['interval'][0]+costs[k]
                  for k,r in results.items() if k!=best)
    selected=selection_mode=='minimax' or separated
    return {'status':'selected' if selected else 'unsupported',
            'plan':best if selected else baseline, 'selection_mode':selection_mode,
            'certified_separation':separated,
            'reason':'minimum risk upper bound plus cost' if selected else 'finite samples do not distinguish plans',
            'risks':results,'familywise_alpha_bound':sum(c.alpha for c in channels.values())}

def require_complete_pair(record):
    """Reject partial external audit records; never infer missing graph facts."""
    if not isinstance(record,Pair) or not isinstance(record.reference,Graph) or not isinstance(record.observed,Graph):
        raise ValueError('complete typed reference/observed Graph pair and frozen version required')
    return record

def paired_trace_replay(pairs, program, train_world_weights, alpha=.05):
    """Strong baseline: complete paired trace, same reference support and source unit."""
    strata=defaultdict(lambda:defaultdict(list))
    for p in pairs: strata[p.reference][p.source_id].append(p)
    if any(w not in strata for w in train_world_weights): return {'status':'unsupported'}
    mean=0.; radius=0.
    for w,weight in train_world_weights.items():
        group=strata[w]
        values=[np.mean([program.evaluate(p.reference)!=program.evaluate(p.observed) for p in ps])
                for ps in group.values()]
        mean+=weight*float(np.mean(values))
        radius+=weight*math.sqrt(math.log(2*len(train_world_weights)/alpha)/(2*len(group)))
    return {'status':'supported','empirical_risk':mean,'interval':[max(0.,mean-radius),min(1.,mean+radius)]}
