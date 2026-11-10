"""Select one actual cached clause for an explicit native SARA applies query.

No names, descendant guesses, labels, aliases or fallback outputs. This is a
common source-cache routing correction, not a learned method contribution.
"""
from copy import deepcopy
import re
from legal_skill_guard.rr.source_structure import explicit_query_target


def bind_explicit_applies(training_source,current_source,programme):
    if training_source['dataset']!=current_source['dataset'] or current_source['dataset']!='SARA_v2_Binary':
        raise ValueError('This actual cached path requires the same SARA task')
    if training_source['public']['rules']!=current_source['public']['rules']:
        raise ValueError('The source cache belongs to different statute bytes')
    if re.match(r'^Section\s+\d+(?:\([A-Za-z0-9]+\))+\s+applies\b',current_source['public']['query']) is None:
        raise ValueError('This path requires an explicit named-section applies question')
    target=explicit_query_target(current_source)
    if target is None:raise ValueError('No unique explicit native citation target')
    owners=[c for c in programme['clauses'] if set(c['sources'])==set(target['unit_ids'])]
    if len(owners)!=1:raise ValueError('Target needs one actual clause with exact source ownership')
    selected=owners[0]
    bound=deepcopy(programme)
    bound['query']={'op':'if','args':[{'var':selected['name']},'Entailment','Contradiction']}
    return bound,{'target':target,'selected_clause':selected['name'],'selected_sources':selected['sources'],
        'selection_basis':'Exact public citation and existing clause ownership; inherited guards remain in the shared compiler.',
        'model_route_repaired_or_reclassified_as_original_success':False}
