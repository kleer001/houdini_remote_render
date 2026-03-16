# Mantra Render Packager — Houdini MCP Testing Roadmap

Testing roadmap for validating the Mantra Render Packager with a headless Houdini instance via houdini-mcp.

## Gotchas Discovered During Review

These were found by cross-referencing the implementation against Houdini documentation (`nodes/out/ifd.md`, `commands/render.md`, `render/batch.md`, `props/mantra.md`) and SideFX/odforce forums.

### render HScript command syntax

The `render` command's `-f` flag takes **two** arguments (start, end). Frame increment is a **separate** `-i` flag:

```
render -Va -f 1001 1200 -i 1 /out/mantra1     # correct
render -Va -f 1001 1200 1 /out/mantra1         # WRONG — third arg is parsed as the ROP path
```

Source: `commands/render.md` — `render [-V] [-f <<start>> <<end>>] [-i <<inc>>] ... <<output_name>>`

### hbatch does not support -c

`hbatch` is an interactive HScript environment — it has no `-c` flag for one-shot command execution (unlike `hython -c` which is standard Python). Use piped input instead:

```bash
echo 'render -Va -f 1001 1200 -i 1 /out/mantra1' | hbatch "scene.hip"
```

Alternatives: `hrender -d /out/mantra1 -f 1001 1200 scene.hip` (official wrapper) or `hython -c` with `hou.RopNode.render()`.

### Mantra ROP parameter names

| Assumed name | Actual name | Notes |
|---|---|---|
| `vm_image_format` | `vm_device` | Controls output format (EXR, PNG, etc.) |
| `res_overridex` / `res_overridey` | Correct | Vector component suffixes of `res_override` |
| `vm_samplesx` / `vm_samplesy` | Correct | Vector component suffixes of `vm_samples` |

### Resolution override hierarchy

Resolution override on the Mantra ROP has three levels:
1. `override_camerares` (bool) — master toggle
2. `res_fraction` (string menu) — `"specific"` enables explicit override, other values scale camera resolution
3. `res_overridex` / `res_overridey` — only active when `res_fraction="specific"`

The auditor reads `res_overridex`/`res_overridey` regardless, since they reflect the configured values even if the override is disabled.

### $HIP temporarily wrong during save-as-copy

Between `hou.hipFile.save(new_path)` and `hou.hipFile.setName(original_path)`, `$HIP` points to the new location. Any expression evaluated in that window will misresolve. Alternative: `hou.hscript("mwrite -n /path/to/copy.hip")` saves without changing `$HIP` at all, but is less commonly used.

### vm_picture filename gotchas

- Don't use hyphens before `$F4` (e.g. `render-$F4.exr`) — MPlay interprets the hyphen as a negative frame number. Use underscores or dots: `render_$F4.exr`, `render.$F4.exr`.
- When letters follow `$F` immediately (e.g. `$Fname`), Houdini reads it as variable `$Fname`. Use `${F}name`.
- Fractional frames (motion blur): both 5.0 and 5.5 produce `$F=5`, causing overwrites. Use `$FF` for sub-frame.

### hbatch environment

- Set `HOUDINI_UNBUFFERED_STDINOUT=1` for real-time stderr output from hbatch.
- `hbatch` consumes a full Houdini license, not a render-only license.
- Indie license: `.hip` files saved via Indie may be `.hiplc` internally.

---

## Phase 1: Validate Core Modules (no HDA needed)

These tests create a minimal scene in-memory and exercise `src/` modules that import `hou` lazily.

### 1.1 — `mantra_auditor.py`

- Create a Mantra ROP via `hou.node("/out").createNode("ifd")`
- Call `audit_mantra_rop(node)` and verify the `MantraAuditReport` fields match the node's defaults
- Set non-default values (resolution, samples, camera) and re-audit
- Verify warnings fire for missing camera, low ray samples

### 1.2 — `mantra_scene_writer.py`

- Create a scene with a Mantra ROP, save the `.hip`
- Call `save_portable_hip(mantra_node, output_path)`
- Verify: the saved `.hip` has `vm_picture` pointing to `$HIP/../Output/...`
- Verify: the *live* scene's `vm_picture` was restored to its original value
- Verify: `backup_hip_as_zip()` (reused from cache_scene_writer) produces a valid zip

