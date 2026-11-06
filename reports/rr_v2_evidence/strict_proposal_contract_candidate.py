"""Offline candidate for the next explicitly authorized contract repair.

Not imported by the active model client. This module supplies complete typed
wire schemas, while the existing source/type/semantic validator stays in charge.
It does not force compilation of unsupported text or encode any task answer.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from legal_skill_guard.rr.interfaces import FIELDS

TARGETS = ("OpenExempt", "RuleArena_Airline", "SARA_v2_Binary")


def obj(properties):
    return {"type": "object", "additionalProperties": False,
            "required": list(properties), "properties": properties}


def array(items):
    return {"type": "array", "items": items}


def ref(name):
    return {"$ref": "#/$defs/" + name}


def strict_proposal_schema(dataset, base_schema):
    if dataset not in TARGETS:
        return deepcopy(base_schema)
    schema = deepcopy(base_schema)
    string = {"type": "string"}
    strings = array(string)
    scalar = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}]}
    atom = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"},
                      {"type": "null"}, obj({"var": string}), ref("operation")]}
    operation = obj({"op": {"enum": ["if", "and", "or", "not", "eq", "ne", "lt", "le", "add", "sub",
                                     "min", "max", "scale", "divide_constant", "array", "pair", "object", "concat"]},
                     "args": array(ref("expression"))})
    amount = obj({"value": {"type": "integer", "minimum": 0}, "unit": string, "owner": string,
                  "period": string, "lineage": {**strings, "minItems": 1},
                  "stage": {"enum": ["element", "closed_group"]}})
    key = {**strings, "minItems": 3, "maxItems": 3}
    bank = obj({"key": key, "balance": {"type": "integer", "minimum": 0},
                "policy": {"enum": ["input_order", "reverse_order"]}, "order_observable": {"type": "boolean"}})
    types = {"integer": {"type": "integer"}, "rational": {"type": "string"}, "scalar": scalar,
             "relation": obj({"columns": strings, "rows": array(strings), "closed": {"type": "boolean"}}),
             "amounts": array(amount), "allowance_bank": array(bank), "resource_key": key, "slot_list": strings}
    binding = {"anyOf": [obj({"name": string, "value": value, "type": {"enum": [kind]}, "source": string})
                         for kind, value in types.items()]}
    bindings = array(ref("binding"))
    links = {"type": "object", "additionalProperties": {**strings, "minItems": 1}}
    def connector(op, arity, params):
        return obj({"op": {"enum": [op]}, "inputs": {"type": "array", "items": ref("connector"),
                    "minItems": arity, "maxItems": arity}, "params": obj(params)})
    graphs = {"anyOf": [obj({"slot": string}),
        connector("bind_rename", 1, {"from": strings, "to": strings}),
        connector("join_on", 2, {"keys": strings}), connector("project_exists", 1, {}),
        connector("group_by", 1, {"keys": strings}),
        connector("map", 1, {"primitive": {"enum": ["cap"]}, "limit_slot": string,
                             "scope": {"enum": ["element", "closed_group"]}}),
        connector("map", 1, {"primitive": {"enum": ["exists"]}}),
        connector("fold_reduce", 1, {"primitive": {"enum": ["sum_amounts", "all", "any"]}}),
        connector("thread_allowance", 1, {"bank_slot": string, "key_slot": string})]}
    expression_body = obj({"bindings": bindings, "query": ref("operation"), "source_links": links})
    connector_body = obj({"bindings": bindings, "candidates": {"type": "array", "items": ref("connector"),
                         "minItems": 1, "maxItems": 32}, "source_links": links,
                          "project": {"enum": ["identity", "amount_value"]}})
    schema["$defs"] = {"expression": atom, "operation": operation, "binding": binding, "connector": graphs}
    schema["properties"]["program"] = {"anyOf": [
        obj({"kind": {"enum": ["expression"]}, "body": expression_body}),
        obj({"kind": {"enum": ["connector"]}, "body": connector_body}),
        obj({"kind": {"enum": ["unsupported"]}, "body": obj({})})]}
    schema["properties"]["interfaces"] = {"type": "array", "maxItems": 8,
        "items": obj({"fields": array({"enum": list(FIELDS)}), "graph": ref("connector"), "bindings": bindings})}
    return schema


def main():
    import hashlib
    import importlib.metadata

    import jsonschema
    import xgrammar

    from legal_skill_guard.rr.engine import analyze, proposal_schema
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/rr_v2_evidence/strict_contract_candidate"
    output.mkdir(exist_ok=True)
    schemas = {d: strict_proposal_schema(d, proposal_schema(d)) for d in TARGETS}
    for dataset, schema in schemas.items():
        jsonschema.Draft202012Validator.check_schema(schema)
        xgrammar.Grammar.from_json_schema(json.dumps(schema), strict_mode=True)
        (output / f"{dataset}.json").write_text(json.dumps(schema, indent=2) + "\n")
    source = {"dataset": "RuleArena_Airline", "public": {"rules": "The fee is 80.", "prompt": "Apply the fee."}}
    valid = {"answer": 80, "program": {"kind": "expression", "body": {
        "bindings": [{"name": "fee", "value": 80, "type": "integer", "source": "s0"}],
        "query": {"op": "add", "args": [{"var": "fee"}, 0]},
        "source_links": {"s0": ["binding:fee"], "s1": ["query"]}}},
        "compiled_units": ["s0", "s1"], "unsupported_units": [], "interfaces": []}
    jsonschema.validate(valid, schemas["RuleArena_Airline"])
    assert analyze(source, json.dumps(valid))["certificate_status"] == "completion_stable"
    malformed = []
    missing = deepcopy(valid)
    del missing["program"]["body"]["query"]
    malformed.append(missing)
    mistyped = deepcopy(valid)
    mistyped["program"]["body"]["bindings"][0]["value"] = "80"
    malformed.append(mistyped)
    bad_interface = deepcopy(valid)
    bad_interface["interfaces"] = [{"allowed_semantic_fields": []}]
    malformed.append(bad_interface)
    for bad in malformed:
        assert not jsonschema.Draft202012Validator(schemas["RuleArena_Airline"]).is_valid(bad)
    unsupported = {**valid, "program": {"kind": "unsupported", "body": {}}, "compiled_units": []}
    jsonschema.validate(unsupported, schemas["RuleArena_Airline"])
    counts = {d: {"saved_calls": 0, "candidate_schema_accepts": 0} for d in TARGETS}
    for path in (root / "artifacts/rr_v2_preflight/oracle_guard/pilot_sources").glob("*.json"):
        record = json.loads(path.read_text())
        dataset = record["dataset"]
        if dataset not in counts:
            continue
        for call in record["calls"]:
            counts[dataset]["saved_calls"] += 1
            try:
                value = json.loads(call["raw_content"])
                counts[dataset]["candidate_schema_accepts"] += jsonschema.Draft202012Validator(schemas[dataset]).is_valid(value)
            except ValueError:
                pass
    receipt = {"kind": "offline_candidate_not_dispatched_or_adopted", "executor_calls_added": 0,
               "teacher_calls_added": 0, "active_request_contract_changed": False,
               "xgrammar_version": importlib.metadata.version("xgrammar"), "three_schemas_compile": True,
               "artificial_executable_example_passed": True, "three_malformed_examples_rejected": True,
               "unsupported_still_allowed": True, "saved_training_output_shape_checks": counts,
               "schemas_sha256": {d: hashlib.sha256((output/f"{d}.json").read_bytes()).hexdigest() for d in TARGETS},
               "candidate_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "real_generation_validation_pending": True}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
