"""Nerf listed explosives to ExtremelyRare using server-exported Default loot files.

Workflow:
  1. In-game admin: #ExportDefaultItemSpawnerPresets  and  #ExportDefaultItemParameters
  2. Run: python apply_explosive_nerfs.py
     - Downloads Default/ from server via SFTP
     - Builds Override/ with target items set to ExtremelyRare
     - Uploads only Override/ back to server

Grenades and gunpowder are NOT in the target list and are left unchanged.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import paramiko

REPO = Path(__file__).resolve().parent
WORK = REPO / "Loot"
import sys

sys.path.insert(0, str(REPO / "tools"))
from sftp_remote import connect as sftp_connect_eu, loot_base

# Exact spawn codes only — grenades & gunpowder intentionally excluded.
# C4_Keypad is the in-game export spelling; C4_KeyPad is kept as an alias.
TARGET_ITEMS = {
    "C4",
    "C4_Pack",
    "TNT",
    "PipeBomb",
    "PressureCookerBomb",
    "Blast_Cap",
    "Cal_40x46",
    "40mm_G",
    "Cal_40_PG-7M",
    "Cal_40_OG-7V",
    "C4_Detonator",
    "C4_CircuitBoard",
    "C4_KeyPad",
    "C4_Keypad",
    "Laser_Detonator",
    "Sensor_Detonator",
}

TARGET_ALIASES = {
    "C4_KeyPad": "C4_Keypad",
}

TARGET_RARITY = "ExtremelyRare"

LOCAL_DEFAULT_PRESETS = WORK / "Spawners" / "Presets" / "Default"
LOCAL_DEFAULT_NODES = WORK / "Nodes" / "Default"
LOCAL_OVERRIDE_PRESETS = WORK / "Spawners" / "Presets" / "Override"
LOCAL_OVERRIDE_NODES = WORK / "Nodes" / "Override"

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


def normalize_item_id(item_id: str) -> str:
    return TARGET_ALIASES.get(item_id, item_id)


def is_target_item(item_id: str | None) -> bool:
    if not item_id:
        return False
    return normalize_item_id(item_id) in TARGET_ITEMS


def contains_target(obj) -> bool:
    if isinstance(obj, str):
        return is_target_item(obj)
    if isinstance(obj, dict):
        iid = obj.get("Id") or obj.get("Name")
        if is_target_item(iid):
            return True
        return any(contains_target(v) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_target(v) for v in obj)
    return False


def patch_rarity_recursive(obj) -> bool:
    changed = False
    if isinstance(obj, dict):
        iid = obj.get("Id") or obj.get("Name")
        if is_target_item(iid):
            canonical = normalize_item_id(iid)
            if "Id" in obj:
                obj["Id"] = canonical
            if "Name" in obj:
                obj["Name"] = canonical
            if obj.get("Rarity") != TARGET_RARITY:
                obj["Rarity"] = TARGET_RARITY
                changed = True
        for value in obj.values():
            if patch_rarity_recursive(value):
                changed = True
    elif isinstance(obj, list):
        for item in obj:
            if patch_rarity_recursive(item):
                changed = True
    return changed


def patch_fixed_items(data: dict) -> bool:
    """Move target FixedItems into Items at ExtremelyRare instead of guaranteed spawns."""
    fixed = data.get("FixedItems")
    if not fixed:
        return False

    changed = False
    items = list(data.get("Items") or [])
    existing_ids = {
        normalize_item_id(entry.get("Id"))
        for entry in items
        if isinstance(entry, dict) and entry.get("Id")
    }

    new_fixed = []
    for item_id in fixed:
        if not is_target_item(item_id):
            new_fixed.append(item_id)
            continue

        canonical = normalize_item_id(item_id)
        if canonical not in existing_ids:
            items.append({"Rarity": TARGET_RARITY, "Id": canonical})
            existing_ids.add(canonical)
        changed = True

    if changed:
        if new_fixed:
            data["FixedItems"] = new_fixed
        else:
            data.pop("FixedItems", None)
        if items:
            data["Items"] = items
    return changed


def patch_preset_or_node(data: dict) -> bool:
    changed = patch_rarity_recursive(data)
    if patch_fixed_items(data):
        changed = True
    return changed


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")


def clear_dir(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for f in path.glob("*.json"):
        f.unlink()


def download_defaults() -> dict:
    transport, sftp, cfg = sftp_connect()
    remote_loot = loot_base(cfg, sftp)
    try:
        preset_count = sftp_download_dir(
            sftp, f"{remote_loot}/Spawners/Presets/Default", LOCAL_DEFAULT_PRESETS
        )
        node_count = sftp_download_dir(sftp, f"{remote_loot}/Nodes/Default", LOCAL_DEFAULT_NODES)
    finally:
        sftp.close()
        transport.close()

    if preset_count == 0:
        raise SystemExit(
            "No preset exports found on server.\n"
            "Run in-game as admin:\n"
            "  #ExportDefaultItemSpawnerPresets\n"
            "  #ExportDefaultItemParameters\n"
            "Then restart or wait for files to appear and run this script again."
        )
    return {"downloaded_presets": preset_count, "downloaded_nodes": node_count}


def build_overrides() -> dict:
    if not LOCAL_DEFAULT_PRESETS.exists() or not any(LOCAL_DEFAULT_PRESETS.glob("*.json")):
        raise SystemExit("No local Default presets. Run download first.")

    clear_dir(LOCAL_OVERRIDE_PRESETS)
    clear_dir(LOCAL_OVERRIDE_NODES)

    patched_presets = 0
    patched_nodes = 0
    preset_hits: dict[str, list[str]] = {item: [] for item in TARGET_ITEMS}
    node_hits: dict[str, list[str]] = {item: [] for item in TARGET_ITEMS}

    for preset_file in sorted(LOCAL_DEFAULT_PRESETS.glob("*.json")):
        data = json.loads(preset_file.read_text(encoding="utf-8"))
        if not contains_target(data):
            continue
        copy = json.loads(json.dumps(data))
        if patch_preset_or_node(copy):
            write_json(LOCAL_OVERRIDE_PRESETS / preset_file.name, copy)
            patched_presets += 1
            text = preset_file.read_text(encoding="utf-8")
            for item in TARGET_ITEMS:
                if item in text or TARGET_ALIASES.get(item, item) in text:
                    preset_hits[item].append(preset_file.name)

    if LOCAL_DEFAULT_NODES.exists():
        for node_file in sorted(LOCAL_DEFAULT_NODES.glob("*.json")):
            data = json.loads(node_file.read_text(encoding="utf-8"))
            if not contains_target(data):
                continue
            copy = json.loads(json.dumps(data))
            if patch_preset_or_node(copy):
                write_json(LOCAL_OVERRIDE_NODES / node_file.name, copy)
                patched_nodes += 1
                text = node_file.read_text(encoding="utf-8")
                for item in TARGET_ITEMS:
                    alias = TARGET_ALIASES.get(item, item)
                    if (
                        f'"Name": "{item}"' in text
                        or f'"Id": "{item}"' in text
                        or f'"Name": "{alias}"' in text
                        or f'"Id": "{alias}"' in text
                    ):
                        node_hits[item].append(node_file.name)

    items_found = {
        item: {
            "presets": sorted(set(preset_hits[item])),
            "nodes": sorted(set(node_hits[item])),
        }
        for item in TARGET_ITEMS
        if preset_hits[item] or node_hits[item]
    }
    items_missing = sorted(
        item for item in TARGET_ITEMS if not preset_hits[item] and not node_hits[item]
    )

    summary = {
        "target_items": sorted(TARGET_ITEMS),
        "target_rarity": TARGET_RARITY,
        "excluded": ["grenades", "gunpowder"],
        "patched_preset_files": patched_presets,
        "patched_node_files": patched_nodes,
        "items_found": items_found,
        "items_not_found_in_exports": items_missing,
    }
    write_json(WORK / "explosive_nerf_summary.json", summary)
    return summary


def upload_overrides() -> dict:
    transport, sftp, cfg = sftp_connect()
    remote_loot = loot_base(cfg, sftp)
    try:
        preset_count = sftp_upload_dir(
            sftp, LOCAL_OVERRIDE_PRESETS, f"{remote_loot}/Spawners/Presets/Override"
        )
        node_count = sftp_upload_dir(sftp, LOCAL_OVERRIDE_NODES, f"{remote_loot}/Nodes/Override")
    finally:
        sftp.close()
        transport.close()
    return {"uploaded_presets": preset_count, "uploaded_nodes": node_count}


def main() -> None:
    print("Step 1: Download Default loot exports from server...")
    dl = download_defaults()
    print(json.dumps(dl, indent=2))

    print("\nStep 2: Build Override files (ExtremelyRare for target items)...")
    summary = build_overrides()
    print(json.dumps(summary, indent=2))

    if summary["patched_preset_files"] == 0 and summary["patched_node_files"] == 0:
        raise SystemExit("No override files generated — check exports contain target items.")

    print("\nStep 3: Upload Override files to server...")
    up = upload_overrides()
    print(json.dumps(up, indent=2))
    print(
        "\nDone. Restart server or run: #ReloadLootCustomizationsAndResetSpawners"
    )


if __name__ == "__main__":
    main()
