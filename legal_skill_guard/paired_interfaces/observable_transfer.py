"""Observable rewrite-set transfer, replacing the unidentified latent mixture.

The estimand is a distribution of *observable sets of compatible rewrites*,
not the probabilities of hidden causal error operators. Dictionary D is fixed
before calibration C. Unrepresented/ambiguous-alignment events retain [0,1].
Transfer requires explicit stationarity and representation assumptions; the
unrestricted latent-error envelope remains [0,1]. No costs enter selection.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import math

from legal_skill_guard.paired_interfaces.graph_matching import GraphMatchLimit, typed_bindings
from legal_skill_guard.paired_interfaces.observed_abstention import learn_dictionary, ObservedAbstention
from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval
from legal_skill_guard.paired_interfaces.structural_channel import observations
from legal_skill_guard.skill_evolution.objects import digest

ASSUMPTIONS = ('source_cluster_exchangeability', 'rewrite_set_stationarity_within_frozen_domain',
               'compatible_rewrite_representation_transfers', 'independent_reference_population',
               'source_reviewed_assertions_and_unknowns_are_valid')
RESIDUAL = ('observable_unrepresented_or_alignment_unknown',)


def images(edit, graph):
    # The historical IndexedJointEdit defaults to identity on a failed match.
    # That behavior cannot assert counterfactual support in this new model.
    if not isinstance(edit, ObservedAbstention) and (edit.before or edit.after):
        if next(iter(typed_bindings(graph, edit.variables, edit.before)), None) is None:
            return frozenset()
    return edit.images(graph)


@dataclass
class ObservableTransfer:
    edits: dict
    calibration: tuple
    events: tuple
    version: str
    schema: str
    context: str
    development_sources: frozenset

    def diagnostics(self):
        counts = Counter(self.events)
        by_source = defaultdict(list)
        for pair,event in zip(self.calibration,self.events):
            by_source[pair.source_id].append(event)
        masses = defaultdict(float)
        for events in by_source.values():
            for event in events:
                masses[event] += 1./len(by_source)/len(events)
        return {'prediction_target':'source-weighted observable compatible-rewrite-set distribution',
            'calibration_sources':len(by_source), 'calibration_pairs':len(self.events),
            'distinct_observable_events':len(counts),
            'observable_residual_mass':masses.get(RESIDUAL,0.),
            'event_source_weighted_mass':[{'compatible_rewrites':list(e),'mass':p} for e,p in sorted(masses.items())],
            'latent_unknown_probability_estimated_or_capped':False,
            'unrestricted_latent_risk_interval':[0.,1.]}

    def predict(self, loss, weights, *, assumptions, delta=.05, loss_for_reference=None):
        if set(assumptions) != set(ASSUMPTIONS):
            raise ValueError('Explicit acceptance of every transfer assumption is required')
        if not 0 < delta < 1 or not weights or any(not math.isfinite(w) or w<=0 for w in weights.values()) or abs(sum(weights.values())-1)>1e-8:
            raise ValueError('Positive normalized reference weights and a valid delta are required')
        if any((g.schema,g.context)!=(self.schema,self.context) for g in weights):
            raise ValueError('Transfer across frozen typed/public-law domains is unsupported')
        event_losses = {}
        for event in set(self.events):
            lo = hi = 0.
            for graph,weight in weights.items():
                current_loss = loss_for_reference(graph) if loss_for_reference else loss
                values = []
                if event == RESIDUAL:
                    values = [[0.,1.]]
                else:
                    for identity in event:
                        try:
                            outcomes = images(self.edits[identity],graph)
                            values.extend(loss_interval(current_loss,graph,y) for y in outcomes)
                            if not outcomes:values.append([0.,1.])
                        except GraphMatchLimit:
                            values.append([0.,1.])
                lo += weight*min(v[0] for v in values)
                hi += weight*max(v[1] for v in values)
            event_losses[event] = [lo,hi]
        by_source = defaultdict(list)
        for pair,event in zip(self.calibration,self.events):
            by_source[pair.source_id].append(event_losses[event])
        source_losses = [[sum(v[k] for v in rows)/len(rows) for k in (0,1)] for rows in by_source.values()]
        empirical = [sum(v[k] for v in source_losses)/len(source_losses) for k in (0,1)]
        radius = math.sqrt(math.log(2/delta)/(2*len(source_losses)))
        return {'supported':True, 'empirical_interval':empirical,
            'interval':[max(0.,empirical[0]-radius),min(1.,empirical[1]+radius)],
            'source_cluster_radius':radius, 'delta':delta,
            'conditional_model_prediction':True, 'assumptions':list(ASSUMPTIONS),
            'unrestricted_latent_risk_interval':[0.,1.],
            'unknown_mass_or_loss_artificially_reduced':False,
            'event_losses':[{'event':list(e),'loss_interval':v} for e,v in sorted(event_losses.items())],
            **self.diagnostics()}


def fit_observable(development,calibration):
    development,calibration = tuple(development),tuple(calibration)
    if not development or not calibration:
        raise ValueError('Disjoint development and calibration are both required')
    if any(p.role!='development' for p in development) or any(p.role!='calibration' for p in calibration):
        raise ValueError('TRAIN dictionary and calibration roles must remain isolated')
    d_sources,c_sources = {p.source_id for p in development},{p.source_id for p in calibration}
    if d_sources & c_sources:raise ValueError('Dictionary and calibration sources overlap')
    domains = {(p.plan_version,p.reference.schema,p.reference.context) for p in development+calibration}
    if len(domains)!=1:raise ValueError('Mixed reader versions or typed/public-law domains')
    dictionary = learn_dictionary(development)
    edits = {e.identity:e for e in dictionary['edits']}
    events = []
    for pair in calibration:
        seen,complete = set(),True
        for y in observations(pair):
            if any(n.startswith('failed-read:') and k=='unresolved_read' for n,k in y.nodes):
                complete=False;break
            try:
                matching = {key for key,e in edits.items() if y in images(e,pair.reference)}
            except GraphMatchLimit:
                complete=False;break
            if not matching:complete=False;break
            seen.update(matching)
        events.append(tuple(sorted(seen)) if complete else RESIDUAL)
    version,schema,context = next(iter(domains))
    return ObservableTransfer(edits,calibration,tuple(events),version,schema,context,frozenset(d_sources))


def choose_observable(predictions, *, baseline):
    """Require actual upper-risk separation; a tie is an explicit nondecision."""
    if baseline not in predictions or any(not p.get('supported') for p in predictions.values()):
        return {'supported':False,'plan':baseline,'risk_informed_ranking':False,'reason':'missing conditional prediction'}
    upper = {k:p['interval'][1] for k,p in predictions.items()}
    best = min(upper.values())
    winners = [k for k,u in upper.items() if abs(u-best)<=1e-12]
    if len(winners)!=1:
        return {'supported':False,'plan':baseline,'risk_informed_ranking':False,
                'reason':'upper risks tied; no M2 selection evidence','upper_risks':upper}
    winner = winners[0]
    return {'supported':True,'plan':winner,'risk_informed_ranking':True,
            'changed_baseline':winner!=baseline,'upper_risks':upper,
            'certified_separation':all(predictions[winner]['interval'][1]<p['interval'][0]
                for k,p in predictions.items() if k!=winner),'costs_used':False}


def model_record(model):
    from legal_skill_guard.paired_interfaces.formal_learning import pair_record
    from legal_skill_guard.paired_interfaces.observed_abstention import edit_record
    record = {'method':'observable-rewrite-set-transfer-v1',
        'edits':[edit_record(e) for e in model.edits.values()],
        'calibration':[pair_record(p) for p in model.calibration],
        'events':[list(e) for e in model.events], 'version':model.version,
        'schema':model.schema, 'context':model.context,
        'development_sources':sorted(model.development_sources)}
    return {**record,'model_sha256':digest(record)}


def restore_model(record):
    from legal_skill_guard.paired_interfaces.formal_learning import restore_pair
    from legal_skill_guard.paired_interfaces.observed_abstention import restore_edit
    if record['method']!='observable-rewrite-set-transfer-v1' or digest({k:v for k,v in record.items() if k!='model_sha256'})!=record['model_sha256']:
        raise ValueError('An observable model lost its frozen binding')
    edits = [restore_edit(e) for e in record['edits']]
    return ObservableTransfer({e.identity:e for e in edits},
        tuple(restore_pair(p) for p in record['calibration']),tuple(tuple(e) for e in record['events']),
        record['version'],record['schema'],record['context'],frozenset(record['development_sources']))
