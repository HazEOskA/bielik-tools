# PROOF REPORT — Bielik Phase 2

## Goal

Run a versioned vLLM compatibility torture pass against the Bielik tool parser stack before modifying parser code or opening an upstream PR.

## Locked scope

- target: `HazEOskA/bielik-tools`
- branch: `feat/osa-tool-parser-proof-suite`
- matrix: vLLM `0.18.0 / 0.19.0 / 0.20.0 / 0.23.0 / 0.24.0 / 0.31.0`
- add test/probe infrastructure
- collect compatibility evidence
- no parser fix
- no upstream PR
- no contact with SpeakLeash

## Phase 2 execution

Added:

- `scripts/vllm_compat_probe.py`
- `.github/workflows/vllm-compat-matrix.yml`

The probe downloads the exact published vLLM wheel from PyPI using `pip download --no-deps --only-binary=:all:`, inspects the Python API shipped inside that wheel, compares it to the Bielik parser selected for the same version, and uploads JSON evidence.

GitHub Actions run:

- run id: `37509330061`
- head SHA: `8474794af0ac3e0933f32ce8a8bf2c47ebc10b76`
- workflow conclusion: `success`
- six matrix jobs completed
- six JSON evidence artifacts uploaded

Important: workflow `success` means the evidence collection completed. Compatibility is determined by each JSON artifact's `verdict`, not by the job conclusion.

## Published-wheel matrix result

| vLLM | Wheel probe verdict | Risks |
|---|---|---|
| 0.18.0 | `COMPATIBLE_API_SHAPE` | none |
| 0.19.0 | `RISK_DETECTED` | `CONSTRUCTOR_TOOLS_MISMATCH` |
| 0.20.0 | `RISK_DETECTED` | `CONSTRUCTOR_TOOLS_MISMATCH`, `REQUIRED_NAMED_ROUTING_FLAG_MISSING` |
| 0.23.0 | `RISK_DETECTED` | `CONSTRUCTOR_TOOLS_MISMATCH`, `REQUIRED_NAMED_ROUTING_FLAG_MISSING` |
| 0.24.0 | `COMPATIBLE_API_SHAPE` | none |
| 0.31.0 | `RISK_DETECTED` | `PARSER_IMPORT_PATH_MISSING` |

## Artifact proof

| vLLM | Artifact ID | SHA-256 digest |
|---|---:|---|
| 0.18.0 | `11432853522` | `14103bef747336daa28f11165de4bb9d79448770aecf9d9c5c4f0e9cd94f8c0f` |
| 0.19.0 | `11431959705` | `feac59b75f17c106c4b08bd5da3b25e5813c2d31afdc9eb45a8b2154be92878e` |
| 0.20.0 | `11434705106` | `b66e2651521a2bd302d95aba57c0db94bd3306810b608a7077a753abf9964a06` |
| 0.23.0 | `11433595281` | `d2a8fd66822cd42c55482bda4d28598bc8012c70918786441f0a795751f1bdcb` |
| 0.24.0 | `11435130025` | `0fe4ad2e64fca24d9d5fe982f592b4aa62b8643f8fbbe8900e1e6d8cd50b1a6d` |
| 0.31.0 | `11434945080` | `441ae66d774530e2c886a8dcfea0216da50be8ab4376d5af202e1324e0fc37f2` |

## Finding P2-F1 — vLLM 0.19 is the constructor break

Published-wheel inspection:

vLLM 0.18 ToolParser:

```text
params = [self, tokenizer]
```

Bielik parser selected for 0.18:

```text
params = [self, tokenizer]
```

Result: compatible API shape.

vLLM 0.19 ToolParser:

```text
params = [self, tokenizer, tools]
```

Bielik parser selected for 0.19:

```text
params = [self, tokenizer]
```

Result:

```text
CONSTRUCTOR_TOOLS_MISMATCH
```

