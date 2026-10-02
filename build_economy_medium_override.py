"""Generate PhazeOut medium-aggression EconomyOverride (Grok-aligned absolute prices)."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\PurpleHaze\Downloads\PhazeOut Scum server")
CATALOG = ROOT / "data" / "trader_prices_catalog.csv"
BASE_ECONOMY = ROOT / "EconomyOverride.json"
OUT_JSON = ROOT / "EconomyOverride.proposed.json"
OUT_MD = ROOT / "medium_trader_override_changelog.md"

OUTPOSTS = ("A_0", "B_4", "C_2", "Z_3")
SHOP_SUFFIXES = (
    "Armory",
    "Hospital",
    "Barber",
    "Saloon",
    "BoatShop",
    "Mechanic",
    "Trader",
    "Hunter",
    "Master_Hunter",
)

# shop_type, tradeable_code, buy, sell, fame, can_buy
# Medium = Grok table + PhazeOut extras (meds, RPG, VSS, NVG, extra calibers). Codes verified vs catalog.
EXPLICIT_OVERRIDES: list[tuple[str, str, int, int, int, str]] = [
    # --- weapons: full-auto / high (Grok) ---
    ("Armory", "Weapon_AK47", 8500, 1200, 800, "true"),
    ("Armory", "Weapon_AK15", 9200, 1400, 900, "true"),
    ("Armory", "Weapon_M16A4", 8800, 1300, 850, "true"),
    ("Armory", "Weapon_SCAR_L", 9500, 1500, 950, "true"),
    ("Armory", "Weapon_M249", 14000, 1800, 1200, "true"),
    ("Armory", "Weapon_RPK-74", 11000, 1600, 1100, "true"),
    ("Armory", "Weapon_MK18", 16000, 2200, 1500, "true"),
    ("Armory", "Weapon_SVD_Dragunov", 14500, 2000, 1400, "true"),
    ("Armory", "Weapon_AWM", 18000, 2500, 1800, "true"),
    ("Armory", "Weapon_AWP", 18000, 2500, 1800, "true"),
    ("Armory", "Weapon_M82A1", 22000, 2800, 2000, "true"),
    # --- weapons: PhazeOut T3/T4 extras (same philosophy as Grok) ---
    ("Armory", "Weapon_SCAR_DMR", 15500, 2100, 1300, "true"),
    ("Armory", "Weapon_VSS_VZ", 12000, 1600, 1000, "true"),
    ("Armory", "Weapon_AS_Val", 10000, 1400, 900, "true"),
    ("Armory", "Weapon_MP5_SD", 8800, 1200, 850, "true"),
    ("Armory", "Weapon_RPG7", 16000, 2200, 1500, "true"),
    # --- magazines (Grok) ---
    ("Armory", "Magazine_AK47", 1100, 180, 600, "true"),
    ("Armory", "Magazine_AK15", 1200, 200, 700, "true"),
    ("Armory", "Magazine_M16", 900, 150, 600, "true"),
    ("Armory", "Magazine_SCAR_DMR", 1100, 180, 700, "true"),
    ("Armory", "Magazine_M249", 2200, 350, 1000, "true"),
    ("Armory", "Magazine_RPK", 1800, 300, 900, "true"),
    ("Armory", "Magazine_SVD_Dragunov", 1800, 300, 1100, "true"),
    ("Armory", "Magazine_AWM", 2000, 350, 1400, "true"),
    ("Armory", "Magazine_AWP", 2000, 350, 1400, "true"),
    ("Armory", "Magazine_M82A1", 2800, 450, 1600, "true"),
    # --- armor (Grok — all plate/tactical/police variants) ---
    ("Armory", "Bulletproof_Vest_01", 2800, 450, 700, "true"),
    ("Armory", "Bulletproof_Vest_01_02", 2800, 450, 700, "true"),
    ("Armory", "Bulletproof_Vest_01_03", 2800, 450, 700, "true"),
    ("Armory", "Bulletproof_Vest_01_04", 2800, 450, 700, "true"),
    ("Armory", "Bulletproof_Vest_01_05", 2800, 450, 700, "true"),
    ("Armory", "Armor_Tactical_Vest_01_01", 4200, 650, 900, "true"),
    ("Armory", "Armor_Tactical_Vest_01_02", 4200, 650, 900, "true"),
    ("Armory", "Armor_Tactical_Vest_01_03", 4200, 650, 900, "true"),
    ("Armory", "Armor_Tactical_Vest_01_04", 4200, 650, 900, "true"),
    ("Armory", "Armor_Tactical_Vest_01_05", 4200, 650, 900, "true"),
    ("Armory", "Armor_Police_Vest_01", 3800, 600, 800, "true"),
    # --- carry / optics ---
    ("Armory", "Military_Backpack_02_03", 2400, 400, 700, "true"),
    ("Armory", "Night_Vision_Goggles_01", 6500, 900, 800, "true"),
    # --- ammo boxes (Grok + extra calibers) ---
    ("Armory", "Cal_5_56x45mm_Ammobox", 1800, 280, 500, "true"),
    ("Armory", "Cal_5_56x45mm_AP_Ammobox", 2800, 400, 700, "true"),
    ("Armory", "Cal_7_62x39mm_Ammobox", 1900, 300, 550, "true"),
    ("Armory", "Cal_7_62x39mm_AP_Ammobox", 2900, 420, 750, "true"),
    ("Armory", "Cal_308_Ammobox", 2200, 350, 700, "true"),
    ("Armory", "Cal_308_Ammobox_AP", 3800, 550, 900, "true"),
    ("Armory", "Cal_7_62x54mmR_Ammobox", 2400, 380, 800, "true"),
    ("Armory", "Cal_7_62x54mmR_AP_Ammobox", 4200, 550, 1000, "true"),
    ("Armory", "Cal_338_Ammobox", 2600, 400, 750, "true"),
    ("Armory", "Cal_50BMG_Ammobox", 18000, 1800, 1500, "true"),
    ("Armory", "Cal_50BMG_AP_Ammobox", 22000, 2200, 1800, "true"),
    # --- C4 / raid tools (sell-only at traders; loot/craft only) ---
    ("Armory", "C4", -1, 600, 2000, "false"),
    ("Armory", "C4_Pack", -1, 400, 1500, "false"),
    ("Armory", "C4_Detonator", -1, 350, 1400, "false"),
    ("Armory", "C4_CircuitBoard", -1, 350, 1400, "false"),
    ("Armory", "C4_Keypad", -1, 350, 1400, "false"),
    # --- hospital raid meds (higher fame than v1) ---
    ("Hospital", "Adrenaline_Shot", 1200, 180, 800, "true"),
    ("Hospital", "AtropineInjection", 1200, 180, 800, "true"),
    ("Hospital", "Hemostatic_Dressing", 1000, 150, 750, "true"),
    ("Hospital", "Emergency_bandage_Big", 2000, 300, 850, "true"),
    ("Hospital", "Tourniquet", 2000, 300, 800, "true"),
]

# Weapon/armor buys must exceed vanilla (table buy is a floor for sells/fame; buy uses max(table, vanilla * mult))
WEAPON_ARMOR_BUY_MULT = 1.15


def is_weapon_or_armor(code: str) -> bool:
    return code.startswith(("Weapon_", "Bulletproof_", "Armor_"))


def weapon_armor_buy(table_buy: int, vanilla_buy: int) -> int:
    if vanilla_buy <= 0:
        return table_buy
    floor_buy = max(int(round(vanilla_buy * WEAPON_ARMOR_BUY_MULT)), vanilla_buy + 1)
    return max(table_buy, floor_buy)


KEYCARD = {
    "tradeable-code": "Keycard",
    "base-purchase-price": "-1",
    "base-sell-price": "2500",
    "delta-price": "0.0",
    "can-be-purchased": "false",
    "required-famepoints": "-1",
    "available-after-sale-only": "default",
}


def load_catalog_codes() -> set[tuple[str, str]]:
    codes: set[tuple[str, str]] = set()
    with CATALOG.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            codes.add((row["shop_type"], row["tradeable_code"]))
    return codes


def load_vanilla_prices() -> dict[tuple[str, str], tuple[int, int]]:
    prices: dict[tuple[str, str], tuple[int, int]] = {}
    with CATALOG.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                prices[(row["shop_type"], row["tradeable_code"])] = (
                    int(row["vanilla_base_purchase"]),
                    int(row["vanilla_base_sell"]),
                )
            except ValueError:
                pass
    return prices


def make_row(code: str, buy: int, sell: int, fame: int, can_buy: str) -> dict[str, str]:
    return {
        "tradeable-code": code,
        "base-purchase-price": str(buy),
        "base-sell-price": str(sell),
        "delta-price": "0.0",
        "can-be-purchased": can_buy,
        "required-famepoints": str(fame),
        "available-after-sale-only": "default",
    }


def empty_traders() -> dict[str, list]:
    return {f"{op}_{suffix}": [] for op in OUTPOSTS for suffix in SHOP_SUFFIXES}


def main() -> None:
    catalog_codes = load_catalog_codes()
    vanilla = load_vanilla_prices()
    base = json.loads(BASE_ECONOMY.read_text(encoding="utf-8"))
    eco = base["economy-override"]
    eco["fully-restock-tradeable-hours"] = "5.0"
    eco["prices-subject-to-delta"] = "0"

    traders = empty_traders()
    changelog: list[dict] = []
    missing: list[str] = []

    for shop, code, table_buy, sell, fame, can_buy in EXPLICIT_OVERRIDES:
        key = (shop, code)
        if key not in catalog_codes:
            missing.append(f"{shop}/{code}")
            continue
        v_buy, v_sell = vanilla.get(key, (-1, -1))
        buy = table_buy
        if can_buy != "false" and shop == "Armory" and is_weapon_or_armor(code):
            buy = weapon_armor_buy(table_buy, v_buy)
        row = make_row(code, buy, sell, fame, can_buy)
        changelog.append(
            {
                "shop_type": shop,
                "tradeable_code": code,
                "vanilla_buy": v_buy,
                "vanilla_sell": v_sell,
                "table_buy": table_buy,
                "new_buy": buy,
                "new_sell": sell,
                "fame": fame,
            }
        )
        for op in OUTPOSTS:
            tid = f"{op}_{shop}"
            traders[tid].append(row.copy())

    for op in OUTPOSTS:
        traders[f"{op}_Armory"].insert(0, KEYCARD.copy())

    eco["traders"] = traders
    OUT_JSON.write_text(json.dumps(base, indent="\t"), encoding="utf-8")

    md = [
        "# Medium trader override changelog (Grok-aligned v2)",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Pricing: Grok medium **sell/fame** table; **weapon & armor buys** = "
        f"max(table, vanilla × {WEAPON_ARMOR_BUY_MULT:.2f}, strictly above vanilla). "
        "Mags/ammo/meds use table buy; C4 line is sell-only.",
        "",
        "## Globals",
        "",
        "| Setting | Value |",
        "|---------|-------|",
        "| `fully-restock-tradeable-hours` | **5.0** |",
        "| `prices-subject-to-delta` | **0** |",
        "",
        f"## Overrides ({len(changelog)} tradeable codes × 4 outposts + Keycard)",
        "",
        "| Shop | Item | Vanilla buy→sell | Table buy | Final buy→sell | Fame |",
        "|------|------|------------------|-----------|----------------|------|",
    ]
    for c in changelog:
        buy_note = ""
        if c["new_buy"] != c["table_buy"]:
            buy_note = f" (was {c['table_buy']})"
        md.append(
            f"| {c['shop_type']} | `{c['tradeable_code']}` | "
            f"{c['vanilla_buy']}→{c['vanilla_sell']} | {c['table_buy']} | "
            f"**{c['new_buy']}**{buy_note}→**{c['new_sell']}** | {c['fame']} |"
        )
    if missing:
        md += ["", "## Not in catalog (skipped)", ""] + [f"- `{m}`" for m in missing]

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"OK: {len(changelog)} items -> {OUT_JSON}")
    if missing:
        print("MISSING:", missing)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