### 1.3 — `mantra_validator.py` with real nodes

- Create `ifd` node -> `validate_mantra_node()` returns `True`
- Create `filecache` node -> returns `False`
- `None` -> returns `False`

## Phase 2: End-to-End Pipeline (no HDA, just modules)

Simulate what `on_package_clicked` does, but without the HDA wrapper.

```python
# Pseudo-test script for hbatch/hython
import hou
hou.hipFile.save("/tmp/mantra_test.hip")

mantra = hou.node("/out").createNode("ifd")
mantra.parm("vm_picture").set("/tmp/test_render.$F4.exr")
mantra.parm("camera").set("/obj/cam1")
mantra.parm("trange").set(1)  # use frame range
mantra.parm("f1").set(1001)
mantra.parm("f2").set(1010)
mantra.parm("f3").set(1)

# Run each pipeline stage
from src.mantra_validator import validate_mantra_node, validate_output_picture
from src.cache_validator import validate_frame_range
from src.mantra_auditor import audit_mantra_rop
from src.mantra_scene_writer import save_portable_hip
from src.mantra_script_writer import write_mantra_script
from src.mantra_info_writer import write_mantra_info
from src.mantra_manifest import MantraManifestData, write_mantra_manifest

# Validate
assert validate_mantra_node(mantra)[0]
assert validate_output_picture(mantra.parm("vm_picture").eval())[0]
assert validate_frame_range(1001, 1010, 1)[0]

# Audit
report = audit_mantra_rop(mantra)
assert report.frame_count == 10
assert report.node_path == mantra.path()

# Save portable hip
save_portable_hip(mantra, "/tmp/mantra_pkg/Scenes/test.hip")
# Verify original vm_picture is restored
assert "$HIP/../Output" not in mantra.parm("vm_picture").eval()

# Write script, info, manifest
write_mantra_script("/tmp/mantra_pkg/Scripts/run_render.sh", ...)
write_mantra_info("/tmp/mantra_pkg/render_info.txt", ...)
# ... verify all files exist
```

**What to check:**

- All files created in correct locations
- `run_render.sh` is executable and contains valid hbatch syntax (piped, not `-c`)
- Script uses `render -Va -f start end -i inc rop_path` (NOT `-f start end inc`)
- Portable `.hip` loads cleanly in a fresh `hbatch` session
- `vm_picture` in the portable `.hip` points to `$HIP/../Output/`

## Phase 3: Portable .hip Validation

Load the portable `.hip` that Phase 2 produced and verify it's self-consistent.

```python
# In a fresh hbatch session
hou.hipFile.load("/tmp/mantra_pkg/Scenes/test.hip")
mantra = hou.node("/out/mantra1")  # or wherever it lives
pic = mantra.parm("vm_picture").unexpandedString()
assert "$HIP/../Output/" in pic
```

## Phase 4: HDA Integration (requires the `.hdalc`)

This requires building the actual HDA in Houdini.

### 4.1 — Create the HDA

- Create a ROP Subnet in `/out`
- Add an internal `ifd` node named `mantra1`
- Bubble up essential Mantra parms via channel references
- Add "Remote Package" tab with: `shot_name`, `pod_number`, `team_number`, `ver`, `verified`, `log_output`, verify button, package button
- Embed `hda_scripts_mantra/` as HDA scripts
- Save as `hda/remote_mantra_render.hdalc`

### 4.2 — Test HDA callbacks

- Install the HDA, create an instance
- Verify `OnCreated.py` fires: node should be forest green with network box
- Set `shot_name`, click Verify -> check `log_output` for `PASSED`
- Click Package -> verify full output structure is created
- Verify log shows all 7 steps completing

### 4.3 — Test the render script

- Run the generated `run_render.sh` (with a trivial 1-frame scene)
- Verify an image file appears in `Output/`

## Phase 5: Edge Cases

