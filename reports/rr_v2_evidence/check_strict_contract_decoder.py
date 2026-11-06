"""Offline token-level check of the pending contract with the pinned tokenizer.

Only schema/tokenizer files are loaded. No model weights, generation, network,
oracle, or active-client mutation is involved. Artificial samples check syntax;
they are not research predictions or proof of translation faithfulness.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import socket
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def samples():
    valid = {"answer": 80, "program": {"kind": "expression", "body": {
        "bindings": [{"name": "fee", "value": 80, "type": "integer", "source": "s0"}],
        "query": {"op": "add", "args": [{"var": "fee"}, 0]},
        "source_links": {"s0": ["binding:fee"], "s1": ["query"]}}},
        "compiled_units": ["s0", "s1"], "unsupported_units": [], "interfaces": []}
    positives = {"integer_expression": valid}
    types = {
        "rational": "0.5", "scalar": True,
        "relation": {"columns": ["entity"], "rows": [["Person"]], "closed": True},
        "amounts": [{"value": 30, "unit": "USD", "owner": "owner", "period": "period",
                     "lineage": ["contribution"], "stage": "element"}],
        "allowance_bank": [{"key": ["rule", "owner", "period"], "balance": 100,
                            "policy": "input_order", "order_observable": True}],
        "resource_key": ["rule", "owner", "period"], "slot_list": ["fee"],
    }
    for kind, value in types.items():
        p = deepcopy(valid)
        p["program"]["body"]["bindings"].append({"name": "extra", "value": value, "type": kind, "source": "s0"})
        positives["binding_" + kind] = p
    specs = {
        "bind_rename": (1, {"from": ["entity"], "to": ["role"]}),
        "join_on": (2, {"keys": ["entity"]}), "project_exists": (1, {}),
        "group_by": (1, {"keys": ["entity"]}),
        "map": (1, {"primitive": "cap", "limit_slot": "fee", "scope": "element"}),
        "fold_reduce": (1, {"primitive": "sum_amounts"}),
        "thread_allowance": (1, {"bank_slot": "bank", "key_slot": "key"}),
    }
    for op, (arity, params) in specs.items():
        p = deepcopy(valid)
        graph = {"op": op, "inputs": [{"slot": "input"}] * arity, "params": params}
        p["program"] = {"kind": "connector", "body": {
            "bindings": [], "candidates": [graph], "source_links": {}, "project": "identity"}}
        positives["connector_syntax_" + op] = p
    unsupported = deepcopy(valid)
    unsupported["program"] = {"kind": "unsupported", "body": {}}
    unsupported["compiled_units"] = []
    positives["explicit_unsupported"] = unsupported
    interface = deepcopy(valid)
    interface["interfaces"] = [{"fields": ["entity_equality"],
        "graph": {"op": "project_exists", "inputs": [{"slot": "input"}], "params": {}}, "bindings": []}]
    positives["exact_interface_fields"] = interface
    negatives = {}
    p = deepcopy(valid)
    del p["program"]["body"]["query"]
    negatives["missing_query"] = p
    p = deepcopy(valid)
    p["program"]["body"]["bindings"][0]["value"] = "80"
    negatives["string_in_integer_binding"] = p
    p = deepcopy(interface)
    p["interfaces"][0]["allowed_semantic_fields"] = p["interfaces"][0].pop("fields")
    negatives["renamed_interface_key"] = p
    p = deepcopy(interface)
    p["interfaces"][0]["graph"]["op"] = "arbitrary_code"
    negatives["unknown_connector"] = p
    p = deepcopy(interface)
    p["interfaces"][0]["graph"]["inputs"] = []
    negatives["wrong_connector_arity"] = p
    p = deepcopy(interface)
    p["interfaces"][0]["graph"]["params"] = {"literal_threshold": 400}
    negatives["literal_graph_parameter"] = p
    return positives, negatives


def main():
    import xgrammar
    from transformers import AutoTokenizer

    root = Path(__file__).resolve().parents[2]
    folder = root / "reports/rr_v2_evidence/strict_contract_candidate"
    config = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    model_root = Path(config["executor"]["model_root"])
    vocab_size = json.loads((model_root / "config.json").read_text())["vocab_size"]
    ledger = sqlite3.connect(root / config["ledger_path"])
    before = ledger.execute("SELECT * FROM calls ORDER BY id").fetchall()

    def deny_network(*args, **kwargs):
        raise RuntimeError("Network forbidden in offline decoder check")

    results, old = {}, {}
    with patch.object(socket.socket, "connect", deny_network), patch.object(socket.socket, "connect_ex", deny_network):
        tokenizer = AutoTokenizer.from_pretrained(str(model_root), local_files_only=True, trust_remote_code=False)
        info = xgrammar.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab_size)
        compiler = xgrammar.GrammarCompiler(info, max_threads=1)
        positives, negatives = samples()
        for dataset in ("OpenExempt", "RuleArena_Airline", "SARA_v2_Binary"):
            schema = json.loads((folder / f"{dataset}.json").read_text())
            compiled = compiler.compile_json_schema(schema, strict_mode=True)

            def accepts(text, *, token_level):
                matcher = xgrammar.GrammarMatcher(compiled)
                if token_level:
                    accepted = all(matcher.accept_token(t) for t in tokenizer.encode(text, add_special_tokens=False))
                else:
                    accepted = matcher.accept_string(text)
                return accepted and matcher.accept_token(tokenizer.eos_token_id) and matcher.is_terminated()

            dataset_results = {}
            for expected, cases in ((True, positives), (False, negatives)):
                for name, value in cases.items():
                    value = deepcopy(value)
                    if dataset == "OpenExempt":
                        value["answer"] = {"EC": {}, "EV": {}}
                    elif dataset == "SARA_v2_Binary":
                        value["answer"] = "Entailment"
                    text = json.dumps(value)
                    by_tokens, by_string = accepts(text, token_level=True), accepts(text, token_level=False)
                    dataset_results[name] = {"expected": expected, "token_level": by_tokens, "string_level": by_string}
                    if by_tokens != expected or by_string != expected:
                        raise AssertionError((dataset, name, expected, by_tokens, by_string))
            results[dataset] = dataset_results
            raw_results = []
            for path in sorted((root / "artifacts/rr_v2_preflight/oracle_guard/pilot_sources").glob("*.json")):
                record = json.loads(path.read_text())
                if record["dataset"] == dataset:
                    raw_results.extend(accepts(c["raw_content"], token_level=True) for c in record["calls"])
            old[dataset] = {"saved_outputs": len(raw_results), "accepted_by_candidate_decoder": sum(raw_results)}
    after = ledger.execute("SELECT * FROM calls ORDER BY id").fetchall()
    if before != after:
        raise AssertionError("Research ledger changed during an offline check")
    receipt = {"kind": "offline_decoder_acceptance_not_model_generation",
        "xgrammar_version": importlib.metadata.version("xgrammar"),
        "tokenizer_model_revision": model_root.name, "vocab_size": vocab_size,
        "tokenizer_json_sha256": hashlib.sha256((model_root / "tokenizer.json").read_bytes()).hexdigest(),
        "network_blocked": True, "model_weights_loaded": False, "executor_calls_added": 0,
        "teacher_calls_added": 0, "ledger_unchanged": True,
        "artificial_cases_per_schema": len(positives) + len(negatives), "results": results,
        "saved_TRAIN_outputs": old, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "active_contract_changed": False, "real_generation_validation_still_requires_authorization": True}
    (folder / "decoder_acceptance.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
