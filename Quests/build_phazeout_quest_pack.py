"""Generate PhazeOut custom quest pack — profession Fetch / Explore / Mix / Kill."""
from __future__ import annotations

import argparse
import copy
import json
import random
import re
from pathlib import Path

import yaml

from item_display import (
    display_name,
    fetch_tracking_caption,
    refresh_display_names_cache,
    servicebp_player_blurb,
)
from quest_economy import effective_sell, load_catalog_sell, load_economy_sell_median

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OVERRIDE = ROOT / "Override"
LIST_DIR = ROOT / "QuestList"
BLOCKED = ROOT / "Blocked" / "BlockedQuests.json"
PROFESSION = ROOT / "data" / "profession_rules.yaml"
EXPLORE_TPL = ROOT / "data" / "explore_interact_template.json"
EXPLORE_TPL_DIR = ROOT / "data" / "explore_templates"
EXPLORE_INDEX = EXPLORE_TPL_DIR / "index.yaml"
SFTP_EU = REPO / ".vscode" / "sftp.json"
KILL_ALLOWED_NPCS = frozenset({"Armorer", "Bartender"})
TOUR_EXPLORE_CHANCE = 0.14  # tier 2–3 explore slots become two-region tours

# Interaction quests must use quest-tool exports: AnchorMesh + Instance + FallbackTransform
# must refer to the same world object. Do not offset transforms without new exports.
REGION_SHIFTS: dict[str, tuple[float, float, float]] = {}

FETCH_VERBS = (
    "Source", "Procure", "Recover", "Deliver", "Hand over", "Bring back", "Collect",
)
FETCH_TITLE_HOOKS = {
    "Mechanic": (
        "Workshop restock", "Garage contract", "Field repair kit", "Yard parts run",
        "Service bay order", "Roadside recovery",
    ),
    "Doctor": (
        "Clinic resupply", "Triage stock", "Field medic drop", "Infirmary order",
        "Emergency cache",
    ),
    "Fisherman": (
        "Harbour stock", "Pier supply", "Net & tackle run", "Dockside order",
        "Coastal resupply",
    ),
    "Armorer": (
        "Armory intake", "Security stock", "Range resupply", "Depot order",
    ),
    "Bartender": (
        "Saloon stock", "Bar back order", "Cellar run", "Taproom supply",
    ),
    "Barber": (
        "Tailor delivery", "Clothier order", "Wardrobe stock", "Stall resupply",
    ),
    "GeneralGoods": (
        "Trader stock", "General store run", "Depot resupply", "Shelf refill",
    ),
    "Banker": (
        "Outfitter order", "Hunting lodge stock", "Trail camp supply", "Range resupply",
    ),
}
EXPLORE_TITLE_PREFIX = (
    "Scout", "Survey", "Walk", "Check", "Recon", "Patrol", "Sweep",
)
KILL_FLAVOR = {
    "puppets": ("Clear the dead", "Puppet sweep", "Undead cull", "Horde break"),
    "armed NPCs": ("Hostile contact", "Raider clear", "Armed sweep", "Threat removal"),
    "animals": ("Cull wildlife", "Predator control", "Game management", "Beast cull"),
    "sentries": ("Sentry takedown", "Drone sweep", "Automated threat", "Sentry clear"),
}

BLOCKED_EXAMPLES = {
    "Example_Elimination.json",
    "Example_Fetch.json",
    "Example_Interact.json",
}
GENERATED_SUFFIX = re.compile(r"_\d{4}\.json$")
LEGACY_KEEP = re.compile(
    r"^T[123]_(FM|BT)_(Fetch|Kill)_[A-Za-z].+\.json$"
)  # no _1234 suffix in middle-end

CLOTHING_HINTS = (
    "Shirt", "Pants", "Jacket", "Coat", "Boots", "Shoes", "Hat", "Cap", "Helmet",
    "Gloves", "Mask", "Sweater", "Hoodie", "Vest", "Shorts", "Skirt", "Dress",
    "Scarf", "Glasses", "Watch", "Backpack", "Socks", "Beret", "Skirt", "Cap",
)

