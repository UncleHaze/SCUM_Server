"""Sell-price lookup for quest reward balancing."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "trader_prices_catalog.csv"
ECONOMY = ROOT / "EconomyOverride.json"


def load_catalog_sell() -> dict[str, dict[str, int]]:
    by_shop: dict[str, dict[str, int]] = {}
    with CATALOG.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            shop = row["shop_type"]
            code = row["tradeable_code"]
            try:
                sell = int(row["phazeout_sell_override"] or row["vanilla_base_sell"] or 0)
            except ValueError:
                sell = 0
            if sell <= 0:
                continue
            by_shop.setdefault(shop, {})[code] = sell
    return by_shop


def load_economy_sell_median() -> dict[str, int]:
    data = json.loads(ECONOMY.read_text(encoding="utf-8"))
    traders = data.get("economy-override", {}).get("traders", {})
    by_code: dict[str, list[int]] = {}
    for _key, entries in traders.items():
        for ent in entries:
            code = ent.get("tradeable-code")
            if not code:
                continue
            try:
                sell = int(ent.get("base-sell-price", 0))
            except (TypeError, ValueError):
                continue
            if sell <= 0:
                continue
            by_code.setdefault(code, []).append(sell)
    return {c: int(statistics.median(vals)) for c, vals in by_code.items()}


def effective_sell(code: str, shop: str, catalog: dict[str, dict[str, int]], economy: dict[str, int]) -> int:
    if code in economy:
        return economy[code]
    return catalog.get(shop, {}).get(code, 50)
