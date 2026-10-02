#!/usr/bin/env python3
"""Patch Sovereign_Manager UAssetAPI JSON: drifter cluster size (Export 1 + 5)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CLUSTER_MIN = 3
CLUSTER_MAX = 6

PREREQ_NAME = "SpawnNPC Prerequisite Funtion"
UBERGRAPH = "ExecuteUbergraph_Sovereign_Manager"
PREREQ_FUNC = "SpawnNPC Prerequisite Funtion"


def map_path(param: dict) -> str | None:
    var = param.get("Variable") or {}
    new = var.get("New") or {}
    path = new.get("Path")
    if isinstance(path, list) and path:
        return path[0]
    return None


def patch_ubergraph_drifter_cluster(exports: list) -> bool:
    for exp in exports:
        if exp.get("ObjectName") != UBERGRAPH:
            continue
        script = exp.get("ScriptBytecode")
        if not isinstance(script, list):
            return False
        for stmt in script:
            if stmt.get("VirtualFunctionName") != PREREQ_NAME:
                continue
            params = stmt.get("Parameters")
            if not isinstance(params, list):
                continue
            if not any(map_path(p) == "ArmedDrifters" for p in params):
                continue
            ints = [
                p
                for p in params
                if p.get("$type", "").endswith("EX_IntConst, UAssetAPI")
            ]
            if not ints:
                continue
            ints[-1]["Value"] = CLUSTER_MAX
            return True
    return False


def patch_prerequisite_random_min(exports: list) -> bool:
    for exp in exports:
        if exp.get("ObjectName") != PREREQ_FUNC:
            continue
        script = exp.get("ScriptBytecode")
        if not isinstance(script, list):
            return False
        for stmt in script:
            expr = stmt.get("Expression")
            if not isinstance(expr, dict):
                continue
            params = expr.get("Parameters")
            if not isinstance(params, list) or len(params) < 2:
                continue
            second = params[1]
            if second.get("$type", "").endswith("EX_LocalVariable, UAssetAPI"):
                path = map_path(second)
                if path == "Cluster Max":
                    first = params[0]
                    if first.get("$type", "").endswith("EX_IntConst, UAssetAPI"):
                        if first.get("Value") == CLUSTER_MIN:
                            return True
                        first["Value"] = CLUSTER_MIN
                        return True
    return False


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python patch_sovereign_cluster.py Sovereign_Manager.json [out.json]"
        )
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else src.with_name(src.stem + ".cluster.json")
    )
    data = json.loads(src.read_text(encoding="utf-8"))
    exports = data.get("Exports") or []
    ok1 = patch_ubergraph_drifter_cluster(exports)
    ok2 = patch_prerequisite_random_min(exports)
    dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Export 1 ArmedDrifters cluster max -> {CLUSTER_MAX}: {ok1}")
    print(f"Export 5 RandomIntegerInRange min -> {CLUSTER_MIN}: {ok2}")
    print(f"Wrote: {dst}")
    if not ok1:
        sys.exit(1)


if __name__ == "__main__":
    main()
