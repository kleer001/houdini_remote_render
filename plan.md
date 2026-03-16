# Mantra Render Packager — Implementation Plan

## Overview

A ROP-context HDA that wraps an existing Mantra ROP and packages the scene for remote rendering. Follows the **Remote File Cache** pattern closely (wrap an internal node, save portable `.hip`, generate launch script), but targets Mantra rendering instead of geometry caching.

**Key architectural decision:** Like the File Cache packager wraps `filecache::2.0`, this wraps a Mantra ROP (`ifd`). The HDA lives in `/out` and connects upstream of (or contains) the Mantra ROP. Since Mantra is a ROP node, `hbatch`'s `render` command works directly — no need for `hython` workarounds.

---

## Output Structure

```
$HIP/{shot_name}_P{pod}T{team}_v{NNN}/
    Output/                 <- rendered images (EXR, etc.)
    Scenes/                 <- portable .hip
    Scripts/                <- run_render.sh
    {shot_name}_manifest.txt
    render_info.txt         <- machine-readable metadata
```

No `Textures/` or `Cache/` subdirs — Mantra resolves textures from the original paths in the .hip. If textures need gathering, that's a future enhancement.

---

## New Files

### `src/` modules (pure logic, no `hou` at module level)

1. **`src/mantra_validator.py`** — Validate the Mantra ROP node
   - `validate_mantra_node(node)` → `(bool, str)` — check node type starts with `ifd` (Mantra's internal type name)
   - `validate_output_picture(path)` → `(bool, str)` — check `vm_picture` is non-empty
   - Reuse `validate_frame_range()` from `cache_validator.py` (it's generic)

2. **`src/mantra_auditor.py`** — Read Mantra ROP params into a dataclass
   - `MantraAuditReport` dataclass: node_path, resolution (vm_resolution), samples (vm_maxraysamples), output path (vm_picture), image format, frame range, render engine, AOV count, camera path, etc.
   - `audit_mantra_rop(node)` → `MantraAuditReport` — read all relevant parms, generate warnings (e.g., low samples, missing camera)

3. **`src/mantra_scene_writer.py`** — Save portable `.hip` with rewritten output paths
   - `save_portable_hip(mantra_node, output_hip_path, remote_output_dir)` — same snapshot/restore pattern as `cache_scene_writer.py`
   - Rewrite `vm_picture` to point to `$HIP/../Output/` so renders land in the package's `Output/` dir
   - Also rewrite any extra image planes / AOV output paths
   - Reuse `backup_hip_as_zip()` from `cache_scene_writer.py` (it's generic — just zips the hip)

4. **`src/mantra_script_writer.py`** — Generate `run_render.sh` using hbatch
   - `write_mantra_script(output_path, shot_name, hip_filename, rop_node_path, frame_start, frame_end, hfs_path)`
   - Uses `hbatch` with inline `render` command: `echo "render -Va {rop_path}" | hbatch Scenes/{hip}`
   - Same HFS sourcing block pattern as existing script writers
   - `-V` for verbose, `-a` for all frames (or specify range with `-f start end`)
   - Actually: hbatch render command syntax is `render -f start end inc rop_path`, so we use that

5. **`src/mantra_info_writer.py`** — Write machine-readable `render_info.txt`
   - Same key=value format as `cache_info_writer.py`
   - Fields: shot_name, folder_name, renderer=mantra, resolution, samples, frame range, output pattern, hip filename, camera, houdini_version

6. **`src/mantra_manifest.py`** — Human-readable manifest
   - `MantraManifestData` dataclass + `write_mantra_manifest(path, data)`
   - Same structure as `cache_manifest.py` but with render-specific sections (resolution, samples, AOVs, camera)

### `hda_scripts_mantra/` — HDA callbacks

7. **`hda_scripts_mantra/PythonModule.py`** — Verify and package callbacks
   - `_ensure_src_path(node)` — same pattern
   - `_get_mantra_node(node)` — return internal Mantra ROP (the node wired as input, or the internal `mantra1` node)
   - `on_verify_clicked(kwargs)` — validate shot name, hip saved, mantra node, frame range, output path
   - `on_package_clicked(kwargs)` — full pipeline: validate → create dirs → backup hip → save portable hip → write render_info → write run_render.sh → write manifest

8. **`hda_scripts_mantra/btn_verify.py`** — one-liner: `hou.phm().on_verify_clicked(kwargs)`

9. **`hda_scripts_mantra/btn_package.py`** — one-liner: `hou.phm().on_package_clicked(kwargs)`

10. **`hda_scripts_mantra/OnCreated.py`** — auto-wire, set color (forest green — distinct from deep red and amber), create network box labeled "Remote Mantra Render"

### Tests

11. **`tests/test_mantra_validator.py`** — CI-safe tests
    - Mock node with FakeNode pattern (same as test_cache_validator.py)
    - Test valid/invalid node types, empty output, frame range edge cases

12. **`tests/test_mantra_script_writer.py`** — CI-safe tests
    - Test file creation, executable bit, contains hbatch command, contains shot info, newline format

13. **`tests/test_mantra_info_writer.py`** — CI-safe tests
    - Test file creation, key=value format, all fields present

14. **`tests/test_mantra_manifest.py`** — CI-safe tests
    - Test file creation, sections present, warnings included

---

## Implementation Details

### Mantra ROP Type Detection

Mantra's node type is `ifd` (the underlying format). Accept any type starting with `ifd`:
```python
def validate_mantra_node(node):
    if node is None:
        return False, "No Mantra ROP node found."
    type_name = node.type().name()
    if not type_name.startswith("ifd"):
        return False, f"Node is type '{type_name}', expected Mantra ROP ('ifd')."
    return True, ""
```

### hbatch Render Script

Key difference from husk (Karma) and hython (File Cache): Mantra uses `hbatch` which natively supports ROP rendering:

```bash
cd "$(dirname "$0")/.."
# ... HFS sourcing ...
cd Scenes
hbatch -c "render -Va -f $START $END $INC $ROP_PATH" "$HIP_FILE"
```

The `-c` flag runs a command and exits. `render -Va` enables verbose all-frame rendering. Frame range: `render -f start end inc /out/mantra1`.

The script `cd`s into `Scenes/` so that `$HIP` resolves to the Scenes dir, and `$HIP/../Output/` reaches the package's Output directory.

### Portable .hip — Output Path Rewriting

Mantra's primary output parm is `vm_picture`. We also need to handle:
- Extra image planes (AOVs) via `vm_filename_plane#` parms
- Deep output via `vm_deepresolver` and `vm_dcmfilename`

For v1, we rewrite `vm_picture` only. AOV paths typically derive from `vm_picture` via expressions, so they should follow automatically.

Snapshot/restore pattern identical to `cache_scene_writer.py`:
1. Unlock HDA contents (if wrapped)
2. Snapshot `vm_picture` expression/value
3. Set `vm_picture` to `$HIP/../Output/{original_filename}`
4. Save .hip copy
5. Restore original `vm_picture`
6. Re-lock HDA

### HDA Design (for future .hdalc creation)

- **Context:** ROP (`/out`)
- **Internal structure:** ROP subnet containing a Mantra ROP (`ifd`) node
- **Parameters bubbled up:** All essential Mantra params via `ch("../parm")` channel refs, plus "Remote Package" tab with shot_name, pod_number, team_number, ver, verify button, package button, log_output
- **Color:** Forest green `(0.2, 0.6, 0.3)` — distinct from deep red (Karma) and amber (File Cache)

Note: The actual `.hdalc` file creation requires a live Houdini session. This plan covers the Python code that the HDA will use.

---

## Execution Order

1. `src/mantra_validator.py` + `tests/test_mantra_validator.py`
2. `src/mantra_auditor.py` (no tests needed for v1 — it's read-only param extraction, requires hou)
3. `src/mantra_scene_writer.py` (requires hou for testing — Houdini-dependent)
4. `src/mantra_script_writer.py` + `tests/test_mantra_script_writer.py`
5. `src/mantra_info_writer.py` + `tests/test_mantra_info_writer.py`
6. `src/mantra_manifest.py` + `tests/test_mantra_manifest.py`
7. `hda_scripts_mantra/` (all 4 files)
8. Update `CLAUDE.md` to document the Mantra packager

---

## What's NOT in scope (v1)

- Texture gathering/conversion (Mantra resolves textures from original paths)
- IFD export (generating .ifd files for standalone mantra rendering — possible future enhancement)
- AOV path rewriting beyond `vm_picture`
- The actual `.hdalc` HDA file (requires live Houdini session to create)
- Redshift ROP packager (separate effort)
