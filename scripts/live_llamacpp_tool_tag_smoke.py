#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8080"
OUT = Path("evidence/phase4-live-llamacpp.json")

TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)

TOOLS = [
    {
        "name": "get_current_weather",
        "description": "Pobierz aktualną pogodę dla miasta.",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    },
    {
        "name": "get_n_day_weather_forecast",
        "description": "Pobierz prognozę pogody na N dni.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "num_days": {"type": "integer"},
            },
            "required": ["location", "num_days"],
        },
    },
]


def completion(prompt: str, *, n_predict: int = 160) -> str:
    payload = {
        "prompt": prompt,
        "temperature": 0.0,
        "n_predict": n_predict,
        "stop": ["<|im_end|>"],
        "cache_prompt": False,
    }
    req = urllib.request.Request(
        BASE_URL + "/completion",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("content", "")


def tool_prompt(user_text: str, *, required: bool = True) -> str:
    mandate = (
        "Musisz wywołać co najmniej jedno narzędzie. Nie odpowiadaj użytkownikowi "
        "bez wcześniejszego wywołania narzędzia."
        if required
        else "Możesz użyć narzędzia, jeżeli jest potrzebne."
    )
    tools_json = json.dumps(TOOLS, ensure_ascii=False, indent=2)
    return (
        "<|im_start|>system\n"
        "Jesteś asystentem z dostępem do narzędzi. "
        + mandate
        + "\nJeżeli wywołujesz narzędzie, MUSISZ użyć dokładnie formatu:\n"
        + '<tool_call>{"name": "<nazwa>", "arguments": {<argumenty>}}</tool_call>\n'
        + "Nie wymyślaj wyniku narzędzia. Dostępne narzędzia:\n"
        + tools_json
        + "\n<|im_end|>\n"
        + "<|im_start|>user\n"
        + user_text
        + "\n<|im_end|>\n"
        + "<|im_start|>assistant\n"
    )


def parse_calls(text: str) -> list[dict]:
    calls = []
    for match in TOOL_CALL_RE.findall(text):
        calls.append(json.loads(match))
    return calls


def require_call(text: str, name: str, expected_args: dict) -> dict:
    calls = parse_calls(text)
    if not calls:
        raise AssertionError(f"no <tool_call> found in: {text!r}")
    call = calls[0]
    if call.get("name") != name:
        raise AssertionError(f"wrong tool name: {call}")
    args = call.get("arguments")
    if not isinstance(args, dict):
        raise AssertionError(f"arguments are not an object: {call}")
    for key, value in expected_args.items():
        if args.get(key) != value:
            raise AssertionError(f"argument mismatch for {key}: {args!r}")
    return call


def main() -> int:
    evidence = {
        "runtime": "llama.cpp CPU",
        "model": "speakleash/Bielik-1.5B-v3.0-Instruct-GGUF:Q8_0",
        "tests": {},
        "started_at_unix": time.time(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)

    try:
        weather_raw = completion(
            tool_prompt("Sprawdź aktualną pogodę w Łodzi. Użyj narzędzia.")
        )
        weather_call = require_call(
            weather_raw,
            "get_current_weather",
            {"location": "Łódź"},
        )
        evidence["tests"]["unicode_required_tool_call"] = {
            "status": "PASS",
            "raw": weather_raw,
            "call": weather_call,
        }

        forecast_raw = completion(
            tool_prompt("Podaj prognozę pogody dla Krakowa na dokładnie 3 dni.")
        )
        forecast_call = require_call(
            forecast_raw,
            "get_n_day_weather_forecast",
            {"location": "Kraków", "num_days": 3},
        )
        evidence["tests"]["numeric_required_tool_call"] = {
            "status": "PASS",
            "raw": forecast_raw,
            "call": forecast_call,
        }

        result_json = json.dumps(
            {"location": "Łódź", "temperature": "11°C", "weather": "deszcz"},
            ensure_ascii=False,
        )
        roundtrip_prompt = (
            tool_prompt("Sprawdź aktualną pogodę w Łodzi. Użyj narzędzia.")
            + weather_raw
            + "<|im_end|>\n"
            + "<|im_start|>tool\n"
            + result_json
            + "<|im_end|>\n"
            + "<|im_start|>assistant\n"
        )
        final_raw = completion(roundtrip_prompt, n_predict=128)
        if not final_raw.strip():
            raise AssertionError("empty final answer after tool result")
        if "<tool_call>" in final_raw:
            raise AssertionError(f"model called tool again after result: {final_raw!r}")
        evidence["tests"]["tool_result_roundtrip"] = {
            "status": "PASS",
            "tool_result": result_json,
            "final": final_raw,
        }

        evidence["verdict"] = "MODEL_LIVE_TOOL_TAG_VERIFIED"
        rc = 0
    except Exception as exc:
        evidence["verdict"] = "MODEL_LIVE_TOOL_TAG_FAILED"
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
