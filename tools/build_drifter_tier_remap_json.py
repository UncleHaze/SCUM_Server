"""Build reference JSON for drifter CommonData tier remap (UAssetGUI guide)."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

SRC = Path(
    r"c:\Users\PurpleHaze\Downloads\f83131ad9315ff62b4106776a012697cbaac3cc4"
    r"\Output\Exports\SCUM\Content\ConZ_Files\Characters\NPCs\Armed_NPCs\Drifter"
)
OUT = Path(__file__).resolve().parents[1] / "fmodel_exports" / "Drifter_tier_remap"

BASE_MAP = [
    ("NPCDrifterCommonData_Lvl_1.json", "NPCDrifterCommonData_Lvl_3.json"),
    ("NPCDrifterCommonData_Lvl_2.json", "NPCDrifterCommonData_Lvl_4.json"),
    ("NPCDrifterCommonData_Lvl_3.json", "NPCDrifterCommonData_Lvl_5.json"),
    ("NPCDrifterCommonData_Lvl_4.json", "NPCDrifterCommonData_Lvl_5.json"),
]

VARIANT_MAP = [
    ("NPCDrifterCommonData_Lvl_3_Radiation.json", "NPCDrifterCommonData_Lvl_5_Radiation.json"),
    ("NPCDrifterCommonData_Lvl_4_Radiation.json", "NPCDrifterCommonData_Lvl_5_Radiation.json"),
    ("NPCDrifterCommonData_Lvl_4_AbandonedBunker.json", "NPCDrifterCommonData_Lvl_5_AbandonedBunker.json"),
]


def load(name: str) -> list:
    return json.loads((SRC / name).read_text(encoding="utf-8"))


def main_asset(data: list) -> dict | None:
    for o in data:
        if o.get("Type") == "ArmedNPCBaseCommonData":
            return o
    return None


def stem(filename: str) -> str:
    return filename.replace(".json", "")


def remap(target_file: str, source_file: str) -> tuple[float | str, int]:
    target_stem = stem(target_file)
    source_stem = stem(source_file)
    data = deepcopy(load(source_file))

    for o in data:
        if o.get("Type") == "ArmedNPCBaseCommonData":
            o["Name"] = target_stem
            o["Package"] = o["Package"].replace(source_stem, target_stem)
        if o.get("Type") == "ExamineAssetData":
            if "ObjectPath" in o:
                o["ObjectPath"] = o["ObjectPath"].replace(source_stem, target_stem)
            outer = o.get("Outer", {})
            if "ObjectName" in outer:
                outer["ObjectName"] = outer["ObjectName"].replace(source_stem, target_stem)

    ma = main_asset(data)
    if ma:
        for entry in ma.get("Properties", {}).get("PossibleItemInHands", []):
            for ref in entry.get("PossibleItemsOnSearch", []):
                if "ObjectPath" in ref:
                    ref["ObjectPath"] = ref["ObjectPath"].replace(source_stem, target_stem)
                if "ObjectName" in ref:
                    ref["ObjectName"] = ref["ObjectName"].replace(source_stem, target_stem)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / target_file).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    hp = ma["Properties"]["MaxHealth"] if ma else "?"
    n = len(ma["Properties"].get("PossibleItemInHands", [])) if ma else 0
    return hp, n


def main() -> None:
    if not SRC.is_dir():
        raise SystemExit(f"Missing FModel exports: {SRC}")

    print(f"Writing reference JSON -> {OUT}\n")
    print("Base remap (Lvl_5 vanilla = no file):")
    for target, source in BASE_MAP:
        hp, n = remap(target, source)
        print(f"  {target} <- {source}  HP={hp}  weapon slots={n}")

    print("\nVariant remap (recommended):")
    for target, source in VARIANT_MAP:
        hp, n = remap(target, source)
        print(f"  {target} <- {source}  HP={hp}  weapon slots={n}")

    readme = OUT / "README.md"
    readme.write_text(
        """# Drifter tier remap (PhazeOut)

## Your base mapping
| Override file | Copy loadout/stats from (vanilla) |
|---------------|-------------------------------------|
| `NPCDrifterCommonData_Lvl_1` | old **Lvl_3** (M1911, M1887, DT11B, Hunter85 — 200 HP) |
| `NPCDrifterCommonData_Lvl_2` | old **Lvl_4** (Deagle, SDASS, M1911 — 220 HP) |
| `NPCDrifterCommonData_Lvl_3` | old **Lvl_5** (SMGs/rifles — 240 HP) |
| `NPCDrifterCommonData_Lvl_4` | old **Lvl_5** (same as new Lvl_3) |
| `NPCDrifterCommonData_Lvl_5` | **unchanged** (do not pack override) |

## Variants (included in reference JSON)
| Override | Copy from |
|----------|-----------|
| `Lvl_3_Radiation` | old `Lvl_5_Radiation` |
| `Lvl_4_Radiation` | old `Lvl_5_Radiation` |
| `Lvl_4_AbandonedBunker` | old `Lvl_5_AbandonedBunker` |

## Server install
1. Edit/export `.uasset` using JSON in this folder as the property guide (UAssetGUI).
2. Repak → `PhazeOut_DrifterTierRemap_P.pak`
3. Upload to `SCUM/Content/Paks/Mods/` on EU host; restart server.

## Guards
Mirror under `Armed_NPCs/Guard/NPCGuardCommonData_Lvl_*` if guards should follow the same ladder.

## Note
Encounter still picks `BP_Drifter_Lvl_1` vs `Lvl_5`; this mod changes **what each level means**, not spawn frequency.
""",
        encoding="utf-8",
    )
    print(f"\nWrote {readme}")


if __name__ == "__main__":
    main()
