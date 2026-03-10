# Remote File Cache SOP — Detailed Build Plan

## Concept

A SOP-level subnet HDA that wraps a File Cache SOP internally. All essential File Cache
parameters are bubbled up. Our remote-packaging parameters (shot name, verify, package)
are bolted on top. The artist uses it like a File Cache SOP and gets remote packaging for free.

## HDA Definition

- **Type:** SOP subnet
- **Name:** `remote_file_cache` (label: "Remote File Cache")
- **Context:** SOP
- **License:** Indie (`.hdalc`)
- **Internal structure:**
  ```
  Remote File Cache (subnet)
  └── filecache1 (File Cache SOP)   ← input wired from subnet input 0
                                     ← output wired to subnet output 0
  ```
- **Pass-through:** Subnet input 0 → filecache1 input 0, filecache1 output → subnet output 0

## Parameters

### Bubbled-Up File Cache Parameters

These are promoted from the internal `filecache1` node. The artist interacts with them
exactly as they would on a normal File Cache SOP.

**Top-level:**
| Internal Name | Label | Type | Default |
|---------------|-------|------|---------|
| `loadfromdisk` | Load from Disk | Toggle | False |
| `filemethod` | File Path | Menu | 0 (Constructed) |
| `timedependent` | Time Dependent Cache | Toggle | True |
| `basename` | Base Name | String | `$HIPNAME.$OS` |
| `filetype` | File Type | Menu | 0 (`.bgeo.sc`) |
| `file` | Geometry File | String | (explicit path) |
| `basedir` | Base Folder | String | `$HIP/geo` |
| `enableversion` | Enable Version | Toggle | True |
| `version` | Version | Int | 1 |

**Caching folder:**
| Internal Name | Label | Type | Default |
|---------------|-------|------|---------|
| `execute` | Save to Disk | Button | — |
| `cookoutputnode` | Save to Disk in Background | Button | — |
| `trange` | Evaluate As | Menu | 1 (Frame Range) |
| `cachesim` | Simulation | Toggle | True |
| `f1` / `f2` / `f3` | Start/End/Inc | Float×3 | scene range |
| `substeps` | Substeps | Int | 1 |

**Advanced → Save (key ones):**
| Internal Name | Label | Type | Default |
|---------------|-------|------|---------|
| `savebackground` | Save in Background | Toggle | True |
| `mkpath` | Create Intermediate Directories | Toggle | True |
| `initsim` | Initialize Simulation OPs | Toggle | False |

**Advanced → Load (key ones):**
| Internal Name | Label | Type | Default |
|---------------|-------|------|---------|
| `missingframe` | Missing Frame | Menu | 1 |
| `loadtype` | Load | Menu | 0 (All Geometry) |

### Our Remote Packaging Parameters

Added in a new folder tab called "Remote Package".

| Internal Name | Label | Type | Default | Notes |
|---------------|-------|------|---------|-------|
| `shot_name` | Shot Name | String | "" | Validated on change |
| `pod` | Pod | Int | 1 | |
| `team` | Team | Int | 1 | |
| `ver` | Version | Int | 1 | Formatted as v001 |
| `btn_verify` | Verify | Button | — | Dry-run checks |
| `btn_package` | Package | Button | — | Full packaging |
| `verified` | (hidden) | Toggle | 0 | Reset on field change |
| `log_output` | Log | String (multiline) | "" | Status/log display |

## Pipeline Steps

### Verify (dry-run)

1. **Shot name valid** — reuse `validator.validate_shot_name()`
2. **HIP file saved** — reuse `validator.validate_hip_saved()`
3. **Internal File Cache check** — confirm filecache1 exists, has valid params
4. **Frame range sanity** — start ≤ end, increment > 0
5. **Background save warning** — warn if `savebackground` is on (hbatch needs blocking)

Log results to `log_output`. Set `verified` flag.

### Package (full run)

1. **Validate** — same checks as Verify, abort on failure
2. **Create dirs** — `$HIP/{folder_name}/` with `Cache/`, `Scenes/`, `Scripts/`
   - `folder_name` = `{shot_name}_P{pod}T{team}_v{NNN}` (same pattern as render packager)
   - `.placeholder` files for Google Drive sync
3. **Backup .hip** — zip current `.hip` to `{folder_name}/{shot_name}_original.hip.zip`
4. **Save portable .hip** — save a copy to `Scenes/{shot_name}.hip`
   - In the saved copy, rewrite filecache1's output path to `$HIP/{folder_name}/Cache/...`
   - Ensure `savebackground` is OFF in the saved copy
   - Ensure `loadfromdisk` is OFF in the saved copy (so it cooks, not loads)
5. **Write `cache_info.txt`** — machine-readable metadata at `{folder_name}/cache_info.txt`
6. **Write `run_cache.sh`** — hbatch launch script at `Scripts/run_cache.sh`
7. **Write manifest** — human-readable report at `{folder_name}/{shot_name}_manifest.txt`

## Output Structure

```
$HIP/{shot_name}_P{pod}T{team}_v{NNN}/
├── Cache/                              ← sim output lands here when run remotely
├── Scenes/
│   └── {shot_name}.hip                 ← portable .hip copy (paths rewritten)
├── Scripts/
│   └── run_cache.sh                    ← hbatch launch script
├── cache_info.txt                      ← machine-readable metadata
├── {shot_name}_manifest.txt            ← human-readable report
└── {shot_name}_original.hip.zip        ← backup of original .hip
```

## File Formats

