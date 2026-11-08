"""Compiler-material persistence and actual placeholder-failure regressions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.compiler_templates import make_template,validate_template,template_examples
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.model_horn import model_horn_prompt,parse_model_horn,LogicTranslationError,_atoms
from legal_skill_guard.rr.horn import Atom
from test_rr_model_horn import actual_source,CONTROL

ROOT=Path(__file__).resolve().parents[1]


def fixture_template():
    # Fictional origin is a unit-test fixture only, never paid/model evidence.
    return make_template(actual_source(),CONTROL,{'role':'teacher','call_id':'offline_fixture',
                                                'request_hash':'offline_fixture'})


def later_source():
    sources=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
    return next(s for s in sources if s['key']=='ProofWriter_OWA_depth5:e95366c5947484c083f10b4fea4f936a17ec6bb58ed903aa3f1d376b7105c2dc')


def test_exact_template_add_update_freeze_restore_and_frozen_no_learning(tmp_path):
    item=fixture_template();library=SkillLibrary()
    key=library.add_compiler_template(item);assert library.add_compiler_template(item)==key
    assert len(library.compiler_templates)==1
    path=tmp_path/'B.frozen.json';library.freeze(path);restored=SkillLibrary.restore(path)
    assert restored.export()==library.export()
    with pytest.raises(ValueError,match='Frozen library'):restored.add_compiler_template(item)
    changed=deepcopy(item);changed['code']=changed['code'].replace('blue(cat)','red(cat)')
    with pytest.raises(ValueError,match='hash differs'):validate_template(changed)


def test_current_source_never_receives_its_own_compiler_program():
    item=fixture_template()
    with pytest.raises(ValueError,match='current program'):
        template_examples(actual_source(),{'compiler_templates':[item]})


def test_same_common_program_material_survives_masking_B_patterns():
    source=later_source();item=fixture_template();libraries=[{'patterns':[], 'compiler_templates':[item]},
        {'patterns':[{'only':'interface metadata'}],'compiler_templates':[item]}]
    payloads=[json.loads(model_horn_prompt(source,lib)[1]['content']) for lib in libraries]
    assert payloads[0]==payloads[1]
    example=payloads[0]['compiler_training_examples'][0]
    assert example['code']==CONTROL and len(example['units'])==23
    assert set(example)=={'template_hash','units','code'}


def test_actual_multiword_identifier_is_a_representation_conversion_and_placeholders_stay_invalid():
    assert _atoms('-visits(bald_eagle,tiger)')==(_atoms('-visits("bald eagle",tiger)')[0],)
    assert _atoms('-visits(bald_eagle,tiger)')==(Atom('visits',('bald eagle','tiger'),False),)
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_horn_pw9_v1_20261108'
    result=json.loads((stage/'result.json').read_text())
    for step in range(2):
        call=stage/'calls'/digest('reference_horn_pw9_v1_20261108:parse:'+str(step))/'result.json'
        raw=json.loads(call.read_text())['content']
        with pytest.raises(LogicTranslationError,match='differs from its public source'):
            parse_model_horn(later_source(),raw)


def test_actual_prepare_rejects_self_template_before_network_or_a_model_request(tmp_path):
    from experiments.rr_v2_reference_frontend import prepare
    content={'frozen':True,'patterns':[],'compiler_templates':[fixture_template()]}
    path=tmp_path/'self.json';path.write_text(json.dumps({'content':content,'sha256':digest(content)}))
    with pytest.raises(ValueError,match='strictly earlier'):
        prepare(ROOT,'offline_self_template',actual_source()['key'],path)
