"""Build SCUM loot overrides: explosives at 1x effective spawn while global loot stays 4x."""
import json
import re
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/v1ktor/scum-loot-tweaker/main/apps/server/src/data/Loot"
OUT = Path(r"C:\Users\PurpleHaze\Downloads\PhazeOut Scum server\Loot")
GLOBAL_MULT = 4.0
TARGET_MULT = 1.0
ADJUST = TARGET_MULT / GLOBAL_MULT  # 0.25

RARITY_ORDER = ["Abundant", "Common", "Uncommon", "Rare", "VeryRare", "ExtremelyRare"]

EXPLOSIVE_ID_RE = re.compile(
    r"(^|_)(Explos|Grenade|Gunpowder|GunPowder|C4_|TNT|Mine_|Detonator|Blasting|"
    r"Nitro|Semtex|IED|AT4|RPG|40mm|40x46|PG-7|PG_7|Frag_|Smoke_Grenade|TearGas|"
    r"EMP_Grenade|Fuse_|Charcoal|Sulfur|Sulphur|Ammonium|ANFO|Promethe|Plastic_Explosive|"
    r"Cal_40|Launcher.*Grenade|GrenadeLauncher|Rocket|RPG7|Claymore|PlasticExplosive)",
    re.I,
)

EXPLOSIVE_NODE_RE = re.compile(r"\.Explosives|\.Grenade|\.Demolition|\.C4|\.TNT|\.Mines|\.RPG|\.Fuses", re.I)

EXCLUDE_IDS = {
    "ActivatedCharcoal_01", "ActivatedCharcoal_02", "ActivatedCharcoal_03",
    "PotassiumIodide_Pills_01", "PotassiumIodide_Pills_02", "PotassiumIodide_Pills_03",
    "Scissors_Plastic",
}

SPAWNER_NAME_RE = re.compile(
    r"Explos|Grenade|(?:^|[_-])C4(?:$|[_-])|TNT|(?:^|[_-])Fuse(?:$|[_-])|"
    r"RPG|AT4|40mm|Demolition|Blasting|Gunpowder|Nitro|Detonator|Rocket|Claymore|IED|Semtex",
    re.I,
)


def fetch_json(path: str):
    url = f"{BASE_URL}/{path.replace(chr(92), '/')}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_text(path: str) -> str:
    url = f"{BASE_URL}/{path.replace(chr(92), '/')}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8")


def is_explosive_id(item_id: str) -> bool:
    if item_id in EXCLUDE_IDS:
        return False
    return bool(EXPLOSIVE_ID_RE.search(item_id))


def build_explosive_ids(parameters: list) -> set[str]:
    ids = set()
    for p in parameters:
        iid = p.get("Id", "")
        cg = p.get("CooldownGroup", "")
        if "Explosives" in cg or "RPGs" in cg or is_explosive_id(iid):
            ids.add(iid)
            for v in p.get("Variations") or []:
                if is_explosive_id(v):
                    ids.add(v)
    return ids


def downgrade_rarity(rarity: str) -> str:
    if rarity not in RARITY_ORDER:
        return rarity
    idx = RARITY_ORDER.index(rarity)
    new_idx = min(len(RARITY_ORDER) - 1, idx + 2)
    return RARITY_ORDER[new_idx]


def patch_node_tree(node):
    changed = False
    name = node.get("Name", "")
    if is_explosive_id(name) or name in {"Explosives", "GrenadeLaunchers", "Grenades", "Mines", "Fuses"}:
        if "Rarity" in node:
            new = downgrade_rarity(node["Rarity"])
            if new != node["Rarity"]:
                node["Rarity"] = new
                changed = True
    for child in node.get("Children") or []:
        if patch_node_tree(child):
            changed = True
    return changed


def patch_spawner(data: dict, explosive_ids: set[str]) -> bool:
    changed = False

    if "Probability" in data:
        old = float(data["Probability"])
        new = max(0.1, round(old * ADJUST, 4))
        if new != old:
            data["Probability"] = new
            changed = True
    else:
        # Explicit probability cancels the 4x boost for dedicated explosive presets
        data["Probability"] = round(100 * ADJUST, 4)
        changed = True

    return changed


def preset_is_explosive(name: str, data: dict, explosive_ids: set[str]) -> bool:
    if SPAWNER_NAME_RE.search(name):
        return True

    fixed = data.get("FixedItems") or []
    items = [i.get("Id") for i in (data.get("Items") or []) if isinstance(i, dict)]
    nodes = []
    for n in data.get("Nodes") or []:
        for nid in n.get("Ids") or []:
            nodes.append(nid)
    subs = [s.get("Id", "") for s in (data.get("Subpresets") or []) if isinstance(s, dict)]

    if fixed and all(x in explosive_ids or is_explosive_id(x) for x in fixed):
        return True
    if items and all(x in explosive_ids or is_explosive_id(x) for x in items):
        return True
    if nodes and all(EXPLOSIVE_NODE_RE.search(x) for x in nodes):
        return True
    if subs and all(SPAWNER_NAME_RE.search(x) for x in subs):
        return True
    return False


def main():
    tree_file = Path(r"C:\Users\PurpleHaze\.cursor\projects\c-Users-PurpleHaze-Downloads-PhazeOut-Scum-server\agent-tools\50c25b00-0594-45c7-8fb9-ed602cf310e4.txt")
    preset_paths = []
    for line in tree_file.read_text(encoding="utf-8").splitlines():
        if "Spawners/Presets/Default/" in line and line.strip().endswith(".json\","):
            p = line.split('"path": "')[1].split('"')[0]
            preset_paths.append(p.split("Loot/", 1)[1])

    params = fetch_json("Items/Default/Parameters.json")["Parameters"]
    explosive_ids = build_explosive_ids(params)

    node_dir = OUT / "Nodes" / "Override"
    spawner_dir = OUT / "Spawners" / "Presets" / "Override"
    node_dir.mkdir(parents=True, exist_ok=True)
    spawner_dir.mkdir(parents=True, exist_ok=True)

    node_files = [
        line.split('"path": "')[1].split('"')[0].split("Loot/", 1)[1]
        for line in tree_file.read_text(encoding="utf-8").splitlines()
        if "Loot/Nodes/Default/" in line and line.strip().endswith('.json",')
    ]

    patched_nodes = 0
    for rel in node_files:
        data = fetch_json(rel)
        if patch_node_tree(data):
            out_name = Path(rel).name
            (node_dir / out_name).write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
            patched_nodes += 1

    patched_spawners = 0
    for rel in preset_paths:
        name = Path(rel).name
        try:
            data = fetch_json(rel)
        except Exception:
            continue
        if not preset_is_explosive(name, data, explosive_ids):
            continue
        if patch_spawner(data, explosive_ids):
            (spawner_dir / name).write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
            patched_spawners += 1

    summary = {
        "explosive_item_ids": len(explosive_ids),
        "patched_node_files": patched_nodes,
        "patched_spawner_presets": patched_spawners,
        "adjustment_factor": ADJUST,
    }
    (OUT / "explosive_override_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
