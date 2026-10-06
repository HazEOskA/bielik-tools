#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
MODEL = "speakleash/Bielik-1.5B-v3.0-Instruct-GGUF"
OUT = Path("evidence/phase4-live-vllm.json")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Pobierz aktualną pogodę dla miasta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "enum": ["Łódź"],
                        "description": "Miasto; w tym teście dokładnie Łódź.",
                    }
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
    }
]


def request_json(path: str, payload: dict | None = None, timeout: int = 120) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def stream_json(path: str, payload: dict, timeout: int = 120) -> list[dict]:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict] = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            body = line[6:]
            if body == "[DONE]":
                break
            events.append(json.loads(body))
    return events


def extract_tool_call(response: dict) -> dict:
    message = response["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if not calls:
        raise AssertionError(f"expected tool call, got message={message}")
    call = calls[0]
    if call["function"]["name"] != "get_current_weather":
        raise AssertionError(f"wrong tool: {call}")
    args = json.loads(call["function"]["arguments"])
    if args.get("location") != "Łódź":
        raise AssertionError(f"unicode/tool args mismatch: {args}")
    return call


def aggregate_stream(events: list[dict]) -> dict:
    calls: dict[int, dict] = {}
    finish_reasons: list[str] = []
    for event in events:
        for choice in event.get("choices", []):
            if choice.get("finish_reason"):
                finish_reasons.append(choice["finish_reason"])
            delta = choice.get("delta") or {}
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                dst = calls.setdefault(
                    idx,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                if tc.get("id"):
                    dst["id"] += tc["id"]
                if tc.get("type"):
                    dst["type"] = tc["type"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    dst["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    dst["function"]["arguments"] += fn["arguments"]

    if not calls:
        raise AssertionError("stream produced no tool_calls")
    call = calls[min(calls)]
    if call["function"]["name"] != "get_current_weather":
        raise AssertionError(f"stream wrong tool: {call}")
    args = json.loads(call["function"]["arguments"])
    if args.get("location") != "Łódź":
        raise AssertionError(f"stream unicode/tool args mismatch: {args}")
    return {"call": call, "finish_reasons": finish_reasons, "event_count": len(events)}


def main() -> int:
    evidence = {
        "model": MODEL,
        "base_url": BASE_URL,
        "tests": {},
        "started_at_unix": time.time(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)

    try:
        models = request_json("/v1/models", timeout=30)
        evidence["tests"]["server_ready"] = {"status": "PASS", "models": models.get("data", [])}

        common = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": "Sprawdź aktualną pogodę w Łodzi. Użyj dostępnego narzędzia.",
                }
            ],
            "tools": TOOLS,
            "temperature": 0,
            "max_tokens": 96,
            "chat_template_kwargs": {"tool_choice": "required", "enable_thinking": False},
        }

        required_payload = dict(common)
        required_payload["tool_choice"] = "required"
        required = request_json("/v1/chat/completions", required_payload)
        call = extract_tool_call(required)
        evidence["tests"]["required_tool_call"] = {
            "status": "PASS",
            "tool_call": call,
        }

        auto_payload = dict(common)
        auto_payload["tool_choice"] = "auto"
        auto_payload["chat_template_kwargs"] = {"enable_thinking": False}
        auto = request_json("/v1/chat/completions", auto_payload)
        auto_call = extract_tool_call(auto)
        evidence["tests"]["auto_tool_call"] = {
            "status": "PASS",
            "tool_call": auto_call,
        }

        stream_payload = dict(common)
        stream_payload["tool_choice"] = "required"
        stream_payload["stream"] = True
        events = stream_json("/v1/chat/completions", stream_payload)
        aggregated = aggregate_stream(events)
        evidence["tests"]["streaming_required_tool_call"] = {
            "status": "PASS",
            **aggregated,
        }

        followup_messages = list(common["messages"])
        followup_messages.append(required["choices"][0]["message"])
        followup_messages.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "name": "get_current_weather",
                "content": json.dumps(
                    {"location": "Łódź", "temperature": "11°C", "weather": "deszcz"},
                    ensure_ascii=False,
                ),
            }
        )
        followup = request_json(
            "/v1/chat/completions",
            {
                "model": MODEL,
                "messages": followup_messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0,
                "max_tokens": 128,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        final_message = followup["choices"][0]["message"]
        if not (final_message.get("content") or "").strip():
            raise AssertionError(f"empty final answer after tool result: {final_message}")
        evidence["tests"]["tool_result_roundtrip"] = {
            "status": "PASS",
            "message": final_message,
        }

        evidence["verdict"] = "LIVE_RUNTIME_VERIFIED"
        return_code = 0
    except Exception as exc:
        evidence["verdict"] = "LIVE_RUNTIME_FAILED"
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = str(exc)
        return_code = 1
    finally:
        evidence["finished_at_unix"] = time.time()
        OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
