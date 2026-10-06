# Bielik tool parser — compatibility evidence matrix

Upstream: `speakleash/bielik-tools`  
Audited upstream HEAD: `77c4f4252bdea8da24ba68ff303cb9d8fac987b4` (2026-09-20)  
Audit date: 2026-10-06  
Phase 2 branch: `feat/osa-tool-parser-proof-suite`

## Phase 2 source/contract matrix

| vLLM tag | vLLM parser construction path | Bielik parser selected by README | Result |
|---|---|---|---|
| 0.18.0 | serving calls `self.tool_parser(tokenizer)`; base `ToolParser.__init__(tokenizer)` | `bielik_vllm_tool_parser_v0.15.0.py` | **PASS — SOURCE/CONTRACT VERIFIED** |
| 0.19.0 | serving calls `self.tool_parser(tokenizer, request.tools)`; base accepts `tools` | `bielik_vllm_tool_parser_v0.15.0.py` whose constructor accepts only `tokenizer` | **FAIL — CONSTRUCTOR MISMATCH** |
| 0.20.0 | parser layer calls `tool_parser_cls(tokenizer, tools)`; required/named routing contract present | same legacy parser, one-arg constructor, no `supports_required_and_named=False` | **FAIL — CONSTRUCTOR + ROUTING MISMATCH** |
| 0.23.0 | parser layer calls `tool_parser_cls(tokenizer, tools)`; required/named routing fallback present | same legacy parser, one-arg constructor | **FAIL — CONSTRUCTOR MISMATCH** |
| 0.24.0 | parser layer calls `tool_parser_cls(tokenizer, tools)`; base accepts `tools` | `bielik_vllm_tool_parser.py` accepts `tools`, sets `supports_required_and_named=False` | **PASS — SOURCE/CONTRACT VERIFIED** |
| 0.31.0 | parser layer calls `tool_parser_cls(tokenizer, tools)`; base accepts `tools` | current parser still imports `vllm.entrypoints.openai.engine.protocol` | **FAIL — IMPORT PATH REMOVED** |

## Finding P2-F1 — vLLM 0.19 is the real constructor break

This is now stronger than the Phase 1 API-shape inference.

In vLLM 0.18, OpenAI chat serving constructs tool parsers as:

```python
self.tool_parser(tokenizer)
```

In vLLM 0.19, the same serving path constructs them as:

```python
self.tool_parser(tokenizer, request.tools)
```

The Bielik parser documented for the whole `0.15.0–0.23.x` range declares:

```python
def __init__(self, tokenizer: TokenizerLike):
```

Therefore the documented parser is source-contract incompatible starting at **vLLM 0.19.0**.

Proof level: `SOURCE/CONTRACT VERIFIED`.

## Finding P2-F2 — 0.20–0.23 also require the required/named routing contract

By vLLM 0.20–0.23 the parser stack contains explicit handling for:

```python
supports_required_and_named
```

and the parser wrapper constructs the tool parser with:

```python
tool_parser_cls(tokenizer, tools)
```

The modern Bielik parser sets:

```python
supports_required_and_named = False
```

but the legacy parser selected for 0.20–0.23 does not. Fixing only the constructor would therefore not fully align the legacy parser with the newer vLLM routing model.

Proof level: `SOURCE/CONTRACT VERIFIED`; live inference behavior still requires execution.

## Finding P2-F3 — current Bielik parser is not source-compatible with vLLM 0.31.0

The current Bielik parser imports protocol models from:

```python
from vllm.entrypoints.openai.engine.protocol import (
    DeltaFunctionCall,
    DeltaMessage,
    DeltaToolCall,
    ExtractedToolCallInformation,
    FunctionCall,
    ToolCall,
)
```

In the official vLLM `v0.31.0` tag, that module path no longer exists.

The protocol models are present under:

```python
vllm.entrypoints.generate.base.protocol
```

This is also the import path used by vLLM's own `hermes_tool_parser.py` in `v0.31.0`.

Therefore the README rule:

```text
>= 0.24.0 -> bielik_vllm_tool_parser.py
```

is too broad for the current parser implementation.

Proof level: `SOURCE/CONTRACT VERIFIED`.

## Import-path checks

The imports used by the legacy/current Bielik parsers were checked at the matrix boundaries:

- vLLM 0.18.0: required import modules present.
- vLLM 0.23.0: required import modules present.
- vLLM 0.24.0: required import modules present.
- vLLM 0.31.0: `vllm.entrypoints.openai.engine.protocol` **missing**.

## CI / real wheel probe

Phase 2 added:

- `scripts/vllm_compat_probe.py`
- `.github/workflows/vllm-compat-matrix.yml`

The workflow matrix targets:

- 0.18.0
- 0.19.0
- 0.20.0
- 0.23.0
- 0.24.0
- 0.31.0

The probe downloads the exact published vLLM wheel and inspects the shipped API surface.

### Current CI status

`BLOCKED`: no GitHub Actions workflow run was created after the workflow commit on the fresh fork.

Repository settings needed to determine/enable Actions are not exposed by the connected GitHub tool, so no runtime/wheel result is claimed.

## Current verdict

- `0.18.0`: source contract GREEN
- `0.19.0`: source contract RED
- `0.20.0`: source contract RED
- `0.23.0`: source contract RED
- `0.24.0`: source contract GREEN
- `0.31.0`: source contract RED

No parser fix has been applied in Phase 2.
