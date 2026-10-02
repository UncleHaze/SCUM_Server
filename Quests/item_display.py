"""Map spawn / tradeable codes to player-facing item names for quest text."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT.parent / "data" / "trader_prices_catalog.csv"
DISPLAY_JSON = ROOT / "data" / "item_display_names.json"
OVERRIDES_JSON = ROOT / "data" / "item_display_overrides.json"

_VEHICLE = {
    "WW": "Wolfs Wagen",
    "BPC": "City Bike",
    "RIS": "RIS",
    "Laika": "Laika",
    "Rager": "Rager",
    "Dirtbike": "Dirtbike",
    "Cruiser": "Cruiser",
    "SidecarBike": "Sidecar Bike",
    "Tractor": "Tractor",
    "Dinghy": "Dinghy",
}

_ACRONYM = {
    "ICU": "Engine Control Unit",
    "WW": "Wolfs Wagen",
    "BPC": "City Bike",
    "RIS": "RIS",
    "BP": "Blueprint",
    "1H": "One-Handed",
    "2H": "Two-Handed",
}


def _load_overrides() -> dict[str, str]:
    if OVERRIDES_JSON.is_file():
        return json.loads(OVERRIDES_JSON.read_text(encoding="utf-8"))
    return {}


def _split_camel(token: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", token)


def _title_words(tokens: list[str]) -> str:
    out: list[str] = []
    for t in tokens:
        if not t or t in ("Item",):
            continue
        t = _split_camel(t)
        for piece in t.split():
            if piece in _ACRONYM:
                out.append(_ACRONYM[piece])
                continue
            if piece in _VEHICLE:
                out.append(_VEHICLE[piece])
                continue
            if re.fullmatch(r"\d+[a-z]?", piece, re.I):
                continue
            out.append(piece.replace("-", " "))
    s = " ".join(out)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return "Supplies"
    return s[0].upper() + s[1:] if len(s) > 1 else s.upper()


def _format_servicebp(code: str) -> str:
    body = code[len("ServiceBP_") :]
    m = re.match(r"^(Install|Repair)_(?:BP_)?(.+)$", body, re.I)
    if not m:
        return _format_generic(code)
    action, rest = m.group(1), m.group(2)
    tokens = [t for t in rest.split("_") if t and t not in ("BP", "Item")]
    if "ICU" in tokens:
        idx = tokens.index("ICU")
        if idx > 0 and tokens[idx - 1].lower() == "engine":
            tokens = tokens[: idx - 1] + ["Engine Control Unit"] + tokens[idx + 1 :]
        else:
            tokens[idx : idx + 1] = ["Engine Control Unit"]
    label = _title_words(tokens)
    if action.lower() == "install":
        return f"Vehicle install kit ({label})"
    return f"Vehicle repair kit ({label})"


def _format_generic(code: str) -> str:
    tokens = code.split("_")
    if tokens and tokens[-1].isdigit() and len(tokens[-1]) <= 2:
        tokens = tokens[:-1]
    if len(tokens) >= 2 and tokens[-2].lower() == tokens[-1].lower():
        tokens = tokens[:-1]
    return _title_words(tokens)


def display_name_for_code(code: str) -> str:
    if code.startswith("ServiceBP_"):
        return _format_servicebp(code)
    return _format_generic(code)


def build_display_name_map() -> dict[str, str]:
    import csv

    codes: set[str] = set()
    with CATALOG.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            codes.add(row["tradeable_code"])
    overrides = _load_overrides()
    mapping = {c: overrides.get(c, display_name_for_code(c)) for c in sorted(codes)}
    return mapping


def load_display_names() -> dict[str, str]:
    if not DISPLAY_JSON.is_file():
        refresh_display_names_cache()
    return json.loads(DISPLAY_JSON.read_text(encoding="utf-8"))


def refresh_display_names_cache() -> None:
    DISPLAY_JSON.parent.mkdir(parents=True, exist_ok=True)
    mapping = build_display_name_map()
    DISPLAY_JSON.write_text(json.dumps(mapping, indent="\t") + "\n", encoding="utf-8")


def display_name(code: str, cache: dict[str, str] | None = None) -> str:
    if cache is None:
        cache = load_display_names()
    return cache.get(code, display_name_for_code(code))


def fetch_tracking_caption(verb: str, code: str, num: int, cache: dict[str, str] | None = None) -> str:
    """Requirement line — item name only; SCUM appends ×RequiredNum in the UI."""
    del num  # quantity shown once by the game client
    name = display_name(code, cache)
    return f"{verb} {name}"


def servicebp_player_blurb() -> str:
    return (
        "Service kits are workshop items used on vehicles to install or repair a specific part "
        "(not generic loot)."
    )
