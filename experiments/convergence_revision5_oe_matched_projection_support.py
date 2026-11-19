"""Separate changes in assertion coverage from shared-title incompatibility."""

from itertools import product
import json
from pathlib import Path
import sqlite3

from experiments import convergence_oe_component_probe as components
from experiments import convergence_oe_conditioned_value_probe as numeric
from experiments import convergence_oe_feedback_pair as feedback
from experiments import convergence_revision5_oe_disclosure as disclosure
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, pointer as fit_pointer
from experiments.convergence_oe_scoped_proposal import projection_policy
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_OE_matched_projection_support_20261119'
ROLES = ('incumbent','candidate')


def direct_title_support(queries, values):
    """Count legal interpretations using the audited amount and component at each position."""
    possibilities = {False, True}
    for query,value in zip(queries,values,strict=True):
        if value is None:
            continue
        amount = query['independently_verified_source_facts']['stated_value_dollars']
        component = query['requested_component']
        if type(amount) is not int or amount<=0 or component not in ('forwarded','withheld'):
            raise ValueError('A direct check needs a positive amount and an exact requested component')
        if type(value) is not int or value not in (0,amount):
            return 0
        possibilities.intersection_update({(component=='forwarded')==(value==amount)})
    return len(possibilities)


def review_pair(queries, signatures, incumbent, candidate):
    if len(incumbent)!=len(candidate) or len(incumbent)!=len(queries):
        raise ValueError('Compare the same ordered query positions')
    common = [i for i,(a,b) in enumerate(zip(incumbent,candidate,strict=True)) if a is not None and b is not None]
    extra = [i for i,(a,b) in enumerate(zip(incumbent,candidate,strict=True)) if a is None and b is not None]
    removed = [i for i,(a,b) in enumerate(zip(incumbent,candidate,strict=True)) if a is not None and b is None]
    changed = [i for i in common if incumbent[i]!=candidate[i]]
    masks = {
        'incumbent_as_observed':incumbent,
        'candidate_as_observed':candidate,
        'incumbent_on_common':[v if i in common else None for i,v in enumerate(incumbent)],
        'candidate_on_common':[v if i in common else None for i,v in enumerate(candidate)],
        'remove_only':[v if i not in removed else None for i,v in enumerate(incumbent)],
        'add_only':[candidate[i] if i in extra else v for i,v in enumerate(incumbent)],
        'replace_only':[candidate[i] if i in changed else v for i,v in enumerate(incumbent)],
    }
    marginal = [set(col) for col in zip(*signatures,strict=True)]
    for state in product(*((None, *sorted(col)) for col in marginal)):
        assert direct_title_support(queries,state)==sum(matches_assertions(list(state),row) for row in signatures)
    support = {}
    for role,values in masks.items():
        shared = sum(matches_assertions(values,row) for row in signatures)
        assert direct_title_support(queries,values)==shared
        support[role] = {'known':sum(v is not None for v in values),'shared':shared,
                         'independent':all(v is None or v in choices for v,choices in zip(values,marginal,strict=True))}
    return {'common_positions':common,'added_positions':extra,'removed_positions':removed,
            'different_at_commonly_asserted_positions':changed,'support':support,
            'direct_check_agreed_on_every_marginal_state':True,'checked_marginal_states':3**len(queries)}


def archived_stage(path):
    binding, terminal = (read(path/name) for name in ('binding.json','terminal.json'))
    assert path.name==digest(binding) and not terminal['TEST_opened']
    assert all(sha(path/'source_snapshot'/p)==h for p,h in binding['source_sha256'].items())
    return binding,terminal


def replay_reads(db, context, stage_rows, program, codec, verified):
    out = []
    system = components.SYSTEM if codec=='tag' else numeric.SYSTEM
    schema = components.SCHEMA if codec=='tag' else numeric.SCHEMA
    for case,query,row in zip(context['cases'],context['inputs'],stage_rows,strict=True):
        assert row['case']==case.source_id and row['source_sha256']==digest(case.public) and row['failure'] is None
        identity=row['physical_call_id']
        if identity not in verified:
            physical_wire(db,{case.root_id},identity,case.root_id)
            verified.add(identity)
        raw,=db.execute('select result from calls where id=?',(identity,)).fetchone()
        response=json.loads(raw)
        request=read(Path(response['artifact_directory'])/'request.json')['payload']
        user={**query,'quoted_reader_policy':projection_policy(program,query)}
        assert request['messages']==[{'role':'system','content':system},
                                     {'role':'user','content':json.dumps(user,ensure_ascii=False,sort_keys=True)}]
        assert request['response_format']['json_schema']['schema']==schema and response['finish_reason']=='stop'
        if codec=='tag':
            amount=query['independently_verified_source_facts']['stated_value_dollars']
            tag,value=components.decode(response,amount)
            assert tag==row['read_tag'] and row['input_sha256']==digest(user)
        else:
            value=json.loads(response['content'])['value']
            assert row['input_sha256']==digest(query)
        assert value==row['value']
        out.append(value)
    return out


