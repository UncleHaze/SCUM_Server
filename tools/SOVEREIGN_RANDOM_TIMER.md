# Random spawn interval (15–90 min) — no Unreal, no Discord

You **can** do this yourself: **UAssetGUI** edits bytecode (via JSON). Unreal is optional.

## What we change

1. **Init timer** (`K2_SetTimerDelegate`): `1.0` + **loop on** → **Random 900–5400 s** + **loop off**
2. **Start of each spawn pass**: schedule the **next** random timer (same range) before the player loop runs

That gives a **new random wait** after every spawn attempt, not a fixed tick.

## Steps

1. **Backup**
   - `Sovereign_Manager.uasset` + `.uexp` (e.g. under `SpawnNPC\Content\MOD\The_Island\`)

2. **UAssetGUI** (engine **4.27**)
   - Open `Sovereign_Manager.uasset`
   - Export full asset to JSON (menu varies by version: **File → Export JSON** or save as `.json` via UAssetAPI JSON export if available)
   - Save as e.g. `Sovereign_Manager.export.json`

3. **Patch** (UAssetAPI JSON from UAssetGUI — your `Sovereign_Manager.json`):

   ```powershell
   cd "C:\Users\PurpleHaze\Downloads\PhazeOut Scum server"
   python tools\patch_sovereign_uassetapi_json.py "C:\...\The_Island\Sovereign_Manager.json"
   ```

   Output: `Sovereign_Manager.patched.json` (same folder)

4. **UAssetGUI**
   - Open the **patched** JSON (or import into a copy of the asset)
   - **Save** → writes `.uasset` / `.uexp` next to the JSON or overwrite your mod copy
   - Re-open the `.uasset` once to confirm no save errors

5. **Repack** → EU server `Mods` / `~mods` → restart

## UAssetGUI cannot edit ScriptBytecode in the UI

Use **JSON out → Python patch → JSON in**:

```powershell
$root = "C:\Users\PurpleHaze\Downloads\PhazeOut Scum server"
$gui  = "$root\tools\bin\UAssetGUI\UAssetGUI.exe"
$dir  = "$root\mod_staging\Sovereign_reference\SCUM\Content\MOD\The_Island"

& $gui tojson "$dir\Sovereign_Manager.uasset" "$root\mod_staging\Sovereign_Manager.work.json" VER_UE4_27
python "$root\tools\patch_sovereign_uassetapi_json.py" "$root\mod_staging\Sovereign_Manager.work.json" "$root\mod_staging\Sovereign_Manager.timer.json"
python "$root\tools\patch_sovereign_cluster.py" "$root\mod_staging\Sovereign_Manager.timer.json" "$root\mod_staging\Sovereign_Manager.final.json"
& $gui fromjson "$root\mod_staging\Sovereign_Manager.final.json" "$dir\Sovereign_Manager.uasset" VER_UE4_27
```

Cluster sizes: edit `CLUSTER_MIN` / `CLUSTER_MAX` at the top of `tools/patch_sovereign_cluster.py`.

## If export JSON is awkward

Manual bytecode (Export **1** → **ScriptBytecode**):

- Find **`K2_SetTimerDelegate`**: change **`1.0`** → use **`RandomFloatInRange(900, 5400)`** as the time pin; change **`True`** → **`False`**
- At the **start of the spawn pass** (before **`Temp_int_Loop_Counter_Variable = 0`**), add another **`K2_SetTimerDelegate`** with the same random range and **loop off** (reuse **`K2Node_CreateDelegate_OutputDelegate`** from init)

## Tune range

Edit `MIN_SEC` / `MAX_SEC` at the top of `tools/patch_sovereign_random_timer.py` (seconds).

## Still do on class defaults (Export 13)

- Empty **Map of Zombies**, keep **ArmedDrifters**, **Max NPCs** 12–20
- Ensure **prisoner** spawn path uses **ArmedDrifters** (Export 1 bytecode), not an empty zombie map
