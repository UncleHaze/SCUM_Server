"""Build survival-focused 4x loot overrides for PhazeOut SCUM server.

Global 4x via ServerSettings.ini (SpawnerProbabilityMultiplier); expiration 1.0x.
Each +1 rarity step ≈ half spawn rate vs same global multiplier.

Grok 4-tier effective targets (approximate):
  T1 Common   — food, tools, building, pistols, basic meds: ~4x (+0 shift)
  T2 Uncommon — shotguns, SMGs, mid rifles, medium armor, vehicle parts: ~2–3x (+1)
  T3 Rare     — full-auto, military armor, large bags, optics/suppressors: ~1.5–2x (+2)
  T4 Very rare — snipers, C4/mines/RPG, keycards: ~1x (+2 force ExtremelyRare on cores)

Phase 2 POI: Police/Military node subtrees (ammo/Weapons/Gear) get −1 rarity step;
bunker/high-tier examine presets get a small probability bump (no explosive/keycard boost).

Outputs Override JSON under Loot/ and uploads via SFTP.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "Loot"
import sys

sys.path.insert(0, str(ROOT / "tools"))
from sftp_remote import connect as sftp_connect_eu, loot_base, windows_server_base

PARAMETERS = WORK / "Items" / "Default" / "Parameters.json"
DEFAULT_PRESETS = WORK / "Spawners" / "Presets" / "Default"
DEFAULT_NODES = WORK / "Nodes" / "Default"
OVERRIDE_PRESETS = WORK / "Spawners" / "Presets" / "Override"
OVERRIDE_NODES = WORK / "Nodes" / "Override"

GLOBAL_MULT = 4.0
RARITY_ORDER = ["Abundant", "Common", "Uncommon", "Rare", "VeryRare", "ExtremelyRare"]

# --- Explosives (from apply_explosive_nerfs.py) ---
EXPLOSIVE_CORE = {
    "C4", "C4_Pack", "TNT", "PipeBomb", "PressureCookerBomb", "Blast_Cap",
    "Cal_40x46", "40mm_G", "Cal_40_PG-7M", "Cal_40_OG-7V", "C4_Detonator",
    "C4_CircuitBoard", "C4_KeyPad", "C4_Keypad", "Laser_Detonator", "Sensor_Detonator",
}
EXPLOSIVE_ALIASES = {"C4_KeyPad": "C4_Keypad"}

EXPLOSIVE_ID_RE = re.compile(
    r"(^|_)(C4_|TNT|Mine_0|Claymore|Frag_Grenade|Smoke_Grenade|TearGas|"
    r"PipeBomb|PressureCooker|Detonator|Cal_40|40mm|PG-7|OG-7|RPG|AT4|IED|"
    r"Plastic_Explosive|Blast_Cap|Semtex|Promethe|Gunpowder|GunPowder)",
    re.I,
)

GRENADE_IDS = {
    "Frag_Grenade", "Smoke_Grenade", "TearGasGrenade", "EMP_Grenade",
    "Claymore", "Mine_01", "Mine_02", "ImprovisedClaymore",
}

KEYCARD_RE = re.compile(r"^KeyCard", re.I)

FULL_AUTO_RIFLE_GROUPS = {
    "Weapons.AssaultRifles.Tier.High",
    "Weapons.AssaultRifles.Tier.Mid",
    "Weapons.AssaultRifles.Tier.Low",
    "Weapons.LMGs",
}

HIGH_WEAPON_GROUPS = {
    "Weapons.DMRSnipers.Tier.High",
    "Weapons.Handguns.Tier.High",
    "Weapons.RPGs.Tier.High",
    "Weapons.RPGs.Tier.Mid",
    "Weapons.Explosives.Tier.High",
    "Weapons.Explosives.Tier.VeryHigh",
    "Weapons.Rifles.Tier.High",
    "Weapons.Shotguns.Tier.High",
}

MID_WEAPON_GROUPS = {
    "Weapons.DMRSnipers.Tier.Mid",
    "Weapons.Handguns.Tier.Mid",
    "Weapons.RPGs.Tier.Low",
    "Weapons.Rifles.Tier.Mid",
    "Weapons.Shotguns.Tier.Mid",
    "Weapons.SMGs.Tier.Mid",
    "Weapons.SMGs.Tier.High",
    "Weapons.Explosives.Tier.Mid",
}

LOW_WEAPON_GROUPS = {
    "Weapons.DMRSnipers.Tier.Low",
    "Weapons.Handguns.Tier.Low",
    "Weapons.Rifles.Tier.Low",
    "Weapons.Shotguns.Tier.Low",
    "Weapons.SMGs.Tier.Low",
    "Weapons.Explosives.Tier.Low",
}

HIGH_WEAPON_IDS = {
    "Weapon_M82A1", "Weapon_SVD_Dragunov", "Weapon_AK15", "Weapon_MK18",
    "Weapon_M249", "Weapon_AWM", "Weapon_M16A4", "Weapon_SCAR_DMR",
    "Weapon_VSS_VZ", "Weapon_AS_VAL", "Weapon_RPG7", "Weapon_AT4",
}

BACKPACK_LARGE_RE = re.compile(
    r"(^Military_Backpack|^Hiking_Backpack_0[23]|^Police_Backpack)",
    re.I,
)

ARMOR_TACTICAL_RE = re.compile(
    r"(^Armor_Tactical|^Bulletproof_Vest|^Tactical_Vest|^Police_Bulletproof)",
    re.I,
)

ARMOR_MILITARY_RE = re.compile(
    r"(^Combat_Helmet|^Military_Vest|^Plate_Carrier|^Ballistic|^K6-3_Helmet|"
    r"^M1_.*Helmet|^Military_Quiver|^NVG|^Night_Vision|^Ghillie|^Military_Boots|"
    r"^Military_Pants|^Military_Shirt|^Military_Jacket|^Military_Gloves|"
    r"^Military_Cap|^Military_Beret|^Military_Helmet)",
    re.I,
)

ATTACHMENT_GEAR_RE = re.compile(
    r"(^WeaponScope_|^WeaponSuppressor_|^WeaponSights_|^WeaponFlashlight_|"
    r"^WeaponRail_|^ImprovisedRail_)",
    re.I,
)

VEHICLE_PARTS_RE = re.compile(
    r"(^Laika_|^Rager_|^Tractor_|^WW_|^Cruiser_|^Dirtbike_|^Kinglet_|^Barba_|"
    r"^Wheel_|^Car_Battery|^Engine_Block|^Alternator|^Spark_Plugs)",
    re.I,
)

POI_NODE_FILES = {"Police.json", "Military.json"}
POI_SUBTREE_NAMES = {"ammo", "Weapons", "Gear"}
POI_RARITY_BOOST_STEPS = -1
BUNKER_PRESET_PROB_BUMP = 1.12

HIGH_TIER_PRESET_RE = re.compile(
    r"(Killbox|Vault|Cargo_Drop|Secret_Bunker|TV_Bunker|Sentry|Research_Facility)",
    re.I,
)

WEAPON_PACK_PRESET_RE = re.compile(
    r"(M249|M82|AWM|SVD|AK15|MK18|ArmoredMilitary|Military_KillBox|RPG|AT4|"
    r"GrenadeLauncher|Explosives|KeyCard|Keycard|C4)",
    re.I,
)


def sftp_connect() -> tuple[paramiko.Transport, paramiko.SFTPClient, dict]:
    return sftp_connect_eu()


def ensure_remote_dir(sftp: paramiko.SFTPClient, path: str) -> None:
    parts = [p for p in path.split("/") if p]
    cur = ""
    for part in parts:
        cur += "/" + part
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def sftp_download_dir(sftp: paramiko.SFTPClient, remote_dir: str, local_dir: Path) -> int:
    local_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    try:
        names = sftp.listdir(remote_dir)
    except OSError as exc:
        raise FileNotFoundError(f"Remote folder missing: {remote_dir} ({exc})") from exc
    for name in names:
        remote_path = f"{remote_dir.rstrip('/')}/{name}"
        local_path = local_dir / name
        try:
            st = sftp.stat(remote_path)
        except OSError:
            continue
        if st.st_mode & 0o40000:
            count += sftp_download_dir(sftp, remote_path, local_path)
        elif name.endswith(".json"):
            sftp.get(remote_path, str(local_path))
            count += 1
    return count


def sftp_upload_dir(sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str) -> int:
    if not local_dir.exists():
        return 0
    count = 0
    for root, _, files in os.walk(local_dir):
        for name in files:
            if not name.endswith(".json"):
                continue
            local_file = Path(root) / name
            rel = local_file.relative_to(local_dir).as_posix()
            remote_file = f"{remote_dir.rstrip('/')}/{rel}"
            ensure_remote_dir(sftp, os.path.dirname(remote_file))
            sftp.put(str(local_file), remote_file)
            count += 1
    return count


def shift_rarity(rarity: str, steps: int) -> str:
    if rarity not in RARITY_ORDER:
        return rarity
    idx = RARITY_ORDER.index(rarity)
    return RARITY_ORDER[max(0, min(len(RARITY_ORDER) - 1, idx + steps))]


def load_item_groups() -> dict[str, str]:
    data = json.loads(PARAMETERS.read_text(encoding="utf-8"))
    groups: dict[str, str] = {}
    for entry in data.get("Parameters", []):
        iid = entry.get("Id", "")
        cg = entry.get("CooldownGroup", "") or ""
        if cg.startswith("Vehicles."):
            groups[iid] = "vehicle_parts"
        elif cg in FULL_AUTO_RIFLE_GROUPS:
            groups[iid] = "weapon_full_auto"
        elif cg in HIGH_WEAPON_GROUPS:
            groups[iid] = "weapon_high"
        elif cg in MID_WEAPON_GROUPS:
            groups[iid] = "weapon_mid"
        elif cg in LOW_WEAPON_GROUPS:
            groups[iid] = "weapon_low"
        for var in entry.get("Variations") or []:
            if iid in groups:
                groups[var] = groups[iid]
    return groups


def normalize_explosive(iid: str) -> str:
    return EXPLOSIVE_ALIASES.get(iid, iid)


def classify_item(item_id: str, item_groups: dict[str, str]) -> str | None:
    if not item_id:
        return None
    iid = normalize_explosive(item_id)

    if iid in EXPLOSIVE_CORE:
        return "explosive_core"
    if iid in GRENADE_IDS or EXPLOSIVE_ID_RE.search(iid):
        return "explosive_grenade"
    # Research Facility keycard (Apex facility) — separate from killbox KeyCard.
    if iid == "KeyCardApex":
        return "keycard_apex"
    if KEYCARD_RE.match(iid):
        return "keycard"
    if item_groups.get(iid) == "weapon_full_auto":
        return "weapon_full_auto"
    if iid in HIGH_WEAPON_IDS or item_groups.get(iid) == "weapon_high":
        return "weapon_high"
    if item_groups.get(iid) == "weapon_mid":
        return "weapon_mid"
    if item_groups.get(iid) == "weapon_low":
        return "weapon_low"
    if item_groups.get(iid) == "vehicle_parts":
        return "vehicle_parts"
    if BACKPACK_LARGE_RE.search(iid):
        return "backpack_large"
    if ARMOR_MILITARY_RE.search(iid):
        return "armor_military"
    if ARMOR_TACTICAL_RE.search(iid):
        return "armor_tactical"
    if ATTACHMENT_GEAR_RE.search(iid):
        return "attachment_gear"
    if VEHICLE_PARTS_RE.search(iid):
        return "vehicle_parts"
    return None


# Rarity step added after global 4x (negative = more common).
RARITY_SHIFT = {
    "explosive_core": +2,
    "explosive_grenade": +1,
    "weapon_full_auto": +2,
    "weapon_high": +2,
    "weapon_mid": +1,
    "weapon_low": 0,
    "keycard": +2,
    "keycard_apex": +3,
    "armor_military": +2,
    "armor_tactical": +1,
    "backpack_large": +2,
    "attachment_gear": +1,
    "vehicle_parts": +1,
}

TIER_EFFECTIVE_MULT = {
    "T1_common": 4.0,
    "T2_uncommon": 2.5,
    "T3_rare": 1.75,
    "T4_very_rare": 1.0,
}

CATEGORY_TIER = {
    "weapon_low": "T1_common",
    "vehicle_parts": "T2_uncommon",
    "weapon_mid": "T2_uncommon",
    "armor_tactical": "T2_uncommon",
    "weapon_full_auto": "T3_rare",
    "armor_military": "T3_rare",
    "backpack_large": "T3_rare",
    "attachment_gear": "T3_rare",
    "weapon_high": "T4_very_rare",
    "explosive_core": "T4_very_rare",
    "explosive_grenade": "T4_very_rare",
    "keycard": "T4_very_rare",
    "keycard_apex": "T4_very_rare",
}

POI_SKIP_CATEGORIES = {"explosive_core", "explosive_grenade", "keycard", "keycard_apex", "weapon_high"}

FORCE_RARITY = {
    "explosive_core": "ExtremelyRare",
    "keycard": "ExtremelyRare",
    "keycard_apex": "ExtremelyRare",
}


def apply_item_rarity(obj: dict, item_groups: dict[str, str]) -> bool:
    iid = obj.get("Id") or obj.get("Name")
    if not iid:
        return False
    cat = classify_item(str(iid), item_groups)
    if not cat:
        return False
    changed = False
    canonical = normalize_explosive(str(iid))
    if "Id" in obj and obj["Id"] != canonical:
        obj["Id"] = canonical
        changed = True
    if "Name" in obj and obj["Name"] != canonical:
        obj["Name"] = canonical
        changed = True
    target = FORCE_RARITY.get(cat)
    if target:
        if obj.get("Rarity") != target:
            obj["Rarity"] = target
            changed = True
    elif "Rarity" in obj:
        new_r = shift_rarity(obj["Rarity"], RARITY_SHIFT[cat])
        if new_r != obj["Rarity"]:
            obj["Rarity"] = new_r
            changed = True
    return changed


def patch_node_tree(node: dict, item_groups: dict[str, str]) -> bool:
    changed = False
    name = node.get("Name", "")
    if name and "Children" not in node:
        cat = classify_item(name, item_groups)
        if cat:
            target = FORCE_RARITY.get(cat)
            if target:
                if node.get("Rarity") != target:
                    node["Rarity"] = target
                    changed = True
            elif "Rarity" in node:
                new_r = shift_rarity(node["Rarity"], RARITY_SHIFT[cat])
                if new_r != node["Rarity"]:
                    node["Rarity"] = new_r
                    changed = True
    for child in node.get("Children") or []:
        if patch_node_tree(child, item_groups):
            changed = True
    return changed


def patch_fixed_items(data: dict, item_groups: dict[str, str]) -> bool:
    fixed = data.get("FixedItems")
    if not fixed:
        return False
    changed = False
    items = list(data.get("Items") or [])
    existing = {
        normalize_explosive(str(e.get("Id")))
        for e in items
        if isinstance(e, dict) and e.get("Id")
    }
    new_fixed = []
    for item_id in fixed:
        if not isinstance(item_id, str):
            new_fixed.append(item_id)
            continue
        cat = classify_item(item_id, item_groups)
        if cat in {"explosive_core", "keycard", "keycard_apex", "weapon_high", "weapon_full_auto"}:
            canonical = normalize_explosive(item_id)
            if canonical not in existing:
                rarity = FORCE_RARITY.get(cat, "VeryRare")
                items.append({"Rarity": rarity, "Id": canonical})
                existing.add(canonical)
            changed = True
            continue
        if cat == "explosive_grenade":
            canonical = normalize_explosive(item_id)
            if canonical not in existing:
                items.append({"Rarity": "VeryRare", "Id": canonical})
                existing.add(canonical)
            changed = True
            continue
        new_fixed.append(item_id)
    if changed:
        if new_fixed:
            data["FixedItems"] = new_fixed
        else:
            data.pop("FixedItems", None)
        if items:
            data["Items"] = items
    return changed


def patch_poi_subtree_rarity(node: dict, item_groups: dict[str, str], in_poi_zone: bool) -> bool:
    changed = False
    name = node.get("Name", "")
    if name in POI_SUBTREE_NAMES:
        in_poi_zone = True
    if in_poi_zone and "Rarity" in node:
        skip = False
        if name and not node.get("Children"):
            cat = classify_item(name, item_groups)
            if cat in POI_SKIP_CATEGORIES:
                skip = True
        if not skip:
            new_r = shift_rarity(node["Rarity"], POI_RARITY_BOOST_STEPS)
            if new_r != node["Rarity"]:
                node["Rarity"] = new_r
                changed = True
    for child in node.get("Children") or []:
        if patch_poi_subtree_rarity(child, item_groups, in_poi_zone):
            changed = True
    return changed


def patch_poi_node_file(data: dict, item_groups: dict[str, str]) -> bool:
    return patch_poi_subtree_rarity(data, item_groups, False)


def patch_bunker_preset_probability(name: str, data: dict) -> bool:
    if not HIGH_TIER_PRESET_RE.search(name):
        return False
    if WEAPON_PACK_PRESET_RE.search(name):
        return False
    changed = False
    if "Probability" in data:
        old = float(data["Probability"])
        new = round(old * BUNKER_PRESET_PROB_BUMP, 4)
        if new != old:
            data["Probability"] = new
            changed = True
    return changed


def patch_preset_probability(name: str, data: dict) -> bool:
    if not (HIGH_TIER_PRESET_RE.search(name) and WEAPON_PACK_PRESET_RE.search(name)):
        return False
    changed = False
    if "Probability" in data:
        old = float(data["Probability"])
        new = max(0.05, round(old * 0.35, 4))
        if new != old:
            data["Probability"] = new
            changed = True
    for sub in data.get("Subpresets") or []:
        if isinstance(sub, dict) and "Rarity" in sub:
            new_r = shift_rarity(sub["Rarity"], +1)
            if new_r != sub["Rarity"]:
                sub["Rarity"] = new_r
                changed = True
    return changed


def patch_quantity_caps(data: dict, item_groups: dict[str, str]) -> bool:
    changed = False
    fixed = data.get("FixedItems") or []
    grenade_count = sum(
        1 for x in fixed
        if isinstance(x, str) and classify_item(x, item_groups) == "explosive_grenade"
    )
    if grenade_count > 1:
        seen = set()
        new_fixed = []
        for x in fixed:
            if isinstance(x, str) and classify_item(x, item_groups) == "explosive_grenade":
                if x in seen:
                    changed = True
                    continue
                seen.add(x)
            new_fixed.append(x)
        if changed:
            data["FixedItems"] = new_fixed
    return changed


def patch_structure(obj, item_groups: dict[str, str]) -> bool:
    changed = False
    if isinstance(obj, dict):
        if "Id" in obj or "Name" in obj:
            if apply_item_rarity(obj, item_groups):
                changed = True
        for value in obj.values():
            if patch_structure(value, item_groups):
                changed = True
    elif isinstance(obj, list):
        for item in obj:
            if patch_structure(item, item_groups):
                changed = True
    return changed


def patch_preset(name: str, data: dict, item_groups: dict[str, str]) -> bool:
    copy_changed = False
    if patch_structure(data, item_groups):
        copy_changed = True
    if patch_fixed_items(data, item_groups):
        copy_changed = True
    if patch_preset_probability(name, data):
        copy_changed = True
    if patch_bunker_preset_probability(name, data):
        copy_changed = True
    if patch_quantity_caps(data, item_groups):
        copy_changed = True
    return copy_changed


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")


def build_overrides(item_groups: dict[str, str]) -> dict:
    OVERRIDE_PRESETS.mkdir(parents=True, exist_ok=True)
    OVERRIDE_NODES.mkdir(parents=True, exist_ok=True)

    preset_count = 0
    node_count = 0
    category_hits: dict[str, int] = {}

    for node_file in sorted(DEFAULT_NODES.glob("*.json")):
        data = json.loads(node_file.read_text(encoding="utf-8"))
        copy = json.loads(json.dumps(data))
        node_changed = patch_node_tree(copy, item_groups)
        if node_file.name in POI_NODE_FILES:
            if patch_poi_node_file(copy, item_groups):
                node_changed = True
        if node_changed:
            write_json(OVERRIDE_NODES / node_file.name, copy)
            node_count += 1

    for preset_file in sorted(DEFAULT_PRESETS.glob("*.json")):
        data = json.loads(preset_file.read_text(encoding="utf-8"))
        copy = json.loads(json.dumps(data))
        if patch_preset(preset_file.name, copy, item_groups):
            write_json(OVERRIDE_PRESETS / preset_file.name, copy)
            preset_count += 1
            text = preset_file.read_text(encoding="utf-8")
            for cat in RARITY_SHIFT:
                if cat.replace("_", "") in text.lower() or any(
                    k in text for k in (HIGH_WEAPON_IDS | EXPLOSIVE_CORE | GRENADE_IDS)
                ):
                    category_hits[cat] = category_hits.get(cat, 0) + 1

    summary = {
        "patched_node_files": node_count,
        "patched_preset_files": preset_count,
        "global_multiplier": GLOBAL_MULT,
        "rarity_shift_by_category": dict(RARITY_SHIFT),
        "category_tier_map": CATEGORY_TIER,
        "tier_target_effective_mult": TIER_EFFECTIVE_MULT,
        "philosophy": {
            "T1_common": "~4x — basics, pistols, low weapons (shift +0)",
            "T2_uncommon": "~2.5x — mid weapons, tactical armor, vehicle parts (shift +1)",
            "T3_rare": "~1.75x — full-auto, military armor, large bags, attachments (shift +2)",
            "T4_very_rare": "~1x — snipers/RPG, explosives, keycards",
            "survival_and_building": "4x global only (unclassified items)",
        },
        "poi_boost": {
            "node_files": sorted(POI_NODE_FILES),
            "subtrees": sorted(POI_SUBTREE_NAMES),
            "rarity_step": POI_RARITY_BOOST_STEPS,
            "skip_categories": sorted(POI_SKIP_CATEGORIES),
            "bunker_preset_prob_multiplier": BUNKER_PRESET_PROB_BUMP,
        },
        "playtest_checklist": [
            "Civilian house: dense T1 (food, tools, pistols)",
            "Police station: T2 ammo/gear; POI slightly richer than open world",
            "Military base: T3 gear still rare; full-auto not flooding",
            "Bunker examine: T4 explosives/keycards still very rare",
            "Kill ~30 each civilian/military/police puppets: ~1 pristine food per type (3% roll)",
            "If mid rifles too scarce, lower weapon_mid shift from +1 to +0 in RARITY_SHIFT",
        ],
        "category_preset_touch_count": category_hits,
    }
    write_json(WORK / "survival_4x_summary.json", summary)
    return summary


def download_defaults() -> dict:
    transport, sftp, cfg = sftp_connect()
    remote_loot = loot_base(cfg, sftp)
    try:
        presets = sftp_download_dir(sftp, f"{remote_loot}/Spawners/Presets/Default", DEFAULT_PRESETS)
        nodes = sftp_download_dir(sftp, f"{remote_loot}/Nodes/Default", DEFAULT_NODES)
        params_remote = f"{remote_loot}/Items/Default/Parameters.json"
        PARAMETERS.parent.mkdir(parents=True, exist_ok=True)
        sftp.get(params_remote, str(PARAMETERS))
    finally:
        sftp.close()
        transport.close()
    if presets == 0:
        raise SystemExit(
            "No Default loot exports on server. Run in-game:\n"
            "  #ExportDefaultItemSpawnerPresets\n"
            "  #ExportDefaultItemParameters"
        )
    return {"downloaded_presets": presets, "downloaded_nodes": nodes}


def upload_overrides() -> dict:
    transport, sftp, cfg = sftp_connect()
    remote_loot = loot_base(cfg, sftp)
    try:
        presets = sftp_upload_dir(sftp, OVERRIDE_PRESETS, f"{remote_loot}/Spawners/Presets/Override")
        nodes = sftp_upload_dir(sftp, OVERRIDE_NODES, f"{remote_loot}/Nodes/Override")
    finally:
        sftp.close()
        transport.close()
    return {"uploaded_presets": presets, "uploaded_nodes": nodes}


def patch_server_settings() -> list[str]:
    transport, sftp, cfg = sftp_connect()
    remote_settings = f"{windows_server_base(cfg, sftp)}/ServerSettings.ini"
    try:
        with sftp.open(remote_settings, "r") as f:
            lines = f.read().decode("utf-8", errors="replace").splitlines()
        changes = []
        replacements = {
            "scum.SpawnerProbabilityMultiplier=": "scum.SpawnerProbabilityMultiplier=4.000000",
            "scum.ExamineSpawnerProbabilityMultiplier=": "scum.ExamineSpawnerProbabilityMultiplier=4.000000",
            "scum.SpawnerExpirationTimeMultiplier=": "scum.SpawnerExpirationTimeMultiplier=1.000000",
            "scum.ExamineSpawnerExpirationTimeMultiplier=": "scum.ExamineSpawnerExpirationTimeMultiplier=1.000000",
        }
        new_lines = []
        for line in lines:
            replaced = False
            for prefix, new_val in replacements.items():
                if line.startswith(prefix):
                    if line.strip() != new_val:
                        changes.append(f"{line.strip()} -> {new_val}")
                    new_lines.append(new_val)
                    replaced = True
                    break
            if not replaced:
                new_lines.append(line)
        if changes:
            with sftp.open(remote_settings, "w") as f:
                f.write("\n".join(new_lines) + "\n")
        return changes
    finally:
        sftp.close()
        transport.close()


def main() -> None:
    print("Step 1: Download latest Default loot + Parameters from server...")
    dl = download_defaults()
    print(json.dumps(dl, indent=2))

    print("\nStep 2: Build survival-focused Override files...")
    item_groups = load_item_groups()
    summary = build_overrides(item_groups)
    print(json.dumps(summary, indent=2))

    if summary["patched_preset_files"] == 0:
        raise SystemExit("No preset overrides generated.")

    print("\nStep 3: Upload Override files...")
    up = upload_overrides()
    print(json.dumps(up, indent=2))

    print("\nStep 4: Patch ServerSettings.ini spawner multipliers...")
    changes = patch_server_settings()
    if changes:
        for c in changes:
            print(" ", c)
    else:
        print("  (already correct)")

    print(
        "\nDone.\n"
        "Restart server OR run in-game as admin:\n"
        "  #ReloadLootCustomizationsAndResetSpawners\n"
        "\nNote: Changes apply to NEW spawns only."
    )


if __name__ == "__main__":
    main()
