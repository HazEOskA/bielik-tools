# Bielik tool parser — compatibility evidence matrix

Upstream: `speakleash/bielik-tools`  
Audited upstream HEAD: `77c4f4252bdea8da24ba68ff303cb9d8fac987b4` (2026-09-20)  
Audit date: 2026-10-06  
Branch: `feat/osa-tool-parser-proof-suite`

## Published-wheel compatibility matrix

| vLLM | Bielik parser | Wheel/API verdict | Risks |
|---|---|---|---|
| 0.18.0 | `bielik_vllm_tool_parser_v0.15.0.py` | **GREEN** | none |
| 0.19.0 | `bielik_vllm_tool_parser_v0.15.0.py` | **RED** | `CONSTRUCTOR_TOOLS_MISMATCH` |
| 0.20.0 | `bielik_vllm_tool_parser_v0.15.0.py` | **RED** | constructor mismatch + missing required/named routing override |
| 0.23.0 | `bielik_vllm_tool_parser_v0.15.0.py` | **RED** | constructor mismatch + missing required/named routing override |
| 0.24.0 | `bielik_vllm_tool_parser.py` | **GREEN** | none at API/import shape level |
| 0.31.0 | `bielik_vllm_tool_parser.py` | **RED** | removed import path `vllm.entrypoints.openai.engine.protocol` |

## Evidence source

GitHub Actions run:

```text
37509330061
```

All six jobs completed and uploaded JSON evidence generated from the exact published vLLM wheels.

The probe:

1. downloads `vllm==<version>` as a wheel from PyPI,
2. reads the shipped `ToolParser` implementation,
3. compares constructor and routing contracts against the selected Bielik parser,
4. validates Bielik's referenced vLLM module paths,
5. emits deterministic JSON evidence.

## Boundary 1 — vLLM 0.19 constructor transition

### vLLM 0.18

Wheel:

```text
ToolParser params = [self, tokenizer]
```

Bielik legacy parser:

```text
BielikToolParser params = [self, tokenizer]
```

Verdict:

```text
COMPATIBLE_API_SHAPE
```

### vLLM 0.19

Wheel:

```text
ToolParser params = [self, tokenizer, tools]
```

Bielik legacy parser:

```text
BielikToolParser params = [self, tokenizer]
```

Verdict:

```text
RISK_DETECTED
CONSTRUCTOR_TOOLS_MISMATCH
```

Tagged source independently confirms that vLLM 0.19 OpenAI serving invokes:

```python
self.tool_parser(tokenizer, request.tools)
```

This makes the mismatch concrete, not speculative.

## Boundary 2 — required/named routing in 0.20–0.23

Published wheel results for 0.20 and 0.23:

```text
base_accepts_tools = true
bielik_accepts_tools = false
base_has_supports_required_and_named = true
bielik_has_supports_required_and_named = false
```

Detected risks:

```text
CONSTRUCTOR_TOOLS_MISMATCH
REQUIRED_NAMED_ROUTING_FLAG_MISSING
```

The modern Bielik parser correctly uses:

```python
supports_required_and_named = False
```

The legacy parser selected by the README for 0.20–0.23 does not.

## Boundary 3 — 0.24 modern parser contract

Published wheel result:

```text
base_accepts_tools = true
bielik_accepts_tools = true
base_has_supports_required_and_named = true
bielik_has_supports_required_and_named = true
missing_vllm_import_modules = []
risks = []
verdict = COMPATIBLE_API_SHAPE
```

Therefore 0.24 is green at the API/import contract level.

## Boundary 4 — vLLM 0.31 protocol relocation

The current Bielik parser imports:

```python
vllm.entrypoints.openai.engine.protocol
```

The published 0.31 wheel does not contain that module.

Wheel result:

```text
missing_vllm_import_modules = [
  "vllm.entrypoints.openai.engine.protocol"
]
risks = [
  "PARSER_IMPORT_PATH_MISSING"
]
verdict = RISK_DETECTED
```

Official vLLM 0.31 source places the required protocol classes in:

```python
vllm.entrypoints.generate.base.protocol
```

and its own Hermes parser imports from that location.

## Artifact integrity

| vLLM | Artifact ID | SHA-256 |
|---|---:|---|
| 0.18.0 | `11432853522` | `14103bef747336daa28f11165de4bb9d79448770aecf9d9c5c4f0e9cd94f8c0f` |
| 0.19.0 | `11431959705` | `feac59b75f17c106c4b08bd5da3b25e5813c2d31afdc9eb45a8b2154be92878e` |
| 0.20.0 | `11434705106` | `b66e2651521a2bd302d95aba57c0db94bd3306810b608a7077a753abf9964a06` |
| 0.23.0 | `11433595281` | `d2a8fd66822cd42c55482bda4d28598bc8012c70918786441f0a795751f1bdcb` |
| 0.24.0 | `11435130025` | `0fe4ad2e64fca24d9d5fe982f592b4aa62b8643f8fbbe8900e1e6d8cd50b1a6d` |
| 0.31.0 | `11434945080` | `441ae66d774530e2c886a8dcfea0216da50be8ab4376d5af202e1324e0fc37f2` |

## Current compatibility verdict

The current README ranges are not technically accurate across the tested matrix.

A minimal compatibility design needs at least these boundaries:

```text
<= 0.18      legacy one-argument parser API
0.19–0.23   tools-aware constructor + required/named routing alignment
0.24–before protocol relocation   modern parser contract
0.31+       new protocol import location
```

The exact last version before the protocol relocation has not been bisected in Phase 2 and remains `UNKNOWN`.

No parser code has been changed yet.
