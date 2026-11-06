"""CPU-only check of all precommitted source-bound round2 schemas and inputs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    import xgrammar
    from transformers import AutoTokenizer

    from legal_skill_guard.rr.coverage import digest
    from legal_skill_guard.rr.data_store import PreflightData
    from legal_skill_guard.rr.engine import proposal_schema

    root = Path(__file__).resolve().parents[2]
    cfg = json.loads((root / "configs/rr_v2_preflight.json").read_text())
    data = PreflightData(root, root / cfg["source_manifest"])
    old = json.loads((root / "reports/rr_v2_evidence/strict_contract_candidate/proposed_validation_plan.json").read_text())
    spec = importlib.util.spec_from_file_location("schema_examples", root / "reports/rr_v2_evidence/check_strict_contract_decoder.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    positives, negatives = module.samples()
    p = deepcopy(positives["integer_expression"])
    p["program"]["body"]["bindings"][0]["source"] = "Facts"
    negatives["invalid_source_alias"] = p
    p = deepcopy(positives["integer_expression"])
    p["program"]["body"]["source_links"] = {"unit": ["s0"]}
    negatives["invalid_source_links_key"] = p
    p = deepcopy(positives["integer_expression"])
    p["program"]["body"]["query"] = {"op": "if", "args": [True]}
    negatives["missing_if_branches"] = p
    def deny(*args, **kwargs):
        raise RuntimeError("No network or generation during schema precheck")
    records = []
    with patch.object(socket.socket, "connect", deny), patch.object(socket.socket, "connect_ex", deny):
        model_root = Path(cfg["executor"]["model_root"])
        tok = AutoTokenizer.from_pretrained(str(model_root), local_files_only=True, trust_remote_code=False)
        vocab = json.loads((model_root / "config.json").read_text())["vocab_size"]
        compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(tok, vocab_size=vocab), max_threads=1)
        for item in old["calls"]:
            source = data.public(item["source"])
            request = None
            for parent in (root / "artifacts/rr_v2_preflight/oracle_guard", root / "artifacts/rr_v2_preflight"):
                path = parent / "calls" / digest(item["reuse_original_prompt_from_call_id"]) / "request.json"
                if path.exists():
                    request = json.loads(path.read_text())
                    break
            tokens = tok.apply_chat_template(request["payload"]["messages"], tokenize=True,
                                            add_generation_prompt=True, enable_thinking=True)
            if tokens != request["tokenization"]["tokens"]:
                raise AssertionError("Literal original prompt no longer has the same serving tokenization")
            schema = proposal_schema(source["dataset"], source=source)
            compiled = compiler.compile_json_schema(schema, strict_mode=True)
            count = 0
            for expected, cases in ((True, positives), (False, negatives)):
                for name, value in cases.items():
                    value = deepcopy(value)
                    if source["dataset"] == "OpenExempt":
                        value["answer"] = {"EC": {}, "EV": {}}
                    elif source["dataset"] == "SARA_v2_Binary":
                        value["answer"] = "Entailment"
                    text = json.dumps(value)
                    matcher = xgrammar.GrammarMatcher(compiled)
                    ok = all(matcher.accept_token(t) for t in tok.encode(text, add_special_tokens=False))
                    ok = ok and matcher.accept_token(tok.eos_token_id) and matcher.is_terminated()
                    if ok != expected:
                        raise AssertionError((source["key"], name, expected, ok))
                    count += 1
            records.append({"source": source["key"], "schema_hash": digest(schema), "compiled": True,
                            "token_matcher_cases_passed": count, "original_tokenization_exact_match": True,
                            "token_ids_hash": digest(tokens), "prompt_tokens": len(tokens),
                            "full_input_plus_reserved_output_fits": len(tokens) + cfg["executor"]["max_tokens"] <= cfg["executor"]["context_tokens"]})
            print(json.dumps({"prechecked": len(records), "source": source["key"], "cases": count}), flush=True)
    result = {"kind": "round2_all12_source_schema_and_input_precheck_not_predictions", "records": records,
              "network_blocked": True, "executor_requests": 0, "teacher_requests": 0, "model_weights_loaded": False,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (root / "reports/rr_v2_evidence/strict_contract_round2/backend_schema_precheck.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
