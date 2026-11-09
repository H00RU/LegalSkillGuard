"""Exact processing repair for an observed lowercase Boolean expression atom.

No field aliases, missing formulas, quotes, domains or source roles are filled.
Original raw generation/validation artifacts remain immutable.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
from legal_skill_guard.rr.source_obligations import compile_module, verify

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109'


def process(path, target):
    raw = json.loads(path.read_text())
    original = json.loads(raw['module']) if isinstance(raw['module'], str) else raw['module']
    value = copy.deepcopy(original)
    names = {r['name'] for r in value['inputs']} | {'result'}
    repairs = []
    fields = [('domain', value, 'domain'), ('expression', value, 'expression')]
    for i, row in enumerate(value['obligations']):
        fields.extend([(f'obligations[{i}].condition', row, 'condition'), (f'obligations[{i}].assertion', row, 'assertion')])
    for field, container, key in fields:
        text = container[key]
        tree = ast.parse(text, mode='eval')
        atoms = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in {'true','false'} and n.id not in names]
        if not atoms:
            continue
        class BooleanAtoms(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id in {'true','false'} and node.id not in names:
                    return ast.copy_location(ast.Constant(node.id == 'true'), node)
                return node
        repaired = ast.unparse(ast.fix_missing_locations(BooleanAtoms().visit(tree)))
        container[key] = repaired
        repairs.append(dict(path='$.'+field,before=text,after=repaired,
            reason='Observed JSON-style Boolean literal in a pure Boolean expression; no declared variable has that name'))
    module = compile_module(value, target['rules'])
    receipt = dict(original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), original_validation=raw['validation'],
        transformations=repairs,module=value,validation=verify(module),quote_positions=module.quote_positions,
        no_missing_semantic_content_supplied=True,original_artifact_overwritten=False,
        new_model_calls=0,source_semantic_review='Still required separately')
    output = path.with_name(path.stem+'.processed.json')
    if output.exists():
        assert json.loads(output.read_text()) == receipt
    else:
        output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return receipt


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--role',choices=['executor','teacher'],required=True)
    p.add_argument('--target',required=True);args=p.parse_args()
    seal=json.loads((STAGE/'seal.json').read_text())
    target=next(t for t in seal['targets'] if t['id']==args.target)
    receipt=process(STAGE/(args.role+'_'+args.target+'.json'),target)
    print(json.dumps(dict(role=args.role,target=args.target,transformations=receipt['transformations'],validation=receipt['validation']),ensure_ascii=False))


if __name__=='__main__':main()
