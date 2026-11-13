"""Zero-generation audit of a closed role interface and acquired typed terms."""
import ast
import json
from pathlib import Path
import xgrammar as xgr

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,read,sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,term_sort
from legal_skill_guard.skill_evolution.source_python import merge_functions,execute
from legal_skill_guard.skill_evolution.source_term_interface import term_schema,validate_value


def run():
    prior=ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113';bundle=read(prior/'seed.json')
    public=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    source=next(s for s in public if s['key'].startswith('ContractNLI:8af247'))
    role=next(o for o in bundle['operations'] if o['name']=='disposal_retention_actor_role')
    probe=merge_functions(bundle['program'],["def apply(inputs,premises):\n    errors=[]\n    actor=_sr_actor(inputs['choice'],inputs['raw'],errors,'audit')\n    return {'actor':actor,'unresolved':errors}\n"])
    images={c['name']:execute(probe,{'choice':c['name'],'raw':source['views'][0]['public']['source_text']}) for c in role['choices']}
    target=['legal_advisors_of',['receiving_party']]
    canonical=target;schema=term_schema(bundle['spec'],'Participant')
    assert validate_value(bundle['spec'],'Participant',canonical)==target
    compiled=xgr.GrammarCompiler(xgr.TokenizerInfo([bytes([i]) for i in range(256)])).compile_json_schema(json.dumps(schema))
    samples={'valid':canonical,'missing_argument':['legal_advisors_of'],
        'cross_sort':['legal_advisors_of',['confidential_information']],
        'extra_argument':['receiving_party',['receiving_party']]}
    outcomes={}
    for name,sample in samples.items():
        matcher=xgr.GrammarMatcher(compiled,terminate_without_stop_token=True)
        accepted=matcher.accept_string(json.dumps(sample))
        outcomes[name]={'grammar_accepted':accepted,'grammar_terminated':matcher.is_terminated()}
    assert outcomes['valid']['grammar_accepted'] and outcomes['valid']['grammar_terminated']
    assert all(not v['grammar_accepted'] for k,v in outcomes.items() if k!='valid')
    preserved=[];common=read(prior/'revision/common_input.json')
    for s in common['original_TRAIN']:
        for statement in s['actual_source_output']['statements']:
            term=statement['term'];sort=term_sort(term,constructors(bundle['spec']))
            assert validate_value(bundle['spec'],sort,term)==term
            preserved.append({'source':s['source'],'sort':sort})
    result={'new_model_requests':0,'uses_existing_acquired_constructor_meanings_only':True,
        'original_TRAIN_source':source['key'],'current_actor_operation_images':images,
        'counterexample_term':target,'counterexample_well_typed':True,
        'counterexample_constructor_form_absent_from_current_images':all(v['actor']!=target for v in images.values()),
        'semantic_aliases_not_automatically_declared_inequivalent':True,
        'actual_current_source_terms_losslessly_roundtripped':preserved,'xgrammar_checks':outcomes,
        'schema':schema,'new_interface_not_installed_in_frozen_validation':True,
        'format_adaptation_not_method_contribution_or_generated_IR_success':True,
        'source_sha256':{'legal_skill_guard/skill_evolution/source_term_interface.py':sha(ROOT/'legal_skill_guard/skill_evolution/source_term_interface.py')},
        'goal_complete':False}
    immutable_json(OUT/'canonical_representation_audit/result.json',result)
    print(json.dumps({'actor_images':images,'roundtrips':len(preserved),'grammar':outcomes,'new_model_calls':0}),flush=True)


if __name__=='__main__':run()
