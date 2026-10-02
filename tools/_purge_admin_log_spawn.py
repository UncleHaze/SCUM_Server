"""One-off: delete today's admin-log messages containing 'spawn' (embeds included)."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

CHANNEL = "1548397651693674573"  # 💬┃admin-log
DAY_PREFIX = "2026-10-01"
KEYWORD = re.compile(r"spawn", re.I)


def load_token() -> str:
    cfg = json.loads(Path.home().joinpath(".cursor", "mcp.json").read_text(encoding="utf-8"))
    return cfg["mcpServers"]["discord"]["env"]["DISCORD_TOKEN"]


def api(token: str, method: str, url: str, data: dict | None = None):
    headers = {"Authorization": f"Bot {token}", "User-Agent": "PhazeOutAdminLogCleanup/1.0"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        if resp.status == 204:
            return None
        raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else None


def _component_text(component: dict) -> str:
    parts: list[str] = []
    if component.get("content"):
        parts.append(str(component["content"]))
    for child in component.get("components") or []:
        parts.append(_component_text(child))
    return "\n".join(parts)


def message_text(message: dict) -> str:
    parts = [message.get("content") or ""]
    for emb in message.get("embeds") or []:
        for key in ("title", "description", "url"):
            if emb.get(key):
                parts.append(str(emb[key]))
        for field in emb.get("fields") or []:
            parts.append(field.get("name") or "")
            parts.append(field.get("value") or "")
    for component in message.get("components") or []:
        parts.append(_component_text(component))
    return "\n".join(parts)


def fetch_recent(token: str) -> list[dict]:
    out: list[dict] = []
    before: str | None = None
    while True:
        url = f"https://discord.com/api/v10/channels/{CHANNEL}/messages?limit=100"
        if before:
            url += f"&before={before}"
        batch = api(token, "GET", url)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        before = batch[-1]["id"]
        if batch[-1]["timestamp"] < f"{DAY_PREFIX}T00:00:00.000000+00:00":
            break
    return out


def main() -> None:
    token = load_token()
    messages = fetch_recent(token)
    today = [m for m in messages if m.get("timestamp", "").startswith(DAY_PREFIX)]
    targets = [m for m in today if KEYWORD.search(message_text(m))]
    print(f"Today: {len(today)} messages; deleting {len(targets)} containing 'spawn'")
    for m in targets:
        api(token, "DELETE", f"https://discord.com/api/v10/channels/{CHANNEL}/messages/{m['id']}")
        time.sleep(0.35)
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}") from e
