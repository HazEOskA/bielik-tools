# PROOF REPORT — Bielik Phase 1

## Goal

Establish a proof-first contribution entry point into `speakleash/bielik-tools` focused on tool parsing, vLLM compatibility and regression tests.

## Scope lock

Approved scope:

- fork under `HazEOskA`
- branch `feat/osa-tool-parser-proof-suite`
- parser audit
- regression/unit test suite
- vLLM compatibility matrix
- proof report
- no upstream PR
- no contact with SpeakLeash

## Execution status

| Item | Status | Evidence |
|---|---|---|
| Read upstream repo | PASS | public upstream inspected |
| Lock upstream HEAD | PASS | `77c4f4252bdea8da24ba68ff303cb9d8fac987b4` |
| Verify fork | PASS | `HazEOskA/bielik-tools`, GitHub reports `fork=true`, parent `speakleash/bielik-tools` |
| Create remote branch | PASS | `feat/osa-tool-parser-proof-suite` |
| Add regression suite | PASS | remote commit `bd4c7f72598d321b25763be03029633933c0f06f` |
| Add source-contract tests | PASS | remote commit `b3444e6b187f7ba35945fe272a9c41c5ceb42c1c` |
| Add compatibility matrix | PASS | remote commit `eb2901e7102f51fdd858b11577958545ade47cb1` |
| Local parser test harness | PASS | `20 passed, 1 xfailed in 0.07s` |
| vLLM constructor compatibility audit | PASS | source verification against vLLM tags |
| Live Bielik model inference | NOT EXECUTED | no GPU/vLLM runtime in execution environment |
| GitHub Actions CI | NOT EXECUTED | upstream repo has no Phase 1 CI workflow added in this scope |
| Upstream PR | NOT EXECUTED | explicitly out of scope |

## Current upstream issues relevant to Phase 1

- #3 `Write unit tests for bielik_vllm_tool_parser.py` — **OPEN**.
- #8 vLLM 0.13 incompatibility — **CLOSED / completed**.
- #9 `tool_choice=required` failure on vLLM 0.13–0.15 — **OPEN**.
- #12 constructor error on vLLM 0.20+ — **OPEN**.

## Test result

```text
20 passed, 1 xfailed in 0.07s
```

Covered behavior:

- plain content / no call
- single tool call
- whitespace after `<tool_call>` (issue #9 reproducer shape)
- newline/whitespace parsing
- multiple calls
- content preceding call
- Polish Unicode / `ensure_ascii=False`
- malformed JSON fail-closed
- unclosed but complete JSON recovery
- missing arguments fail-closed
- `tool_choice=required` → `auto` redirect
- structured-output regex contract
- `tool_choice=auto`
- `tool_choice=none`
- `supports_required_and_named=False`
- constructor accepting `tools` on modern parser
- streaming plain-text passthrough
- streaming tool-name emission
- source-level protocol markers

## Finding F1 — documentation/API range mismatch

**Severity: HIGH for compatibility.**

Current README states:

- `0.15.0–0.23.x` → `bielik_vllm_tool_parser_v0.15.0.py`
- `>=0.24.0` → `bielik_vllm_tool_parser.py`

Source verification of vLLM tags shows:

- 0.15–0.18: base `ToolParser.__init__(tokenizer)`
- **0.19+: base `ToolParser.__init__(tokenizer, tools=None)`**

The Bielik `v0.15.0` parser still declares `__init__(tokenizer)` only. This matches the failure class reported in open issue #12 and moves the API boundary earlier than the current README table implies.

### Proof level

`SOURCE_VERIFIED`; runtime matrix remains pending.

## Finding F2 — required/named routing boundary

vLLM 0.20 contains the `supports_required_and_named` routing contract in the base parser. The modern Bielik parser explicitly sets it to `False`; the `v0.15.0` Bielik parser does not.

Constructor repair alone may therefore be insufficient for vLLM 0.20–0.23. Required/named tool-choice behavior needs versioned tests against real vLLM.

### Proof level

`SOURCE_VERIFIED`; runtime behavior remains `UNKNOWN`.

## Finding F3 — streaming close edge

A regression test is intentionally marked XFAIL for a streaming close path where the final delta does not contain the literal substring `"}`.

Current close logic contains:

```python
if '"}' not in delta_text:
    return None
```

The isolated unit harness demonstrates that a synthetic numeric-final argument closing chunk can be dropped by this path.

### Proof level

`UNIT_REPRODUCED`; live tokenizer chunking still requires vLLM/model verification.

## Finding F4 — open issue #3 is a clean contribution door

The upstream project itself requests unit tests for this parser and the issue remains open. A narrow regression-test contribution is therefore a lower-risk first upstream PR than introducing an external runtime/framework integration immediately.

## Harness limitation

The executable tests stub vLLM protocol/model classes so parser logic can be exercised without installing vLLM or loading a model. The parser source under test is the repository file at `tools/bielik_vllm_tool_parser.py`.

Therefore:

- exercised parser logic = mechanically tested
- vLLM package integration = not yet proven
- live Bielik inference = not yet proven
- no claim of upstream compatibility closure is made

## Recommended next patch sequence

1. Run the test branch in a real vLLM matrix for 0.18 / 0.19 / 0.20 / 0.23 / 0.24.
2. Resolve #12 with a version-correct constructor strategy.
3. Verify `supports_required_and_named=False` behavior for 0.20–0.23.
4. Reproduce or dismiss the streaming XFAIL with real tokenizer chunks.
5. Only after green evidence: prepare an upstream PR.

## Verdict

**Phase 1 technical thesis: CONFIRMED.**

`bielik-tools` has a concrete, currently open testing/compatibility surface where a focused external contribution can add immediate value. The fork and Phase 1 branch exist and contain the proof/test pack; upstream remains untouched.
