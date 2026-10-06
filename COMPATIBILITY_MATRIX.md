# Bielik tool parser — compatibility matrix after Phase 3

Upstream: `speakleash/bielik-tools`  
Audited upstream base: `77c4f4252bdea8da24ba68ff303cb9d8fac987b4`  
Branch: `feat/osa-tool-parser-proof-suite`  
Verification date: 2026-10-06

## Final published-wheel matrix

| vLLM | Parser | Phase 2 | Phase 3 |
|---|---|---|---|
| 0.18.0 | `bielik_vllm_tool_parser_v0.15.0.py` | GREEN | **GREEN** |
| 0.19.0 | `bielik_vllm_tool_parser_v0.15.0.py` | RED — constructor mismatch | **GREEN** |
| 0.20.0 | `bielik_vllm_tool_parser_v0.15.0.py` | RED — constructor + routing | **GREEN** |
| 0.23.0 | `bielik_vllm_tool_parser_v0.15.0.py` | RED — constructor + routing | **GREEN** |
| 0.24.0 | `bielik_vllm_tool_parser.py` | GREEN | **GREEN** |
| 0.31.0 | `bielik_vllm_tool_parser.py` | RED — protocol import removed | **GREEN** |

Final CI assertion for every wheel:

```text
verdict=COMPATIBLE_API_SHAPE
risks=[]
```

## Compatibility changes

### Legacy parser: 0.15–0.23

The parser now accepts the newer vLLM call shape:

```python
def __init__(self, tokenizer: TokenizerLike, tools=None):
```

and adapts across the constructor boundary:

```python
try:
    super().__init__(tokenizer, tools)
except TypeError:
    super().__init__(tokenizer)
```

It also declares:

```python
supports_required_and_named: bool = False
```

This preserves the 0.18 one-argument base constructor while aligning 0.19–0.23 with tools-aware construction and the required/named routing contract.

The legacy parser intentionally does **not** import the vLLM `Tool` alias because that alias is not exported by vLLM 0.18.

## Modern parser: protocol relocation

The modern parser uses a version-safe protocol import:

```python
try:
    from vllm.entrypoints.generate.base.protocol import ...
except ImportError:
    from vllm.entrypoints.openai.engine.protocol import ...
```

This preserves the 0.24-era module location and supports the 0.31 location.

## Final CI proof

GitHub Actions run:

```text
37511150105
```

Head SHA tested:

```text
15494cb4e288dd2ac79c0d365805a6367d5e0e51
```

Results:

- parser unit regression suite: **22 passed, 1 xfailed**
- vLLM 0.18.0: **COMPATIBLE_API_SHAPE**
- vLLM 0.19.0: **COMPATIBLE_API_SHAPE**
- vLLM 0.20.0: **COMPATIBLE_API_SHAPE**
- vLLM 0.23.0: **COMPATIBLE_API_SHAPE**
- vLLM 0.24.0: **COMPATIBLE_API_SHAPE**
- vLLM 0.31.0: **COMPATIBLE_API_SHAPE**

The remaining XFAIL is the pre-existing Phase 1 streaming-close edge and was intentionally outside the Phase 3 fix scope.

## Artifact integrity

| vLLM | Artifact ID | SHA-256 |
|---|---:|---|
| 0.18.0 | `11435847019` | `dc016e07304727d51ebf346a4ff9f10e68b82d79c4b0d268de383eca86473caf` |
| 0.19.0 | `11435652291` | `592768ff2a99f670d1b19b1302ebad164b5d52f66b4945d8fb97ea59dbded3e5` |
| 0.20.0 | `11434367287` | `f431b9005e61af9ee47756f7178d40e73d809e905e9e15206e7da8e186b2cc7f` |
| 0.23.0 | `11434567420` | `332e0421462e37f727cf259df8d68c43fd09b60c6125b4eb7fc4c63a11c5cb74` |
| 0.24.0 | `11435547044` | `995784fd2d4eea6e98543320b7cc65b64bc5d6127941e25a51b7059a5c4090cf` |
| 0.31.0 | `11435847024` | `b4ec5fc67839c4acdf310e34847c3d7766ada7abce91f51460bf33365295a40f` |

## Proof boundary

Phase 3 proves compatibility at:

- parser unit-test level,
- published vLLM wheel API/import-contract level,
- CI assertion level.

Still not proven:

- `vllm serve` with a real Bielik model,
- GPU inference,
- tokenizer-driven streaming behavior for the XFAIL,
- end-to-end tool execution.

Those remain separate execution stages.
