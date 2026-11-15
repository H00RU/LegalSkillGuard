"""Exact reachable output profiles for fully observed multi-stage G programs.

Derived-rule interactions prevent the direct-rule union shortcut. Enumerate
actual rule subsets and deduplicate only identical deployed output theories.
No individual head is independently selected, and no source meaning is added.
"""
from copy import deepcopy
import time

from .relational_learning import execute_composition
from .relational_rules import canonical,context_identity,language_identity,validate_context
from .source_composition import render_composition


def admissible_program_compositions(library,observation,check_native,*,timeout_seconds=30):
    language=library['language'];context=observation['context'];validate_context(context,language)
    if context['unknown_groups']:
        raise ValueError('Fully observed inputs required; do not fill unknown readings')
    if timeout_seconds<=0:raise ValueError('Positive finite search time required')
    started=time.monotonic();deadline=started+timeout_seconds
    base={'language_sha256':language_identity(language),'context_sha256':context_identity(context),
          'enumeration_scope':'outputs_reachable_by_subsets_of_current_rules',
          'not_a_complete_relaxed_representation_diagnostic':True,'new_model_requests':0}
    def normalize(result):
        return [{k:deepcopy(v) for k,v in atom.items() if k!='context_index'}
                for atom in result['certain_outputs']]
    evaluations=[];allowed=[];seen=set();vocabulary={};subsets=1<<len(language['rules'])
    for mask in range(subsets):
        remaining=deadline-time.monotonic()
        if remaining<=0:
            return {**base,'status':'timeout','allowed_theories':None,'evaluations':evaluations}
        witness=[r['id'] for i,r in enumerate(language['rules']) if mask&(1<<i)]
        result=execute_composition(language,witness,context,timeout_seconds=remaining)
        if not result['complete']:
            return {**base,'status':'timeout' if result['status']=='timeout' else 'inconsistent_observations',
                    'allowed_theories':None,'evaluations':evaluations}
        theory=sorted(normalize(result),key=canonical);key=canonical(theory)
        if key in seen:continue
        seen.add(key);keys={canonical(a) for a in theory};vocabulary.update({canonical(a):a for a in theory})
        hard=({canonical(a) for a in context['required']}<=keys and
              not {canonical(a) for a in context['forbidden']}.intersection(keys))
        record={'theory_index':len(evaluations),'theory':theory,'witness_rule_ids':witness,
                'partial_source_constraints_satisfied':hard}
        if not hard:
            record.update(admissible=False,reason='explicit_partial_source_constraint')
        else:
            try:
                output=render_composition(language,library['renderers'],observation,result,library['spec'])
                feedback=check_native(output)
                if type(feedback['accepted']) is not bool or not isinstance(feedback['reason'],str):
                    raise ValueError('Explicit actual native feedback required')
                record.update(native_feedback=feedback,admissible=feedback['accepted'],reason=feedback['reason'])
                if feedback['accepted']:allowed.append(theory)
            except (ValueError,KeyError,TypeError) as error:
                record.update(admissible=False,reason='type_or_provenance_failure',error=str(error))
        evaluations.append(record)
    return {**base,'status':'complete','evaluations':evaluations,
            'vocabulary':[vocabulary[k] for k in sorted(vocabulary)],'allowed_theories':allowed,
            'finite_theory_count':len(evaluations),'rule_subsets_checked':subsets,
            'accepted_theory_count':len(allowed),'elapsed_seconds':time.monotonic()-started}
