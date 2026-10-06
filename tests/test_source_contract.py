from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "tools" / "bielik_vllm_tool_parser.py").read_text(encoding="utf-8")


def test_upstream_024_contract_markers_present():
    assert "vLLM >= 0.24.0" in SRC
    assert "supports_required_and_named: bool = False" in SRC
    assert "def __init__(self, tokenizer: TokenizerLike, tools: list[Tool] | None = None)" in SRC


def test_required_workaround_markers_present():
    assert 'if request.tool_choice == "required"' in SRC
    assert 'request.tool_choice = "auto"' in SRC
    assert "StructuredOutputsParams" in SRC


def test_tool_tag_protocol_is_explicit():
    assert 'self.tool_call_start_token: str = "<tool_call>"' in SRC
    assert 'self.tool_call_end_token: str = "</tool_call>"' in SRC
