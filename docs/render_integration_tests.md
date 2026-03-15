# Render Integration Tests

Automated tests that invoke standalone `husk` via the generated `run_render.sh` script and verify the output. These catch regressions in the render script writer, husk CLI flag syntax, HFS environment sourcing, and output path resolution.

## Prerequisites

- **Houdini 21.0+** installed (any license tier)
- **`$HFS`** environment variable set to the Houdini install path (e.g., `/opt/hfs21.0.631`)
- **No GPU required** — tests use Karma CPU at 320x240 / 16 samples (~1 second per frame)
- **No Houdini session needed** — tests run headless via `husk`, not `hou`

## Running the tests

```bash
# Set HFS, then run all tests including integration
export HFS=/opt/hfs21.0.631
pytest tests/test_render_integration.py -v
```

These tests are marked `pytest.mark.houdini` and are automatically skipped during CI:

```bash
# CI command — skips all houdini-marked tests
pytest -m "not houdini"
```

## What each test does

### `test_single_frame_render`

Creates a temporary shot directory with a minimal USD scene (sphere, camera, dome light, render settings at 320x240), generates `run_render.sh`, executes it, and asserts:

- husk exits with code 0
- `Output/test.0001.exr` exists
- File size is > 1 KB (not an empty or corrupt file)

**Manual equivalent:**

```bash
mkdir -p /tmp/test_shot/{Scenes,Output,Scripts}
# Write a .usda with a sphere, camera, dome light, and render settings
# (see _MINIMAL_USDA in the test file for the exact content)
python3 -c "
from src.render_script_writer import write_render_script
write_render_script('/tmp/test_shot/Scripts/run_render.sh', 'test', 'test.usda', 1, 1)
"
bash /tmp/test_shot/Scripts/run_render.sh
ls -la /tmp/test_shot/Output/test.0001.exr
```

**Expected:** A valid EXR file in `Output/`.

### `test_multi_frame_render`

Same setup but with `frame_start=1, frame_end=3`. Asserts:

- husk exits with code 0
- `test.0001.exr`, `test.0002.exr`, `test.0003.exr` all exist in `Output/`
- Each file is > 1 KB

This verifies that the `<F4>` frame token in `productName` is expanded correctly by husk, and that the `-f START -n COUNT -i INC` frame range flags work.

**Expected:** Three numbered EXR files.

### `test_restart_delegate_in_sequence`

Generates a render script for a 3-frame sequence and checks the script text for `--restart-delegate 1`. This is a "smart default" — sequences auto-add this flag to prevent memory accumulation across frames.

**Expected:** The flag is present in the script for sequences, absent for single frames (see next test).

### `test_no_restart_delegate_single_frame`

Generates a render script for a single frame and asserts `--restart-delegate` is NOT in the script. Single frames don't need delegate restarts.

### `test_hfs_sourced_in_script`

Checks that the generated script contains `houdini_setup_bash` — the Houdini environment sourcing block. Without this, `husk` won't have the correct library paths and USD plugins.

### `test_output_resolution`

Renders a single frame, then runs `iinfo` (Houdini's image info tool at `$HFS/bin/iinfo`) on the output EXR and checks for `320 x 240` in the output. This verifies that the resolution authored in the USD `RenderSettings` prim is respected by husk.

**Manual equivalent:**

```bash
$HFS/bin/iinfo /tmp/test_shot/Output/test.0001.exr
# Should show: Resolution: 320 x 240
```

## How the test scene works

The tests use a hand-written `.usda` file (no `pxr` Python dependency) containing:

| Prim | Purpose |
|------|---------|
| `/World/sphere` | Geometry to render (unit sphere) |
| `/World/camera` | Camera at z=10, focal length 50mm |
| `/World/domeLight` | Ambient lighting (prevents black render since `--headlight none` is always set) |
| `/Render/settings` | 320x240 resolution, 16 path-traced samples, wired to camera and product |
| `/Render/product` | Output path `../Output/test.<F4>.exr` (relative to `Scenes/`) |
| `/Render/product/beauty` | Beauty AOV (`C`) |

The `productName` path `../Output/test.<F4>.exr` is relative to the `Scenes/` directory because `husk` resolves it relative to CWD, and the render script does `cd Scenes` before invoking husk.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: No module named 'pxr'` | Running houdini-marked tests without Houdini | Set `$HFS` and ensure Houdini is installed |
| `husk: command not found` | HFS sourcing block skipped or incorrect | Check `$HFS` points to a valid Houdini install |
| `Unable to load USD file` | Invalid USDA syntax or wrong CWD | Check the `.usda` content — prim names can't contain `/` |
| `No such file or directory: 'iinfo'` | `$HFS` not set when running resolution test | `export HFS=/opt/hfs21.0.631` before running pytest |
| Output EXR in wrong directory | husk resolves productName relative to CWD | The render script must `cd Scenes` before calling husk |
