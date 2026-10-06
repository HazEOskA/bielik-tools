# PHASE 4 REPORT — Bielik live runtime proof

## Goal

Move beyond source/API compatibility and execute a real Bielik model through a live serving runtime, exercising tool calling with the repository's advanced tool-aware chat template.

## Scope

Approved Phase 4 scope:

- stay on `HazEOskA/bielik-tools`
- branch `feat/osa-tool-parser-proof-suite`
- run live model/runtime checks
- avoid paid GPU provisioning without proof it is necessary
- exercise real tool-call behavior, Unicode arguments, numeric arguments, and tool-result roundtrip
- no upstream PR

## Final verdict

| Layer | Verdict |
|---|---|
| Phase 3 parser/unit compatibility | **VERIFIED** |
| Published vLLM wheel compatibility | **VERIFIED** |
| Real Bielik model load on CPU | **VERIFIED** |
| Real Bielik tool API behavior with `bielik_advanced_chat_template.jinja` | **VERIFIED** |
| Required Unicode argument (`Łódź`) | **VERIFIED** |
| Required numeric argument (`num_days: 3`) | **VERIFIED** |
| Tool-result → assistant roundtrip | **VERIFIED** |
| vLLM 0.31 + GGUF + CPU inference | **BLOCKED BY CUDA-ONLY GGUF DEQUANT BACKEND** |
| vLLM live tool parser with real Bielik model | **NOT YET VERIFIED** |

Overall:

```text
MODEL_LIVE_TOOL_API_VERIFIED
VLLM_LIVE_BLOCKED_BY_CUDA_BACKEND
```

This is intentionally not reported as full `LIVE_RUNTIME_VERIFIED` for vLLM.

---

## Live model used

```text
speakleash/Bielik-1.5B-v3.0-Instruct-GGUF:Q8_0
```

Runtime used for successful CPU live proof:

```text
llama.cpp CPU
+
tools/bielik_advanced_chat_template.jinja
+
OpenAI-compatible /v1/chat/completions tools API
```

## Successful live run

GitHub Actions:

```text
run: 37515907598
tested head: f00714100663bc9a81b2075d089a5bd754d91b10
conclusion: success
```

Evidence artifact:

```text
artifact id: 11436024632
sha256: 5c1bc9f3df60550e9f055978324ab24cca43182ed6e8d6df35b81f9403c244dd
```

### Test 1 — required Unicode tool call

Request required the weather tool for Łódź.

Observed OpenAI-style tool call:

```json
{
  "type": "function",
  "function": {
    "name": "get_current_weather",
    "arguments": "{\"location\": \"Łódź\"}"
  }
}
```

Result:

```text
PASS
```

### Test 2 — required numeric tool call

Request required a three-day forecast for Kraków.

Observed OpenAI-style tool call:

```json
{
  "type": "function",
  "function": {
    "name": "get_n_day_weather_forecast",
    "arguments": "{\"location\": \"Kraków\", \"num_days\": 3}"
  }
}
```

Result:

```text
PASS
```

### Test 3 — tool-result roundtrip

Injected real-shaped tool result:

```json
{
  "location": "Łódź",
  "temperature": "11°C",
  "weather": "deszcz"
}
```

Observed final assistant content:

```text
Aktualna pogoda w Łodzi to 11°C z deszczem.
```

Result:

```text
PASS
```

## Runtime evidence

llama.cpp server log confirms:

```text
model loaded
listening on http://0.0.0.0:8080
```

The three test requests executed real inference on the loaded Bielik Q8_0 model.

Observed CPU generation performance in this CI environment was roughly 19–21 generated tokens/second for the tested requests.

---

# vLLM live investigation

## Attempt 1 — insufficient failure retention

Run:

```text
37512922965
```

The initial workflow used an auto-removing Docker container, causing the crashed container logs to disappear before diagnosis.

This was a harness problem, not a Bielik verdict.

## Attempt 2 — missing GGUF Hugging Face config

Run:

```text
37513339679
```

The vLLM API server started, but the GGUF repository did not provide the Hugging Face `config.json` model metadata expected by vLLM.

Observed error:

