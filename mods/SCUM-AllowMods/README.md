# scum-allow-mods v0.1.0

A drop-in install bundle that re-enables loading of **unsigned PAK mods** in **SCUM** after the developers blocked the `-fileopenlog` modding workflow in late April 2026.

This bundle contains:
- **UE4SS Experimental v3.0.1-946** (commit `265115c0`) — official upstream release
- The `scum_allow_mods` patch mod (28 KB)
- A pre-configured `UE4SS-settings.ini` with safe hook settings
- Built-in UE4SS mods (all disabled by default)
- Everything else needed — drop into `Win64/`, done

> ⚠️ **USE AT YOUR OWN RISK** — there is no guarantee against future bans. Read the entire README before installing.

---

## What this does

In late April 2026, the SCUM developers neutralized the `-fileopenlog` launch parameter that the modding community had relied on for asset modding. This blocked the engine's PAK signature validation from being bypassed via the CLI flag — meaning unsigned mod-PAKs could no longer be mounted by the game.

This bundle restores PAK modding by patching a UE 4.27.2 engine-internal validation function directly in the running game process:

1. On mod init, an AOB pattern scan locates the validation function in `SCUM.exe`.
2. The pattern matches twice (engine-typical paired prologue); the second match is the real target.
3. `VirtualProtect` opens the page for writing.
4. The first byte of the function is overwritten with `0xC3` (x86 `RET`).
5. The function returns immediately on every invocation — validation never runs — unsigned PAKs mount without rejection.

Verified working on **client** (`SCUM.exe`) — same approach also works on **server** (`SCUMServer.exe`) since both binaries use UE 4.27.2.

---

## Quick install

See **[INSTALL.txt](INSTALL.txt)** at the top level of this bundle for a 6-step quick-start.

---

## Detailed install (Client)

### Step 1 — Disable BattlEye

The Steam launch parameter `-nobattleye` alone is **not enough**. You also need to stop the BattlEye Windows service:

PowerShell as Administrator:
```powershell
Stop-Service -Name BEService -Force
Set-Service -Name BEService -StartupType Disabled
```

If the kernel driver `BEDaisy` keeps loading after a reboot:
```powershell
sc stop BEDaisy
sc config BEDaisy start= disabled
```

### Step 2 — Extract this bundle

Extract everything in this bundle (next to `INSTALL.txt`) directly into:
```
<Steam>/steamapps/common/SCUM/SCUM/Binaries/Win64/
```

After extraction your `Win64/` folder should contain:
```
Win64/
├── dwmapi.dll                      (from this bundle — UE4SS proxy DLL)
├── SCUM.exe                        (already there, game's own)
├── ue4ss/                          (from this bundle)
│   ├── UE4SS.dll
│   ├── UE4SS-settings.ini
│   ├── LICENSE                     (UE4SS license)
│   └── Mods/
│       ├── mods.txt
│       ├── scum_allow_mods/
│       │   ├── dlls/
│       │   │   └── main.dll
│       │   └── enabled.txt
│       └── (UE4SS built-in mods, all disabled by default)
└── (other game files left untouched)
```

### Step 3 — Set Steam launch options

Steam → SCUM → Properties → Launch Options:
```
-nobattleye
```

Do **NOT** add `-fileopenlog` — this mod replaces it.

### Step 4 — Launch SCUM directly

Steam's Play button still triggers the BattlEye launcher even with `-nobattleye`. Bypass it by launching `SCUM.exe` directly:
```
<Steam>/steamapps/common/SCUM/SCUM/Binaries/Win64/SCUM.exe
```

Easiest: create a desktop shortcut to this `SCUM.exe`, or use a Steam Custom Launcher tool.

### Step 5 — Verify the mod loaded

Open `<Win64>/ue4ss/UE4SS.log`. Search for:
```
[ScumAllowMods]: Init.
[ScumAllowMods]: Delegate found and patched.
```