EXPLORE_CAPTIONS = {
    "Mechanic": ("Survey the garage yard", "Inspect workshop markers", "Walk the service lane"),
    "Doctor": ("Clinic perimeter check", "Inspect medical outpost", "Survey triage route"),
    "Fisherman": ("Harbour walkthrough", "Inspect dock markers", "Survey the pier"),
    "Armorer": ("Check armory exterior", "Survey security post"),
    "Bartender": ("Saloon district walk", "Inspect bar frontage"),
    "Barber": ("Tailor shop circuit", "Inspect clothing stalls"),
    "GeneralGoods": ("Storefront survey", "Inspect supply depot"),
    "Banker": ("Hunting lodge approach", "Survey trail markers"),
}

TIER_MARGIN = {1: 1.45, 2: 1.32, 3: 1.22}
TIER_FAME = {1: (14, 24), 2: (58, 92), 3: (125, 175)}
TIER_XP = {1: 3500, 2: 11000, 3: 22000}
TIER_TIME = {1: 24, 2: 48, 3: 72}
TIER_QTY = {1: (1, 2), 2: (2, 4), 3: (3, 6)}
EXPLORE_MIN = {1: (2, 3), 2: (3, 4), 3: (3, 4)}


def slug(s: str, max_len: int = 36) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "", s)
    return s[:max_len] or "X"


def short_item_label(code: str, names: dict[str, str], max_len: int = 42) -> str:
    s = display_name(code, names)
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def pool_for_tier(pool: list[tuple[str, int]], tier: int) -> list[tuple[str, int]]:
    if not pool:
        return pool
    sorted_pool = sorted(pool, key=lambda x: x[1])
    n = len(sorted_pool)
    if tier == 1:
        return sorted_pool[: max(8, int(n * 0.5))]
    if tier == 2:
        lo = int(n * 0.2)
        hi = max(lo + 8, int(n * 0.82))
        return sorted_pool[lo:hi] or sorted_pool
    lo = int(n * 0.42)
    return sorted_pool[lo:] or sorted_pool


def fetch_description(npc_cfg: dict, region_label: str, codes: list[str], hook: str) -> str:
    base = (
        f"{hook} in the {region_label} area. "
        f"Deliver to the {npc_cfg['associated'].lower()}—exact items only."
    )
    if any(c.startswith("ServiceBP_") for c in codes):
        return f"{base} {servicebp_player_blurb()}"
    return base


def _shift_transform_triplet(triplet: str, dx: float, dy: float, dz: float) -> str:
    parts = triplet.split("|")
    if len(parts) != 3:
        return triplet
    xyz = [float(x) for x in parts[0].split(",")]
    xyz[0] += dx
    xyz[1] += dy
    xyz[2] += dz
    parts[0] = f"{xyz[0]:.6f},{xyz[1]:.6f},{xyz[2]:.6f}"
    return "|".join(parts)


def _shift_map_location(loc: str, dx: float, dy: float, dz: float) -> str:
    m = re.search(
        r"X=([-\d.]+)\s+Y=([-\d.]+)\s+Z=([-\d.]+)",
        loc,
    )
    if not m:
        return loc
    x, y, z = float(m.group(1)), float(m.group(2)), float(m.group(3))
    return loc.replace(m.group(0), f"X={x + dx:.3f} Y={y + dy:.3f} Z={z + dz:.3f}")


def shift_explore_template(base: dict, dx: float, dy: float, dz: float) -> dict:
    """Legacy helper — only safe when dx=dy=dz=0 (copy). Shifting breaks AnchorMesh pairing."""
    tpl = copy.deepcopy(base)
    if dx or dy or dz:
        for loc in tpl.get("Locations", []):
            ft = loc.get("FallbackTransform")
            if ft:
                loc["FallbackTransform"] = _shift_transform_triplet(ft, dx, dy, dz)
        for entry in tpl.get("LocationsShownOnMap", []):
            if entry.get("Location"):
                entry["Location"] = _shift_map_location(entry["Location"], dx, dy, dz)
    tpl.pop("WorldMarkerShowDistance", None)
    return tpl


def canonical_explore_template(base: dict) -> dict:
    return shift_explore_template(base, 0.0, 0.0, 0.0)