Tagged-source inspection independently confirms vLLM 0.19 OpenAI serving constructs the parser as:

```python
self.tool_parser(tokenizer, request.tools)
```

**Evidence level: PUBLISHED_WHEEL_VERIFIED + SOURCE/CONTRACT_VERIFIED.**

## Finding P2-F2 — 0.20–0.23 need more than a constructor patch

Wheel evidence for both 0.20 and 0.23:

```text
base_accepts_tools = true
bielik_accepts_tools = false
base_has_supports_required_and_named = true
bielik_has_supports_required_and_named = false
```

Risks:

```text
CONSTRUCTOR_TOOLS_MISMATCH
REQUIRED_NAMED_ROUTING_FLAG_MISSING
```

Tagged vLLM parser source also shows the fallback path for model-specific parsers when `supports_required_and_named=False`.

**Evidence level: PUBLISHED_WHEEL_VERIFIED + SOURCE/CONTRACT_VERIFIED.**

## Finding P2-F3 — 0.24 is aligned at API shape

Wheel evidence:

```text
base_accepts_tools = true
bielik_accepts_tools = true
base_has_supports_required_and_named = true
bielik_has_supports_required_and_named = true
missing_vllm_import_modules = []
risks = []
verdict = COMPATIBLE_API_SHAPE
```

This does not yet prove model inference, but the parser API/import contract matches the published 0.24 wheel.

**Evidence level: PUBLISHED_WHEEL_VERIFIED.**

## Finding P2-F4 — current parser breaks again on vLLM 0.31.0

Wheel evidence:

```text
missing_vllm_import_modules = [
  "vllm.entrypoints.openai.engine.protocol"
]
risks = [
  "PARSER_IMPORT_PATH_MISSING"
]
verdict = RISK_DETECTED
```

Official vLLM 0.31.0 source contains the required protocol classes under:

```python
vllm.entrypoints.generate.base.protocol
```

and the built-in vLLM 0.31 Hermes parser imports:

- `DeltaFunctionCall`
- `DeltaMessage`
- `DeltaToolCall`
- `ExtractedToolCallInformation`
- `FunctionCall`
- `ToolCall`

from that new location.

**Evidence level: PUBLISHED_WHEEL_VERIFIED + SOURCE/CONTRACT_VERIFIED.**

## Phase 1 parser harness

Still valid:

```text
20 passed, 1 xfailed
```

The XFAIL is the isolated streaming-close edge. It remains intentionally unresolved in Phase 2 because parser fixes were out of scope.

## What Phase 2 proves

- The documented `0.15–0.23` parser range breaks at the API boundary beginning in 0.19.
- 0.20–0.23 additionally require required/named routing alignment.
- 0.24 matches the modern parser API shape.
- The open-ended README range `>=0.24` is stale because 0.31 removes an import path used by the current parser.
- These findings are reproduced against actual published vLLM wheels, not only inferred from GitHub source.
- Upstream SpeakLeash remains untouched.

## What remains UNKNOWN

- full `import bielik_vllm_tool_parser` with every vLLM dependency installed,
- live `vllm serve`,
- Bielik model inference,
- tokenizer chunk behavior for the streaming XFAIL,
- GPU runtime behavior.

## Recommended Phase 3 patch boundary

Minimal, test-driven patch only:

1. make 0.19–0.23 parser construction compatible with `tools`,
2. align `supports_required_and_named=False` where the vLLM routing contract requires it,
3. make protocol imports compatible with the 0.31 path transition,
4. extend the wheel probe to enforce expected verdicts,
5. run matrix again,
6. then run a real `vllm serve` smoke test before any upstream PR.

## Verdict

**PHASE 2 = PUBLISHED_WHEEL_VERIFIED.**

The Bielik tool-parser compatibility surface is now bounded by three concrete transitions: vLLM 0.19 constructor change, vLLM 0.20 required/named routing contract, and vLLM 0.31 protocol-module relocation.
