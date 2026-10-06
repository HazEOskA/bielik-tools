# PHASE 3 REPORT — Bielik vLLM compatibility fixes

## Goal

Apply the smallest compatibility patch that closes the Phase 2 contract failures without touching upstream.

## Scope executed

- legacy constructor compatibility for vLLM 0.19–0.23
- required/named routing alignment for the legacy parser
- version-safe protocol import for vLLM 0.31+
- source-contract tests
- parser unit regression gate
- published-wheel compatibility assertions
- no streaming-XFAIL fix
- no upstream PR

## Code changes

### Legacy parser

File:

`tools/bielik_vllm_tool_parser_v0.15.0.py`

Changes:

- accepts `tools=None`
- calls the tools-aware base constructor when supported
- falls back to the one-argument constructor for older vLLM
- sets `supports_required_and_named=False`
- avoids importing the `Tool` alias so vLLM 0.18 remains import-compatible

### Modern parser

File:

`tools/bielik_vllm_tool_parser.py`

Changes:

- prefers `vllm.entrypoints.generate.base.protocol`
- falls back to `vllm.entrypoints.openai.engine.protocol`

This covers the protocol-module relocation observed by vLLM 0.31.

### Test and CI infrastructure

- `tests/test_source_contract.py` updated for Phase 3 contracts
- `scripts/vllm_compat_probe.py` understands alternative protocol module locations
- `.github/workflows/vllm-compat-matrix.yml` now:
  - runs the parser unit suite
  - uploads evidence even when compatibility fails
  - fails a matrix job when `verdict != COMPATIBLE_API_SHAPE`

## Final verification

GitHub Actions run:

`37511150105`

Tested head:

`15494cb4e288dd2ac79c0d365805a6367d5e0e51`

Workflow conclusion:

`success`

Unit suite:

`22 passed, 1 xfailed`

Published-wheel assertions:

- vLLM 0.18.0 — PASS
- vLLM 0.19.0 — PASS
- vLLM 0.20.0 — PASS
- vLLM 0.23.0 — PASS
- vLLM 0.24.0 — PASS
- vLLM 0.31.0 — PASS

Each matrix job reported:

```text
verdict=COMPATIBLE_API_SHAPE
risks=[]
```

## Remaining XFAIL

The single XFAIL is the known streaming-close edge discovered in Phase 1.

It remains intentionally unresolved because Phase 3 scope was compatibility boundaries, not streaming behavior.

## Proof boundary

Verified:

- unit regression behavior
- exact published-wheel API/import shape
- CI-enforced compatibility assertions

Not yet verified:

- real `vllm serve`
- Bielik model load
- GPU inference
- live tokenizer streaming
- end-to-end tool execution

## Verdict

**PHASE 3 PASS — COMPATIBILITY PATCH VERIFIED.**

The previously failing matrix points 0.19, 0.20, 0.23 and 0.31 are green at the enforced published-wheel contract level while 0.18 and 0.24 remain green.