If you see `Delegate not found. Unable to patch.`, the AOB pattern needs to be updated for the current SCUM build — see [Troubleshooting](#troubleshooting).

### Step 6 — Drop in your mods

Place your unsigned `.pak` files into:
```
<Steam>/steamapps/common/SCUM/SCUM/Content/Paks/~mods/
```

Re-launch SCUM. Check `<SCUM>/Saved/Logs/SCUM.log` for:
```
LogPakFile: Display: Mounting pak file ../../../SCUM/Content/Paks/~mods/YourMod_P.pak.
```

If the mount line appears, you're done. Connect to a server that has the same mod-PAKs (hash-match required) and play.

---

## Server-side install

If you run a SCUM dedicated server with custom unsigned mod-PAKs, you also need this mod server-side — otherwise your server's own engine refuses to mount them on boot.

Same procedure, but install to:
```
<ServerInstall>/SCUM/Binaries/Win64/ue4ss/Mods/scum_allow_mods/
```

The `-fileopenlog` flag also still works server-side at the moment, but this mod replaces it cleanly. Pick one — either flag, or this mod, not both.

---

## Important caveats

- **Hash-match required for multiplayer**: When you connect to a server, the server compares your mounted PAK list against its own. If they don't match, you get kicked. Use this on **modded servers** that have matching PAKs, or on your own server.
- **No cheating**: This mod re-enables asset/cosmetic modding only. It does not bypass server authority for gameplay (item spawning, position, stats — those are server-state). Don't expect this to enable cheats.
- **Future SCUM updates may break it**: If the developers refactor the validated function, the AOB pattern needs updating. PRs welcome.
- **No ban guarantee**: BattlEye is disabled while running this. Theoretically the developers could add server-side detection of modified clients in future updates.

---

## Troubleshooting

### `Delegate not found. Unable to patch.` in UE4SS.log

The AOB pattern didn't match in the current `SCUM.exe`. A SCUM update changed the validation function's prologue. To fix:
1. Open `SCUM.exe` in IDA / Ghidra.
2. Find the function with the original prologue pattern (search for the disassembly shape: `gs:[0x58]` TLS access followed by indexed reads).
3. Update the AOB string in the source `dllmain.cpp` and rebuild.

See the GitHub repository for the source code and build instructions.

### Game crashes with `EXCEPTION_ACCESS_VIOLATION`

Most often this is **not** caused by this mod, but by UE4SS itself. The bundle's `UE4SS-settings.ini` has all the recommended fixes pre-applied (all hooks off, `bUseUObjectArrayCache = false`, `EngineVersionOverride` set to 4.27). If you still get crashes:

1. Delete `<Win64>/ue4ss/UE4SS_Cache_*.bin` (force fresh AOB scan).
2. Verify all `Hook*` settings in `<Win64>/ue4ss/UE4SS-settings.ini` are `0` (you may have edited them).
3. If you installed other UE4SS mods, disable them one by one in `mods.txt` to find the culprit.

### Mod loads but my PAK isn't mounted

Check `SCUM.log` (in `<SCUM>/Saved/Logs/`):
- `Found Pak file ... attempting to mount.` — engine sees your PAK.
- `Mounting pak file ...` — actual mount happened. ✅
- Anything mentioning `signature`, `rejected`, `failed`, or `invalid` — the patch isn't taking effect. Re-verify UE4SS.log shows `Delegate found and patched`.

If the PAK file isn't even seen by the engine, double-check the path:
```
<Steam>/steamapps/common/SCUM/SCUM/Content/Paks/~mods/YourMod_P.pak
```

The `~mods` folder must exist; the underscore-suffix `_P` on the file name is required by UE4 for mod PAKs.

### BattlEye keeps reactivating after reboot

If the BE service starts back up:
1. Confirm `Set-Service -Name BEService -StartupType Disabled` ran successfully.
2. Check `services.msc` — BE Service status should be "Disabled".
3. Some games re-install the BE service via Steam validation. If you ran "Verify Integrity of Game Files", BE may have been restored. Re-disable it.

### Steam still launches BattlEye

The `-nobattleye` Steam launch option only suppresses Steam's wrapper — Steam itself may still trigger the BE launcher. Solution:
- Launch `SCUM.exe` directly (not through Steam's Play button).
- Use a Steam Custom Launcher tool that bypasses the wrapper.

---

## Credits

- **Narknon** & **Truman** — Original [AllowModsMod](https://github.com/narknon/AllowModsMod) for PAYDAY 3, whose architecture and patch approach inspired this bundle.
- **UE4SS-RE Team** — [RE-UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) framework (Experimental v3.0.1-946 included).
- **SKRYPT Community** — SCUM-specific AOB pattern extraction + verification.

---

## Licenses

- **scum_allow_mods**: MIT — see [LICENSE](LICENSE) at top level.
- **UE4SS framework**: see `ue4ss/LICENSE`.
