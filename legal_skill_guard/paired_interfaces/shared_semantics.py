"""Finite shared-interpretation supervision for external skill updates.

This is the convergence Goal's M2, independent of the historical risk selector.
Law alternatives are scoped by legal version/definition; unknown case facts
are scoped by mother source. A patch is tested against audited semantics, not
against another patch. Exact relations and cumulative explanation factors are
separate from native positive supervision and actual-model efficacy evidence.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from itertools import product
import json
from typing import Callable

from legal_skill_guard.skill_evolution.objects import digest


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def evidence_binding(provenance):
    permitted={'explicit_source','official_task_assumption','independent_source_audit'}
    if not provenance or any(p.get('kind') not in permitted or not p.get('evidence_sha256') for p in provenance):
        raise ValueError('Relations require independently sourced semantic provenance')
    return digest(provenance)


@dataclass(frozen=True)
class SourceCase:
    source_id: str
    root_id: str
    law_scope: str
    public: dict
    primitives: dict
    # field -> (public field, begin, end); spans are explicit and need not be unique globally.
    spans: dict = field(default_factory=dict)
    interventions: dict = field(default_factory=dict)
    parent_source_sha256: str | None = None


@dataclass(frozen=True)
class DerivedField:
    name: str
    dependencies: tuple[str,...]
    compute: Callable


@dataclass(frozen=True)
class Theory:
    law_alternatives: dict
    root_alternatives: dict
    reference: Callable
    reference_sha256: str
    provenance: tuple[dict,...]
    derived: tuple[DerivedField,...] = ()
    allowed_edits: frozenset[str] = frozenset()
    # constraint_holds filters impossible K-worlds. well_formed is the local
    # consumer's applicability boundary; a legal off-scope world is retained.
    constraint_holds: Callable = lambda values,law: True
    well_formed: Callable = lambda values,law: True

    def __post_init__(self):
        evidence_binding(self.provenance)
        if len(self.reference_sha256)!=64:
            raise ValueError('Pin the audited semantic reference implementation')
        for mapping in (self.law_alternatives,self.root_alternatives):
            if any(not key or not values for key,values in mapping.items()):
                raise ValueError('Each semantic scope needs a nonempty finite alternative family')
            if any(len({canonical(v) for v in values})!=len(values) for values in mapping.values()):
                raise ValueError('Duplicate semantic alternatives cannot count as evidence')
        names=[d.name for d in self.derived]
        if len(names)!=len(set(names)) or set(names)&set(self.allowed_edits):
            raise ValueError('Only primitive fields can be edited; derived definitions must be unique')
        self.derived_order()  # Detect cycles before generating a source group.

    def derived_order(self):
        pending={d.name:d for d in self.derived}; ordered=[]
        while pending:
            ready=[d for d in pending.values() if not (set(d.dependencies)&set(pending))]
            if not ready:raise ValueError('Derived semantic dependency cycle')
            for d in sorted(ready,key=lambda d:d.name):ordered.append(d);del pending[d.name]
        return ordered

    def complete(self,case,law,latent):
        if set(latent)&set(case.primitives):
            raise ValueError('A latent alternative cannot overwrite an explicitly observed primitive')
        if not set(case.interventions)<=set(self.allowed_edits):
            raise ValueError('An intervention is outside the audited primitive edit grammar')
        values={**deepcopy(latent),**deepcopy(case.primitives),**deepcopy(case.interventions)}
        for d in self.derived_order():
            if not set(d.dependencies)<=set(values):
                raise ValueError('Missing input for an audited derived field: '+d.name)
            values[d.name]=d.compute(deepcopy(values),deepcopy(law))
        return values


def source_variant(case,theory,changes,renderers):
    """Change only actual permitted source spans; otherwise UNREALIZABLE.

    Latent edits need their own explicit source span. In particular, an unseen
    date/ownership cannot be materialized merely because it helps a candidate.
    """
    if not changes or not set(changes)<=set(theory.allowed_edits):
        return {'status':'UNREALIZABLE','reason':'not an allowed nonempty primitive change'}
    if not set(changes)<=set(case.spans) or not set(changes)<=set(renderers):
        return {'status':'UNREALIZABLE','reason':'a changed primitive lacks a real source span/renderer'}
    patches=[]
    for name,value in changes.items():
        public_field,start,end=case.spans[name]
        text=case.public.get(public_field)
        if not isinstance(text,str) or not (0<=start<end<=len(text)):
            return {'status':'UNREALIZABLE','reason':'invalid source span'}
        if name in case.primitives and case.primitives[name] is not None:
            expected=renderers[name](case.primitives[name])
            if text[start:end]!=expected:
                return {'status':'UNREALIZABLE','reason':'primitive value does not bind its current source span'}
        replacement=renderers[name](value)
        if not isinstance(replacement,str) or not replacement:
            return {'status':'UNREALIZABLE','reason':'renderer did not produce a source literal'}
        patches.append((public_field,start,end,replacement,name))
    for left,right in zip(sorted(patches),sorted(patches)[1:]):
        if left[0]==right[0] and left[2]>right[1]:
            return {'status':'UNREALIZABLE','reason':'overlapping source interventions'}
    public=deepcopy(case.public)
    for public_field,start,end,replacement,_ in sorted(patches,reverse=True):
        public[public_field]=public[public_field][:start]+replacement+public[public_field][end:]
    interventions={**case.interventions,**deepcopy(changes)}
    variant=SourceCase(case.source_id+':edit:'+digest(changes)[:16],case.root_id,case.law_scope,
        public,deepcopy(case.primitives),{},interventions,digest(case.public))
    return {'status':'REALIZABLE','case':variant,'receipt':{
        'parent_source_sha256':digest(case.public),'variant_source_sha256':digest(public),
        'changed_primitives':sorted(changes),'patched_spans':[list(p[:4]) for p in patches],
        'unchanged_source_bytes_preserved':True,'derived_fields_recomputed_at_reference_execution':True,
        'newly_invented_source_fields':False}}


def allowed_relation(theory,cases,*,mode='shared'):
    """Return exact signatures with their scoped explanation assignments.

    Independent/single-interpretation modes are explicit controls, not claimed
    valid replacements for the shared reference. Off-scope is a real outcome.
    """
    if not cases:raise ValueError('A source group cannot be empty')
    if mode not in ('shared','independent_completions','single_interpretation'):
        raise ValueError('Unknown semantic supervision mode')
    laws=sorted({c.law_scope for c in cases});roots=sorted({c.root_id for c in cases})
    if any(s not in theory.law_alternatives for s in laws) or any(s not in theory.root_alternatives for s in roots):
        raise ValueError('A source has no audited law/root alternative family')
    if mode=='independent_completions':
        values=[list(allowed_relation(theory,[c])['signatures'].values()) for c in cases]
        tuples=[tuple(v[0] for v in xs) for xs in product(*values)]
        return {'signatures':{canonical(v):list(v) for v in tuples},'supports':{},'variables':{},
            'mode':mode,'exhaustive':True,'shared_explanation_enforced':False}
    variables={**{'law:'+s:list(range(len(theory.law_alternatives[s]))) for s in laws},
               **{'root:'+s:list(range(len(theory.root_alternatives[s]))) for s in roots}}
    if mode=='single_interpretation':variables={k:[v[0]] for k,v in variables.items()}
    signatures={};supports={}
    for choices in product(*variables.values()):
        assignment=dict(zip(variables,choices));outputs=[];admissible=True
        for case in cases:
            law=theory.law_alternatives[case.law_scope][assignment['law:'+case.law_scope]]
            latent=theory.root_alternatives[case.root_id][assignment['root:'+case.root_id]]
            values=theory.complete(case,law,latent)
            if not theory.constraint_holds(values,law):
                admissible=False;break
            value=(theory.reference(values,deepcopy(law)) if theory.well_formed(values,law)
                   else {'status':'off_scope'})
            outputs.append(value)
        if admissible:
            key=canonical(outputs);signatures[key]=outputs;supports.setdefault(key,[]).append(assignment)
    if not signatures:
        raise ValueError('Audited K has no jointly admissible explanation; an empty relation cannot reject all patches')
    return {'signatures':signatures,'supports':supports,'variables':variables,
        'mode':mode,'exhaustive':True,'shared_explanation_enforced':mode=='shared',
        'reference_sha256':theory.reference_sha256,'constraint_provenance_sha256':evidence_binding(theory.provenance)}


def consistent_factors(factors):
    """Exact finite join. Keeps all local factors rather than a favorable ω/group."""
    def search(assignment,remaining):
        if not remaining:return True
        options=[]
        for rows in remaining:
            compatible=[r for r in rows if all(k not in assignment or assignment[k]==v for k,v in r.items())]
            if not compatible:return False
            options.append(compatible)
        index=min(range(len(options)),key=lambda i:len(options[i]))
        tail=remaining[:index]+remaining[index+1:]
        return any(search({**assignment,**row},tail) for row in options[index])
    return search({},list(factors))


@dataclass
class ExplanationState:
    """One candidate patch's cumulative audited explanation factors."""
    theory: Theory
    patch_sha256: str
    factors: list = field(default_factory=list)
    observations: list = field(default_factory=list)

    def snapshot(self):
        """Persist Ω factors, not a single explanation chosen for this group."""
        return {'patch_sha256':self.patch_sha256,'reference_sha256':self.theory.reference_sha256,
            'law_alternatives':deepcopy(self.theory.law_alternatives),
            'root_alternatives':deepcopy(self.theory.root_alternatives),
            'provenance':deepcopy(list(self.theory.provenance)),
            'factors':deepcopy(self.factors),'observations':deepcopy(self.observations)}

    @classmethod
    def restore(cls,theory,record):
        if theory.reference_sha256!=record['reference_sha256']:
            raise ValueError('Changed semantic reference requires explicit revalidation')
        for name,current in [('law_alternatives',theory.law_alternatives),('root_alternatives',theory.root_alternatives)]:
            if any(k not in current or canonical(current[k])!=canonical(v) for k,v in record[name].items()):
                raise ValueError('Existing semantic alternatives changed; do not reset accumulated Ω')
        evidence={canonical(p) for p in theory.provenance}
        if not all(canonical(p) in evidence for p in record['provenance']):
            raise ValueError('Previously audited semantic evidence cannot disappear on resume')
        return cls(theory,record['patch_sha256'],deepcopy(record['factors']),deepcopy(record['observations']))

    def observe(self,cases,actual_outputs,*,physical_call_ids,evidence_kind='symbolic_check',physical_verifier=None):
        if len(actual_outputs)!=len(cases) or len(physical_call_ids)!=len(cases):
            raise ValueError('Every real source variant needs an actual output/call binding')
        if any(not v for v in physical_call_ids):
            raise ValueError('Symbolic defect predictions are not physical model observations')
        if evidence_kind not in ('symbolic_check','actual_model'):
            raise ValueError('Declare whether observations are symbolic or actual frozen-model outputs')
        verified=False
        if evidence_kind=='actual_model':
            if physical_verifier is None:
                raise ValueError('Actual-model evidence needs a continuous-ledger physical verifier')
            for identity,case,output in zip(physical_call_ids,cases,actual_outputs):
                if physical_verifier(identity,case,output) is not True:
                    raise ValueError('Physical model output differs from its source/ledger binding')
            verified=True
        relation=allowed_relation(self.theory,cases)
        key=canonical(actual_outputs);supports=relation['supports'].get(key,[])
        self.factors.append(supports)
        feasible=consistent_factors(self.factors)
        def unknown(value):
            if isinstance(value,dict):
                return value.get('status') in ('unknown','unread') or bool(value) and all(unknown(v) for v in value.values())
            if isinstance(value,list):return bool(value) and all(unknown(v) for v in value)
            return value is None or value in ('U','unknown','unread')
        all_unknown=all(unknown(v) for v in actual_outputs)
        row={'patch_sha256':self.patch_sha256,'source_ids':[c.source_id for c in cases],
            'root_ids':[c.root_id for c in cases],'law_scopes':[c.law_scope for c in cases],
            'actual_signature':deepcopy(actual_outputs),'physical_call_ids':list(physical_call_ids),
            'locally_allowed':bool(supports),'cumulative_shared_explanation_exists':feasible,
            'status':'not_refuted' if feasible else 'refuted','native_correctness_certified':False,
            'all_unknown_is_positive_evidence':False,'native_positive_supervision_required':True,
            'physical_model_evidence_verified':verified,'evidence_kind':evidence_kind,
            'nontrivial_model_relation_observation':verified and feasible and not all_unknown,
            'allowed_signatures':list(relation['signatures'].values()),
            'reference_sha256':self.theory.reference_sha256,
            'constraint_provenance_sha256':evidence_binding(self.theory.provenance)}
        self.observations.append(row);return row


