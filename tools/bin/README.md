# Modding tools (local)

| Tool | Path | Version |
|------|------|---------|
| **UAssetGUI** | `UAssetGUI/UAssetGUI.exe` | v1.1.0 (GitHub) |
| **repak** | `repak/repak.exe` | v0.2.3 (GitHub trumank/repak) |

FModel: use your existing install.

## First launch — UAssetGUI

1. Run `UAssetGUI.exe`.
2. Set engine version to **UE 4.27** (matches SCUM).
3. Open exported `.uasset` from FModel (`Export` with `.uexp` enabled).

## repak (after edited files are in `mod_staging`)

From PowerShell:

```powershell
cd "C:\Users\PurpleHaze\Downloads\PhazeOut Scum server\tools\bin\repak"
.\repak.exe --help
.\repak.exe pack --help
```

SCUM may require **AES encryption** on the pak; if the server ignores an unencrypted pak, check repak `pack` options for `--key` / SCUM modding Discord guides and use the same AES key as FModel.

Full workflow: `tools/DRIFTER_TIER_REMAP_MOD.md`
