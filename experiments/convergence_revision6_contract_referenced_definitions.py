"""Test reference-aware evidence selection on the original paired ContractNLI reads."""

from collections import Counter
import json
from pathlib import Path
import re
import sqlite3

from experiments import convergence_revision6_contract_citation_roles as previous
from experiments import convergence_revision6_contract_link_control as control
from experiments import convergence_revision6_contract_links as links
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision6_contract_referenced_definitions'
POINTER = HANDOFF / 'revision6_contract_referenced_definitions_current.json'
DECLARED_HEAD = re.compile(
    r'[“"“](?P<head>[A-Za-z][A-Za-z -]{0,50})[”"]\s+(?:shall\s+(?:mean|include)|means?|includes?)\b',
    re.I,
)
DECLARED_ALIAS = re.compile(
    r'\b(?:collectively|hereinafter(?:\s+referred\s+to\s+as)?)\s*,?\s*'
    r'[“"](?P<head>[A-Za-z][A-Za-z -]{0,50})[”"]', re.I,
)


def definition_head(text):
    normalized = ' '.join(text.split())
    heads = {match.group('head').casefold() for pattern in (DECLARED_HEAD, DECLARED_ALIAS)
             for match in pattern.finditer(normalized)}
    return next(iter(heads)) if len(heads) == 1 else None


def shared_projection(spans, native, permission, definition):
    """Follow aliases used by the cited operative proof, even beside inline employees."""
    if native['answer'] != 'Entailment':
        return native
    retained, _ = previous.select_citations(spans, permission, None)
    _, old_definition = previous.select_citations(spans, retained, definition)
    if definition is not None and old_definition is None:
        # Keep unknown or multiple heads. Delete a known alias only when the surviving
        # permission spans establish inline membership and make no reference to it.
        head = definition_head(spans[definition])
        uses = ' '.join(' '.join(spans[i].split()) for i in retained).casefold()
        if head and not re.search(r'(?<!\w)'+re.escape(head)+r'(?!\w)', uses):
            definition = None
    ids = set(retained)
    if definition is not None:
        ids.add(definition)
    return {**native, 'evidence_sentence_ids':sorted(ids)}


def run():
    control_spec, cohort, views, wires, study, linked_root, linked_end = control.materials()
    direct_root = ROOT / read(control.POINTER)['artifact_root']
    direct_end = verify(read(direct_root/'terminal.json'), 'terminal_sha256')
    filtered_root = ROOT / read(previous.POINTER)['artifact_root']
    filtered = verify(read(filtered_root/'terminal.json'), 'terminal_sha256')
    if (direct_root.name != digest(control_spec) or read(direct_root/'binding.json') != control_spec
            or direct_end['TEST_opened'] or filtered['TEST_opened']
            or sha(direct_root/'direct_predictions.json') != direct_end['prediction_sha256']
            or sha(filtered_root/'predictions.json') != filtered['predictions_sha256']):
        raise ValueError('Require the same native responses and original filtering comparison')
    _, train_rows, all_views, *_ = links.materials()
    bind = {'stage':'revision6_contract_referenced_definitions', 'TEST_opened':False,
            'linked_terminal':linked_end['terminal_sha256'], 'direct_terminal':direct_end['terminal_sha256'],
            'previous_filter_terminal':filtered['terminal_sha256'],
            'source_sha256':{str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))}}
    out = HOME / digest(bind)
    immutable_json(out/'binding.json', bind)
    if (out/'terminal.json').exists():
        print(out)
        return
    bank = read(filtered_root/'predictions.json')
    arm_names = ('fixed','learned','direct_same_input')
    bank.update({arm+'_referenced':{} for arm in arm_names})
    training = Counter()
    selected = {row['source']:'synthesized' if row['picked_synthesized'] else 'fixed'
                for row in linked_end['pre_read_selected_pairs']}
    reviews = {item['source']['key']:links.linked.REVIEWS[pos] for pos,item in train_rows.items()}
    for path in (linked_root/'measured_reads').glob('*.json'):
        row = read(path)
        key, observed = row['source'], row['native']
        split = 'train' if key in reviews else 'dev'
        view = all_views[split][key]
        role, = (p['name'] for p in view['plans'] if p['version'] == row['raw_read_version'])
        raw = links.native(observed)
        revised = shared_projection(view['spans'], raw, observed['permission_spans'], observed['definition_span'])
        if split == 'train':
            _, definition, required, allowed = reviews[key]
            needed = required | ({definition} if definition is not None else set())
            removed = set(raw['evidence_sentence_ids']) - set(revised['evidence_sentence_ids'])
            training['removed_required'] += len(needed & removed)
            training['removed_extraneous'] += len(removed - allowed - needed)
            training['paired_reads'] += 1
            continue
        if raw != bank[role][key]:
            raise ValueError('A measured relation decode differs from the sealed study')
        if role == 'fixed':
            bank['fixed_referenced'][key] = revised
        if role == selected[key]:
            bank['learned_referenced'][key] = revised
    if training['removed_required'] or not training['removed_extraneous']:
        raise ValueError('The TRAIN source audits must support the evidence projection')
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        for key, view in views.items():
            receipt = read(direct_root/'physical_reads'/(digest(key)+'.json'))
            record = previous.raw_call(db, receipt['call_id'], key, 'skill_dev')
            raw = bank['direct_same_input'][key]
            if control.decode(view,wires[key][1],record) != raw or receipt['output'] != raw:
                raise ValueError('Require the exact same-input direct extraction')
            if raw['answer'] == 'Entailment':
                slots = links.citations.canonical_citations(json.loads(record['content']))
                raw = shared_projection(view['spans'],raw,slots['permission_spans'],slots['definition_span'])
            bank['direct_same_input_referenced'][key] = raw
    prediction_hash = immutable_json(out/'sealed_predictions.json', bank)
    path = study['grading_paths'][links.linked.DATASET]
    if 'dev' not in Path(path).parts or sha(ROOT/path) != study['grading_file_sha256'][path]:
        raise ValueError('Use the sealed original DEV labels after forming predictions')
    labels = read(ROOT/path)
    scores = links.first.compare(cohort, bank, labels)
    pairs = {}
    for a,b in (('learned','learned_referenced'), ('direct_same_input','direct_same_input_referenced'),
                ('direct_same_input_referenced','learned_referenced')):
        cells = [[{'source':s['key'], 'view':links.linked.TASK, 'grade':links.first.native_score(
                    s, bank[role][s['key']], labels)['evidence_f1']} for s in cohort] for role in (a,b)]
        pairs[b+'_vs_'+a] = paired_source_effect(*cells)
    result = sealed({'status':'settled_revision6_contract_referenced_definitions', 'binding_sha256':out.name,
                     'TRAIN':dict(training),'DEV_mothers':len(cohort),'scores':scores,'effects':pairs,
                     'prediction_sha256':prediction_hash,'new_executor_calls':0,'TEST_opened':False},'terminal_sha256')
    immutable_json(out/'terminal.json',result)
    write_status(out,{'status':result['status'],'terminal_sha256':result['terminal_sha256']},POINTER)
    print(out)


if __name__ == '__main__':
    run()