def refresh_region_template_files(base: dict, *, force: bool = False) -> int:
    """Write quest-tool-safe Interaction data to each region file (same anchors until POI exports)."""
    EXPLORE_TPL_DIR.mkdir(parents=True, exist_ok=True)
    index = yaml.safe_load(EXPLORE_INDEX.read_text(encoding="utf-8"))
    payload = canonical_explore_template(base)
    text = json.dumps(payload, indent="\t") + "\n"
    written = 0
    for region in index["regions"]:
        path = EXPLORE_TPL_DIR / region["file"]
        if not force and path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        path.write_text(text, encoding="utf-8")
        written += 1
    return written


def ensure_region_template_files(base: dict) -> None:
    refresh_region_template_files(base, force=False)


def load_explore_regions(base: dict) -> list[dict]:
    ensure_region_template_files(base)
    index = yaml.safe_load(EXPLORE_INDEX.read_text(encoding="utf-8"))
    regions: list[dict] = []
    for entry in index["regions"]:
        path = EXPLORE_TPL_DIR / entry["file"]
        tpl = json.loads(path.read_text(encoding="utf-8"))
        regions.append(
            {
                "id": entry["id"],
                "label": entry["label"],
                "weight": float(entry.get("weight", 1.0)),
                "template": tpl,
            }
        )
    return regions


