#!/usr/bin/env python3
"""Probe Bielik parser compatibility against real published vLLM wheels.

This does not load a model or execute CUDA. It downloads the exact vLLM wheel
from PyPI, inspects the shipped Python API surface, and compares that surface
with the Bielik parser selected for the same version.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def parser_signature(source: str, class_name: str) -> dict:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_attrs = set()
            init = None
            for child in node.body:
                if isinstance(child, (ast.Assign, ast.AnnAssign)):
                    target = child.targets[0] if isinstance(child, ast.Assign) else child.target
                    if isinstance(target, ast.Name):
                        class_attrs.add(target.id)
                if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                    init = child
            if init is None:
                return {"params": [], "class_attrs": sorted(class_attrs)}
            params = [a.arg for a in init.args.args]
            defaults = len(init.args.defaults)
            required = params[: max(0, len(params) - defaults)]
            return {
                "params": params,
                "required_params": required,
                "has_varargs": init.args.vararg is not None,
                "has_varkw": init.args.kwarg is not None,
                "class_attrs": sorted(class_attrs),
            }
    raise RuntimeError(f"class {class_name} not found")


def module_candidates(module: str) -> list[str]:
    base = module.replace(".", "/")
    return [base + ".py", base + "/__init__.py"]


def imported_vllm_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("vllm"):
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("vllm"):
                    mods.add(alias.name)
    return sorted(mods)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--parser", required=True)
    ap.add_argument("--output", default="vllm-compat-result.json")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    parser_path = repo / args.parser
    parser_src = parser_path.read_text(encoding="utf-8")
    bielik = parser_signature(parser_src, "BielikToolParser")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--disable-pip-version-check",
            "--no-deps",
            "--only-binary=:all:",
            "--dest",
            str(td_path),
            f"vllm=={args.version}",
        ]
        cp = subprocess.run(cmd, text=True, capture_output=True)
        result = {
            "vllm_version": args.version,
            "parser": args.parser,
            "pip_download_returncode": cp.returncode,
            "pip_stdout_tail": cp.stdout[-2000:],
            "pip_stderr_tail": cp.stderr[-2000:],
        }
        if cp.returncode != 0:
            result["verdict"] = "WHEEL_DOWNLOAD_FAILED"
            Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))
            return 0

        wheels = list(td_path.glob("vllm-*.whl"))
        if not wheels:
            result["verdict"] = "NO_WHEEL"
            Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))
            return 0

        wheel = wheels[0]
        result["wheel"] = wheel.name
        with zipfile.ZipFile(wheel) as zf:
            names = set(zf.namelist())
            abstract_candidates = [
                "vllm/tool_parsers/abstract_tool_parser.py",
                "vllm/entrypoints/openai/tool_parsers/abstract_tool_parser.py",
            ]
            abstract_path = next((p for p in abstract_candidates if p in names), None)
            if not abstract_path:
                result["verdict"] = "ABSTRACT_PARSER_NOT_FOUND"
                Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(json.dumps(result, indent=2))
                return 0

            abstract_src = zf.read(abstract_path).decode("utf-8")
            base = parser_signature(abstract_src, "ToolParser")
            result["wheel_abstract_parser"] = abstract_path
            result["vllm_toolparser_signature"] = base
            result["bielik_parser_signature"] = bielik

            imported_modules = imported_vllm_modules(parser_src)
            protocol_compat_group = {
                "vllm.entrypoints.openai.engine.protocol",
                "vllm.entrypoints.generate.base.protocol",
            }

            missing_modules = []
            for mod in imported_modules:
                if mod in protocol_compat_group:
                    continue
                if not any(candidate in names for candidate in module_candidates(mod)):
                    missing_modules.append(mod)

            used_protocol_group = bool(protocol_compat_group.intersection(imported_modules))
            protocol_group_present = any(
                any(candidate in names for candidate in module_candidates(mod))
                for mod in protocol_compat_group
            )
            if used_protocol_group and not protocol_group_present:
                missing_modules.append("vllm.protocol.compat-group")

            result["missing_vllm_import_modules"] = missing_modules

            base_accepts_tools = (
                "tools" in base.get("params", [])
                or base.get("has_varargs", False)
                or base.get("has_varkw", False)
            )
            bielik_accepts_tools = (
                "tools" in bielik.get("params", [])
                or bielik.get("has_varargs", False)
                or bielik.get("has_varkw", False)
            )
            base_has_required_named = "supports_required_and_named" in base.get("class_attrs", [])
            bielik_has_required_named = "supports_required_and_named" in bielik.get("class_attrs", [])

            risks = []
            if missing_modules:
                risks.append("PARSER_IMPORT_PATH_MISSING")
            if base_accepts_tools and not bielik_accepts_tools:
                risks.append("CONSTRUCTOR_TOOLS_MISMATCH")
            if base_has_required_named and not bielik_has_required_named:
                risks.append("REQUIRED_NAMED_ROUTING_FLAG_MISSING")

            result["checks"] = {
                "base_accepts_tools": base_accepts_tools,
                "bielik_accepts_tools": bielik_accepts_tools,
                "base_has_supports_required_and_named": base_has_required_named,
                "bielik_has_supports_required_and_named": bielik_has_required_named,
            }
            result["risks"] = risks
            result["verdict"] = "COMPATIBLE_API_SHAPE" if not risks else "RISK_DETECTED"

    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
