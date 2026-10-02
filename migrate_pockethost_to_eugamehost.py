"""Copy PhazeOut SCUM Saved data from PocketHost SFTP to EUgameHost SFTP.

Migrates:
  - SCUM/Saved/Config/WindowsServer (ini, json, Loot, Quests, ...)
  - SCUM/Saved/SaveFiles (SCUM.db, db-backups; skips SaveFiles/Logs by default)
  - SCUM/Saved/Metadata.json if present

Does NOT copy game paks (already on EU host).

Stop the EUgameHost SCUM server in TCAdmin before running (database must not be in use).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent
POCKET_CFG = ROOT / ".vscode" / "sftp.pockethost.json.disabled"
EU_CFG = ROOT / ".vscode" / "sftp.json"
import sys

sys.path.insert(0, str(ROOT / "tools"))
from sftp_remote import service_root as eu_service_root_from_cfg

SOURCE_SAVED = "/SCUM/Saved"
SKIP_TOP = {"Crashes", "Logs", "Temp"}
SKIP_SAVEFILES = {"Logs"}


def connect(cfg_path: Path) -> tuple[paramiko.Transport, paramiko.SFTPClient]:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    transport = paramiko.Transport((cfg["host"], int(cfg["port"])))
    transport.banner_timeout = 120
    transport.connect(username=cfg["username"], password=cfg["password"])
    return transport, paramiko.SFTPClient.from_transport(transport)


def eu_service_root(sftp: paramiko.SFTPClient, cfg: dict) -> str:
    return eu_service_root_from_cfg(cfg, sftp)


def ensure_remote_dir(sftp: paramiko.SFTPClient, path: str) -> None:
    parts = [p for p in path.split("/") if p]
    cur = ""
    for part in parts:
        cur += "/" + part
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def walk_remote(sftp: paramiko.SFTPClient, base: str):
    for name in sftp.listdir(base):
        yield base.rstrip("/") + "/" + name, name


def should_skip(rel_parts: list[str]) -> bool:
    if not rel_parts:
        return False
    if rel_parts[0] in SKIP_TOP:
        return True
    if rel_parts[0] == "SaveFiles" and len(rel_parts) > 1 and rel_parts[1] in SKIP_SAVEFILES:
        return True
    if rel_parts[0] == "Config" and rel_parts[1:2] == ["CrashReportClient"]:
        return True
    return False


def migrate_tree(src: paramiko.SFTPClient, dst: paramiko.SFTPClient, src_base: str, dst_base: str) -> dict:
    stats = {"files": 0, "bytes": 0, "dirs": 0, "errors": []}

    def recurse(src_dir: str, dst_dir: str, rel: list[str]) -> None:
        if should_skip(rel):
            return
        ensure_remote_dir(dst, dst_dir)
        for src_path, name in walk_remote(src, src_dir):
            rel_child = rel + [name]
            if should_skip(rel_child):
                continue
            dst_path = dst_dir.rstrip("/") + "/" + name
            try:
                st = src.stat(src_path)
            except OSError as exc:
                stats["errors"].append(f"stat {src_path}: {exc}")
                continue
            if st.st_mode & 0o40000:
                stats["dirs"] += 1
                recurse(src_path, dst_path, rel_child)
            else:
                try:
                    ensure_remote_dir(dst, os.path.dirname(dst_path))
                    with src.open(src_path, "rb") as rf, dst.open(dst_path, "wb") as wf:
                        while True:
                            chunk = rf.read(1024 * 1024)
                            if not chunk:
                                break
                            wf.write(chunk)
                    stats["files"] += 1
                    stats["bytes"] += len(data)
                    if stats["files"] % 50 == 0:
                        print(f"  ... {stats['files']} files ({stats['bytes'] / 1e6:.1f} MB)")
                except OSError as exc:
                    stats["errors"].append(f"copy {src_path} -> {dst_path}: {exc}")

    recurse(src_base, dst_base, [])
    return stats


def main() -> None:
    if not POCKET_CFG.exists():
        raise SystemExit(f"Missing {POCKET_CFG}")
    if not EU_CFG.exists():
        raise SystemExit(f"Missing {EU_CFG}")

    print("Connecting PocketHost...")
    pt, ps = connect(POCKET_CFG)
    print("Connecting EUgameHost...")
    eu_cfg = json.loads(EU_CFG.read_text(encoding="utf-8"))
    et, es = connect(EU_CFG)
    try:
        eu_root = eu_service_root(es, eu_cfg)
        dst_saved = f"{eu_root}/SCUM/Saved"
        print(f"EU destination: {dst_saved}")
        print(f"Source: {SOURCE_SAVED}")
        print("Migrating (server should be STOPPED on EU)...", flush=True)
        for wal in (
            f"{dst_saved}/SaveFiles/SCUM.db-wal",
            f"{dst_saved}/SaveFiles/SCUM.db-shm",
        ):
            try:
                es.remove(wal)
                print(f"Removed stale {wal}", flush=True)
            except OSError:
                pass
        t0 = time.time()
        stats = migrate_tree(ps, es, SOURCE_SAVED, dst_saved)
        elapsed = time.time() - t0
        print(json.dumps({"elapsed_sec": round(elapsed, 1), **stats}, indent=2))
        if stats["errors"]:
            print("First errors:", stats["errors"][:10])
            sys.exit(1)
    finally:
        ps.close()
        pt.close()
        es.close()
        et.close()

    print("\nDone. Start EU server after verifying ServerSettings.ini and SCUM.db.")


if __name__ == "__main__":
    main()
