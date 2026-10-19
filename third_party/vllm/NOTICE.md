# vLLM 0.10.2 structured-output EOS alignment

Upstream: https://github.com/vllm-project/vllm/tree/v0.10.2

Original module: `vllm/v1/structured_output/backend_xgrammar.py`, SPDX Apache-2.0,
Copyright contributors to the vLLM project. The Apache-2.0 license text is already
distributed at `third_party/ace/LICENSE.txt`; it also applies to this adaptation.
The original runtime module's SPDX header is retained unchanged.

Local change, 2026-10-20: construct the Hugging Face XGrammar tokenizer metadata
with the union of the tokenizer EOS and the model generation-config EOS IDs.
The vLLM sampler reads that generation config even with neutral `vllm` sampling
defaults. This aligns syntactic generation termination; it does not select legal
citations, change amounts, repair an answer, or provide a failed-answer retry.

The exact reproducible diff is
`patches/vllm-0.10.2-hf-generation-eos-alignment.patch`. It is a local dependency
repair, not an upstream-merged change or a claimed skill-learning innovation.
The original module SHA-256 is
`2dc0349c7306655d161c04c7036addda1e2b59da8ac747ba27d9f31c9546546c`.
The repaired module SHA-256 is
`673dc25710d9f59c42baa2c0e4e665b48aa8c1a3b8f9670a89af649875fe49da`.
Both original source archives and the real failed trajectory are retained on
two disks. The new inference profile binds the installed dependency bytes and
the model service process; old-run scores are never retrospectively replaced.
