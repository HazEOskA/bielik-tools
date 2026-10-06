import importlib.util
import json
import logging
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARSER_PATH = ROOT / "tools" / "bielik_vllm_tool_parser.py"


class Model:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self, exclude_none=False):
        out = dict(self.__dict__)
        if exclude_none:
            out = {k: v for k, v in out.items() if v is not None}
        return out


class FunctionCall(Model):
    pass


class ToolCall(Model):
    pass


class DeltaFunctionCall(Model):
    pass


class DeltaToolCall(Model):
    pass


class DeltaMessage(Model):
    def __init__(self, content=None, tool_calls=None, **kwargs):
        super().__init__(content=content, tool_calls=tool_calls, **kwargs)


class ExtractedToolCallInformation(Model):
    pass


class ChatCompletionRequest(Model):
    def __init__(self, tools=None, tool_choice="auto", skip_special_tokens=True,
                 response_format="sentinel", structured_outputs=None):
        super().__init__(
            tools=tools,
            tool_choice=tool_choice,
            skip_special_tokens=skip_special_tokens,
            response_format=response_format,
            structured_outputs=structured_outputs,
        )


class StructuredOutputsParams(Model):
    pass


class FakeTokenizer:
    def __init__(self):
        self.vocab = {"<tool_call>": 101, "</tool_call>": 102}


class MistralTokenizer(FakeTokenizer):
    def __init__(self):
        super().__init__()
        self.tokenizer = FakeTokenizer()


class Tool:
    pass


class ToolParser:
    def __init__(self, tokenizer, tools=None):
        self.model_tokenizer = tokenizer
        self.vocab = tokenizer.vocab
        self.tools = tools


class ToolParserManager:
    @staticmethod
    def register_module(_name):
        def decorator(cls):
            return cls
        return decorator


class Allow:
    ALL = 0b1111
    STR = 0b0001


class MalformedJSON(Exception):
    pass


def _install_module(name, module):
    sys.modules[name] = module
    if "." in name:
        parent_name, child_name = name.rsplit(".", 1)
        parent = sys.modules.get(parent_name)
        if parent is not None:
            setattr(parent, child_name, module)


def install_stubs():
    partial = types.ModuleType("partial_json_parser")
    partial.loads = lambda payload, _flags: json.loads(payload)
    core = types.ModuleType("partial_json_parser.core")
    options = types.ModuleType("partial_json_parser.core.options")
    options.Allow = Allow
    exceptions = types.ModuleType("partial_json_parser.core.exceptions")
    exceptions.MalformedJSON = MalformedJSON
    core.options = options
    core.exceptions = exceptions
    partial.core = core
    for name, mod in [
        ("partial_json_parser", partial),
        ("partial_json_parser.core", core),
        ("partial_json_parser.core.options", options),
        ("partial_json_parser.core.exceptions", exceptions),
    ]:
        _install_module(name, mod)

    names = [
        "vllm",
        "vllm.entrypoints",
        "vllm.entrypoints.openai",
        "vllm.entrypoints.openai.chat_completion",
        "vllm.entrypoints.openai.chat_completion.protocol",
        "vllm.entrypoints.openai.engine",
        "vllm.entrypoints.openai.engine.protocol",
        "vllm.logger",
        "vllm.sampling_params",
        "vllm.tokenizers",
        "vllm.tokenizers.mistral",
        "vllm.tool_parsers",
        "vllm.tool_parsers.abstract_tool_parser",
        "vllm.utils",
    ]
    mods = {name: types.ModuleType(name) for name in names}
    for name, mod in mods.items():
        _install_module(name, mod)

    mods["vllm.entrypoints.openai.chat_completion.protocol"].ChatCompletionRequest = ChatCompletionRequest
    protocol = mods["vllm.entrypoints.openai.engine.protocol"]
    protocol.DeltaFunctionCall = DeltaFunctionCall
    protocol.DeltaMessage = DeltaMessage
    protocol.DeltaToolCall = DeltaToolCall
    protocol.ExtractedToolCallInformation = ExtractedToolCallInformation
    protocol.FunctionCall = FunctionCall
    protocol.ToolCall = ToolCall
    mods["vllm.logger"].init_logger = lambda _name: logging.getLogger(_name)
    mods["vllm.sampling_params"].StructuredOutputsParams = StructuredOutputsParams
    mods["vllm.tokenizers"].TokenizerLike = object
    mods["vllm.tokenizers.mistral"].MistralTokenizer = MistralTokenizer
    abstract = mods["vllm.tool_parsers.abstract_tool_parser"]
    abstract.Tool = Tool
    abstract.ToolParser = ToolParser
    abstract.ToolParserManager = ToolParserManager
    mods["vllm.utils"].random_uuid = lambda: "unit-test-uuid"


install_stubs()
spec = importlib.util.spec_from_file_location("bielik_parser_under_test", PARSER_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BielikToolParser = module.BielikToolParser


@pytest.fixture
def parser():
    return BielikToolParser(FakeTokenizer())


def req(choice="auto", tools=True):
    return ChatCompletionRequest(tools=[{"type": "function"}] if tools else [], tool_choice=choice)


def test_no_tool_call_is_plain_content(parser):
    result = parser.extract_tool_calls("Zwykła odpowiedź", req())
    assert result.tools_called is False
    assert result.tool_calls == []
    assert result.content == "Zwykła odpowiedź"


def test_single_tool_call(parser):
    result = parser.extract_tool_calls(
        '<tool_call>{"name":"get_weather","arguments":{"city":"Warszawa"}}</tool_call>', req()
    )
    assert result.tools_called is True
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].function.name == "get_weather"
    assert json.loads(result.tool_calls[0].function.arguments) == {"city": "Warszawa"}
    assert result.content is None