def choose_groups(theory,groups,candidate_signatures,*,costs=None,max_groups=None):
    """Cover patch classes refuted by a group or a shared-explanation join.

    Predictions here can be symbolic or cached actual traces. New physical
    execution must confirm them before they count as real update evidence.
    """
    if len(groups)!=len(candidate_signatures):raise ValueError('Group/signature table mismatch')
    costs=costs or [1.0]*len(groups)
    if len(costs)!=len(groups) or any(v<=0 for v in costs):raise ValueError('Declare positive group costs')
    rows = []
    allowed_factors = {}
    patch_factors = {}
    for i,(group,predictions) in enumerate(zip(groups,candidate_signatures)):
        relation=allowed_relation(theory,group)
        allowed_factors[i] = [assignment for assignments in relation['supports'].values()
                              for assignment in assignments]
        rejected = set()
        for name, output in predictions.items():
            support = relation['supports'].get(canonical(output), [])
            patch_factors.setdefault(name, {})[i] = support
            if not support:
                rejected.add(name)
        rows.append({'index':i,'rejected_candidates':sorted(rejected),'cost':costs[i],
                     'allowed_signatures':list(relation['signatures'].values())})

    def refuted(factors, indices):
        return not consistent_factors([factors[i] for i in indices if i in factors])

    # A candidate can appear valid in every group when each group selects a
    # different value of the same variable. Preserve a small conflict witness.
    # A contradictory reference pool cannot be used to reject a candidate.
    witness_pool = {(row['index'],) for row in rows if row['rejected_candidates']}
    for factors in patch_factors.values():
        indices = sorted(factors)
        if any(not support for support in factors.values()):
            continue
        if refuted(allowed_factors, indices) or not refuted(factors, indices):
            continue
        for index in sorted(indices, key=lambda i: (-costs[i], i)):
            smaller = [i for i in indices if i != index]
            if refuted(factors, smaller):
                indices = smaller
        witness_pool.add(tuple(indices))

    selected = []
    covered = set()
    witness_receipts = []
    while witness_pool:
        options = []
        for witness in sorted(witness_pool):
            added = [i for i in witness if i not in selected]
            if not added or (max_groups is not None and len(selected) + len(added) > max_groups):
                continue
            combined = selected + added
            if refuted(allowed_factors, combined):
                continue
            newly = {name for name, factors in patch_factors.items()
                     if name not in covered and refuted(factors, combined)}
            if newly:
                cost = sum(costs[i] for i in added)
                options.append((-len(newly) / cost, cost, witness, added, newly))
        if not options:
            break
        _, _, witness, added, newly = min(options, key=lambda option: option[:3])
        witness_pool.remove(witness)
        selected.extend(added)
        covered.update(newly)
        witness_receipts.append({'added_indices': added, 'witness_indices': list(witness),
                                 'newly_refuted_candidate_classes': sorted(newly)})
    return {'selected_indices':selected,'refuted_candidate_classes':sorted(covered),'groups':rows,
        'shared_explanation_witnesses': witness_receipts,
        'selection_uses_reference_violation_not_candidate_disagreement':True,
        'physical_model_evidence_established_by_selection':False,
        'no_witness_means_global_unidentifiability':False}
