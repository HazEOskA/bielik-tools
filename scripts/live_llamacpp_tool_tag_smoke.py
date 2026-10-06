#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8080"
OUT = Path("evidence/phase4-live-llamacpp.json")

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
                    }
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
    },
    {
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
    },
]


def get(path: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(BASE_URL + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(path: str, payload: dict, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(model: str, messages: list[dict], tools: list[dict], tool_choice: str = "required") -> dict:
    return post(
        "/v1/chat/completions",
        {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": False,
            "temperature": 0.0,
            "max_tokens": 128,
            "chat_template_kwargs": {
                "enable_thinking": False,
                "tool_choice": tool_choice,
            },
        },
    )


def only_tool(name: str) -> list[dict]:
    return [t for t in TOOLS if t["function"]["name"] == name]


def extract_tool_call(response: dict, expected_name: str, expected_args: dict) -> dict:
    message = response["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if not calls:
        raise AssertionError(
            "OpenAI tool_calls missing; "
            f"content={message.get('content')!r}, full_message={message!r}"
        )
    call = calls[0]
    fn = call.get("function") or {}
    if fn.get("name") != expected_name:
        raise AssertionError(f"wrong tool name: {call!r}")
    raw_args = fn.get("arguments") or "{}"
    args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
    for key, value in expected_args.items():
        if args.get(key) != value:
            raise AssertionError(f"argument mismatch for {key}: {args!r}")
    return call


def main() -> int:
    evidence = {
        "runtime": "llama.cpp CPU + bielik_advanced_chat_template.jinja",
        "model": "speakleash/Bielik-1.5B-v3.0-Instruct-GGUF:Q8_0",
        "tests": {},
        "started_at_unix": time.time(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)

    try:
        models = get("/v1/models")
        model = models["data"][0]["id"]
        evidence["served_model_id"] = model

        weather_messages = [
            {
                "role": "user",
                "content": "Sprawdź aktualną pogodę w Łodzi. Użyj dostępnego narzędzia.",
            }
        ]
        weather = chat(
            model,
            weather_messages,
            only_tool("get_current_weather"),
            "required",
        )
        weather_call = extract_tool_call(
            weather,
            "get_current_weather",
            {"location": "Łódź"},
        )
        evidence["tests"]["required_unicode_tool_call"] = {
            "status": "PASS",
            "message": weather["choices"][0]["message"],
        }

        forecast = chat(
            model,
            [
                {
                    "role": "user",
                    "content": "Sprawdź prognozę dla Krakowa na dokładnie 3 dni. Użyj narzędzia.",
                }
            ],
            only_tool("get_n_day_weather_forecast"),
            "required",
        )
        forecast_call = extract_tool_call(
            forecast,
            "get_n_day_weather_forecast",
            {"location": "Kraków", "num_days": 3},
        )
        evidence["tests"]["required_numeric_tool_call"] = {
            "status": "PASS",
            "message": forecast["choices"][0]["message"],
        }

        tool_result = json.dumps(
            {"location": "Łódź", "temperature": "11°C", "weather": "deszcz"},
            ensure_ascii=False,
        )
        followup_messages = list(weather_messages)
        followup_messages.append(weather["choices"][0]["message"])
        followup_messages.append(
            {
                "role": "tool",
                "tool_call_id": weather_call["id"],
                "name": "get_current_weather",
                "content": tool_result,
            }
        )
        final = chat(
            model,
            followup_messages,
            only_tool("get_current_weather"),
            "auto",
        )
        final_message = final["choices"][0]["message"]
        if not (final_message.get("content") or "").strip():
            raise AssertionError(f"empty final answer after tool result: {final_message!r}")
        evidence["tests"]["tool_result_roundtrip"] = {
            "status": "PASS",
            "tool_result": tool_result,
            "message": final_message,
        }

        evidence["verdict"] = "MODEL_LIVE_TOOL_API_VERIFIED"
        rc = 0
    except Exception as exc:
        evidence["verdict"] = "MODEL_LIVE_TOOL_API_FAILED"
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = str(exc)
        rc = 1
    finally:
        evidence["finished_at_unix"] = time.time()
        OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
