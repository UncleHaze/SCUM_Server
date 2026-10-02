# Drifter tier remap (PhazeOut)

## Your base mapping
| Override file | Copy loadout/stats from (vanilla) |
|---------------|-------------------------------------|
| `NPCDrifterCommonData_Lvl_1` | old **Lvl_4** (Deagle, SDASS, M1911 — 220 HP) |
| `NPCDrifterCommonData_Lvl_2` | old **Lvl_4** (same as new Lvl_1) |
| `NPCDrifterCommonData_Lvl_3` | old **Lvl_5** (SMGs/rifles — 240 HP) |
| `NPCDrifterCommonData_Lvl_4` | old **Lvl_5** (same as new Lvl_3) |
| `NPCDrifterCommonData_Lvl_5` | **unchanged** (do not pack override) |

## Variants (included in reference JSON)
| Override | Copy from |
|----------|-----------|
| `Lvl_3_Radiation` | old `Lvl_5_Radiation` |
| `Lvl_4_Radiation` | old `Lvl_5_Radiation` |
| `Lvl_4_AbandonedBunker` | old `Lvl_5_AbandonedBunker` |

## Server install
1. Edit/export `.uasset` using JSON in this folder as the property guide (UAssetGUI).
2. Repak → `PhazeOut_DrifterTierRemap_P.pak`
3. Upload to `SCUM/Content/Paks/Mods/` on EU host; restart server.

## Guards
Mirror under `Armed_NPCs/Guard/NPCGuardCommonData_Lvl_*` if guards should follow the same ladder.

## Note
Encounter still picks `BP_Drifter_Lvl_1` vs `Lvl_5`; this mod changes **what each level means**, not spawn frequency.
