#!/usr/bin/env python3
"""
Patch Spawn Sovereign Sovereign_Manager for random spawn intervals (seconds).

Workflow (no Unreal Editor):
  1. Backup Sovereign_Manager.uasset + .uexp
  2. UAssetGUI 4.27 → open asset → File → save/export JSON (full asset JSON)
  3. python tools/patch_sovereign_random_timer.py path/to/export.json
  4. UAssetGUI → import/open patched JSON → File → Save (writes .uasset/.uexp)
  5. Repak → server

Default: random delay 900–5400 s (15–90 minutes) per tick, non-looping timer,
re-armed at the start of each spawn pass (inserted before the player-loop init).
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

MIN_SEC = 900.0
MAX_SEC = 5400.0


def random_float_in_range(min_v: float, max_v: float) -> dict:
    return {
        "Inst": "CallMath",
        "Function": "RandomFloatInRange",
        "ContextClass": "/Script/Engine.KismetMathLibrary",
        "Parameters": [
            {"Inst": "FloatConst", "Value": min_v},
            {"Inst": "FloatConst", "Value": max_v},
        ],
    }


def set_timer_delegate(delegate_var: str = "K2Node_CreateDelegate_OutputDelegate") -> dict:
    return {
        "Inst": "CallMath",
        "Function": "K2_SetTimerDelegate",
        "ContextClass": "/Script/Engine.KismetSystemLibrary",
        "Parameters": [
            {
                "Inst": "LocalVariable",
                "Variable Outer": {
                    "PinCategory": "Delegate",
                    "PinSubCategory": "Delegate",
                },
                "Variable Name": delegate_var,
            },
            random_float_in_range(MIN_SEC, MAX_SEC),
            {"Inst": "False"},
            {"Inst": "FloatConst", "Value": 0.0},
            {"Inst": "FloatConst", "Value": 0.0},
        ],
    }


def patch_set_timer_node(node: dict) -> bool:
    if node.get("Inst") != "CallMath" or node.get("Function") != "K2_SetTimerDelegate":
        return False
    params = node.get("Parameters")
    if not isinstance(params, list) or len(params) < 3:
        return False
    # Replace period + looping (keep delegate + initial delays)
    params[1] = random_float_in_range(MIN_SEC, MAX_SEC)
    params[2] = {"Inst": "False"}
    return True


def walk_patch_timers(obj: object) -> int:
    n = 0
    if isinstance(obj, dict):
        if patch_set_timer_node(obj):
            n += 1
        for v in obj.values():
            n += walk_patch_timers(v)
    elif isinstance(obj, list):
        for item in obj:
            n += walk_patch_timers(item)
    return n


def find_ubergraph_scripts(root: object) -> list[list]:
    scripts: list[list] = []

    def walk(o: object) -> None:
        if isinstance(o, dict):
            if o.get("Name") == "ExecuteUbergraph_Sovereign_Manager" and isinstance(
                o.get("Script"), list
            ):
                scripts.append(o["Script"])
            if isinstance(o.get("Script"), list) and any(
                s.get("Function") == "K2_SetTimerDelegate"
                for s in o["Script"]
                if isinstance(s, dict)
            ):
                scripts.append(o["Script"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for item in o:
                walk(item)

    walk(root)
    # dedupe by id
    seen: set[int] = set()
    out: list[list] = []
    for s in scripts:
        key = id(s)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def is_spawn_loop_init(stmt: dict) -> bool:
    """Let Temp_int_Loop_Counter_Variable = IntConst 0 at start of spawn pass."""
    if stmt.get("Inst") != "Let":
        return False
    var = stmt.get("Variable") or {}
    if var.get("Variable Name") != "Temp_int_Loop_Counter_Variable":
        return False
    expr = stmt.get("Expression") or {}
    return expr.get("Inst") == "IntConst" and expr.get("Value") == 0


def insert_rearm_before_spawn_loop(script: list) -> bool:
    for i, stmt in enumerate(script):
        if not is_spawn_loop_init(stmt):
            continue
        # Already inserted?
        prev = script[i - 1] if i else None
        if isinstance(prev, dict) and prev.get("Function") == "K2_SetTimerDelegate":
            return False
        script.insert(i, deepcopy(set_timer_delegate()))
        return True
    return False


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python patch_sovereign_random_timer.py <UAssetGUI-export.json> [out.json]")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name(src.stem + ".patched.json")
    data = json.loads(src.read_text(encoding="utf-8"))

    timer_patches = walk_patch_timers(data)
    scripts = find_ubergraph_scripts(data)
    rearm = 0
    for script in scripts:
        if insert_rearm_before_spawn_loop(script):
            rearm += 1

    dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Patched timer nodes (random {MIN_SEC}-{MAX_SEC}s, no loop): {timer_patches}")
    print(f"Spawn-pass re-arm inserts: {rearm}")
    print(f"Wrote: {dst}")
    if timer_patches == 0:
        print("WARNING: no K2_SetTimerDelegate found — JSON may be incomplete or already patched.")
    if rearm == 0:
        print(
            "WARNING: could not insert re-arm before spawn loop "
            "(look for Let Temp_int_Loop_Counter_Variable = 0). Add SetTimer manually in UAssetGUI bytecode."
        )


if __name__ == "__main__":
    main()
