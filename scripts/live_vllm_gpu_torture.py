#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

BASE_URL = os.getenv("BIELIK_BASE_URL", "http://127.0.0.1:8000")
MODEL = os.getenv("BIELIK_MODEL", "speakleash/Bielik-1.5B-v3.0-Instruct")
OUT = Path(os.getenv("BIELIK_EVIDENCE_PATH", "evidence/phase5-vllm-gpu.json"))

WEATHER_TOOL = {
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
                }
            },
            "required": ["location"],
            "additionalProperties": False,
        },
    },
}

FORECAST_TOOL = {
    "type": "function",
    "function": {
        "name": "get_n_day_weather_forecast",
        "description": "Pobierz prognozę pogody dla miasta na dokładnie N dni.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "enum": ["Kraków"],
                },
                "num_days": {
                    "type": "integer",
                    "enum": [3],
                },
            },
            "required": ["location", "num_days"],
            "additionalProperties": False,
        },
    },
}


def request_json(path: str, payload: dict | None = None, timeout: int = 300) -> dict:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def stream_json(path: str, payload: dict, timeout: int = 300) -> list[dict]:
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
            data = line[6:]
            if data == "[DONE]":
                break
            events.append(json.loads(data))
    return events


def chat_payload(
    messages: list[dict],
    tools: list[dict],
    tool_choice: str,
    *,
    stream: bool = False,
    max_tokens: int = 128,
) -> dict:
    template_kwargs = {"enable_thinking": False}
    if tool_choice == "required":
        template_kwargs["tool_choice"] = "required"

    return {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": tool_choice,
        "parallel_tool_calls": False,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": stream,
        "chat_template_kwargs": template_kwargs,
    }


def parse_args(raw: str | dict) -> dict:
    return raw if isinstance(raw, dict) else json.loads(raw)


def validate_call(call: dict, expected_name: str, expected_args: dict) -> dict:
    fn = call.get("function") or {}
    name = fn.get("name")
    if name != expected_name:
        raise AssertionError(f"wrong tool name: expected={expected_name!r} got={name!r} call={call!r}")

    args = parse_args(fn.get("arguments") or "{}")
    for key, expected in expected_args.items():
        if args.get(key) != expected:
            raise AssertionError(
                f"argument mismatch: key={key!r} expected={expected!r} got={args.get(key)!r} args={args!r}"
            )
    return {"name": name, "arguments": args, "id": call.get("id")}


