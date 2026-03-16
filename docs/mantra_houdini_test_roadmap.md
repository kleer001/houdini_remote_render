# Mantra Render Packager — Houdini MCP Testing Roadmap

Testing roadmap for validating the Mantra Render Packager with a headless Houdini instance via houdini-mcp.

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
- `run_render.sh` is executable and contains valid hbatch syntax
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
| Invalid shot name (`has spaces!`) | Verify button reports FAIL |
| Frame start > end | Verify button reports FAIL |
| No camera assigned | Verify shows WARN, package still works |
| `trange=0` (current frame only) | WARN in verify log |
| Existing output folder | Overwrite prompt in package |
| Versioned Mantra (`ifd::2.0`) | Validator accepts it |

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