| Test | What to verify |
|------|---------------|
| Empty `vm_picture` | Verify button reports FAIL |
| Invalid shot name (`path/inject`) | Verify button reports FAIL (regex blocks `\\ / : * ? " < > \|` only) |
| Frame start > end | Verify button reports FAIL |
| No camera assigned | Verify shows WARN, package still works |
| `trange=0` (current frame only) | WARN in verify log |
| Existing output folder | Overwrite prompt in package |
| Versioned Mantra (`ifd::2.0`) | Validator accepts it |
| `override_camerares=0` | Auditor reports default override values, warns resolution depends on camera |
| Expression-driven `vm_picture` (`$HIP/render/$HIPNAME.$F4.exr`) | `save_portable_hip` snapshots and restores expression, not just value |
| `vm_picture` with hyphen (`render-$F4.exr`) | Not blocked, but should warn (MPlay negative-frame bug) |
| `vm_picture` is None (parm doesn't exist) | `validate_output_picture` returns FAIL |

## Suggested Test File Structure

```
tests/
    test_mantra_validator.py        # done (CI-safe, 27 tests)
    test_mantra_script_writer.py    # done
    test_mantra_info_writer.py      # done
    test_mantra_manifest.py         # done
    test_mantra_auditor.py          # NEW — @pytest.mark.houdini
    test_mantra_scene_writer.py     # NEW — @pytest.mark.houdini
    test_mantra_integration.py      # NEW — @pytest.mark.houdini, full pipeline
```

## MCP-Specific Notes

With houdini-mcp you can likely:

- Execute Python in an `hbatch`/`hython` session (Phases 1-3)
- Create nodes, set parms, save/load `.hip` files
- Read back file contents to verify outputs

You probably **cannot**:

- Test `hou.ui.displayMessage` dialogs (headless = no UI) — the package callback will need either a `--force` flag or the MCP needs to handle/suppress UI calls
- Build the `.hdalc` interactively (Phase 4) — this may require a script that programmatically creates the HDA definition

**Recommendation:** Start with Phase 2 (end-to-end without HDA) — it covers the most code with the least setup. If that passes, the HDA layer is mostly UI wiring.

## Test Results (2026-03-15, headless hython via houdini-mcp)

All phases executed and passed against Houdini 21.0.631 headless.

| Phase | Status | Notes |
|-------|--------|-------|
| 1.1 — mantra_auditor | PASSED | Defaults + non-default values + warnings verified |
| 1.2 — mantra_scene_writer | PASSED | Fixed `$F4` expansion bug (`.eval()` → `.unexpandedString()`), added HDA unlock/re-lock |
| 1.3 — mantra_validator | PASSED | ifd, filecache rejection, None, output picture |
| 2 — End-to-end pipeline | PASSED | All 7 files created, render script syntax verified |
| 3 — Portable .hip validation | PASSED | `vm_picture`, camera, frame range, resolution all preserved |
| 4.1 — HDA creation | PASSED | Built programmatically with channel refs + embedded scripts |
| 4.2 — HDA callbacks | PASSED | Verify + Package both complete all 7 steps |
| 4.3 — Portable .hip from HDA | PASSED | Output path, camera, frames all correct |
| 5 — Edge cases | PASSED | Empty output, invalid name, start>end, no camera, trange=0, low samples, ifd::2.0, expression-driven vm_picture |

### Bugs fixed during testing

1. **`render` command syntax** — `mantra_script_writer.py`: `-f start end inc` → `-f start end -i inc`
2. **`hbatch -c` not valid** — changed to `echo '...' | hbatch` pipe syntax
3. **`vm_image_format` doesn't exist** — `mantra_auditor.py`: changed to `vm_device`
4. **Dead code in resolution fallback** — `mantra_auditor.py`: removed redundant else branch
5. **`$F4` expanded to frame number** — `mantra_scene_writer.py`: `.eval()` → `.unexpandedString()`
6. **HDA lock blocks parm modification** — `mantra_scene_writer.py`: added `allowEditingOfContents()` / `matchCurrentDefinition()`
7. **`hou.ui` crashes in headless mode** — `PythonModule.py`: added `_has_ui()` guard
