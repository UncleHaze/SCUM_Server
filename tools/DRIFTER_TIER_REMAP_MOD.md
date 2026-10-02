# PhazeOut: Drifter tier remap → server `.pak` mod

Turn `fmodel_exports/Drifter_tier_remap/*.json` into a working override on EUgameHost.

## What you are building

Override **`NPCDrifterCommonData_Lvl_*`** assets so spawn level stays vanilla, but loadout/HP match the remap table in `Drifter_tier_remap/README.md`.

**Lvl 5 base file is not overridden** (stays vanilla).

---

## Tools (install once)

| Tool | Purpose |
|------|---------|
| **FModel** | Export vanilla `.uasset` / `.uexp` |
| **UAssetGUI** | Edit properties (UE **4.27**) — https://github.com/atenfyr/UAssetGUI/releases |
| **RePak** (or SCUM modding repack tool your tutorial uses) | Build `*_P.pak` |
| **SCUM AES key** | Same key as FModel (for repak if your tool requires encryption) |

Watch one end-to-end SCUM pak mod video first (FModel → UAssetGUI → repak) so clicks are familiar.

Your server already loads mods from:

`SCUM/Content/Paks/Mods/`  
(with `SCUM_UnofficialEditorModLoader_P.pak` present)

---

## Step 1 — Export vanilla binaries from FModel

For **each override** below, select the asset in FModel → **Export** → enable **`.uasset` + `.uexp`** (not JSON-only).

Export these **vanilla sources** (read-only reference):

- `NPCDrifterCommonData_Lvl_3` (source for new Lvl_1)
- `NPCDrifterCommonData_Lvl_4` (source for new Lvl_2)
- `NPCDrifterCommonData_Lvl_5` (source for new Lvl_3 and Lvl_4)
- `NPCDrifterCommonData_Lvl_5_Radiation` (for Lvl_3/4 radiation overrides)
- `NPCDrifterCommonData_Lvl_5_AbandonedBunker` (for Lvl_4 bunker override)

Export these **targets** (you will replace their contents):

- `NPCDrifterCommonData_Lvl_1`
- `NPCDrifterCommonData_Lvl_2`
- `NPCDrifterCommonData_Lvl_3`
- `NPCDrifterCommonData_Lvl_4`
- `NPCDrifterCommonData_Lvl_3_Radiation`
- `NPCDrifterCommonData_Lvl_4_Radiation`
- `NPCDrifterCommonData_Lvl_4_AbandonedBunker`

Path in FModel:

`ConZ_Files/Characters/NPCs/Armed_NPCs/Drifter/`

---

## Step 2 — Edit (easiest method: “copy tier file → rename package”)

For each row in the remap table, **copy the source `.uasset` + `.uexp`** and rename to the **target** filename, then fix the internal asset name in UAssetGUI.

Example: **new Lvl_1** = old Lvl 3 loadout

1. Copy `NPCDrifterCommonData_Lvl_3.uasset` + `.uexp` → `NPCDrifterCommonData_Lvl_1.uasset` + `.uexp`
2. Open **`NPCDrifterCommonData_Lvl_1.uasset`** in **UAssetGUI** (engine **4.27**).
3. Change **Name** / **Package** / top-level object name from `NPCDrifterCommonData_Lvl_3` → `NPCDrifterCommonData_Lvl_1` (must match filename).
4. Save.

Repeat:

| Target files | Copy from vanilla export |
|--------------|-------------------------|
| `Lvl_1` | `Lvl_3` |
| `Lvl_2` | `Lvl_4` |
| `Lvl_3` | `Lvl_5` |
| `Lvl_4` | `Lvl_5` |
| `Lvl_3_Radiation` | `Lvl_5_Radiation` |
| `Lvl_4_Radiation` | `Lvl_5_Radiation` |
| `Lvl_4_AbandonedBunker` | `Lvl_5_AbandonedBunker` |

**Check:** Open remapped JSON in `fmodel_exports/Drifter_tier_remap/` and spot-check **MaxHealth** and first weapon path match UAssetGUI after save.

**Alternative:** Open target uasset and manually paste **PossibleItemInHands** / **MaxHealth** from JSON (slower, same result).

---

## Step 3 — Stage folder for repak

Create this tree (project folder `mod_staging/DrifterTierRemap/`):

```text
SCUM/Content/ConZ_Files/Characters/NPCs/Armed_NPCs/Drifter/
  NPCDrifterCommonData_Lvl_1.uasset
  NPCDrifterCommonData_Lvl_1.uexp
  NPCDrifterCommonData_Lvl_2.uasset
  NPCDrifterCommonData_Lvl_2.uexp
  NPCDrifterCommonData_Lvl_3.uasset
  NPCDrifterCommonData_Lvl_3.uexp
  NPCDrifterCommonData_Lvl_4.uasset
  NPCDrifterCommonData_Lvl_4.uexp
  NPCDrifterCommonData_Lvl_3_Radiation.uasset
  NPCDrifterCommonData_Lvl_3_Radiation.uexp
  NPCDrifterCommonData_Lvl_4_Radiation.uasset
  NPCDrifterCommonData_Lvl_4_Radiation.uexp
  NPCDrifterCommonData_Lvl_4_AbandonedBunker.uasset
  NPCDrifterCommonData_Lvl_4_AbandonedBunker.uexp
```

Do **not** include Lvl_5 unless you change it later.

---

## Step 4 — Build the pak

1. Use your repack tool to pack the **`SCUM/`** folder into:

   **`PhazeOut_DrifterTierRemap_P.pak`**

   Name must end with **`_P.pak`** (SCUM convention).

2. If the tool asks for **UE version**, use **4.27**.

3. If the server does not load the pak, check EUgameHost docs for **mod loader / startup flags** (your host already runs other `_P.pak` mods).

Reference: open **`SCUM_SpawnSovereign_P.pak`** from your server in FModel — same kind of small override pak.

---

## Step 5 — Upload & test (PhazeOut EU)

1. SFTP upload to:

   `.../8979 - 82_153_118_107_8107/SCUM/Content/Paks/Mods/PhazeOut_DrifterTierRemap_P.pak`

2. **Restart** the dedicated server.

3. In-game: trigger a **low-tier** drifter spawn (old Lvl 1 area). They should carry **old Lvl 3** guns (M1911 / M1887 / DT11B / Hunter85), not bows.

4. **Rollback:** remove the pak from `Mods/` and restart.

---

## Guards (optional second pak)

Same remap under:

`ConZ_Files/Characters/NPCs/Armed_NPCs/Guard/NPCGuardCommonData_Lvl_*`

Export/edit/repak the same way, or include in the same pak under `Guard/`.

---

## Regenerate JSON reference after game updates

```powershell
python tools/build_drifter_tier_remap_json.py
```

Re-export from FModel if SCUM patches — then redo uasset overrides.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Server starts but no change | Wrong path inside pak; must be `SCUM/Content/ConZ_Files/...`, not `Content/...` only |
| UAssetGUI crash | Set engine **4.27**; export again from FModel |
| CTD on join | Bad uasset rename — package name must match file name |
| Bows still appear | Wrong variant asset (bunker/radiation) not overridden; or Guard NPCs not remapped |

When Step 2 is done for **Lvl_1**, say what UAssetGUI shows for **MaxHealth** and we can verify before you repak all seven files.
