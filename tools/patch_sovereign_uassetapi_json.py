#!/usr/bin/env python3
"""Patch UAssetAPI-format Sovereign_Manager.json for random spawn timer (900-5400s)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

MIN_SEC = 900.0
MAX_SEC = 5400.0

STACK_RANDOM = -301  # RandomFloatInRange import index in this asset
STACK_SET_TIMER = -310  # K2_SetTimerDelegate


def random_float_expr() -> dict:
    return {
        "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_CallMath, UAssetAPI",
        "StackNode": STACK_RANDOM,
        "Parameters": [
            {
                "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_FloatConst, UAssetAPI",
                "Value": MIN_SEC,
            },
            {
                "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_FloatConst, UAssetAPI",
                "Value": MAX_SEC,
            },
        ],
    }


def set_timer_stmt() -> dict:
    """EX_Let wrapping K2_SetTimerDelegate (matches existing init block shape)."""
    return {
        "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_Let, UAssetAPI",
        "Value": {
            "$type": "UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI",
            "New": {
                "$type": "UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI",
                "Path": ["CallFunc_K2_SetTimerDelegate_ReturnValue"],
                "ResolvedOwner": 1,
            },
        },
        "Variable": {
            "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_LocalVariable, UAssetAPI",
            "Variable": {
                "$type": "UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI",
                "New": {
                    "$type": "UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI",
                    "Path": ["CallFunc_K2_SetTimerDelegate_ReturnValue"],
                    "ResolvedOwner": 1,
                },
            },
        },
        "Expression": {
            "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_CallMath, UAssetAPI",
            "StackNode": STACK_SET_TIMER,
            "Parameters": [
                {
                    "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_LocalVariable, UAssetAPI",
                    "Variable": {
                        "$type": "UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI",
                        "New": {
                            "$type": "UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI",
                            "Path": ["K2Node_CreateDelegate_OutputDelegate"],
                            "ResolvedOwner": 1,
                        },
                    },
                },
                random_float_expr(),
                {"$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_False, UAssetAPI"},
                {
                    "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_FloatConst, UAssetAPI",
                    "Value": "+0",
                },
                {
                    "$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_FloatConst, UAssetAPI",
                    "Value": "+0",
                },
            ],
        },
    }


def patch_init_timer(script: list) -> bool:
    for i, stmt in enumerate(script):
        if not isinstance(stmt, dict):
            continue
        expr = stmt.get("Expression")
        if not isinstance(expr, dict):
            continue
        if expr.get("StackNode") != STACK_SET_TIMER:
            continue
        params = expr.get("Parameters")
        if not isinstance(params, list) or len(params) < 3:
            continue
        # period + loop
        params[1] = random_float_expr()
        params[2] = {"$type": "UAssetAPI.Kismet.Bytecode.Expressions.EX_False, UAssetAPI"}
        return True
    return False


def is_spawn_loop_init(stmt: dict) -> bool:
    if stmt.get("$type") != "UAssetAPI.Kismet.Bytecode.Expressions.EX_Let, UAssetAPI":
        return False
    var = stmt.get("Variable") or {}
    inner = var.get("Variable") or {}
    path = (inner.get("New") or {}).get("Path") or []
    if path != ["Temp_int_Loop_Counter_Variable"]:
        return False
    expr = stmt.get("Expression") or {}
    return (
        expr.get("$type") == "UAssetAPI.Kismet.Bytecode.Expressions.EX_IntConst, UAssetAPI"
        and expr.get("Value") == 0
    )


def insert_rearm(script: list) -> bool:
    for i, stmt in enumerate(script):
        if not is_spawn_loop_init(stmt):
            continue
        if i > 0 and isinstance(script[i - 1], dict):
            prev = script[i - 1]
            if prev.get("Expression", {}).get("StackNode") == STACK_SET_TIMER:
                return False
        script.insert(i, copy.deepcopy(set_timer_stmt()))
        return True
    return False


def find_ubergraph_script(data: dict) -> list | None:
    exports = data.get("Exports") or []
    for exp in exports:
        if not isinstance(exp, dict):
            continue
        if exp.get("ObjectName") == "ExecuteUbergraph_Sovereign_Manager":
            script = exp.get("ScriptBytecode")
            if isinstance(script, list):
                return script
    # fallback: search
    def walk(o):
        if isinstance(o, dict):
            if o.get("ObjectName") == "ExecuteUbergraph_Sovereign_Manager":
                sc = o.get("ScriptBytecode")
                if isinstance(sc, list):
                    return sc
            for v in o.values():
                r = walk(v)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v)
                if r is not None:
                    return r
        return None

    return walk(data)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python patch_sovereign_uassetapi_json.py Sovereign_Manager.json [out.json]")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name(src.stem + ".patched.json")
    data = json.loads(src.read_text(encoding="utf-8"))
    script = find_ubergraph_script(data)
    if script is None:
        print("ERROR: ExecuteUbergraph_Sovereign_Manager ScriptBytecode not found")
        sys.exit(1)
    ok_timer = patch_init_timer(script)
    ok_rearm = insert_rearm(script)
    dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Init timer patched: {ok_timer}")
    print(f"Spawn-pass re-arm inserted: {ok_rearm}")
    print(f"Random range: {MIN_SEC}-{MAX_SEC} seconds")
    print(f"Wrote: {dst}")
    if not ok_timer:
        sys.exit(1)


if __name__ == "__main__":
    main()
