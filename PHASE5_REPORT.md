# PHASE 5 REPORT — CUDA vLLM runtime gate

## Goal

Run the last missing proof stage:

```text
CUDA GPU
→ vLLM 0.31
→ real Bielik model
→ bielik_vllm_tool_parser.py
→ bielik_advanced_chat_template.jinja
→ required + auto + streaming
→ Unicode + numeric args
→ tool-result roundtrip
→ streaming-edge verdict
```

## Current verdict

```text
PHASE5_HARNESS_READY
CUDA_RUNTIME_EXECUTION_BLOCKED_BY_GPU_CAPACITY
```

This is **not** reported as `VLLM_CUDA_LIVE_VERIFIED`.

## Why execution stopped

The approved Phase 5 scope explicitly avoided creating paid GPU infrastructure blindly.

### DigitalOcean evidence

Connected DigitalOcean account state:

- no active Droplets returned by the connector
- account balance / month-to-date usage previously read as `0.00`
- account status: `warning`
- status message says the team has reached its allowed Droplet count

GPU-capable regions do advertise GPU size slugs, including:

```text
tor1 → gpu-4000adax1-20gb
```

The smallest relevant NVIDIA option is an RTX 4000 Ada with 20 GB VRAM.

Current public DigitalOcean price checked on 2026-10-06:

```text
$0.76 / GPU / hour
```

DigitalOcean bills GPU Droplets per second with a minimum charge.

Because there is no existing GPU or credit balance available through the connected account, Phase 5 did not create a paid GPU Droplet.

## GitHub-hosted GPU boundary

Standard public GitHub-hosted runners are CPU-only.

GitHub-hosted GPU larger runners use an NVIDIA Tesla T4 with 16 GB VRAM, but larger runners are an organization / enterprise feature for GitHub Team or GitHub Enterprise Cloud.

The current repository is the personal fork:

```text
HazEOskA/bielik-tools
```

Therefore no free GitHub-hosted CUDA runner is available for this Phase 5 execution.

---

# Phase 5 implementation

## 1. Live CUDA torture harness

Added:

```text
scripts/live_vllm_gpu_torture.py
```

The harness executes these real OpenAI-compatible API tests against vLLM:

1. server readiness / model listing
2. `tool_choice=required` with Unicode argument `Łódź`
3. `tool_choice=auto` with Unicode argument `Łódź`
4. required numeric argument:
   - `location = Kraków`
   - `num_days = 3`
5. required streaming tool call with Unicode argument
6. streaming numeric edge reproducer
7. tool-result → final assistant roundtrip

### Verdict contract

If all mandatory tests pass and the historical streaming edge also passes:

```text
VLLM_CUDA_LIVE_VERIFIED
```

If all mandatory tests pass but the known numeric streaming edge reproduces:

```text
VLLM_CUDA_LIVE_VERIFIED_WITH_KNOWN_STREAMING_XFAIL
```

If a mandatory test fails:

```text
VLLM_CUDA_LIVE_FAILED
```

The known streaming edge is therefore never silently converted into a green result.

## 2. One-command CUDA runner

Added:

```text
scripts/run_phase5_cuda.sh
```

It performs:

```text
docker + nvidia-smi precheck
→ GPU evidence capture
→ pull exact vLLM 0.31 CUDA image
→ start real Bielik-1.5B-v3.0-Instruct
→ mount current Bielik parser
→ mount current advanced chat template
→ wait for /health
→ execute torture harness
→ preserve logs + docker inspect
→ stop/remove container
```

Pinned runtime image:

```text
vllm/vllm-openai:v0.31.0
```

Pinned model:

```text
speakleash/Bielik-1.5B-v3.0-Instruct
```

Parser under proof:

```text
tools/bielik_vllm_tool_parser.py
```

Template under proof:

```text
tools/bielik_advanced_chat_template.jinja
```

## 3. Manual GPU workflow

Added:

```text
.github/workflows/bielik-phase5-cuda.yml
```

It deliberately targets:

```yaml
runs-on: [self-hosted, linux, x64, gpu]
```

and is `workflow_dispatch` only.

It will not burn compute automatically after future pushes.

## 4. Static proof workflow

Added:

```text
.github/workflows/bielik-phase5-harness-static.yml
```

GitHub Actions run:

```text
37519019732
```

Tested head:

```text
f36912443bfb240e54722d28f50a1ad046f42a5e
```

Conclusion:

```text
SUCCESS
```

Passed checks:

- Python syntax
- Bash syntax
- exact `vllm/vllm-openai:v0.31.0` CUDA image manifest exists
- Phase 5 verdict markers exist
- parser-plugin mount marker exists
- advanced-template mount marker exists
- real Bielik model ID marker exists

This proves that the execution package is mechanically ready, but it does not replace CUDA runtime execution.

---

# Evidence state

## Proven before Phase 5

- published-wheel vLLM compatibility matrix: green
- parser unit suite: green except one intentional streaming XFAIL
- real Bielik model live on CPU: green
- advanced chat template with real Bielik: green
- required tool call: green
- Unicode tool argument: green
- numeric tool argument: green
- tool-result roundtrip: green

## Proven in Phase 5

- final CUDA test contract exists
- exact vLLM 0.31 CUDA image exists
- one-command execution runner is syntactically valid
- GPU-targeted workflow is wired
- evidence capture path is wired
- historical streaming edge has an explicit live verdict path
- no paid GPU resource was created

## Still not proven

```text
real CUDA execution
+
vLLM 0.31 inference
+
real Bielik
+
bielik_vllm_tool_parser.py
```

Therefore:

```text
CLAIM: full Bielik vLLM CUDA runtime verified
PROOF: absent
STATUS: BLOCKED_BY_GPU_CAPACITY
```

## Exact RUN NOW gate

Any Linux x64 machine with a working NVIDIA Container Toolkit and enough VRAM can now run:

```bash
bash scripts/run_phase5_cuda.sh
```

The target model is only 1.5B parameters, so the harness is intentionally designed for a small single-GPU test rather than an H100-class machine.

## Phase 5 conclusion

**Phase 5 implementation is complete and mechanically verified. Runtime proof is blocked only by the absence of an approved CUDA GPU execution environment.**

No upstream PR was opened.
No SpeakLeash upstream branch was modified.
No paid GPU was provisioned.
