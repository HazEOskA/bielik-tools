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

## Changes made in Phase 2

1. Added `scripts/vllm_compat_probe.py`.
2. Added `.github/workflows/vllm-compat-matrix.yml`.
3. Updated `COMPATIBILITY_MATRIX.md` with source/contract results.

## Evidence levels

### MECHANICALLY VERIFIED

Phase 1 parser harness remains:

```text
20 passed, 1 xfailed
```

The XFAIL is the known streaming-close edge.

### SOURCE/CONTRACT VERIFIED

Official tagged vLLM source was inspected for:

- base `ToolParser` constructor shape,
- actual tool-parser construction call sites,
- `supports_required_and_named` routing,
- import module availability,
- current protocol model location.

## Matrix result

| vLLM | Result | Evidence |
|---|---|---|
| 0.18.0 | GREEN | serving constructs parser with tokenizer only; legacy Bielik parser matches |
| 0.19.0 | RED | serving constructs parser with `tokenizer, request.tools`; Bielik legacy parser accepts tokenizer only |
| 0.20.0 | RED | two-argument parser construction plus required/named routing contract; legacy Bielik parser is behind both contracts |
| 0.23.0 | RED | two-argument parser construction; legacy Bielik parser constructor mismatch persists |
| 0.24.0 | GREEN | modern Bielik parser accepts tools and sets `supports_required_and_named=False` |
| 0.31.0 | RED | current Bielik parser imports removed module `vllm.entrypoints.openai.engine.protocol` |

## Finding P2-F1 — issue #12 begins at vLLM 0.19

vLLM 0.18 chat serving:

```python
self.tool_parser(tokenizer)
```

vLLM 0.19 chat serving:

```python
self.tool_parser(tokenizer, request.tools)
```

Bielik legacy parser:

```python
def __init__(self, tokenizer: TokenizerLike):
```

Result: a direct constructor contract conflict starts at `0.19.0`.

**Status:** CONFIRMED BY TAGGED SOURCE.

## Finding P2-F2 — constructor-only repair is incomplete for 0.20–0.23

The newer vLLM parser stack uses `supports_required_and_named` to decide whether required/named choices go through standard JSON parsing or fall back to a model-specific tool parser.

The modern Bielik parser explicitly sets:

```python
supports_required_and_named = False
```

The legacy parser selected by README for 0.20–0.23 does not.

Result: 0.20–0.23 need both constructor compatibility and routing-contract verification.

**Status:** CONFIRMED BY TAGGED SOURCE.

## Finding P2-F3 — vLLM 0.31 breaks the current import path

Bielik current parser imports:

```python
vllm.entrypoints.openai.engine.protocol
```

Official vLLM 0.31.0 no longer contains that module.

The required classes now exist in:

```python
vllm.entrypoints.generate.base.protocol
```

and vLLM 0.31's built-in Hermes parser imports the protocol models from that new path.

Result: the Bielik README range `>=0.24.0` is not valid without another compatibility split or adaptive import strategy.

**Status:** CONFIRMED BY TAGGED SOURCE.

## GitHub Actions matrix

A workflow was committed to execute a published-wheel probe across all six versions.

### Expected workflow

Each job:

1. checks out this branch,
2. downloads the exact vLLM wheel from PyPI with `--no-deps`,
3. inspects the API shipped in the wheel,
4. compares it with the selected Bielik parser,
5. uploads JSON evidence.

### Actual workflow status

`BLOCKED`.

No Actions run was created after the workflow commit.

The connected GitHub tooling can read workflow runs but cannot read/change the repository Actions enablement setting or dispatch a workflow manually. Therefore the wheel-level run is not claimed as executed.

## What is proven now

- The 0.19 constructor break is not hypothetical.
- 0.20–0.23 have an additional routing-contract concern.
- 0.24 is aligned at source-contract level.
- 0.31 has a new hard import-path break.
- The existing README compatibility table is stale/incomplete.
- No upstream code was changed.

## What remains UNKNOWN

- real package import results from the GitHub Actions wheel matrix,
- live vLLM server behavior,
- Bielik model inference behavior,
- tokenizer chunk behavior for the streaming XFAIL,
- GPU/runtime behavior.

## Recommended Phase 3 patch boundary

Do not build a broad refactor.

Minimal patch candidates:

1. split legacy parser compatibility at `0.19` or make its constructor safely accept `tools`,
2. align required/named routing for 0.20–0.23,
3. introduce version-safe protocol imports for 0.31+,
4. verify all six matrix points,
5. only then prepare an upstream PR.

## Verdict

**PHASE 2 = SOURCE/CONTRACT VERIFIED, CI BLOCKED.**

The compatibility problem is now bounded to concrete vLLM API transitions rather than a vague parser bug.