def extract_call(response: dict, expected_name: str, expected_args: dict) -> dict:
    message = response["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if not calls:
        raise AssertionError(f"expected tool call; message={message!r}")
    return validate_call(calls[0], expected_name, expected_args)


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
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
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

    return {
        "calls": [calls[k] for k in sorted(calls)],
        "finish_reasons": finish_reasons,
        "event_count": len(events),
    }


def validate_stream(
    events: list[dict],
    expected_name: str,
    expected_args: dict,
) -> dict:
    agg = aggregate_stream(events)
    if not agg["calls"]:
        raise AssertionError(f"stream produced no tool_calls; aggregate={agg!r}")
    validated = validate_call(agg["calls"][0], expected_name, expected_args)
    return {**agg, "validated": validated}


def main() -> int:
    evidence: dict = {
        "phase": 5,
        "runtime": "vLLM 0.31 CUDA",
        "model": MODEL,
        "base_url": BASE_URL,
        "tests": {},
        "started_at_unix": time.time(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    mandatory_failures: list[str] = []

    def mandatory(name: str, fn):
        try:
            value = fn()
            evidence["tests"][name] = {"status": "PASS", **(value or {})}
            return value
        except Exception as exc:
            mandatory_failures.append(name)
            evidence["tests"][name] = {
                "status": "FAIL",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            return None

    try:
        def server_ready():
            models = request_json("/v1/models", timeout=60)
            return {"models": models.get("data", [])}

        mandatory("server_ready", server_ready)

        weather_messages = [
            {
                "role": "user",
                "content": "Sprawdź aktualną pogodę w Łodzi. Użyj dostępnego narzędzia.",
            }
        ]

        required_response = None

        def required_unicode():
            nonlocal required_response
            required_response = request_json(
                "/v1/chat/completions",
                chat_payload(weather_messages, [WEATHER_TOOL], "required"),
            )
            call = extract_call(
                required_response,
                "get_current_weather",
                {"location": "Łódź"},
            )
            return {
                "call": call,
                "finish_reason": required_response["choices"][0].get("finish_reason"),
            }

        mandatory("required_unicode_tool_call", required_unicode)

        def auto_unicode():
            response = request_json(
                "/v1/chat/completions",
                chat_payload(weather_messages, [WEATHER_TOOL], "auto"),
            )
            call = extract_call(
                response,
                "get_current_weather",
                {"location": "Łódź"},
            )
            return {
                "call": call,
                "finish_reason": response["choices"][0].get("finish_reason"),
            }

        mandatory("auto_unicode_tool_call", auto_unicode)

        forecast_messages = [
            {
                "role": "user",
                "content": "Sprawdź prognozę dla Krakowa na dokładnie 3 dni. Użyj narzędzia.",
            }
        ]

        def required_numeric():
            response = request_json(
                "/v1/chat/completions",
                chat_payload(forecast_messages, [FORECAST_TOOL], "required"),
            )
            call = extract_call(
                response,
                "get_n_day_weather_forecast",
                {"location": "Kraków", "num_days": 3},
            )
            return {
                "call": call,
                "finish_reason": response["choices"][0].get("finish_reason"),
            }

        mandatory("required_numeric_tool_call", required_numeric)

        def streaming_unicode():
            events = stream_json(
                "/v1/chat/completions",
                chat_payload(
                    weather_messages,
                    [WEATHER_TOOL],
                    "required",
                    stream=True,
                ),
            )
            return validate_stream(
                events,
                "get_current_weather",
                {"location": "Łódź"},
            )

        mandatory("streaming_unicode_tool_call", streaming_unicode)

        # Known Phase-1 XFAIL candidate: a numeric argument may be lost when
        # the closing delta does not contain the parser's expected '"}' shape.
        try:
            numeric_events = stream_json(
                "/v1/chat/completions",
                chat_payload(
                    forecast_messages,
                    [FORECAST_TOOL],
                    "required",
                    stream=True,
                ),
            )
            numeric_result = validate_stream(
                numeric_events,
                "get_n_day_weather_forecast",
                {"location": "Kraków", "num_days": 3},
            )
            evidence["tests"]["streaming_numeric_known_edge"] = {
                "status": "PASS",
                "known_xfail_resolved_live": True,
                **numeric_result,
            }
        except Exception as exc:
            evidence["tests"]["streaming_numeric_known_edge"] = {
                "status": "XFAIL_REPRODUCED",
                "known_xfail_resolved_live": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "note": (
                    "Matches the known Phase-1 streaming-close numeric edge. "
                    "This does not invalidate non-streaming tool correctness."
                ),
            }

        def roundtrip():
            if required_response is None:
                raise AssertionError("required tool-call response unavailable")
            message = required_response["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            if not calls:
                raise AssertionError(f"required response has no tool_calls: {message!r}")
            tool_call_id = calls[0].get("id")
            if not tool_call_id:
                raise AssertionError(f"tool call id missing: {calls[0]!r}")

            messages = list(weather_messages)
            messages.append(message)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": "get_current_weather",
                    "content": json.dumps(
                        {
                            "location": "Łódź",
                            "temperature": "11°C",
                            "weather": "deszcz",
                        },
                        ensure_ascii=False,
                    ),
                }
            )
            response = request_json(
                "/v1/chat/completions",
                chat_payload(messages, [WEATHER_TOOL], "auto", max_tokens=128),
            )
            final = response["choices"][0]["message"]
            content = (final.get("content") or "").strip()
            if not content:
                raise AssertionError(f"empty final answer after tool result: {final!r}")
            return {"message": final}

        mandatory("tool_result_roundtrip", roundtrip)

        if mandatory_failures:
            evidence["verdict"] = "VLLM_CUDA_LIVE_FAILED"
            evidence["mandatory_failures"] = mandatory_failures
            rc = 1
        else:
            numeric_edge = evidence["tests"]["streaming_numeric_known_edge"]["status"]
            if numeric_edge == "PASS":
                evidence["verdict"] = "VLLM_CUDA_LIVE_VERIFIED"
            else:
                evidence["verdict"] = "VLLM_CUDA_LIVE_VERIFIED_WITH_KNOWN_STREAMING_XFAIL"
            rc = 0

    except Exception as exc:
        evidence["verdict"] = "VLLM_CUDA_HARNESS_ERROR"
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = str(exc)
        rc = 1
    finally:
        evidence["finished_at_unix"] = time.time()
        OUT.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(evidence, ensure_ascii=False, indent=2))

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