def test_whitespace_after_opening_tag_regression_issue_9(parser):
    result = parser.extract_tool_calls(
        '<tool_call> {"name":"get_db","arguments":{}}</tool_call>', req("required")
    )
    assert result.tools_called is True
    assert result.tool_calls[0].function.name == "get_db"


def test_newline_after_opening_tag(parser):
    result = parser.extract_tool_calls(
        '<tool_call>\n  {"name":"lookup","arguments":{"q":"żółć"}}\n</tool_call>', req()
    )
    assert result.tools_called is True
    assert json.loads(result.tool_calls[0].function.arguments) == {"q": "żółć"}


def test_multiple_tool_calls(parser):
    output = (
        '<tool_call>{"name":"first","arguments":{"x":1}}</tool_call>'
        '<tool_call>{"name":"second","arguments":{"y":2}}</tool_call>'
    )
    result = parser.extract_tool_calls(output, req())
    assert result.tools_called is True
    assert [c.function.name for c in result.tool_calls] == ["first", "second"]


def test_content_before_tool_call_is_preserved(parser):
    result = parser.extract_tool_calls(
        'Sprawdzam. <tool_call>{"name":"check","arguments":{}}</tool_call>', req()
    )
    assert result.tools_called is True
    assert result.content == "Sprawdzam. "


def test_unicode_arguments_are_not_ascii_escaped(parser):
    result = parser.extract_tool_calls(
        '<tool_call>{"name":"echo","arguments":{"tekst":"Zażółć gęślą jaźń"}}</tool_call>', req()
    )
    assert "Zażółć gęślą jaźń" in result.tool_calls[0].function.arguments


def test_malformed_json_fails_closed(parser):
    output = '<tool_call>{"name":"broken","arguments":</tool_call>'
    result = parser.extract_tool_calls(output, req())
    assert result.tools_called is False
    assert result.tool_calls == []
    assert result.content == output


def test_unclosed_but_complete_json_is_parsed(parser):
    output = '<tool_call>{"name":"recover","arguments":{"ok":true}}'
    result = parser.extract_tool_calls(output, req())
    assert result.tools_called is True
    assert result.tool_calls[0].function.name == "recover"


def test_missing_arguments_fails_closed(parser):
    output = '<tool_call>{"name":"no_args"}</tool_call>'
    result = parser.extract_tool_calls(output, req())
    assert result.tools_called is False
    assert result.content == output


def test_required_is_redirected_to_auto_with_guided_regex(parser):
    request = req("required")
    request.response_format = {"type": "json_schema"}
    result = parser.adjust_request(request)
    assert result.tool_choice == "auto"
    assert result.skip_special_tokens is False
    assert result.response_format is None
    assert isinstance(result.structured_outputs, StructuredOutputsParams)
    regex = re.compile(result.structured_outputs.regex)
    assert regex.fullmatch('<tool_call>{"name":"x","arguments":{}}</tool_call>')
    assert not regex.fullmatch("plain text")


def test_auto_keeps_choice_and_disables_skip_special_tokens(parser):
    request = req("auto")
    result = parser.adjust_request(request)
    assert result.tool_choice == "auto"
    assert result.skip_special_tokens is False
    assert result.structured_outputs is None


def test_none_does_not_touch_request(parser):
    request = req("none")
    result = parser.adjust_request(request)
    assert result.tool_choice == "none"
    assert result.skip_special_tokens is True


def test_parser_declares_required_and_named_not_natively_supported():
    assert BielikToolParser.supports_required_and_named is False


def test_vllm_024_constructor_accepts_tools_argument():
    tokenizer = FakeTokenizer()
    p = BielikToolParser(tokenizer, tools=[Tool()])
    assert len(p.tools) == 1


def test_streaming_plain_text_passthrough(parser):
    result = parser.extract_tool_calls_streaming(
        previous_text="",
        current_text="hello",
        delta_text="hello",
        previous_token_ids=[],
        current_token_ids=[999],
        delta_token_ids=[999],
        request=req(),
    )
    assert result.content == "hello"


def test_streaming_emits_tool_name_when_complete_json_is_available(parser):
    current = '<tool_call>{"name":"search","arguments":{}}'
    result = parser.extract_tool_calls_streaming(
        previous_text="",
        current_text=current,
        delta_text=current,
        previous_token_ids=[],
        current_token_ids=[101, 999],
        delta_token_ids=[101, 999],
        request=req(),
    )
    assert result.tool_calls[0].function["name"] == "search"
    assert result.tool_calls[0].id == "chatcmpl-tool-unit-test-uuid"


@pytest.mark.xfail(
    reason="Known streaming edge: closing delta without substring '\"}' is dropped; numeric/bool/object final argument may hit this path",
    strict=True,
)
def test_streaming_close_numeric_argument_emits_final_delta(parser):
    parser.current_tool_id = 0
    parser.current_tool_name_sent = True
    parser.prev_tool_call_arr = [{"arguments": {"x": 1}}]
    parser.streamed_args_for_tool = ['{"x":']
    result = parser.extract_tool_calls_streaming(
        previous_text='<tool_call>{"name":"calc","arguments":{"x":',
        current_text='<tool_call>{"name":"calc","arguments":{"x":1}}',
        delta_text='1}}</tool_call>',
        previous_token_ids=[101],
        current_token_ids=[101, 102],
        delta_token_ids=[999, 102],
        request=req(),
    )
    assert result is not None
    assert result.tool_calls