def pick_region(regions: list[dict], rng: random.Random, exclude_id: str | None = None) -> dict:
    pool = [r for r in regions if r["id"] != exclude_id] or regions
    weights = [r["weight"] for r in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def is_clothing(code: str) -> bool:
    return any(h in code for h in CLOTHING_HINTS)


def item_pool(catalog: dict, shop: str, npc_cfg: dict) -> list[tuple[str, int]]:
    items = list(catalog.get(shop, {}).items())
    items = [
        (c, p)
        for c, p in items
        if "UltimateQuestReward" not in c and "Human_" not in c and "Humanguts" not in c
    ]
    if npc_cfg.get("clothing_only"):
        items = [(c, p) for c, p in items if is_clothing(c)]
    elif npc_cfg["code"] == "GG":
        items = [(c, p) for c, p in items if not is_clothing(c)]
    items.sort(key=lambda x: x[1])
    return items


def reward_credits(tier: int, item_value: int) -> int:
    base = int(item_value * TIER_MARGIN[tier])
    caps = {1: 850, 2: 2200, 3: 3600}
    floors = {1: 280, 2: 650, 3: 1200}
    return max(floors[tier], min(caps[tier], base))


def count_reward_slots(reward: dict) -> int:
    slots = 0
    if any(reward.get(k) for k in ("CurrencyNormal", "CurrencyGold", "Fame")):
        slots += 1
    slots += len(reward.get("Skills") or [])
    deals = reward.get("TradeDeals") or []
    if deals:
        slots += 2 + max(0, len(deals) - 1)
    return slots


def make_reward(npc_cfg: dict, tier: int, credits: int, fame: int, rng: random.Random) -> dict:
    r: dict = {
        "CurrencyNormal": credits,
        "Fame": fame,
        "Skills": [{"Skill": npc_cfg["skill"], "Experience": TIER_XP[tier]}],
    }
    if tier == 3 and npc_cfg["allow_elimination"] and rng.random() < 0.25:
        r["CurrencyGold"] = 1
    assert count_reward_slots(r) <= 5
    return r


def fetch_condition(caption: str, items: list[str], num: int, seq: int = 0) -> dict:
    return {
        "TrackingCaption": caption,
        "SequenceIndex": seq,
        "CanBeAutoCompleted": True,
        "Type": "Fetch",
        "DisablePurchaseOfRequiredItems": False,
        "PlayerKeepsItems": False,
        "RequiredItems": [{"AcceptedItems": items, "RequiredNum": num}],
    }


def explore_condition(
    tier: int,
    caption: str,
    tpl: dict,
    rng: random.Random,
    *,
    sequence_index: int = 0,
) -> dict:
    lo, hi = EXPLORE_MIN[tier]
    all_locs = list(tpl.get("Locations") or [])
    if len(all_locs) > 2:
        rng.shuffle(all_locs)
        cap = min(len(all_locs), rng.randint(max(2, lo), min(hi + 1, len(all_locs))))
        all_locs = all_locs[:cap]
    need = min(rng.randint(lo, hi), len(all_locs) or hi)
    if not all_locs or need < 1:
        raise ValueError("Interaction condition needs at least one Location and MinNeeded >= 1")
    # Match Quests/Override/Example_Interact.json field order (LocationsShownOnMap before Type).
    cond = {
        "TrackingCaption": caption,
        "SequenceIndex": sequence_index,
        "CanBeAutoCompleted": True,
        "LocationsShownOnMap": copy.deepcopy(tpl["LocationsShownOnMap"]),
        "Type": "Interaction",
        "Locations": copy.deepcopy(all_locs),
        "MinNeeded": need,
        "MaxNeeded": need,
        "SpawnOnlyNeeded": False,
    }
    return cond


def explore_caption(npc: str, region_label: str, rng: random.Random) -> str:
    base = rng.choice(EXPLORE_CAPTIONS[npc])
    prefix = rng.choice(EXPLORE_TITLE_PREFIX)
    return f"{prefix} {region_label}: {base.lower()}"


def kill_condition(tier: int, npc_code: str, rng: random.Random) -> tuple[dict, str]:
    if npc_code == "HN":
        targets, label = ["Animal"], "animals"
        amount = {1: rng.randint(5, 10), 2: rng.randint(10, 16), 3: rng.randint(14, 22)}[tier]
    elif npc_code in ("AR", "BT"):
        if tier == 1:
            targets, label, amount = ["Puppet"], "puppets", rng.randint(8, 12)
        elif tier == 2:
            if rng.random() < 0.45:
                targets, label, amount = ["ArmedNPC"], "armed NPCs", rng.randint(6, 10)
            else:
                targets, label, amount = ["Puppet"], "puppets", rng.randint(12, 18)
        else:
            if rng.random() < 0.3:
                targets, label, amount = ["Sentry"], "sentries", rng.randint(2, 5)
            else:
                targets, label, amount = ["ArmedNPC"], "armed NPCs", rng.randint(12, 18)
    else:
        raise ValueError("kill not allowed")
    return {
        "TrackingCaption": f"Eliminate {amount} {label}",
        "SequenceIndex": 0,
        "CanBeAutoCompleted": True,
        "Type": "Elimination",
        "TargetCharacters": targets,
        "Amount": amount,
    }, label


def quest_shell(npc_cfg: dict, tier: int, title: str, desc: str, conditions: list, reward: dict) -> dict:
    return {
        "AssociatedNPC": npc_cfg["associated"],
        "Tier": tier,
        "Title": title,
        "Description": desc,
        "TimeLimitHours": TIER_TIME[tier],
        "RewardPool": [reward],
        "Conditions": conditions,
    }


def pick_items(
    pool: list[tuple[str, int]], tier: int, rng: random.Random
) -> list[tuple[str, int, int]]:
    band = pool_for_tier(pool, tier)
    lo, hi = TIER_QTY[tier]
    n_types = 1 if tier == 1 else (2 if tier == 2 else min(3, rng.randint(2, 3)))
    picks = []
    for _ in range(n_types):
        code, price = band[rng.randrange(len(band))]
        num = max(1, min(rng.randint(lo, hi), 8))
        picks.append((code, price, num))
    return picks


def gen_fetch(
    npc_cfg,
    tier,
    pool,
    catalog,
    economy,
    rng,
    qid_suffix: str,
    regions: list[dict],
    names: dict[str, str],
):
    picks = pick_items(pool, tier, rng)
    value = sum(effective_sell(c, npc_cfg["shop"], catalog, economy) * n for c, _, n in picks)
    credits = reward_credits(tier, value)
    fame = rng.randint(*TIER_FAME[tier])
    region = pick_region(regions, rng)
    hook = rng.choice(FETCH_TITLE_HOOKS[npc_cfg["associated"]])
    verb = rng.choice(FETCH_VERBS)
    conds = []
    codes = [c for c, _, _ in picks]
    for i, (code, _, num) in enumerate(picks):
        conds.append(
            fetch_condition(fetch_tracking_caption(verb, code, num, names), [code], num, seq=i)
        )
    label = picks[0][0]
    qid = f"T{tier}_{npc_cfg['code']}_Fetch_{slug(label)}_{qid_suffix}"
    title = f"{hook}: {short_item_label(label, names, 36)}"
    desc = fetch_description(npc_cfg, region["label"], codes, hook)
    return qid, quest_shell(npc_cfg, tier, title, desc, conds, make_reward(npc_cfg, tier, credits, fame, rng))


def gen_explore(npc_cfg, tier, regions: list[dict], rng, qid_suffix: str):
    region = pick_region(regions, rng)
    cap = explore_caption(npc_cfg["associated"], region["label"], rng)
    cond = explore_condition(tier, cap, region["template"], rng)
    credits = {1: 380, 2: 900, 3: 1600}[tier]
    fame = rng.randint(*TIER_FAME[tier])
    qid = f"T{tier}_{npc_cfg['code']}_Explore_{slug(region['id'] + cap)}_{qid_suffix}"
    title = cap[:64]
    desc = (
        f"Check interaction markers around {region['label']}. "
        f"Contract from the {npc_cfg['associated'].lower()}—stay off the main roads if you can."
    )
    return qid, quest_shell(npc_cfg, tier, title, desc, [cond], make_reward(npc_cfg, tier, credits, fame, rng))


def gen_tour(npc_cfg, tier, regions: list[dict], rng, qid_suffix: str):
    r1 = pick_region(regions, rng)
    r2 = pick_region(regions, rng, exclude_id=r1["id"])
    cap1 = explore_caption(npc_cfg["associated"], r1["label"], rng)
    cap2 = explore_caption(npc_cfg["associated"], r2["label"], rng)
    conds = [
        explore_condition(tier, cap1, r1["template"], rng, sequence_index=0),
        explore_condition(tier, cap2, r2["template"], rng, sequence_index=1),
    ]
    credits = {2: 1100, 3: 1950}[tier]
    fame = rng.randint(*TIER_FAME[tier]) + 8
    qid = f"T{tier}_{npc_cfg['code']}_Tour_{slug(r1['id'] + r2['id'])}_{qid_suffix}"
    title = f"Island tour: {r1['label']} → {r2['label']}"[:64]
    desc = (
        f"Two-stop route for the {npc_cfg['associated'].lower()}: "
        f"complete markers at {r1['label']}, then {r2['label']}. "
        "Take your time—this is how we map trouble spots."
    )
    return qid, quest_shell(npc_cfg, tier, title, desc, conds, make_reward(npc_cfg, tier, credits, fame, rng))


def gen_mix(
    npc_cfg,
    tier,
    pool,
    catalog,
    economy,
    regions: list[dict],
    rng,
    qid_suffix: str,
    names: dict[str, str],
):
    picks = pick_items(pool, tier, rng)
    value = sum(effective_sell(c, npc_cfg["shop"], catalog, economy) * n for c, _, n in picks)
    credits = reward_credits(tier, value) + 150
    fame = rng.randint(*TIER_FAME[tier])
    region = pick_region(regions, rng)
    cap = explore_caption(npc_cfg["associated"], region["label"], rng)
    verb = rng.choice(FETCH_VERBS)
    conds = [explore_condition(tier, cap, region["template"], rng, sequence_index=0)]
    for i, (code, _, num) in enumerate(picks):
        conds.append(
            fetch_condition(
                fetch_tracking_caption(verb, code, num, names),
                [code],
                num,
                seq=i + 1,
            )
        )
    qid = f"T{tier}_{npc_cfg['code']}_Mix_{slug(region['id'] + cap)}_{qid_suffix}"
    title = f"Scout {region['label']}: route + resupply"[:64]
    desc = (
        f"Scout {region['label']}, then hand in supplies to the "
        f"{npc_cfg['associated'].lower()}. Two-phase contract."
    )
    return qid, quest_shell(npc_cfg, tier, title, desc, conds, make_reward(npc_cfg, tier, credits, fame, rng))


def gen_kill(npc_cfg, tier, rng, qid_suffix: str):
    cond, label = kill_condition(tier, npc_cfg["code"], rng)
    amount = cond["Amount"]
    credits = min(3600, {1: 520, 2: 1400, 3: 2800}[tier] + amount * 40)
    fame = rng.randint(*TIER_FAME[tier])
    flavor = rng.choice(KILL_FLAVOR.get(label, ("Combat contract",)))
    qid = f"T{tier}_{npc_cfg['code']}_Kill_{slug(label)}{amount}_{qid_suffix}"
    title = f"{flavor} ({amount} {label})"[:64]
    desc = (
        f"{flavor}: eliminate {amount} {label} for the "
        f"{npc_cfg['associated'].lower()}. Keep it quiet if you can."
    )
    cond["TrackingCaption"] = title[:48]
    return qid, quest_shell(npc_cfg, tier, title, desc, [cond], make_reward(npc_cfg, tier, credits, fame, rng))


def is_legacy_keep(path: Path) -> bool:
    if path.name in BLOCKED_EXAMPLES:
        return True
    if GENERATED_SUFFIX.search(path.name):
        return False
    if LEGACY_KEEP.match(path.name):
        return True
    if path.name.startswith("T") and "_Kill_" not in path.name and "_Fetch_" in path.name:
        if "_MR_" in path.name:
            return False
        if not GENERATED_SUFFIX.search(path.name):
            return True
    return False


def rebuild_clean(full: bool = False) -> int:
    removed = 0
    for path in list(OVERRIDE.glob("*.json")):
        if path.name in BLOCKED_EXAMPLES:
            continue
        if not full and is_legacy_keep(path):
            continue
        path.unlink()
        removed += 1
    return removed


def patch_legacy_fetches() -> int:
    n = 0
    for path in OVERRIDE.glob("*.json"):
        if path.name in BLOCKED_EXAMPLES:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for cond in data.get("Conditions", []):
            if cond.get("Type") == "Fetch" and cond.get("PlayerKeepsItems") is False:
                if not cond.get("CanBeAutoCompleted"):
                    cond["CanBeAutoCompleted"] = True
                    changed = True
            if cond.get("AssociatedNPC") == "Merchant":
                data["AssociatedNPC"] = "Barber"
                changed = True
        if data.get("AssociatedNPC") == "Merchant":
            data["AssociatedNPC"] = "Barber"
            changed = True
        if changed:
            path.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
            n += 1
    return n


def existing_ids() -> set[str]:
    return {p.stem for p in OVERRIDE.glob("*.json") if p.name not in BLOCKED_EXAMPLES}


def write_quest(qid: str, data: dict) -> None:
    (OVERRIDE / f"{qid}.json").write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")


def write_meta() -> None:
    LIST_DIR.mkdir(parents=True, exist_ok=True)
    custom = sorted(p.stem for p in OVERRIDE.glob("*.json") if p.name not in BLOCKED_EXAMPLES)
    LIST_DIR.joinpath("CustomQuestList.json").write_text(json.dumps(custom, indent="\t") + "\n", encoding="utf-8")
    LIST_DIR.joinpath("DefaultQuestList.json").write_text("[]\n", encoding="utf-8")
    blocked = {
        "BlockAllDefaultQuests": False,
        "BlockQuestNames": [f"Quests/Override/{n}" for n in sorted(BLOCKED_EXAMPLES)],
    }
    BLOCKED.parent.mkdir(parents=True, exist_ok=True)
    BLOCKED.write_text(json.dumps(blocked, indent="\t") + "\n", encoding="utf-8")


def validate_summary() -> dict:
    stats: dict = {"by_npc": {}, "errors": []}
    for path in OVERRIDE.glob("*.json"):
        if path.name in BLOCKED_EXAMPLES:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        npc = data.get("AssociatedNPC", "?")
        stats["by_npc"].setdefault(npc, {"Fetch": 0, "Interaction": 0, "Elimination": 0, "Mix": 0, "Tour": 0, "files": 0})
        stats["by_npc"][npc]["files"] += 1
        types = [c.get("Type") for c in data.get("Conditions", [])]
        if "_Tour_" in path.stem:
            stats["by_npc"][npc]["Tour"] += 1
        if len(types) > 1 and len(set(types)) > 1:
            stats["by_npc"][npc]["Mix"] += 1
        for t in types:
            if t in ("Fetch", "Interaction", "Elimination"):
                stats["by_npc"][npc][t] += 1
        if "Elimination" in types and npc not in KILL_ALLOWED_NPCS:
            stats["errors"].append(f"{path.name}: elimination on {npc}")
        for r in data.get("RewardPool", []):
            if count_reward_slots(r) > 5:
                stats["errors"].append(f"{path.name}: reward slots > 5")
        for cond in data.get("Conditions", []):
            if cond.get("Type") != "Interaction":
                continue
            if cond.get("WorldMarkerShowDistance") is not None:
                stats["errors"].append(
                    f"{path.name}: WorldMarkerShowDistance on Interaction (omit; see Example_Interact)"
                )
            locs = cond.get("Locations") or []
            need = cond.get("MinNeeded") or 0
            if need > len(locs):
                stats["errors"].append(
                    f"{path.name}: MinNeeded {need} > Locations {len(locs)}"
                )
            for i, loc in enumerate(locs):
                for key in ("AnchorMesh", "Instance", "FallbackTransform", "VisibleMesh"):
                    if key not in loc:
                        stats["errors"].append(f"{path.name}: Location[{i}] missing {key}")
    return stats


def allowed_override_stems() -> set[str]:
    custom = json.loads(LIST_DIR.joinpath("CustomQuestList.json").read_text(encoding="utf-8"))
    return set(custom) | {Path(n).stem for n in BLOCKED_EXAMPLES}


def cleanup_remote_override_orphans(sftp, remote_quests: str) -> int:
    """SCUM loads every Override/*.json — remove files not in CustomQuestList."""
    allowed = allowed_override_stems()
    remote_override = f"{remote_quests.rstrip('/')}/Override"
    removed = 0
    for name in sftp.listdir(remote_override):
        if not name.endswith(".json"):
            continue
        if name in BLOCKED_EXAMPLES or name[:-5] in allowed:
            continue
        sftp.remove(f"{remote_override}/{name}")
        removed += 1
    return removed


def upload_eu() -> None:
    import paramiko

    cfg = json.loads(SFTP_EU.read_text(encoding="utf-8"))
    transport = paramiko.Transport((cfg["host"], int(cfg["port"])))
    transport.connect(username=cfg["username"], password=cfg["password"])
    sftp = paramiko.SFTPClient.from_transport(transport)
    try:
        service = sftp.listdir("/")[0]
        remote_quests = f"/{service}/SCUM/Saved/Config/WindowsServer/Quests"

        def upload_tree(local: Path, remote: str) -> int:
            n = 0
            for child in local.iterdir():
                r = remote.rstrip("/") + "/" + child.name
                if child.is_dir():
                    try:
                        sftp.stat(r)
                    except OSError:
                        sftp.mkdir(r)
                    n += upload_tree(child, r)
                else:
                    sftp.put(str(child), r)
                    n += 1
            return n

        n = upload_tree(ROOT, remote_quests)
        rm = cleanup_remote_override_orphans(sftp, remote_quests)
        print(f"EU SFTP: uploaded {n} files -> {remote_quests}")
        print(f"EU SFTP: removed {rm} orphan Override quest files")
    finally:
        sftp.close()
        transport.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target", type=int, default=600)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--rebuild-professions", action="store_true")
    parser.add_argument(
        "--refresh-explore-templates",
        action="store_true",
        help="Rewrite data/explore_templates/*.json from explore_interact_template.json (fixes bad offsets).",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--cleanup-remote-only",
        action="store_true",
        help="Delete EU Override/*.json not listed in CustomQuestList (no upload).",
    )
    args = parser.parse_args()

    if args.cleanup_remote_only:
        import paramiko

        cfg = json.loads(SFTP_EU.read_text(encoding="utf-8"))
        transport = paramiko.Transport((cfg["host"], int(cfg["port"])))
        transport.connect(username=cfg["username"], password=cfg["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            service = sftp.listdir("/")[0]
            remote_quests = f"/{service}/SCUM/Saved/Config/WindowsServer/Quests"
            rm = cleanup_remote_override_orphans(sftp, remote_quests)
            print(f"EU SFTP: removed {rm} orphan Override quest files")
        finally:
            sftp.close()
            transport.close()
        return

    if args.validate_only:
        stats = validate_summary()
        stats["custom_quest_count"] = len(existing_ids())
        print(json.dumps(stats, indent=2))
        return

    rng = random.Random(args.seed)
    refresh_display_names_cache()
    names = json.loads((ROOT / "data" / "item_display_names.json").read_text(encoding="utf-8"))
    cfg = yaml.safe_load(PROFESSION.read_text(encoding="utf-8"))
    base_tpl = json.loads(EXPLORE_TPL.read_text(encoding="utf-8"))
    if args.refresh_explore_templates or args.rebuild_professions:
        n_tpl = refresh_region_template_files(base_tpl, force=True)
        if n_tpl:
            print(f"Refreshed {n_tpl} explore template file(s) from quest-tool base anchors")
    regions = load_explore_regions(base_tpl)
    catalog = load_catalog_sell()
    economy = load_economy_sell_median()

    if args.rebuild_professions:
        rm = rebuild_clean(full=True)
        print(f"Removed {rm} quest files (full rebuild, kept examples only)")

    patch_legacy_fetches()
    ids = existing_ids()
    expected_total = len(cfg["npcs"]) * cfg["per_npc"]
    if not args.rebuild_professions and len(ids) >= expected_total:
        print(
            f"Skip generation: {len(ids)} quests already (expected {expected_total}). "
            "Use --rebuild-professions to replace."
        )
        write_meta()
        stats = validate_summary()
        stats["custom_quest_count"] = len(ids)
        stats["created_this_run"] = 0
        (ROOT / "quest_pack_summary.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
        if args.upload:
            upload_eu()
        return
    per_npc = cfg["per_npc"]
    tier_share = cfg["tier_share"]
    created = 0

    kinds_order = ("fetch", "explore", "mix", "kill")

    for _name, npc_cfg in cfg["npcs"].items():
        pool = item_pool(catalog, npc_cfg["shop"], npc_cfg)
        if not pool and npc_cfg["code"] != "BT":
            print(f"WARN empty pool {_name}")
        mix = npc_cfg["condition_mix"]
        counts = {k: max(0, int(round(per_npc * mix[k]))) for k in mix}
        while sum(counts.values()) < per_npc:
            counts["fetch"] += 1
        while sum(counts.values()) > per_npc:
            counts["fetch"] = max(0, counts["fetch"] - 1)

        plan: list[tuple[str, int]] = []
        for kind in kinds_order:
            if kind == "kill" and not npc_cfg["allow_elimination"]:
                continue
            total = counts.get(kind, 0)
            for tier in (1, 2, 3):
                n_tier = int(round(total * tier_share[tier]))
                plan.extend([(kind, tier)] * n_tier)
        while len(plan) < per_npc:
            plan.append(("fetch", 1))
        plan = plan[:per_npc]
        rng.shuffle(plan)

        used_titles: set[str] = set()

        for kind, tier in plan:
            suffix = str(rng.randint(1000, 9999))
            if kind == "fetch":
                if not pool:
                    continue
                qid, data = gen_fetch(
                    npc_cfg, tier, pool, catalog, economy, rng, suffix, regions, names
                )
            elif kind == "explore":
                if tier >= 2 and rng.random() < TOUR_EXPLORE_CHANCE:
                    qid, data = gen_tour(npc_cfg, tier, regions, rng, suffix)
                else:
                    qid, data = gen_explore(npc_cfg, tier, regions, rng, suffix)
            elif kind == "mix":
                if not pool:
                    continue
                qid, data = gen_mix(
                    npc_cfg, tier, pool, catalog, economy, regions, rng, suffix, names
                )
            elif kind == "kill":
                qid, data = gen_kill(npc_cfg, tier, rng, suffix)
            else:
                continue
            while qid in ids:
                qid += "x"
            title = data.get("Title", "")
            if title in used_titles:
                data["Title"] = f"{title} #{suffix}"[:64]
            used_titles.add(data["Title"])
            write_quest(qid, data)
            ids.add(qid)
            created += 1

    write_meta()
    stats = validate_summary()
    stats["custom_quest_count"] = len(ids)
    stats["created_this_run"] = created
    (ROOT / "quest_pack_summary.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: stats[k] for k in ("custom_quest_count", "created_this_run", "errors")}, indent=2))
    print("by_npc:", json.dumps(stats["by_npc"], indent=2))

    if args.upload:
        upload_eu()


if __name__ == "__main__":
    main()
