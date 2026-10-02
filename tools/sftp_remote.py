"""EUgameHost SFTP paths — read `.vscode/sftp.json` (remotePath + credentials)."""
from __future__ import annotations

import json
from pathlib import Path

import paramiko

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / ".vscode" / "sftp.json"


def load_config(path: Path | None = None) -> dict:
    path = path or DEFAULT_CONFIG
    return json.loads(path.read_text(encoding="utf-8"))


def connect(
    cfg: dict | None = None,
    *,
    config_path: Path | None = None,
) -> tuple[paramiko.Transport, paramiko.SFTPClient, dict]:
    cfg = cfg or load_config(config_path)
    transport = paramiko.Transport((cfg["host"], int(cfg["port"])))
    transport.banner_timeout = 120
    transport.auth_timeout = 120
    transport.connect(username=cfg["username"], password=cfg["password"])
    sftp = paramiko.SFTPClient.from_transport(transport)
    return transport, sftp, cfg


def service_root(cfg: dict, sftp: paramiko.SFTPClient | None = None) -> str:
    """Instance folder on SFTP (e.g. `/8979 - 82_153_118_107_8107`)."""
    rp = (cfg.get("remotePath") or "").strip().rstrip("/")
    if rp:
        return rp if rp.startswith("/") else f"/{rp}"
    if sftp is None:
        raise ValueError("sftp.json needs remotePath, or pass an open SFTP client")
    names = sftp.listdir("/")
    if len(names) != 1:
        raise SystemExit(f"Expected one service folder at SFTP root, got: {names}")
    return f"/{names[0]}"


def windows_server_base(cfg: dict, sftp: paramiko.SFTPClient | None = None) -> str:
    return f"{service_root(cfg, sftp)}/SCUM/Saved/Config/WindowsServer"


def loot_base(cfg: dict, sftp: paramiko.SFTPClient | None = None) -> str:
    return f"{windows_server_base(cfg, sftp)}/Loot"


def quests_base(cfg: dict, sftp: paramiko.SFTPClient | None = None) -> str:
    return f"{windows_server_base(cfg, sftp)}/Quests"
