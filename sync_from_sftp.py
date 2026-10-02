"""Mirror EUgameHost WindowsServer config into this repo (SFTP = source of truth)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent
import sys

sys.path.insert(0, str(ROOT / "tools"))
from sftp_remote import connect as sftp_connect_eu, windows_server_base

# Download to repo root (same layout as server under WindowsServer)
ROOT_FILES = (
    "ServerSettings.ini",
    "EconomyOverride.json",
    "RaidTimes.json",
    "Notifications.json",
    "GameUserSettings.ini",
    "AdminUsers.ini",
    "BannedUsers.ini",
    "WhitelistedUsers.ini",
    "ExclusiveUsers.ini",
    "SilencedUsers.ini",
    "ServerSettingsAdminUsers.ini",
    "Input.ini",
)

REMOTE_DIRS = ("Loot", "Quests")

SKIP_REMOTE_NAMES = {"Input.ini.bak"}

# Local-only paths removed after sync (not on server)
REMOVE_PATHS = [
    "phoenix-analysis",
    "economy_export",
    "economy_overview_for_grok.md",
    "EconomyOverride.proposed.json",
    "EconomyOverride.remote.json",
    "ServerSettings.remote.ini",
    "build_economy_snapshot.py",
    "SCUM-log-tail-remote.txt",
    "fix-broken-mod-remote.mjs",
    "server-cleanup-remote.mjs",
    "list-win64-remote.mjs",
    "disable-ue4ss-remote.mjs",
    "purge-phoenix-remote.mjs",
    "delete-phoenix-remote.mjs",
    "purge_spawnitem_admin_log.py",
    "purge_discord_channels.py",
    "Loot/Types.xml",
    "Loot/Types.sample.xml",
    "Loot/survival_4x_summary.json",
    "Loot/explosive_nerf_summary.json",
    "Loot/puppet_loot_rewards_summary.json",
    "build_loot_types_sample.py",
    "build_loot_types_full.py",
]


def download_dir(sftp: paramiko.SFTPClient, remote_dir: str, local_dir: Path) -> int:
    local_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for name in sftp.listdir(remote_dir):
        if name in SKIP_REMOTE_NAMES:
            continue
        remote_path = f"{remote_dir.rstrip('/')}/{name}"
        local_path = local_dir / name
        try:
            sftp.listdir(remote_path)
        except OSError:
            sftp.get(remote_path, str(local_path))
            count += 1
        else:
            count += download_dir(sftp, remote_path, local_path)
    return count


def main() -> None:
    transport, sftp, cfg = sftp_connect_eu()
    remote_base = windows_server_base(cfg, sftp)
    try:
        files = 0
        for name in ROOT_FILES:
            remote = f"{remote_base}/{name}"
            try:
                sftp.get(remote, str(ROOT / name))
                files += 1
                print(f"OK {name}")
            except OSError as exc:
                print(f"SKIP {name}: {exc}")

        dirs = 0
        for dirname in REMOTE_DIRS:
            remote = f"{remote_base}/{dirname}"
            local = ROOT / dirname
            if local.exists():
                shutil.rmtree(local)
            n = download_dir(sftp, remote, local)
            dirs += n
            print(f"OK {dirname}/ ({n} files)")

        catalog_src = ROOT / "economy_export" / "trader_prices_catalog.csv"
        catalog_dst = ROOT / "data" / "trader_prices_catalog.csv"
        if catalog_src.exists():
            catalog_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(catalog_src, catalog_dst)
            print(f"OK kept catalog -> {catalog_dst.relative_to(ROOT)}")

        removed = 0
        for rel in REMOVE_PATHS:
            path = ROOT / rel
            if not path.exists():
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed += 1
            print(f"RM {rel}")

        print(f"Done: {files} root configs, {dirs} loot/quest files, removed {removed} local-only paths")
    finally:
        sftp.close()
        transport.close()


if __name__ == "__main__":
    main()
