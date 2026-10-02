"""Build Notifications.json for SCUM scheduled restart warnings.

EUgameHost reboots on **even hours** on the dedicated server clock path we target below
(panel schedule: every 2h). SCUM matches `Notifications.json` `time` entries to the
**VM OS clock** (EU PhazeOut host ≈ **UTC**).

If warnings say “60 minutes” exactly when the server reboots, restart hours were modeled
1h off (odd local hours + panel +1h guess). Use **even** `Europe/Amsterdam` hours so
warnings line up with real reboots.

Run: python tools/build_restart_notifications.py
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
OUT_PATHS = (
    REPO / "WindowsServer" / "Notifications.json",
    REPO / "Notifications.json",
)

# VM clock for Notifications.json (EUgameHost ≈ UTC).
SERVER_TZ = ZoneInfo("UTC")
# When the server actually goes down for you in Amsterdam.
RESTART_TZ = ZoneInfo("Europe/Amsterdam")

# When the host actually reboots (even hours, local Amsterdam — matches panel in practice).
RESTART_HOURS = tuple(range(0, 24, 2))  # 0, 2, 4, …, 22

WARN_MINUTES = (90, 60, 30, 10, 5, 1)
MESSAGES = {m: f"Server restart in {m} minutes" for m in WARN_MINUTES}
COLORS = {
    90: "255-200-100",
    60: "255-180-80",
    30: "255-165-0",
    10: "255-140-0",
    5: "255-69-0",
    1: "255-0-0",
}
DURATIONS = {90: 18, 60: 16, 30: 15, 10: 15, 5: 10, 1: 20}


def warning_clock_times(minutes_before: int) -> list[str]:
    seen: set[str] = set()
    base = datetime(2026, 9, 28, tzinfo=RESTART_TZ)
    for hour in RESTART_HOURS:
        restart = base.replace(hour=hour, minute=0, second=0, microsecond=0)
        warn = restart - timedelta(minutes=minutes_before)
        on_server = warn.astimezone(SERVER_TZ)
        seen.add(on_server.strftime("%H:%M"))
    return sorted(seen)


def build_notifications() -> dict:
    notifications = []
    for mins in WARN_MINUTES:
        notifications.append(
            {
                "day": "Everyday",
                "time": warning_clock_times(mins),
                "duration": DURATIONS[mins],
                "color": COLORS[mins],
                "message": MESSAGES[mins],
            }
        )
    return {"Notifications": notifications}


def upload_eu() -> None:
    import sys

    sys.path.insert(0, str(REPO / "tools"))
    from sftp_remote import connect as sftp_connect_eu, windows_server_base

    transport, sftp, cfg = sftp_connect_eu()
    try:
        remote = f"{windows_server_base(cfg, sftp)}/Notifications.json"
        sftp.put(str(OUT_PATHS[0]), remote)
        print(f"SFTP: uploaded -> {remote}")
    finally:
        sftp.close()
        transport.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true", help="Push WindowsServer/Notifications.json to EU host")
    args = parser.parse_args()

    doc = build_notifications()
    text = json.dumps(doc, indent="\t") + "\n"
    for path in OUT_PATHS:
        path.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT_PATHS[0]}")
    print(
        f"Restarts @ {RESTART_HOURS} {RESTART_TZ.key} -> {SERVER_TZ.key} notify:"
    )
    for block in doc["Notifications"]:
        print(f"  {block['message']}: {', '.join(block['time'])}")

    if args.upload:
        upload_eu()


if __name__ == "__main__":
    main()
