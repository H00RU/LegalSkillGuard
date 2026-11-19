"""Reconcile saved M2 group factors across repeated TRAIN projection requests."""

import base64
from collections import Counter, defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_m2_pairwise_scope import (
    closure, previous_validations, projection_compatibility,
)
from legal_skill_guard.paired_interfaces.shared_semantics import (
    consistent_assignment, evidence_binding, matches_assertions,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_M2_cumulative_audit_20261119'
EARLIER_FAMILIES = (
    'm2_update_probe',
    'm2_oe_title_partition',
    'm2_amount_update',
    'm2_oe_conditioned_value',
    'm2_oe_title_value',
)


def archived_validations(tree, path):
    """Extract receipts from the known TRAIN-only pilot terminal formats."""
    if isinstance(tree, dict):
        if 'explanation_state' in tree:
            yield path, tree
            return
        for key, item in tree.items():
            yield from archived_validations(item, f'{path}/{key}')
    elif isinstance(tree, list):
        for index, item in enumerate(tree):
            yield from archived_validations(item, f'{path}/{index}')


def earlier_validations():
    for family in EARLIER_FAMILIES:
        for file in sorted((BASE/family).glob('*/terminal.json')):
            stage=file.parent
            terminal=read(file)
            if (not terminal['status'].startswith('completed') or terminal.get('TEST_opened')
                    or digest(read(stage/'binding.json'))!=stage.name):
                raise ValueError('Require the original completed TRAIN pilot')
            for label, record in archived_validations(terminal, family):
                yield label,stage,record


def physical_wire(db, train, identity, root):
    if root not in train:
        raise ValueError('New cumulative analysis can reuse only scoped TRAIN evidence')
    physical=db.execute('select role,source,purpose,status,request_hash,result from calls where id=?',
                        (identity,)).fetchone()
    if physical[:4]!=('executor',root,'skill_actor','completed'):
        raise ValueError('The projection lacks a completed physical TRAIN response')
    result=json.loads(physical[5])
    folder=Path(result['artifact_directory'])
    if not folder.is_relative_to(ROOT/'artifacts') or result['thinking_requested'] is not False:
        raise ValueError('Use the same local, thinking-off executor')
    original=read(folder/'request.json')
    wire=read(folder/'wire_request.json')
    raw=base64.b64decode(wire['body_b64'])
    if (original['id']!=identity or original['source']!=root
            or original['request_hash']!=physical[4] or result['request_hash']!=physical[4]
            or hashlib.sha256(raw).hexdigest()!=wire['body_sha256']
            or json.loads(raw)!=original['payload']
            or read(folder/'result.json')!=result):
        raise ValueError('The physical record differs from its exact request and response')
    payload=original['payload']
    assert payload['chat_template_kwargs']['enable_thinking'] is False
    assert payload['model']=='Qwen/Qwen3-8B'
    # Same decoder schema, reader instruction and sampling envelope. Source
    # user messages vary as intended and are already hash-bound individually.
    return digest({**{k:v for k,v in payload.items() if k!='messages'},
                   'system_messages':[p for p in payload['messages'] if p['role']=='system']})


def bind_factors(record, db, train, verified):
    state=record['explanation_state']
    snapshot={k:v for k,v in state.items() if k not in ('factors','observations')}
    context=digest(snapshot)
    if set(snapshot)!= {'patch_sha256','reference_sha256','provenance','root_alternatives','law_alternatives'}:
        raise ValueError('Review the original scope fields before joining')
    domains={f'{level}:{key}':value for level in ('law','root')
             for key,value in state[f'{level}_alternatives'].items()}
    for obs, factor in zip(state['observations'],state['factors'],strict=True):
        expected_keys={*('law:'+k for k in obs['law_scopes']), *('root:'+k for k in obs['root_ids'])}
        if not expected_keys<=set(domains):
            raise ValueError('Assignment contains a variable outside the bound scope')
        if (obs['evidence_kind']!='actual_model' or obs['physical_model_evidence_verified'] is not True
                or obs['constraint_provenance_sha256']!=evidence_binding(state['provenance'])
                or obs['reference_sha256']!=state['reference_sha256']
                or obs['patch_sha256']!=state['patch_sha256']):
            raise ValueError('Use only archived actual observations and unchanged constraints')
        for assignment in factor:
            if (set(assignment)!=expected_keys or any(type(value) is not int or
                    not 0<=value<len(domains[key]) for key,value in assignment.items())):
                raise ValueError('An assignment no longer names the same admissible world')
        for identity,root in zip(obs['physical_call_ids'],obs['root_ids'],strict=True):
            previous=verified.get(identity)
            if previous is not None and previous[0]!=root:
                raise ValueError('A response cannot be shared across TRAIN mothers')
            if previous is None:
                verified[identity]=(root,physical_wire(db,train,identity,root))
        wires=tuple(sorted({verified[i][1] for i in obs['physical_call_ids']}))
        observed=obs['actual_signature']
        allowed=obs['allowed_signatures']
        exact,reconstructed=closure(allowed)
        local=any(matches_assertions(observed, row) for row in allowed)
        if local!=obs['locally_allowed'] or local!=bool(factor):
            raise ValueError('Local membership and saved explanation support must agree')
        if len(observed)!=len(obs['physical_call_ids']):
            raise ValueError('Each output coordinate needs one archived actual read')
        yield {'semantic_scope_sha256':context,'wire_scope_sha256':digest(wires),
               'patch_reference_pair':digest((state['patch_sha256'], state['reference_sha256'])),
               'positive_native_companion':record['native_utility_sum_delta']>0,
               'observed':observed,'local':local,'factors':factor,'calls':set(obs['physical_call_ids']),
               'informative':obs['asserted_output_present'] and len(factor)<expected_worlds(domains, expected_keys),
               'pairwise_closure_additions':len(reconstructed-exact),
               'pairwise_matches_local':projection_compatibility(allowed,observed)==local}


def expected_worlds(domains, keys):
    size=1
    for key in keys:
        size*=len(domains[key])
    return size


def cumulative(groups):
    joined=[]
    for _, rows in groups.items():
        if len(rows)<2:
            continue
        all_support=[r['factors'] for r in rows]
        live_rows=[r for r in rows if r['local']]
        live_support=[r['factors'] for r in live_rows]
        combined_calls=set.union(*(r['calls'] for r in rows))
        joined.append({'conditions':[r['condition'] for r in rows],
                       'observations':len(rows),'wire_contracts':len({r['wire_scope_sha256'] for r in rows}),
                       'locally_compatible_observations':len(live_rows),'distinct_physical_responses':len(combined_calls),
                       'has_reused_calls_across_groups':len(combined_calls)<sum(len(r['calls']) for r in rows),
                       'has_full_group_equal_to_union_of_calls':any(r['calls']==combined_calls for r in rows),
                       'cumulative_support_exists':consistent_assignment(all_support) is not None,
                       'locally_compatible_groups_jointly_conflict':consistent_assignment(live_support) is None})
    return joined


def run():
    checkpoint=ROOT/read(BOOTSTRAP)['artifact_root']
    train={c['key'] for batch in load_roster(read(checkpoint/'binding.json')) for c in batch}
    current=tuple(previous_validations())
    legacy=tuple(earlier_validations())
    records=[]
    verified={}
    strict=defaultdict(list)
    including_wire_changes=defaultdict(list)
    by_patch_and_reference=defaultdict(list)
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('begin')
        counts=dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
        for condition,stage,record in (*current,*legacy):
            for row in bind_factors(record,db,train,verified):
                row.update(condition=condition,terminal_sha256=sha(stage/'terminal.json'))
                strict[row['semantic_scope_sha256'],row['wire_scope_sha256']].append(row)
                including_wire_changes[row['semantic_scope_sha256']].append(row)
                by_patch_and_reference[row['patch_reference_pair']].append(row)
                records.append(row)

    exact_groups=cumulative(strict)
    relaxed_groups=cumulative(including_wire_changes)
    scope_mismatches=sum(a['semantic_scope_sha256']!=b['semantic_scope_sha256']
                         for group in by_patch_and_reference.values() for a,b in combinations(group,2))
    result={'previously_audited_validation_records':len(current),'additional_earlier_validation_records':len(legacy),
            'total_projection_observations':len(records),'distinct_physical_responses_verified':len(verified),
            'repeated_semantic_scope_observations_with_exact_same_wire':exact_groups,
            'repeated_semantic_scope_observations_allowing_wire_changes':relaxed_groups,
            'same_patch_reference_pairs_excluded_for_different_semantic_scope':scope_mismatches,
            'strict_cross_group_only_conflicts':sum(r['locally_compatible_groups_jointly_conflict'] for r in exact_groups),
            'cross_group_only_conflicts_even_allowing_wire_changes':
                sum(r['locally_compatible_groups_jointly_conflict'] for r in relaxed_groups),
            'groups_with_support_beyond_pairwise_closure':sum(r['pairwise_closure_additions']>0 for r in records),
            'groups_where_pairwise_and_joint_disagree_on_actual_read':sum(not r['pairwise_matches_local'] for r in records),
            'by_archived_condition':[{k:r[k] for k in
                 ('condition','terminal_sha256','local','informative','positive_native_companion',
                  'wire_scope_sha256','pairwise_closure_additions','pairwise_matches_local')} for r in records],
            'no_new_selection_or_forward_native_result_claimed':True,'DEV_or_TEST_opened':False,
            'new_model_requests':0,'ledger_rows':sum(counts.values()),'bound_audit_sha256':sha(Path(__file__))}
    immutable_json(HOME/'terminal.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='by_archived_condition'},sort_keys=True),flush=True)


if __name__=='__main__':
    run()
