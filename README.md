# PhazeOut SCUM server (config repo)

**GitHub:** [UncleHaze/SCUM_Server](https://github.com/UncleHaze/SCUM_Server) — use this repo for **Cursor Cloud Agents** / phone (`cursor.com/agents`) so mod and config work syncs without Remote Control to your PC.

Clone:

```bash
git clone https://github.com/UncleHaze/SCUM_Server.git
```

Keep **`.vscode/sftp.json`** local only (gitignored) for EUgameHost uploads.

Live dedicated server config is on **EUgameHost** SFTP:

`{remotePath}/SCUM/Saved/Config/WindowsServer/`

Credentials and `remotePath` live in **`.vscode/sftp.json`** (gitignored). VS Code SFTP extension uses the same file.

## Layout

| Path | On server |
|------|-----------|
| `ServerSettings.ini`, `EconomyOverride.json`, `RaidTimes.json`, … | Same filenames at `WindowsServer/` root |
| `Loot/` | `WindowsServer/Loot/` |
| `Quests/` | `WindowsServer/Quests/` |
| `wiki/` | Not on server (wiki.gg only) |
| `build_*.py`, `sync_from_sftp.py` | Local tooling |
| `tools/sftp_remote.py` | Shared EUgameHost path helpers for deploy scripts |
| `data/trader_prices_catalog.csv` | Reference for economy override script (not deployed) |

**Not in repo:** world save (`/SCUM/Saved/SaveFiles/SCUM.db`), game `.pak` files.

**Legacy:** `migrate_pockethost_to_eugamehost.py` / `sync_pocket_savefiles_to_eu.py` are one-off PocketHost → EU migrations only (need `sftp.pockethost.json.disabled` if you still run them).

## Sync from live (SFTP = source of truth)

```bash
python sync_from_sftp.py
```

Downloads root INIs/JSON + full `Loot/` and `Quests/`, removes local-only cruft.

## Common deploy flows

```bash
python build_survival_4x_loot.py --upload    # loot overrides + settings if script supports it
python build_economy_medium_override.py      # writes EconomyOverride.proposed.json
python build_puppet_loot_rewards.py --upload
python Quests/build_phazeout_quest_pack.py --target 600 --upload
```

After editing config locally, upload via SFTP extension or your deploy script, then restart the server.
