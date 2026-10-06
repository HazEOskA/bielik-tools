from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODERN = (ROOT / "tools" / "bielik_vllm_tool_parser.py").read_text(encoding="utf-8")
LEGACY = (ROOT / "tools" / "bielik_vllm_tool_parser_v0.15.0.py").read_text(encoding="utf-8")


def test_modern_parser_contract_markers_present():
    assert "vLLM >= 0.24.0" in MODERN
    assert "supports_required_and_named: bool = False" in MODERN
    assert "def __init__(self, tokenizer: TokenizerLike, tools: list[Tool] | None = None)" in MODERN


def test_legacy_parser_accepts_tools_across_019_023_boundary():
    assert "supports_required_and_named: bool = False" in LEGACY
    assert "def __init__(self, tokenizer: TokenizerLike, tools=None)" in LEGACY
    assert "super().__init__(tokenizer, tools)" in LEGACY
    assert "super().__init__(tokenizer)" in LEGACY


def test_modern_protocol_import_has_031_fallback():
    assert "vllm.entrypoints.generate.base.protocol" in MODERN
    assert "vllm.entrypoints.openai.engine.protocol" in MODERN
    assert "except ImportError:" in MODERN


def test_required_workaround_markers_present():
    assert 'if request.tool_choice == "required"' in MODERN
    assert 'request.tool_choice = "auto"' in MODERN
    assert "StructuredOutputsParams" in MODERN


def test_tool_tag_protocol_is_explicit():
    assert 'self.tool_call_start_token: str = "<tool_call>"' in MODERN
    assert 'self.tool_call_end_token: str = "</tool_call>"' in MODERN
