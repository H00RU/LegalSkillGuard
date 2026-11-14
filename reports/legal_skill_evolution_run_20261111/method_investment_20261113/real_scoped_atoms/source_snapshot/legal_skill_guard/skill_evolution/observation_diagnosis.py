"""Finite representation certificates for the selected acquisition algorithm.

The caller supplies *all* inputs visible to its composition program and complete
finite admissible-theory sets in one frozen language. This kernel does not infer
legal meaning, discard source text, invent negatives, or identify alpha-renamings.
Exact canonical JSON equality is a conservative initial equivalence relation.
"""
from collections import Counter, defaultdict
import hashlib
import json


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def _intersection(items):
    result=set(items[0])
    for item in items[1:]:
        result.intersection_update(item)
    return result


def diagnose_observations(records, *, observation_contract_sha256,
                          theory_language_sha256, composition_status='not_run'):
    """Distinguish inadequate observations from a restricted composition bias.

Each record has context_id, visible_inputs, allowed_theories and solver_status.
Statuses are complete or timeout. `complete` means the supplied finite language
was exhaustively checked, not merely that one candidate was found. Empty sets
are local theory/constraint failures, never representation-conflict evidence.
The returned bounds count constraint contexts, not independent mother sources.
"""
    if composition_status not in ('sat','complete_unsat','timeout','not_run'):
        raise ValueError('Explicit composition-search status required')
    for identity in (observation_contract_sha256,theory_language_sha256):
        if not isinstance(identity,str) or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):
            raise ValueError('Frozen observation and theory-language SHA256 identities required')
    groups=defaultdict(list);seen=set()
    for raw in records:
        name=raw['context_id']
        if not isinstance(name,str) or not name or name in seen:
            raise ValueError('Distinct context identifiers required')
        seen.add(name)
        if raw['solver_status'] not in ('complete','timeout'):
            raise ValueError('Completeness or timeout must be explicit')
        if not isinstance(raw['allowed_theories'],list):
            raise ValueError('Admissible theories must be an explicit finite list')
        allowed={_canonical(t) for t in raw['allowed_theories']}
        groups[_canonical(raw['visible_inputs'])].append({'context_id':name,
            'allowed':allowed,'status':raw['solver_status']})
    certificates=[];unresolved=[];local=[];bound=0
    for visible,group in sorted(groups.items()):
        key=hashlib.sha256(visible.encode()).hexdigest()
        empty=[r['context_id'] for r in group if r['status']=='complete' and not r['allowed']]
        if empty:
            local.extend({'context_id':name,'visible_input_sha256':key,
                'reason':'No admissible theory even for this context; check output language, semantics or constraints.'}
                for name in empty)
            continue
        if any(r['status']=='timeout' for r in group):
            unresolved.append({'contexts':[r['context_id'] for r in group],
                'visible_input_sha256':key,'reason':'Incomplete admissible-theory enumeration.'})
            continue
        support=Counter(t for r in group for t in r['allowed'])
        lower=len(group)-max(support.values())
        bound+=lower
        if not lower:
            continue
        # Deletion-minimal, deterministic conflict core; not minimum cardinality.
        core=list(group)
        for candidate in list(group):
            trial=[r for r in core if r is not candidate]
            if trial and not _intersection([r['allowed'] for r in trial]):
                core=trial
        assert len(core)>1 and all(r['allowed'] for r in core)
        assert not _intersection([r['allowed'] for r in core])
        certificates.append({'visible_input_sha256':key,
            'contexts':[r['context_id'] for r in group],
            'deletion_minimal_core':[r['context_id'] for r in core],
            'allowed_theories_in_core':{r['context_id']:[json.loads(t) for t in sorted(r['allowed'])] for r in core},
            'unsatisfied_context_lower_bound':lower,
            'claim':'No deterministic composition using these exact visible inputs can satisfy all supplied constraints in the frozen theory language.'})
    if (certificates or local) and composition_status=='sat':
        raise ValueError('Composition SAT contradicts the supplied finite-language constraints')
    if not records:
        decision='no_evidence'
    elif local:
        decision='local_theory_or_constraint_failure'
    elif certificates:
        decision='representation_insufficient'
    elif unresolved:
        decision='unresolved'
    elif composition_status=='complete_unsat':
        decision='composition_bias_insufficient'
    elif composition_status=='sat':
        decision='observed_constraints_satisfied'
    else:
        decision='composition_search_unresolved'
    return {'decision':decision,'representation_certificates':certificates,
        'local_failures':local,'unresolved_classes':unresolved,
        'lower_bound_on_complete_nonlocal_classes':bound,
        'context_count':len(records),'equivalence_class_count':len(groups),
        'observation_contract_sha256':observation_contract_sha256,
        'theory_language_sha256':theory_language_sha256,
        'equivalence':'Exact canonical equality of supplied full G-visible inputs; no lossy projection or inferred graph renaming.',
        'semantics':'Relative to complete finite admissible-theory sets supplied by the caller; not a proof of source interpretation or generalization.'}