def materials():
    typed_binding,_,_,context,programs=components._materials()
    root=ROOT/read(components.POINTER)['artifact_root']
    p,t=archived_stage(root)
    assert p==typed_binding
    assert all(digest(programs[r])==p['program_sha256'][r] for r in ROLES)
    yield 'B8_typed_component',root,context,'tag',programs,{r:t['details'][r]['reads'] for r in ROLES},\
        t['summary']['isolated_shared_rejection_applied']

    first=ROOT/read(feedback.POINTER)['artifact_root']
    binding,terminal=archived_stage(first)
    assert binding['typed_terminal_sha256']==sha(root/'terminal.json') and binding['original_context']==context['binding']
    fault=read(first/'shared_explanation.json')
    assert fault['controls']['native_only'] and fault['controls']['literal_only']
    assert fault['controls']['independent_completions'] and not fault['controls']['shared_explanation']
    assert digest(fault['candidate'])==terminal['outcome']['condition_results']['shared_explanation']['program_sha256']
    yield 'initial_shared_feedback',first,context,'tag',{'incumbent':programs['candidate'],'candidate':fault['candidate']},\
        {'incumbent':t['details']['candidate']['reads'],'candidate':fault['audit']['typed_reads']},True

    for batch in (7,8):
        fit=ROOT/read(fit_pointer(batch))['artifact_root']
        frozen,end=archived_stage(fit)
        decisions=read(fit/'matched_decisions.json')
        assert digest(decisions)==end['matched_decisions_sha256'] and end['batch']==batch
        signal=decisions['relation'][OE]
        projections=signal['conditioned_projection']
        assert projections['binding']==context['binding']
        checkpoint=ROOT/frozen['checkpoint_root']
        study=read(checkpoint/'binding.json')
        assert digest(study)==frozen['study_binding_sha256']
        journal=TrainingJournal(checkpoint,study,load_roster(study))
        pair={'incumbent':journal.library(M2,batch-1)['programs'][OE],
              'candidate':read(fit/'candidates'/ORDINARY/OE/'measurements.json')['candidate']}
        assert digest(pair['candidate'])==signal['matched_proposal_sha256']
        for r in ROLES:
            assert digest(pair[r])==projections['evidence'][r]['validation']['patch_sha256']
        yield f'B{batch}_numeric_projection',fit,context,'number',pair,\
            {r:projections['evidence'][r]['reads'] for r in ROLES},signal['isolated_shared_rejection_applied']

    scope,_,_,_,other,_,pair=disclosure.materials()
    doc=ROOT/read(disclosure.POINTER)['artifact_root']
    bound_results,end=archived_stage(doc)
    assert bound_results==scope and end['status']==disclosure.DONE
    assert all(digest(pair[r])==bound_results['program_sha256'][r] for r in ROLES)
    yield 'B8_omitted_disclosure',doc,other,'tag',pair,{r:end['results'][r]['reads'] for r in ROLES},\
        end['selection']['isolated_shared_rejection_applied']


def run():
    results, binding, physical = {}, {}, set()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        counts=dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
        for name,stage,context,codec,programs,rows,original_veto in materials():
            signatures=feedback.signatures(context,'shared')
            independent=feedback.signatures(context,'independent_completions')
            assert len(signatures)==2 and len(independent)==16
            actual=[replay_reads(db,context,rows[r],programs[r],codec,physical) for r in ROLES]
            check=review_pair(context['inputs'],signatures,*actual)
            check.update({'actual_component_outputs':actual,'wire_mode':codec,'original_shared_veto':original_veto,
                          'shared_same_assertion_scope_changes_compatibility':bool(
                              check['support']['incumbent_on_common']['shared'])!=bool(
                              check['support']['candidate_on_common']['shared'])})
            results[name]=check
            binding[name]={'archived_terminal_sha256':sha(stage/'terminal.json'),
                           'cases_sha256':digest([c.public for c in context['cases']]),
                           'program_sha256':{r:digest(programs[r]) for r in ROLES},
                           'physical_calls_sha256':digest([rows[r] for r in ROLES]),
                           'allowed_signatures_sha256':digest(signatures)}
    lock={'scope':'archived_OpenExempt_TRAIN_title_projection_only','runner_sha256':sha(Path(__file__)),
          'source_bindings':binding}
    out=HOME/digest(lock)
    immutable_json(out/'binding.json',lock)
    terminal={'status':'settled_OE_matched_assertion_support','matched_pairs':len(results),
              'physical_responses_verified':len(physical),'by_pair':results,'ledger':counts,
              'paired_compatibility_differences_under_common_mask':sum(r['shared_same_assertion_scope_changes_compatibility']
                                                                      for r in results.values()),
              'original_library_changes':0,'new_requests':0,'original_TEST_content_or_labels_used':False}
    immutable_json(out/'terminal.json',terminal)
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**terminal},sort_keys=True),flush=True)


if __name__=='__main__':
    run()
