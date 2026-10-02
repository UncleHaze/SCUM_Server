"""Copy PocketHost SaveFiles (world DB + backups) and Metadata.json to EUgameHost."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent


def connect(cfg_path: Path) -> tuple[paramiko.Transport, paramiko.SFTPClient]:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    transport = paramiko.Transport((cfg["host"], int(cfg["port"])))
    transport.banner_timeout = 120
    transport.connect(username=cfg["username"], password=cfg["password"])
    return transport, paramiko.SFTPClient.from_transport(transport)


def eu_root(sftp: paramiko.SFTPClient, cfg: dict) -> str:
    sys.path.insert(0, str(ROOT / "tools"))
    from sftp_remote import service_root

    return service_root(cfg, sftp)


def copy_file(src: paramiko.SFTPClient, dst: paramiko.SFTPClient, src_p: str, dst_p: str) -> int:
    size = src.stat(src_p).st_size
    print(f"  {src_p} -> {dst_p} ({size / 1e6:.2f} MB)", flush=True)
    with src.open(src_p, "rb") as rf, dst.open(dst_p, "wb") as wf:
        sent = 0
        while True:
            chunk = rf.read(1024 * 1024)
            if not chunk:
                break
            wf.write(chunk)
            sent += len(chunk)
    return sent


def main() -> None:
    pt, ps = connect(ROOT / ".vscode" / "sftp.pockethost.json.disabled")
    eu_cfg_path = ROOT / ".vscode" / "sftp.json"
    et, es = connect(eu_cfg_path)
    eu_cfg = json.loads(eu_cfg_path.read_text(encoding="utf-8"))
    try:
        dst_sf = f"{eu_root(es, eu_cfg)}/SCUM/Saved/SaveFiles"
        src_sf = "/SCUM/Saved/SaveFiles"
        for wal in ("SCUM.db-wal", "SCUM.db-shm"):
            try:
                es.remove(f"{dst_sf}/{wal}")
                print(f"Removed EU {wal}", flush=True)
            except OSError:
                pass
        total = 0
        for name in sorted(ps.listdir(src_sf)):
            if name == "Logs":
                continue
            if name.endswith(("-wal", "-shm")) or name.endswith(".db-wal") or name.endswith(".db-shm"):
                continue
            src_p = f"{src_sf}/{name}"
            dst_p = f"{dst_sf}/{name}"
            if ps.stat(src_p).st_mode & 0o40000:
                continue
            total += copy_file(ps, es, src_p, dst_p)
        meta_src = "/SCUM/Saved/Metadata.json"
        meta_dst = f"{eu_root(es)}/SCUM/Saved/Metadata.json"
        total += copy_file(ps, es, meta_src, meta_dst)
        print(f"Done. {total / 1e6:.2f} MB copied.", flush=True)
    finally:
        ps.close()
        pt.close()
        es.close()
        et.close()


if __name__ == "__main__":
    main()
