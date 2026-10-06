# Bielik tool parser — compatibility evidence matrix

Upstream: `speakleash/bielik-tools`  
Audited upstream HEAD: `77c4f4252bdea8da24ba68ff303cb9d8fac987b4` (2026-09-20)  
Audit date: 2026-10-06

## Source-verified vLLM ToolParser constructor boundary

| vLLM tag | ToolParser constructor observed | Bielik README selection | Verdict |
|---|---|---|---|
| 0.15.0 | `__init__(tokenizer)` | `bielik_vllm_tool_parser_v0.15.0.py` | API-shape consistent |
| 0.16.0 | `__init__(tokenizer)` | `bielik_vllm_tool_parser_v0.15.0.py` | API-shape consistent |
| 0.17.0 | `__init__(tokenizer)` | `bielik_vllm_tool_parser_v0.15.0.py` | API-shape consistent |
| 0.18.0 | `__init__(tokenizer)` | `bielik_vllm_tool_parser_v0.15.0.py` | API-shape consistent |
| 0.19.0 | `__init__(tokenizer, tools=None)` | `bielik_vllm_tool_parser_v0.15.0.py` | **API mismatch risk** |
| 0.20.0 | `__init__(tokenizer, tools=None)` + `supports_required_and_named` | `bielik_vllm_tool_parser_v0.15.0.py` | **design mismatch risk** |
| 0.23.0 | `__init__(tokenizer, tools=None)` + required/named routing flag | `bielik_vllm_tool_parser_v0.15.0.py` | **API mismatch risk** |
| 0.24.0 | `__init__(tokenizer, tools=None)` + required/named routing flag | `bielik_vllm_tool_parser.py` | API-shape consistent |

## Conclusion

The repository README currently groups vLLM `0.15.0–0.23.x` under a parser whose constructor is `__init__(tokenizer)`.

Source verification of vLLM tags shows that the base constructor changes by `v0.19.0` to accept `tools` as a second argument. Therefore the current documented compatibility range needs explicit runtime/CI verification and likely a split or adaptive constructor strategy.

This does **not** claim full runtime incompatibility for every vLLM release in 0.19–0.23. It proves the API boundary and identifies the range requiring versioned tests.

## Proposed validation matrix

- vLLM 0.15.0
- vLLM 0.18.0
- vLLM 0.19.0
- vLLM 0.20.0
- vLLM 0.23.0
- vLLM 0.24.0
- latest supported vLLM

For each version:

1. parser import
2. parser construction
3. `tool_choice=auto`
4. `tool_choice=required`
5. named tool choice
6. non-streaming single/multiple calls
7. streaming string/numeric/bool/object arguments
8. Polish Unicode arguments
9. malformed and partial JSON
