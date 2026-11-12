"""Fixed-program source-selection impossibility witnesses, not new legal gold."""
import ast
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import execute_helper
from experiments.legal_skill_evolution_whole_source_control import RUN, PRODUCER, CONSUMER, counts


def read(p):return json.loads(p.read_text())


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'artifacts' / RUN
    protocol, actual = read(folder / 'protocol.json'), read(folder / 'completed.json')
    if digest(protocol) != actual['protocol_hash']:raise ValueError('Control binding differs')
    library = Library.load(root / protocol['libraries']['Full']['path'])
    producer, consumer = library.skills[PRODUCER], library.skills[CONSUMER]
    tree = ast.parse(producer.procedure)
    loop = next(n for n in ast.walk(tree) if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'clause_text')
    names = ('prohibits_third_parties', 'express_permission', 'confidentiality_condition',
             'need_condition', 'purpose_condition', 'qualified_permission')
    expressions = {n.targets[0].id: n.value for n in loop.body if isinstance(n, ast.Assign)
        and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names}
    if tuple(expressions) != names:raise ValueError('Witness applies only to the reviewed fixed producer structure')
    # These gates are the actual learned expressions, not a host legal parser.
    for i, name in enumerate(names):
        free = {n.id for n in ast.walk(expressions[name]) if isinstance(n, ast.Name)}
        if not free <= {'clause_text', *names[:i]}:raise ValueError('Cross-span gate unsupported by this witness')
    for flag in ('employee_permission', 'professional_advisor_permission'):
        stores = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == flag for t in n.targets)]
        if len(stores) != 2 or not all(isinstance(n.value, ast.Constant) and type(n.value.value) is bool for n in stores):
            raise ValueError('The reviewed permission flags must only initialize False and latch True')
        guarded = [n for n in ast.walk(loop) if isinstance(n, ast.If) and any(
            isinstance(t, ast.Assign) and any(isinstance(a, ast.Name) and a.id == flag for a in t.targets)
            for t in n.body)]
        if len(guarded) != 1 or not (isinstance(guarded[0].test, ast.BoolOp) and isinstance(guarded[0].test.op, ast.And)
                and isinstance(guarded[0].test.values[0], ast.Name) and guarded[0].test.values[0].id == 'qualified_permission'):
            raise ValueError('A permission flag has another route to True')
    records = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    ledger = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3';before = counts(ledger)
    witnesses = []
    for key in protocol['next_original_TRAIN_parents']:
        source = records[key];public = source['views'][0]['public']
        spans = source_spans({'source_text': public['source_text'], 'sentence_spans': public['sentence_spans']})
        supported = {n: [] for n in ('prohibits_third_parties', 'qualified_permission')}
        for span in spans:
            env = {'clause_text': span['text']}
            for name in names:
                env[name] = eval(compile(ast.Expression(expressions[name]), '<fixed-learned-gate>', 'eval'), {'__builtins__': {}}, env)
            for name in supported:
                if env[name]:supported[name].append(span['id'])
        if any(supported.values()):raise ValueError('Absence witness does not establish this source')
        roots = []
        for view in source['views']:
            if view['id'] not in ('nda-5', 'nda-7'):continue
            possibilities = []
            for exception in (False, True):
                for prohibition in (False, True):
                    inputs = {'current_question': view['public']['question'],
                        'representative_exception_applies': exception, 'general_third_party_prohibition': prohibition}
                    answer = execute_helper(consumer, inputs, {})['answer']
                    possibilities.append({'exception': exception, 'general_prohibition': prohibition, 'answer': answer})
            target = grading[key][view['id']]['answer']
            roots.append({'view': view['id'], 'native_TRAIN_target': target,
                'consumer_output_with_current_source_gates_False': possibilities[0]['answer'],
                'reachable_by_varying_existing_producer_output_interface': target in {p['answer'] for p in possibilities},
                'counterfactual_output_interface_table': possibilities,
                'counterfactual_values_not_acquired_rules_or_proposed_repairs': True})
        witnesses.append({'source': key, 'source_text_sha256': hashlib.sha256(public['source_text'].encode()).hexdigest(),
            'all_supplied_rule_spans_checked': len(spans), 'actual_learned_gate_support_ids': supported,
            'any_literal_span_selection_cannot_activate_permission_or_prohibition': True,
            'scope': 'Any subset, order or repetition of these exact current-source spans; no rewriting, invented law or fallback. This is not a theorem about other programs, neural procedures or the two methods in general.',
            'root_interface_analysis': roots})
    after = counts(ledger);assert before == after
    result = {'producer_hash': producer.hash, 'consumer_hash': consumer.hash,
        'reviewed_actual_expressions': {n: ast.unparse(e) for n, e in expressions.items()},
        'witnesses': witnesses, 'new_model_requests': 0, 'ledger_before': before, 'ledger_after': after,
        'conclusion': 'All six current Full errors require a procedure/learning-object change, not another literal-span selection. Every target is expressible through the existing consumer interface, so this sequence does not itself force consumer co-revision. Output-interface reachability is not a demonstrated source-grounded producer repair.',
        'not_global_impossibility_of_Lift_or_CoRev': True, 'goal_complete': False}
    immutable_json(folder / 'literal_selection_witnesses.json', result)
    print(json.dumps({'sources': len(witnesses), 'fixed_Full_errors_not_repairable_by_selection': sum(len(w['root_interface_analysis']) for w in witnesses),
        'source_grounded_new_repair_not_claimed': True, 'new_model_requests': 0}))


if __name__ == '__main__':main()