```text
Unrecognized model in speakleash/Bielik-1.5B-v3.0-Instruct-GGUF.
Should have a model_type key in its config.json.
```

The workflow was corrected to use config/tokenizer metadata from:

```text
speakleash/Bielik-1.5B-v3.0-Instruct-FP8-Dynamic
```

while retaining the public Q8_0 GGUF weights.

## Attempt 3 — exact compute/backend blocker identified

Run:

```text
37514552289
```

Evidence artifact:

```text
artifact id: 11436812505
sha256: 2d118400185ba3bb9d5e1509e3a9cf9d2a20de49742c96bac86b32e26824e0d9
```

The previous config/tokenizer failure was resolved. vLLM progressed through:

- API server initialization
- Bielik architecture/config resolution
- tokenizer/config path
- engine worker startup
- real GGUF weight execution
- `torch.ops.vllm._apply_gguf_embedding`

The exact root cause was then:

```text
ValueError: Triton dequant kernels require CUDA tensors
```

vLLM propagated it as:

```text
RuntimeError: Worker failed with error
'Triton dequant kernels require CUDA tensors'
```

Container state:

```text
OOMKilled: false
ExitCode: 1
```

Therefore this failure is not:

- runner RAM exhaustion
- CPU instruction-set failure
- Bielik config failure
- Bielik tokenizer failure
- parser-plugin import failure
- repository compatibility regression

It is the GGUF plugin's CUDA-only dequantization path.

## Host proof

The free GitHub runner exposed approximately:

```text
CPU: 4 vCPU
RAM: 15 GiB
free RAM before serving: ~12 GiB
disk free: ~87 GiB
AVX512: available
```

No paid GPU infrastructure was provisioned.

---

## Important intermediate model finding

Before switching llama.cpp to its OpenAI tool-aware generic handler, a raw completion test produced:

```json
{"name": "get_curent_weather", "arguments": {"location": "Łódź"}}
```

This proved real model inference and Unicode argument generation, but it also showed why raw completion is not a valid substitute for tool-serving infrastructure:

- control/special tool tags were not surfaced as literal text,
- the unconstrained model misspelled the function name.

After using llama.cpp's official tool-aware Jinja/OpenAI path with this repository's `bielik_advanced_chat_template.jinja`, the exact tool names and schemas were enforced and all three live tests passed.

---

## Files added for Phase 4

```text
scripts/live_vllm_torture.py
.github/workflows/bielik-live-vllm.yml
scripts/live_llamacpp_tool_tag_smoke.py
.github/workflows/bielik-live-model-cpu.yml
PHASE4_REPORT.md
```

## Proof boundary

### Proven

- Bielik Q8_0 can load and infer on a CPU runner.
- The repository's advanced chat template works with a live Bielik model.
- OpenAI-style required tool calls are produced with exact function names.
- Polish Unicode survives the full live request/output path.
- Integer tool arguments survive the full live request/output path.
- A tool result can be fed back and produce a correct natural-language response.
- Phase 3 API/import fixes remain separately verified by the published-wheel matrix.

### Not proven

- real Bielik model loaded under vLLM with the custom Bielik parser plugin through inference
- vLLM streaming parser behavior against live Bielik token chunks
- the Phase 1 streaming XFAIL against a real vLLM tokenizer stream
- GPU execution

Those require a CUDA-capable vLLM runtime.

## Next evidence gate

The next meaningful run is not another CPU workaround.

It is:

```text
CUDA GPU
→ vLLM 0.31
→ real Bielik model
→ bielik_vllm_tool_parser.py
→ bielik_advanced_chat_template.jinja
→ required + auto + streaming
→ tool result roundtrip
→ evidence artifact
```

Until that run exists:

```text
CLAIM: full vLLM live verified
PROOF: absent
STATUS: UNKNOWN / BLOCKED_BY_CUDA
```

## Phase 4 conclusion

**Phase 4 achieved live Bielik model/tool execution and isolated the remaining vLLM gate to a concrete CUDA-only backend dependency.**

The result is stronger than a generic compute limitation: the exact failing operation, runtime layer, successful model alternative, successful tool calls, and artifact digests are all captured.