### cache_info.txt
```
shot_name=explosion_v003
folder_name=explosion_v003_P1T1_v001
startframe=1001
endframe=1200
frameinc=1
substeps=1
framecount=200
cache_format=.bgeo.sc
cache_node_path=/obj/geo1/remote_file_cache1/filecache1
cache_output_pattern=Cache/{basename}.{frame}.bgeo.sc
hipfile=Scenes/explosion_v003.hip
houdini_version=21.0.631
generated_at=2026-03-09T14:30:00
```

### run_cache.sh
```bash
#!/bin/bash
# Remote File Cache — hbatch launcher
# Shot: explosion_v003
# Generated: 2026-03-09T14:30:00

set -e
cd "$(dirname "$0")/.."

echo "Starting cache: explosion_v003"
echo "Frames: 1001-1200"
echo "Node: /obj/geo1/remote_file_cache1/filecache1"

hbatch -c "mread Scenes/explosion_v003.hip; render -f 1001 1200 /obj/geo1/remote_file_cache1/filecache1; quit"

echo "Cache complete."
```

### Manifest
Same format as render packager manifest — human-readable with:
- Shot name, Houdini version, timestamp
- Frame range
- Cache format and output pattern
- File sizes (of .hip, zip backup)
- Warnings collected during packaging
- Elapsed time

## Module Structure

### New modules (src/)
| Module | Purpose |
|--------|---------|
| `cache_validator.py` | Validate File Cache SOP exists, params sane, background save warning |
| `cache_auditor.py` | Read frame range, format, output path, substeps from File Cache node |
| `cache_scene_writer.py` | Save .hip copy with rewritten cache output path |
| `cache_script_writer.py` | Generate `run_cache.sh` |
| `cache_info_writer.py` | Generate `cache_info.txt` |

### Reused modules (src/)
| Module | What's reused |
|--------|---------------|
| `validator.py` | `validate_shot_name()`, `validate_hip_saved()` |
| `platform_utils.py` | `ensure_dir()`, `normalize_path()`, `check_disk_space()` |
| `manifest.py` | Adapt `ManifestData` / `write_manifest()` for cache metadata |

### HDA scripts (hda_scripts/ or embedded in HDA)
| File | Purpose |
|------|---------|
| `PythonModule.py` | All callback logic (verify, package, field changed) |
| `OnCreated.py` | Auto-wire into SOP network, set color, create network box |
| `btn_verify.py` | `hou.phm().on_verify_clicked(kwargs)` |
| `btn_package.py` | `hou.phm().on_package_clicked(kwargs)` |

## HDA OnCreated Behavior

1. Check if inside a SOP network (`parent.childTypeCategory() == hou.sopNodeTypeCategory()`)
2. If a node was selected, connect it to our input 0
3. Set node color (different from render packager — maybe orange/amber for sim)
4. Create network box with label "Remote File Cache"
5. Open parameter pane

## Scene Writer — Path Rewriting Strategy

The key challenge: rewrite the File Cache output in the saved `.hip` so caches land
in the portable folder, without modifying the artist's live scene.

**Approach:**
1. Temporarily change filecache1's output path to the remote-friendly path
2. `hou.hipFile.save(portable_hip_path)`
3. Immediately revert filecache1's output path back to original
4. Also set `savebackground` = OFF and `loadfromdisk` = OFF in the temp save

**Remote-friendly path rewriting:**
- If filemethod = "Constructed":
  - Set `basedir` to `$HIP/Cache`
  - Keep `basename`, `filetype`, `version` as-is
- If filemethod = "Explicit":
  - Rewrite `file` to `$HIP/Cache/{original_filename_pattern}`

**Important:** The saved `.hip` uses `$HIP` which will resolve to the remote
machine's location of `Scenes/` — so cache output will be `Scenes/../Cache/` = `Cache/`.
Actually, `$HIP` in the saved `.hip` resolves to wherever the `.hip` is opened from.
Since we save it to `{folder}/Scenes/{shot}.hip`, `$HIP` = `{folder}/Scenes/`.
So `basedir` should be `$HIP/../Cache` to land in `{folder}/Cache/`.

## Build Phases

### Phase 1: Core validation & auditing
- `cache_validator.py` — validate File Cache node existence and params
- `cache_auditor.py` — read File Cache params into a dataclass
- Tests for both (CI-safe, no hou dependency — mock hou calls)

### Phase 2: Scene + metadata writers
- `cache_scene_writer.py` — save portable .hip with path rewriting
- `cache_info_writer.py` — write cache_info.txt
- `cache_script_writer.py` — write run_cache.sh
- Tests (cache_info and script writers are CI-safe, scene writer needs hou)

### Phase 3: Manifest adaptation
- Extend or adapt `manifest.py` for cache packaging metadata
- Tests

### Phase 4: HDA creation
- Create HDA definition (subnet with internal filecache1)
- Promote File Cache parameters
- Add Remote Package parameter folder
- Write PythonModule.py callbacks
- Write OnCreated.py
- Write button scripts

### Phase 5: Integration testing
- Test with live Houdini via MCP
- Verify hbatch execution of generated script
- End-to-end: create geo → File Cache → Remote File Cache → Package → run remotely

## Open Decisions (noted, not blocking)

1. **Color scheme** — deep red is taken by render packager. Suggest orange (0.8, 0.5, 0.1) for cache/sim work.
2. **Separate HDA file or same repo?** — Same repo makes sense, different `.hdalc` file: `hda/remote_file_cache.hdalc`
3. **hbatch vs hython** — `hbatch` is standard for ROP cooking. `hython` is alternative but `hbatch` is more conventional.
4. **Multiple File Cache support** — Deferred. Single cache per HDA instance for now. Artist can use multiple HDA instances.
