"""Add balanced rare bonus loot to puppet categories via DeadPuppets node tree + SK presets.

Category themes (all probabilistic — no FixedItems):
  Civilian   — cash, food, basic medical, building mats, rare backpacks
  Hospital   — strong medical supplies
  Military   — ammo boxes, magazines, military backpacks
  Police     — 9mm/12ga ammo, magazines, police vest

Usage:
  python build_puppet_loot_rewards.py
  python build_puppet_loot_rewards.py --upload
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import paramiko

ROOT = Path(r"C:\Users\PurpleHaze\Downloads\PhazeOut Scum server")
WORK = ROOT / "Loot"
PARAMETERS = WORK / "Items" / "Default" / "Parameters.json"
DEFAULT_NODES = WORK / "Nodes" / "Default"
DEFAULT_PRESETS = WORK / "Spawners" / "Presets" / "Default"
OVERRIDE_NODES = WORK / "Nodes" / "Override"
OVERRIDE_PRESETS = WORK / "Spawners" / "Presets" / "Override"
import sys

sys.path.insert(0, str(ROOT / "tools"))
from sftp_remote import connect as sftp_connect_eu, loot_base

# Leaf nodes reference item/category names in the global loot tree.
BONUS_BY_CATEGORY: dict[str, list[dict]] = {
    "Civilian": [
        {
            "Name": "BonusRewards",
            "Rarity": "Rare",
            "Children": [
                {
                    "Name": "Cash",
                    "Rarity": "Rare",
                    "PostSpawnActions": ["SetCashAmount_SmallStash"],
                },
                {"Name": "Emergency_bandage", "Rarity": "Uncommon"},
                {"Name": "Painkillers_01", "Rarity": "Uncommon"},
                {"Name": "Nails", "Rarity": "Rare"},
                {"Name": "Metal_Scrap_01", "Rarity": "Rare"},
                {"Name": "Rope1", "Rarity": "Rare"},
                {"Name": "Duct_Tape", "Rarity": "Uncommon"},
                {"Name": "Screwdriver", "Rarity": "Rare"},
                {"Name": "1H_Hatchet", "Rarity": "Rare"},
            ],
        },
    ],
    "Hospital": [
        {
            "Name": "BonusMedical",
            "Rarity": "Rare",
            "Children": [
                {"Name": "Emergency_bandage_Big", "Rarity": "Uncommon"},
                {"Name": "Emergency_bandage", "Rarity": "Uncommon"},
                {"Name": "Tourniquet", "Rarity": "Rare"},
                {"Name": "Pressure_Dressing", "Rarity": "Rare"},
                {"Name": "Hemostatic_Dressing", "Rarity": "VeryRare"},
                {"Name": "Antibiotics_02", "Rarity": "Rare"},
                {"Name": "Antibiotics_01", "Rarity": "Uncommon"},
                {"Name": "Painkillers_01", "Rarity": "Uncommon"},
                {"Name": "Vitamins_01", "Rarity": "Uncommon"},
            ],
        },
    ],
    "MilitaryItems": [
        {
            "Name": "BonusGear",
            "Rarity": "Rare",
            "Children": [
                {"Name": "Magazine_HS9", "Rarity": "Rare"},
                {"Name": "Magazine_M9", "Rarity": "Rare"},
                {"Name": "Magazine_MP5", "Rarity": "VeryRare"},
                {"Name": "Magazine_AK47", "Rarity": "ExtremelyRare"},
                {"Name": "Cal_9mm_Ammobox", "Rarity": "Rare"},
                {"Name": "Cal_5_56x45mm_Ammobox", "Rarity": "ExtremelyRare"},
                {"Name": "Cal_7_62x39mm_Ammobox", "Rarity": "ExtremelyRare"},
            ],
        }
    ],
    "MilitaryAmmo": [
        {
            "Name": "BonusAmmoboxes",
            "Rarity": "VeryRare",
            "Children": [
                {"Name": "Cal_9mm_Ammobox", "Rarity": "Rare"},
                {"Name": "Cal_5_56x45mm_Ammobox", "Rarity": "VeryRare"},
                {"Name": "12_Gauge_Buckshot_Ammobox", "Rarity": "Rare"},
            ],
        }
    ],
    "PoliceItems": [
        {
            "Name": "BonusGear",
            "Rarity": "Rare",
            "Children": [
                {"Name": "Police_Bulletproof_Vest_01", "Rarity": "VeryRare"},
                {"Name": "Magazine_M9", "Rarity": "Rare"},
                {"Name": "Magazine_HS9", "Rarity": "Rare"},
                {"Name": "Cal_9mm_Ammobox", "Rarity": "Rare"},
                {"Name": "Cal_38_Ammobox", "Rarity": "Rare"},
                {"Name": "Cash", "Rarity": "Rare", "PostSpawnActions": ["SetCashAmount_SmallStash"]},
            ],
        }
    ],
    "PoliceAmmo": [
        {
            "Name": "BonusAmmo",
            "Rarity": "Rare",
            "Children": [
                {
                    "Name": "SmallStash",
                    "Rarity": "Common",
                    "PostSpawnActions": ["SetAmmoAmount_SmallStash"],
                    "Children": [
                        {"Name": "Cal_9mm", "Rarity": "Uncommon"},
                        {"Name": "Cal_38", "Rarity": "Uncommon"},
                        {"Name": "12_Gauge_Buckshot", "Rarity": "Rare"},
                    ],
                }
            ],
        }
    ],
}

# Food lives on a separate loot branch and is rolled through the pristine food-pack preset.
FOOD_BY_CATEGORY: dict[str, list[dict]] = {
    "Civilian": [
        {"Name": "Canned_Tuna", "Rarity": "Uncommon"},
        {"Name": "CannedSardine", "Rarity": "Uncommon"},
        {"Name": "Crackers", "Rarity": "Uncommon"},
        {"Name": "BakedBeans", "Rarity": "Uncommon"},
        {"Name": "CannedPeas", "Rarity": "Uncommon"},
        {"Name": "CannedSpaghetti", "Rarity": "Uncommon"},
        {"Name": "BabyFood", "Rarity": "Uncommon"},
        {"Name": "ChocolateCandy_01", "Rarity": "Rare"},
        {"Name": "BeefRavioli", "Rarity": "Rare"},
        {"Name": "BeefStew", "Rarity": "Rare"},
        {"Name": "CannedGoulash", "Rarity": "Rare"},
        {"Name": "MeatSnack_01", "Rarity": "Rare"},
        {"Name": "Raisins", "Rarity": "Rare"},
    ],
    "Hospital": [
        {"Name": "Canned_Tuna", "Rarity": "Uncommon"},
        {"Name": "CannedPeas", "Rarity": "Uncommon"},
        {"Name": "BabyFood", "Rarity": "Uncommon"},
        {"Name": "Crackers", "Rarity": "Uncommon"},
        {"Name": "ChocolateCandy_01", "Rarity": "Rare"},
    ],
    "Military": [
        {"Name": "MRE_Cheeseburger", "Rarity": "Uncommon"},
        {"Name": "MRE_Stew", "Rarity": "Uncommon"},
        {"Name": "MRE_TunaSalad", "Rarity": "Uncommon"},
        {"Name": "Canned_Tuna", "Rarity": "Uncommon"},
        {"Name": "BeefStew", "Rarity": "Rare"},
        {"Name": "CannedGoulash", "Rarity": "Rare"},
    ],
    "Police": [
        {"Name": "Canned_Tuna", "Rarity": "Uncommon"},
        {"Name": "CannedSardine", "Rarity": "Uncommon"},
        {"Name": "Crackers", "Rarity": "Uncommon"},
        {"Name": "ChocolateCandy_01", "Rarity": "Rare"},
        {"Name": "BeefRavioli", "Rarity": "Rare"},
    ],
}

# Rare worn-gear bonus appended to SK (clothing) presets — _04 assault/vest via probabilistic subpresets.
SK_BONUS_ITEMS: dict[str, list[dict]] = {
    # Muscle / armored bonuses via subpresets (18–30% durability on bonus item only).
    "Character-Puppets-Military-Examine_SK_Military_Zombie_04.json": [],
    "Character-Puppets-Military-Examine_SK_Military_Zombie_06.json": [],
    "Character-Puppets-Police-Examine_SK_Police_Zombie_01.json": [
        {"Rarity": "VeryRare", "Id": "Police_Bulletproof_Vest_01"},
        {"Rarity": "Rare", "Id": "Police_Gloves_01"},
    ],
    "Character-Puppets-Police-Examine_SK_Police_Zombie_02.json": [
        {"Rarity": "VeryRare", "Id": "Police_Bulletproof_Vest_01"},
        {"Rarity": "Rare", "Id": "Police_Jacket_01"},
    ],
    "Character-Puppets-Police-Examine_SK_Police_Zombie_03.json": [
        {"Rarity": "VeryRare", "Id": "Police_Bulletproof_Vest_01"},
        {"Rarity": "Rare", "Id": "Police_Shirt_01"},
    ],
    "Character-Puppets-Police-Examine_SK_Police_Zombie_04.json": [
        {"Rarity": "VeryRare", "Id": "Police_Bulletproof_Vest_01"},
        {"Rarity": "Rare", "Id": "Police_Beanie_01"},
    ],
}

# SK overrides removed from SK_BONUS_ITEMS are deleted so Default presets apply again.
SK_OVERRIDE_PRUNE = [
    "Character-Puppets-Military-Examine_SK_Military_Zombie_01.json",
    "Character-Puppets-Military-Examine_SK_Military_Zombie_04.json",
    "Character-Puppets-Military-Examine_SK_Military_Zombie_05.json",
    "Character-Puppets-Military-Examine_SK_Military_Zombie_06.json",
    "Character-Puppets-Police-Examine_SK_Police_Zombie_01.json",
    "Character-Puppets-Police-Examine_SK_Police_Zombie_02.json",
    "Character-Puppets-Police-Examine_SK_Police_Zombie_03.json",
    "Character-Puppets-Police-Examine_SK_Police_Zombie_04.json",
    "Character-Puppets-Civilian-Examine_SK_Dressed_Mid_01_V2.json",
    "Character-Puppets-Civilian-Female-Examine_SK_Dressed_Skinny_01_V1_Female.json",
]

# Spawn: #SpawnZombie BP_Zombie_Military_Muscle / BP_Zombie_Military_Armored
SK_MILITARY_ZOMBIE_04 = "Character-Puppets-Military-Examine_SK_Military_Zombie_04.json"
SK04_ASSAULT_BACKPACK_ITEM = "Military_Backpack_01_03"
SK04_BONUS_SUBPRESET = (
    "Character-Puppets-Military-Examine_SK_Military_Zombie_04-Bonus_Backpack.json"
)
SK04_BONUS_SUBPRESET_ID = SK04_BONUS_SUBPRESET.removesuffix(".json")
# 5% base × 4× ExamineSpawnerProbabilityMultiplier ≈ 20% on muscle SK clothing examine.
SK04_BACKPACK_BASE_PROBABILITY = 5
BP_ZOMBIE_MILITARY_ARMORED = "BP_Zombie_Military_Armored"
SK_MILITARY_ZOMBIE_ARMORED = "Character-Puppets-Military-Examine_SK_Military_Zombie_06.json"
SK_ARMORED_TACTICAL_VEST_ITEM = "Armor_Tactical_Vest_01_01"
SK06_BONUS_SUBPRESET = (
    "Character-Puppets-Military-Examine_SK_Military_Zombie_06-Bonus_Tactical_Vest.json"
)
SK06_BONUS_SUBPRESET_ID = SK06_BONUS_SUBPRESET.removesuffix(".json")
MILITARY_BONUS_SUBPRESET_RARITY = "Uncommon"
MILITARY_BONUS_ITEM_RARITY = "VeryRare"
# Durability 18–30% → damage 70–82 on InitialDamage + RandomDamage.
MILITARY_BONUS_CONDITION_MIN_PCT = 18
MILITARY_BONUS_CONDITION_MAX_PCT = 30
MILITARY_BONUS_INITIAL_DAMAGE = 100 - MILITARY_BONUS_CONDITION_MAX_PCT
MILITARY_BONUS_RANDOM_DAMAGE = (
    MILITARY_BONUS_CONDITION_MAX_PCT - MILITARY_BONUS_CONDITION_MIN_PCT
)
MILITARY_BONUS_SUBPRESET_FILES = (SK04_BONUS_SUBPRESET, SK06_BONUS_SUBPRESET)
# Broken subpresets / wrong targets — delete from Override on build + upload.
MILITARY_OBSOLETE_SUBPRESET_FILES = (
    "Character-Puppets-Military-Examine_SK_Military_Zombie_04_Tactical_Vest.json",
    "Character-Puppets-Military-Examine_SK_Military_Zombie_04_Assault_Backpack.json",
    "Character-Puppets-Military-Examine_SK_Military_Zombie_05_Tactical_Vest.json",
    "Character-Puppets-Military-Examine_SK_Military_Zombie_06_Tactical_Vest.json",
)

FOOD_PACK_PRESET = "Character-Puppets-Loot-Examine_Loot_Puppet_Food_Pack.json"
FOOD_PACK_PRESET_ID = FOOD_PACK_PRESET.removesuffix(".json")
# Middle ground: pristine food, but not on every pocket examine.
FOOD_BRANCH_RARITY = "Uncommon"
FOOD_SUBPRESET_RARITY = "Uncommon"
FOOD_PACK_PROBABILITY = 1
FOOD_PACK_QUANTITY_MIN = 1
FOOD_PACK_QUANTITY_MAX = 1
LOOT_PUPPET_FOOD_PACK_RARITY = "Common"

# Pocket presets that keep vanilla worn damage but add a separate pristine food roll.
EQUIPMENT_WITH_FOOD_SUBPRESET = [
    "Character-Puppets-Civilian-Examine_Zombie_Civilian_Equipment.json",
    "Character-Puppets-Hospital-Examine_Zombie_Hospital_Equipment.json",
    "Character-Puppets-Military-Examine_Zombie_Military.json",
    "Character-Puppets-Police-Examine_Zombie_Police.json",
]

# Presets that should not keep stale survival-4x equipment overrides (food via subpreset).
EQUIPMENT_REVERT_TO_DEFAULT: list[str] = []


def load_valid_ids() -> set[str]:
    data = json.loads(PARAMETERS.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for entry in data["Parameters"]:
        ids.add(entry["Id"])
        ids.update(entry.get("Variations") or [])
    return ids


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")


def find_node(node: dict, path: list[str]) -> dict | None:
    if not path:
        return node
    head, *tail = path
    for child in node.get("Children") or []:
        if child.get("Name") == head:
            return find_node(child, tail)
    return None


def merge_food_branch(tree: dict, category_path: list[str], items: list[dict]) -> str:
    parent = find_node(tree, category_path)
    if parent is None:
        raise SystemExit(f"DeadPuppets path not found: {category_path}")
    children = parent.setdefault("Children", [])
    food_node = {
        "Name": "Food",
        "Rarity": FOOD_BRANCH_RARITY,
        "Children": copy.deepcopy(items),
    }
    for idx, child in enumerate(children):
        if child.get("Name") == "Food":
            children[idx] = food_node
            return "updated"
    children.append(food_node)
    return "added"


def merge_bonus_branches(tree: dict, parent_path: list[str], branches: list[dict]) -> dict[str, int]:
    parent = find_node(tree, parent_path)
    if parent is None:
        raise SystemExit(f"DeadPuppets path not found: {parent_path}")
    children = parent.setdefault("Children", [])
    by_name = {c.get("Name"): i for i, c in enumerate(children)}
    added = 0
    updated = 0
    for branch in branches:
        name = branch["Name"]
        payload = copy.deepcopy(branch)
        if name in by_name:
            children[by_name[name]] = payload
            updated += 1
        else:
            children.append(payload)
            by_name[name] = len(children) - 1
            added += 1
    return {"added": added, "updated": updated}


def validate_branch_items(branches: list[dict], valid: set[str]) -> None:
    def walk(node: dict) -> None:
        name = node.get("Name")
        if name and "Children" not in node and name not in {
            "BonusRewards",
            "BonusFood",
            "BonusMedical",
            "BonusGear",
            "BonusAmmoboxes",
            "BonusAmmo",
            "SmallStash",
            "Cash",
            "Money",
            "Fabric",
            "FirstAid",
            "Lockpicks",
            "12Gauge",
            "AP",
            "Regular",
            "Tracers",
        }:
            # Leaf names should be spawnable item ids or known ammo categories.
            if name not in valid and not name.startswith("Cal_") and not name.startswith("12_Gauge"):
                raise SystemExit(f"Unknown loot node/item name: {name}")
        for child in node.get("Children") or []:
            walk(child)

    for branch in branches:
        walk(branch)


def build_dead_puppets_override(valid: set[str]) -> dict:
    src = DEFAULT_NODES / "DeadPuppets.json"
    tree = json.loads(src.read_text(encoding="utf-8"))
    stats: dict[str, int] = {}

    mapping = [
        ("Civilian", ["DeadPuppets", "Civilian", "Items"], BONUS_BY_CATEGORY["Civilian"]),
        ("Hospital", ["DeadPuppets", "Hospital", "Items"], BONUS_BY_CATEGORY["Hospital"]),
        ("MilitaryItems", ["DeadPuppets", "Military", "Items"], BONUS_BY_CATEGORY["MilitaryItems"]),
        ("MilitaryAmmo", ["DeadPuppets", "Military", "ammo"], BONUS_BY_CATEGORY["MilitaryAmmo"]),
        ("PoliceItems", ["DeadPuppets", "Police", "Items"], BONUS_BY_CATEGORY["PoliceItems"]),
        ("PoliceAmmo", ["DeadPuppets", "Police", "ammo"], BONUS_BY_CATEGORY["PoliceAmmo"]),
    ]
    for key, path, branches in mapping:
        validate_branch_items(branches, valid)
        stats[key] = merge_bonus_branches(tree, path, branches)

    food_stats: dict[str, str] = {}
    for category, items in FOOD_BY_CATEGORY.items():
        validate_branch_items(items, valid)
        food_stats[category] = merge_food_branch(tree, ["DeadPuppets", category], items)

    out = OVERRIDE_NODES / "DeadPuppets.json"
    write_json(out, tree)
    return {
        "file": str(out.relative_to(ROOT)),
        "branches_added": stats,
        "food_branches": food_stats,
    }


def merge_sk_preset(filename: str, bonus: list[dict], valid: set[str]) -> dict:
    for item in bonus:
        if item["Id"] not in valid:
            raise SystemExit(f"Unknown SK item: {item['Id']}")
    override_path = OVERRIDE_PRESETS / filename
    default_path = DEFAULT_PRESETS / filename
    if override_path.exists():
        preset = json.loads(override_path.read_text(encoding="utf-8"))
    elif default_path.exists():
        preset = json.loads(default_path.read_text(encoding="utf-8"))
    else:
        raise SystemExit(f"Missing preset: {filename}")

    items = preset.setdefault("Items", [])
    existing_ids = {entry.get("Id") for entry in items}
    for entry in bonus:
        if entry["Id"] not in existing_ids:
            items.append(dict(entry))
    return preset


def load_default_preset(filename: str) -> dict:
    default_path = DEFAULT_PRESETS / filename
    if not default_path.exists():
        raise SystemExit(f"Missing preset: {filename}")
    return json.loads(default_path.read_text(encoding="utf-8"))


def upsert_food_subpreset(preset: dict) -> None:
    subpresets = list(preset.get("Subpresets") or [])
    for entry in subpresets:
        if entry.get("Id") == FOOD_PACK_PRESET_ID:
            entry["Rarity"] = FOOD_SUBPRESET_RARITY
            preset["Subpresets"] = subpresets
            return
    subpresets.append({"Rarity": FOOD_SUBPRESET_RARITY, "Id": FOOD_PACK_PRESET_ID})
    preset["Subpresets"] = subpresets


def build_equipment_food_subpreset_overrides() -> list[str]:
    written = []
    for filename in EQUIPMENT_WITH_FOOD_SUBPRESET:
        preset = load_default_preset(filename)
        upsert_food_subpreset(preset)
        write_json(OVERRIDE_PRESETS / filename, preset)
        written.append(filename)
    return written


def revert_equipment_overrides() -> list[str]:
    removed = []
    for filename in EQUIPMENT_REVERT_TO_DEFAULT:
        override_path = OVERRIDE_PRESETS / filename
        if override_path.exists():
            override_path.unlink()
            removed.append(filename)
    return removed


def build_food_pack_override() -> str:
    preset = {
        "Nodes": [
            {
                "Rarity": FOOD_BRANCH_RARITY,
                "Ids": [
                    "ItemLootTreeNodes.DeadPuppets.Civilian.Food",
                    "ItemLootTreeNodes.DeadPuppets.Hospital.Food",
                    "ItemLootTreeNodes.DeadPuppets.Military.Food",
                    "ItemLootTreeNodes.DeadPuppets.Police.Food",
                ],
            }
        ],
        "Probability": FOOD_PACK_PROBABILITY,
        "QuantityMin": FOOD_PACK_QUANTITY_MIN,
        "QuantityMax": FOOD_PACK_QUANTITY_MAX,
        "AllowDuplicates": False,
        "ShouldFilterItemsByZone": False,
        "ShouldApplyLocationSpecificProbabilityModifier": False,
        "ShouldApplyLocationSpecificDamageModifier": False,
        "InitialDamage": 0,
        "RandomDamage": 0,
        "InitialUsage": 0,
        "RandomUsage": 0,
        "InitialStack": 0,
        "RandomStack": 0,
    }
    write_json(OVERRIDE_PRESETS / FOOD_PACK_PRESET, preset)
    return FOOD_PACK_PRESET


def build_loot_puppet_food_override() -> str | None:
    filename = "Character-Puppets-Loot-Examine_Loot_Puppet.json"
    override_path = OVERRIDE_PRESETS / filename
    default_path = DEFAULT_PRESETS / filename
    if override_path.exists():
        preset = json.loads(override_path.read_text(encoding="utf-8"))
    elif default_path.exists():
        preset = json.loads(default_path.read_text(encoding="utf-8"))
    else:
        return None
    food_id = FOOD_PACK_PRESET_ID
    changed = False
    for sub in preset.get("Subpresets") or []:
        if sub.get("Id") == food_id and sub.get("Rarity") != LOOT_PUPPET_FOOD_PACK_RARITY:
            sub["Rarity"] = LOOT_PUPPET_FOOD_PACK_RARITY
            changed = True
    if not changed:
        return None
    write_json(override_path, preset)
    return filename


def prune_obsolete_sk_subpreset_files() -> list[str]:
    removed = []
    for filename in MILITARY_OBSOLETE_SUBPRESET_FILES:
        path = OVERRIDE_PRESETS / filename
        if path.exists():
            path.unlink()
            removed.append(filename)
    return removed


def build_military_worn_bonus_subpreset(
    valid: set[str],
    item_id: str,
    preset_filename: str,
    *,
    base_probability: float | None = None,
) -> str:
    """Bonus roll with fixed 18–30% durability (separate from parent SK clothing wear)."""
    if item_id not in valid:
        raise SystemExit(f"Unknown military bonus item: {item_id}")
    preset: dict = {
        "Items": [{"Rarity": MILITARY_BONUS_ITEM_RARITY, "Id": item_id}],
        "QuantityMin": 1,
        "QuantityMax": 1,
        "AllowDuplicates": False,
        "ShouldFilterItemsByZone": False,
        "ShouldApplyLocationSpecificProbabilityModifier": False,
        "ShouldApplyLocationSpecificDamageModifier": False,
        "InitialDamage": MILITARY_BONUS_INITIAL_DAMAGE,
        "RandomDamage": MILITARY_BONUS_RANDOM_DAMAGE,
        "InitialUsage": MILITARY_BONUS_INITIAL_DAMAGE,
        "RandomUsage": MILITARY_BONUS_RANDOM_DAMAGE,
        "InitialStack": 0,
        "RandomStack": 0,
        "PostSpawnActions": ["SetClothesDirtiness_DeadPuppets"],
    }
    if base_probability is not None:
        preset["Probability"] = float(base_probability)
    write_json(OVERRIDE_PRESETS / preset_filename, preset)
    return preset_filename


def upsert_subpreset(preset: dict, preset_id: str, rarity: str) -> None:
    subpresets = list(preset.get("Subpresets") or [])
    for entry in subpresets:
        if entry.get("Id") == preset_id:
            entry["Rarity"] = rarity
            preset["Subpresets"] = subpresets
            return
    subpresets.append({"Rarity": rarity, "Id": preset_id})
    preset["Subpresets"] = subpresets


def prune_sk_overrides() -> list[str]:
    keep = set(SK_BONUS_ITEMS.keys())
    removed = []
    for filename in SK_OVERRIDE_PRUNE:
        if filename in keep:
            continue
        path = OVERRIDE_PRESETS / filename
        if path.exists():
            path.unlink()
            removed.append(filename)
    return removed


def build_sk_overrides(valid: set[str]) -> list[str]:
    prune_sk_overrides()
    written = []
    for filename, bonus in SK_BONUS_ITEMS.items():
        preset = json.loads((DEFAULT_PRESETS / filename).read_text(encoding="utf-8"))
        items = preset.setdefault("Items", [])
        if filename == SK_MILITARY_ZOMBIE_04:
            # Drop vanilla uncommon bag so bonus VeryRare roll is separate.
            items[:] = [
                entry
                for entry in items
                if entry.get("Id") != "Military_Backpack_03_03"
            ]
        if filename == SK_MILITARY_ZOMBIE_04:
            preset.pop("Subpresets", None)
            upsert_subpreset(
                preset, SK04_BONUS_SUBPRESET_ID, MILITARY_BONUS_SUBPRESET_RARITY
            )
        elif filename == SK_MILITARY_ZOMBIE_ARMORED:
            preset.pop("Subpresets", None)
            upsert_subpreset(
                preset, SK06_BONUS_SUBPRESET_ID, MILITARY_BONUS_SUBPRESET_RARITY
            )
        else:
            existing_ids = {entry.get("Id") for entry in items}
            for entry in bonus:
                if entry["Id"] not in valid:
                    raise SystemExit(f"Unknown SK item: {entry['Id']}")
                if entry["Id"] not in existing_ids:
                    items.append(dict(entry))
            preset.pop("Subpresets", None)
        out = OVERRIDE_PRESETS / filename
        write_json(out, preset)
        written.append(filename)
    return written


def build_all() -> dict:
    valid = load_valid_ids()
    node_result = build_dead_puppets_override(valid)
    equipment_files = build_equipment_food_subpreset_overrides()
    reverted_equipment = revert_equipment_overrides()
    food_pack = build_food_pack_override()
    loot_puppet_food = build_loot_puppet_food_override()
    obsolete = prune_obsolete_sk_subpreset_files()
    sk04_bonus = build_military_worn_bonus_subpreset(
        valid,
        SK04_ASSAULT_BACKPACK_ITEM,
        SK04_BONUS_SUBPRESET,
        base_probability=SK04_BACKPACK_BASE_PROBABILITY,
    )
    sk06_bonus = build_military_worn_bonus_subpreset(
        valid, SK_ARMORED_TACTICAL_VEST_ITEM, SK06_BONUS_SUBPRESET
    )
    sk_files = build_sk_overrides(valid)
    summary = {
        "dead_puppets": node_result,
        "equipment_food_subpresets": equipment_files,
        "equipment_reverted_to_default": reverted_equipment,
        "food_pack_preset": food_pack,
        "loot_puppet_food_pack": loot_puppet_food,
        "sk_presets_patched": sk_files,
        "military_obsolete_subpresets_removed": obsolete,
        "sk_military_bonus": {
            "SK04_backpack_subpreset": sk04_bonus,
            "SK06_vest_subpreset": sk06_bonus,
            "bp_armored_spawn": BP_ZOMBIE_MILITARY_ARMORED,
            "durability_pct": f"{MILITARY_BONUS_CONDITION_MIN_PCT}-{MILITARY_BONUS_CONDITION_MAX_PCT}",
            "SK04_backpack_base_probability": SK04_BACKPACK_BASE_PROBABILITY,
            "SK04_backpack_effective_at_4x_pct": SK04_BACKPACK_BASE_PROBABILITY * 4,
        },
        "categories": {
            "civilian": "worn pocket loot + separate pristine food roll, bandages, building mats",
            "hospital": "worn medical pocket loot + separate pristine food roll",
            "military": (
                "magazines, ammoboxes + ~1% food; SK04 backpack 5% base (~20% at 4×); "
                "SK06 vest subpreset 18–30% durability"
            ),
            "police": "9mm/38 ammo, magazines, police vest, cash + ~1% pristine food",
        },
        "balance_note": (
            f"Pristine food ~{FOOD_PACK_PROBABILITY}% per pocket examine, "
            f"{FOOD_PACK_QUANTITY_MAX} item max; other pocket loot keeps vanilla wear"
        ),
    }
    write_json(WORK / "puppet_loot_rewards_summary.json", summary)
    return summary


def upload() -> dict:
    transport, sftp, cfg = sftp_connect_eu()
    uploaded = []
    try:
        remote_loot = loot_base(cfg, sftp)
        remote_node = f"{remote_loot}/Nodes/Override/DeadPuppets.json"
        local_node = OVERRIDE_NODES / "DeadPuppets.json"
        sftp.put(str(local_node), remote_node)
        uploaded.append("Nodes/Override/DeadPuppets.json")

        upload_presets = (
            list(MILITARY_BONUS_SUBPRESET_FILES)
            + list(SK_BONUS_ITEMS.keys())
            + list(EQUIPMENT_WITH_FOOD_SUBPRESET)
            + [FOOD_PACK_PRESET]
        )
        loot_puppet = OVERRIDE_PRESETS / "Character-Puppets-Loot-Examine_Loot_Puppet.json"
        if loot_puppet.exists():
            upload_presets.append("Character-Puppets-Loot-Examine_Loot_Puppet.json")
        for filename in upload_presets:
            local_p = OVERRIDE_PRESETS / filename
            remote_p = f"{remote_loot}/Spawners/Presets/Override/{filename}"
            sftp.put(str(local_p), remote_p)
            uploaded.append(f"Spawners/Presets/Override/{filename}")

        for filename in EQUIPMENT_REVERT_TO_DEFAULT:
            remote_p = f"{remote_loot}/Spawners/Presets/Override/{filename}"
            try:
                sftp.remove(remote_p)
                uploaded.append(f"removed Spawners/Presets/Override/{filename}")
            except OSError:
                pass

        for filename in MILITARY_OBSOLETE_SUBPRESET_FILES:
            remote_p = f"{remote_loot}/Spawners/Presets/Override/{filename}"
            try:
                sftp.remove(remote_p)
                uploaded.append(f"removed Spawners/Presets/Override/{filename}")
            except OSError:
                pass

        keep_sk = set(SK_BONUS_ITEMS.keys())
        for filename in SK_OVERRIDE_PRUNE:
            if filename in keep_sk:
                continue
            remote_p = f"{remote_loot}/Spawners/Presets/Override/{filename}"
            try:
                sftp.remove(remote_p)
                uploaded.append(f"removed Spawners/Presets/Override/{filename}")
            except OSError:
                pass
    finally:
        sftp.close()
        transport.close()
    return {"uploaded": uploaded, "count": len(uploaded)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()

    summary = build_all()
    print(json.dumps(summary, indent=2))

    if args.upload:
        up = upload()
        print("\nUpload:", json.dumps(up, indent=2))
        print(
            "\nApply with server restart OR in-game admin:\n"
            "  #ReloadLootCustomizationsAndResetSpawners\n"
            "(New puppet spawns only.)"
        )


if __name__ == "__main__":
    main()
