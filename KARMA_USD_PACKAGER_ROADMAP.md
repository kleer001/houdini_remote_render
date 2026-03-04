# Karma USD Packager — Implementation Roadmap
**Target Platform:** Houdini 21.0.631 (LOP context)  
**Python:** 3.10+ (Houdini-bundled)  
**OS Support:** Linux, Windows, macOS  
**USD:** Houdini-bundled (pxr, UsdUtils)  
**Testing:** Live Houdini session via Houdini MCP — no mocking required

---

## Repository Structure

Mapping onto the existing `houdini_remote_render/` repo:

```
houdini_remote_render/
│
├── docs/
│   ├── images/
│   └── README.md
│
├── hda/
│   └── karma_usd_packager.hdalc        <- compiled HDA (Indie license, binary, git-tracked)
│
├── src/
│   ├── __init__.py
│   ├── main.py                         <- existing, repurpose as pipeline entry point
│   ├── auditor.py                      <- Stage 1: render settings audit
│   ├── classifier.py                   <- Stage 2: dependency classification
│   ├── converter.py                    <- Stage 3: texture conversion (imaketx)
│   ├── gatherer.py                     <- Stage 4: file copy + path rewriting
│   ├── output_injector.py              <- Stage 5: render product path injection
│   ├── packager.py                     <- Stage 6+7: flatten + USDZ creation
│   ├── wrapper_writer.py               <- Stage 8: thin .usda wrapper authoring
│   ├── manifest.py                     <- Stage 9: manifest writer
│   ├── validator.py                    <- Shot name + path guards
│   └── platform_utils.py              <- OS-agnostic path + executable helpers
│
├── hda_scripts/
│   ├── OnCreated.py                    <- Auto-wire on tab-in
│   ├── PythonModule.py                 <- HDA-embedded Python entry points
│   ├── btn_verify.py                   <- Verify button callback
│   └── btn_package.py                  <- Package & Stage button callback
│
├── tests/
│   ├── __init__.py
│   ├── test_main.py                    <- existing
│   ├── test_auditor.py
│   ├── test_classifier.py
│   ├── test_converter.py
│   ├── test_gatherer.py
│   ├── test_packager.py
│   ├── test_platform_utils.py
│   ├── test_validator.py
│   └── minimal_test_scene.usda        <- small hand-authored USD for integration tests
│
├── LICENSE
├── README.md
├── requirements.txt
└── ROADMAP.md
```

---

## HDA Specification

### Node Type
- **Context:** LOPs (Solaris)
- **Type name:** `karma_usd_packager`
- **Tab menu category:** `Rendering`
- **Node color:** Distinct — RGB (0.2, 0.6, 0.8) teal
- **Network box:** Created by OnCreated script, wraps this node, same color, label "USD Packager"

### HDA License Tier
- **Indie license** (current): HDA file extension is `.hdalc` (locked commercial).
  Indie HDAs can only be opened in Indie or Commercial Houdini.
- **Commercial license**: HDA file extension would be `.hdalib`.
- **Apprentice license**: HDA file extension would be `.hdanc`.
- The repository currently targets **Indie** (`.hdalc`).

### Inputs / Outputs
- **Input 0:** LOP stage (from upstream network)
- **Output 0:** Pass-through — the same LOP stage, unmodified. This node is a sidecar operator; it does not alter the live cooking stage.

### Parameters Interface (in order)

```
--- Shot Info --------------------------------------------------
Shot Name          string    default: "SHOT_NAME_HERE"
                             Python callback: flag red bg if value == default or empty
--- Output Files -----------------------------------------------
USDZ Filename      string    default: $shotname.usdz  (expression-driven)
Wrapper Filename   string    default: $shotname.usda  (expression-driven)
--- Options ----------------------------------------------------
Frame Range        [start]   [end]    default: inherit from connected ROP
                   Button: "Get From ROP"
Include Caches     toggle    default: True
--- Actions ----------------------------------------------------
[ Verify ]                            <- dry run, populates log area
[ Package & Stage ]                   <- full run
--- Log --------------------------------------------------------
Output Log         text area   read-only   multiparm
                   Button: "Clear Log"
----------------------------------------------------------------
```

---

## Module Implementation Guide

### `src/platform_utils.py`
**Purpose:** All OS-sensitive logic lives here. Nothing else in the codebase does OS detection.

Implement:
- `get_imaketx_path() -> str`
  Locate `imaketx` (Linux/macOS) or `imaketx.exe` (Windows) inside `$HFS/bin/`.
  Use `hou.expandString("$HFS")` to get Houdini's install root.
  Raise a clear `RuntimeError` if not found.
  **Note:** Houdini 21.0 ships `imaketx`, not `maketx`. This is Houdini's own mipmapped
  texture converter — not identical to OIIO's `maketx`.
- `normalize_path(p: str) -> str`  
  Wraps `pathlib.Path(p).resolve().as_posix()` on all platforms for consistent separators in USD paths. USD always expects forward slashes internally.
- `path_join(*parts) -> str`  
  Wraps `os.path.join()` but returns posix-style string.
- `ensure_dir(path: str) -> None`  
  `os.makedirs(path, exist_ok=True)`
- `get_hip_dir() -> str`
  `Path(hou.hipFile.path()).parent.as_posix()`
  Guard: if `hou.hipFile.path()` ends in `untitled.hip`, raise a descriptive error asking user to save first.
  All shot directories are created at `$HIP/{shot_name}/` (e.g. `$HIP/shot_001/Output/`).

**OS Notes:**
- Never use string concatenation for paths. Always `os.path.join` or `pathlib.Path`.
- On Windows, `subprocess` calls need `shell=False` and the `.exe` extension resolved explicitly.
- `$HFS` is reliably set by Houdini on all platforms.

---

### `src/validator.py`
**Purpose:** All go/no-go checks before any file operations run.

Implement:
- `validate_shot_name(name: str) -> tuple[bool, str]`  
  Fail if: value is `"SHOT_NAME_HERE"`, empty, or contains characters illegal in filenames on any OS: `\ / : * ? " < > |`  
  Return `(False, human-readable reason)` or `(True, "")`.
- `validate_hip_saved() -> tuple[bool, str]`  
  Fail if `hou.hipFile.hasUnsavedChanges()` — warn but do not block.  
  Fail hard if hip path contains `untitled`.
- `validate_shot_structure(shot_root: str) -> tuple[bool, str]`  
  Check that `Output/`, `Textures/`, `Cache/`, `Scenes/`, `Scripts/` all exist under shot directory.
  If missing, return list of missing dirs so caller can prompt user.
  Each directory gets a `.placeholder` file for Google Drive sync compatibility.
- `validate_rop_connection(node) -> tuple[bool, str]`  
  Walk node outputs to find a connected Karma ROP. Warn if none found but do not block — user may be running standalone.

---

### `src/auditor.py`
**Purpose:** Inspect the incoming USD stage, verify or author required prims.

Implement:
- `audit_stage(stage) -> AuditReport`  
  Returns a dataclass with fields: `has_render_settings`, `has_camera`, `has_render_products`, `warnings: list[str]`.
- `ensure_render_settings(stage) -> None`  
  If no `/Render/rendersettings` prim exists, author a minimal one with Karma defaults.
- `ensure_camera(stage) -> None`  
  If no camera prim exists, log a warning — do not create a default camera, that requires user intent.
- `check_instance_density(stage) -> int`  
  Walk stage for PointInstancer prims. Return total estimated instance count. If over a threshold (configurable, default 1,000,000), add a warning to AuditReport about flatten impact.

---

### `src/classifier.py`
**Purpose:** Scan all asset dependencies and sort them into buckets.

Implement:
- `classify_dependencies(stage_path: str) -> ClassifiedDeps`  
  Use `UsdUtils.ComputeAllDependencies(stage_path)`.  
  Returns dataclass:
  ```python
  @dataclass
  class ClassifiedDeps:
      textures:      list[str]   # .png .jpg .tiff .exr .hdr .tx .rat
      caches:        list[str]   # .vdb .bgeo.sc .abc
      sublayers:     list[str]   # .usd .usda .usdc
      udim_patterns: list[str]   # detected <UDIM> pattern strings
      unresolved:    list[str]   # anything that couldn't be found on disk
  ```
- `expand_udim_pattern(pattern: str) -> list[str]`  
  Given a path like `/tex/wood.<UDIM>.tx`, glob the directory for all matching tiles.  
  Return list of real file paths.
- `detect_udim_pattern(paths: list[str]) -> list[str]`  
  Given a list of resolved texture paths, detect which ones are UDIM tile sets and collapse them back to their `<UDIM>` pattern string for path rewriting.

---

### `src/converter.py`
**Purpose:** Convert source textures to mipmapped format using `imaketx`.

Implement:
- `needs_conversion(path: str) -> bool`
  Return `True` if extension is not `.rat` or already a mipmapped `.exr`.
- `convert_texture(src: str, dst_dir: str, fmt: str = "OpenEXR") -> str`
  Build the `imaketx` command using `platform_utils.get_imaketx_path()`.
  Usage: `imaketx [infile] [outfile] [options]`.
  Supported output formats: `OpenEXR`, `RAT`, `TIFF` (via `--format` flag).
  Output goes to `dst_dir` with same base name, format-appropriate extension.
  Use `subprocess.run()` with `shell=False`.
  Capture stdout/stderr, raise on non-zero return code with message.
  Return path of converted file.
- `convert_all(textures: list[str], dst_dir: str, dry_run: bool = False) -> ConversionReport`
  Iterate, skip already-optimal formats, convert the rest.
  `dry_run=True` returns what would be done without executing.
  Returns dataclass with `converted`, `skipped`, `failed` lists.
- `convert_udim_set(pattern: str, dst_dir: str, dry_run: bool = False) -> str`
  Expand pattern, convert each tile, return new pattern string pointing to `dst_dir`.

**`imaketx` flags reference (verified on Houdini 21.0.631):**
```
imaketx [infile] [outfile] [options]
  -v, --verbose              Show progress messages
  -a, --aov <name>           AOV of infile to process (default: C)
  -x, --tile_width <n>       Tile width (default: 64)
  -y, --tile_height <n>      Tile height (default: 64)
  -f, --filter <name>        Downscale filter: box gauss point sinc bartlett blackman catrom hanning mitchell
  -F, --format <fmt>         Output format: OpenEXR, RAT, TIFF
  --newer                    Only convert if source is newer than existing output
  -c, --colorconvert <s> <t> Source and target color spaces
  -l, --linearize <0|1|2>    sRGB linearization (0=off, 1=force, 2=auto)
  --no-sanitize              Pass data through without replacing inf/NaN
```

---

### `src/gatherer.py`
**Purpose:** Copy files to staging locations and rewrite USD paths.

Implement:
- `gather_textures(converted_paths: list[str], usdz_staging_dir: str) -> dict[str, str]`  
  Copy each file into `usdz_staging_dir/textures/`.  
  Return `{original_path: new_staged_path}` mapping.
- `gather_caches(cache_paths: list[str], shot_cache_dir: str) -> dict[str, str]`  
  Copy each file into `shot_cache_dir/`.  
  Preserve frame-numbered filenames exactly.  
  Return path mapping.
- `rewrite_paths_in_layer(layer, path_map: dict[str, str]) -> None`  
  Use `UsdUtils.ModifyAssetPaths()` with a replacement function built from `path_map`.
- `make_cache_relative_path(cache_abs: str, wrapper_usda_path: str) -> str`  
  Compute the relative path from `Scenes/` up to `Cache/`.  
  Result should always be `../Cache/<filename>`.  
  Use `os.path.relpath()` then convert to posix.

---

### `src/output_injector.py`
**Purpose:** Set RenderProduct output paths to write into `../Output/`.

Implement:
- `inject_output_paths(stage, output_dir_relative: str = "../Output") -> None`  
  Find all prims of type `RenderProduct`.  
  Set `productName` attribute to `{output_dir_relative}/{aov_name}.$F4.exr`.  
  Author via `Sdf` edit so it survives flatten.

---

### `src/packager.py`
**Purpose:** Flatten the stage and create the USDZ archive.

Implement:
- `flatten_stage(stage, staging_dir) -> str`
  Use `stage.Flatten()` — returns an `Sdf.Layer` (not a `Usd.Stage`).
  Export to a temp `.usda` file in the staging directory via `layer.Export()`.
  Returns the path to the flattened file.
- `create_usdz(flattened_usda: str, texture_staging_dir: str, output_usdz: str, dry_run: bool = False) -> list[str]`  
  Use `UsdUtils.CreateNewUsdzPackage(flattened_usda, output_usdz)`.  
  Use the non-ARKit variant — do not call `UsdUtils.CreateNewARKitUsdzPackage`.  
  `dry_run=True` returns the file list that would be included without writing.  
  Return list of files actually packaged.

---

### `src/wrapper_writer.py`
**Purpose:** Author the thin `.usda` file that combines the USDZ with cache references.

Implement:
- `write_wrapper(usdz_relative_path: str, cache_path_map: dict[str, str], output_usda: str) -> None`  
  Create a new `Usd.Stage`.  
  Add USDZ as a sublayer: `stage.GetRootLayer().subLayerPaths.append(usdz_relative_path)`.  
  For each cache reference in `cache_path_map`, author an override opinion at the correct prim path setting the asset path to the relative cache path.  
  Save the layer to `output_usda`.  
  USDZ path in the wrapper should be just the filename (e.g. `shot_001.usdz`) since both files live in `Scenes/`.

---

### `src/manifest.py`
**Purpose:** Write a human-readable log to `Scripts/`.

Implement:
- `write_manifest(output_path: str, data: ManifestData) -> None`  
  `ManifestData` dataclass contains:
  - `shot_name: str`
  - `houdini_version: str`  (from `hou.applicationVersionString()`)
  - `generated_at: str`  (ISO 8601 timestamp)
  - `usdz_path: str`
  - `wrapper_path: str`
  - `textures_converted: list[tuple[str, str]]`  (src, dst)
  - `textures_skipped: list[str]`
  - `caches_copied: list[tuple[str, str]]`
  - `warnings: list[str]`
  - `total_usdz_size_mb: float`
  - `total_cache_size_mb: float`  
  Plain text format. Human-readable. No JSON, no XML.

---

### `hda_scripts/OnCreated.py`
**Purpose:** Auto-wire the HDA into the network on creation.

Implement:
- Get `kwargs["node"]` — the newly created HDA instance.
- Check if it was created inside a LOP network.
- If the user had a node selected when tabbing in, attempt to wire:
  - Connect selected node's output 0 -> HDA input 0.
  - Walk selected node's existing outputs — if any go to a Karma ROP, rewire: HDA output 0 -> Karma ROP input.
- Create a network box around the HDA node, set color and label.
- Open the parameter dialog and set focus to the Shot Name field.
- All wiring wrapped in `try/except` — if it fails, log a warning but do not crash creation.

---

### `hda_scripts/PythonModule.py`
**Purpose:** Entry points called by HDA parameter callbacks and buttons.

Implement these functions (called by HDA button parameters):
- `on_shot_name_changed(kwargs)` — parameter callback, drives field color
- `on_verify_clicked(kwargs)` — dry-run pipeline, populate log
- `on_package_clicked(kwargs)` — full pipeline run, populate log
- `on_get_from_rop_clicked(kwargs)` — walks outputs to find Karma ROP, reads frame range

Each button callback follows this pattern:
```python
def on_package_clicked(kwargs):
    node = kwargs["node"]
    log = []
    try:
        # 1. run validator, abort with hou.ui.displayMessage() on failure
        # 2. call each pipeline stage in order
        # 3. append progress to log, set node parm "log_output"
    except Exception as e:
        hou.ui.displayMessage(str(e), severity=hou.severityType.Error)
```

---

## OS-Agnostic Rules — Enforced Throughout

These rules apply to every module. Claude Code should flag any violation:

1. **No hardcoded path separators.** Use `os.path.join()` or `pathlib.Path` everywhere.
2. **All USD-internal paths use forward slashes.** Call `.as_posix()` before writing into any USD layer.
3. **`imaketx` is located via `$HFS`, never hardcoded.** Extension `.exe` added on Windows via `platform.system() == "Windows"` check in `platform_utils.py` only.
4. **`subprocess.run()` with `shell=False` always.** Pass argument lists, not strings.
5. **Temp directories via `tempfile.mkdtemp()`.** Never write to hardcoded `/tmp/` paths.
6. **File size checks via `os.path.getsize()`.** No platform-specific `du` or `dir` calls.
7. **Line endings in manifest: `\n` always.** Open files with `newline="\n"` explicitly.

---

## Testing Approach

### MCP Integration Tests (Primary)

All integration tests run inside a live Houdini 21.0.631 session via the **Houdini MCP**. Claude Code should:

- Execute test code by sending it through the MCP connection directly
- Use the real `hou` module and real `pxr` USD libraries — no mocking needed at any phase
- Keep a minimal LOP network open in Houdini as a persistent test fixture (a simple sphere with a material and a Karma ROP is sufficient for most phases)
- Use `tests/minimal_test_scene.usda` as a known-good USD file for dependency scanning and packaging tests that don't require a full Houdini cook
- After each phase, verify results by inspecting the Houdini scene state through the MCP before moving on

### CI Unit Tests (GitHub Actions)

GitHub Actions CI does **not** have a Houdini installation. Tests that require `hou` or a live
Houdini session cannot run in CI. Strategy:

- **Pure-Python unit tests** (no `hou` dependency) run in CI via `pytest`:
  - `test_validator.py` — shot name validation, illegal character checks (no `hou` calls)
  - `test_platform_utils.py` — `normalize_path`, `path_join`, `ensure_dir` (no `hou` calls)
  - `test_manifest.py` — manifest file writing
- **Houdini-dependent tests** are marked with `@pytest.mark.houdini` and skipped in CI:
  - Tests that import `hou`, access a USD stage via Houdini, or call `imaketx`
  - Use `pytest.importorskip("hou")` at the top of Houdini-dependent test files
- **CI workflow** runs: `pytest -m "not houdini"` to skip Houdini-dependent tests

---

## Implementation Order for Claude Code

Implement in this sequence. Each step is independently testable before proceeding.

```
Phase 1 — Foundation
  1. src/platform_utils.py   +  tests/test_platform_utils.py
  2. src/validator.py        +  tests/test_validator.py

Phase 2 — USD Analysis
  3. src/auditor.py          +  tests/test_auditor.py
  4. src/classifier.py       +  tests/test_classifier.py

Phase 3 — Asset Processing
  5. src/converter.py        +  tests/test_converter.py
  6. src/gatherer.py         +  tests/test_gatherer.py

Phase 4 — USD Authoring
  7. src/output_injector.py
  8. src/packager.py         +  tests/test_packager.py
  9. src/wrapper_writer.py

Phase 5 — Reporting
  10. src/manifest.py

Phase 6 — HDA
  11. Build HDA parameter interface (hda/ directory)
  12. hda_scripts/PythonModule.py
  13. hda_scripts/OnCreated.py
  14. hda_scripts/btn_verify.py
  15. hda_scripts/btn_package.py

Phase 7 — Integration Test
  16. End-to-end test with a real Houdini scene via MCP
```

---

## Key USD API References

```python
# Dependency scanning
from pxr import UsdUtils
all_layers, all_assets, unresolved = UsdUtils.ComputeAllDependencies(path)

# Path rewriting
UsdUtils.ModifyAssetPaths(layer, path_fn)

# Flattening (returns Sdf.Layer, not Usd.Stage)
flat_layer = stage.Flatten()
flat_layer.Export("/path/to/output.usda")

# USDZ packaging (non-ARKit)
UsdUtils.CreateNewUsdzPackage(input_usda, output_usdz)

# Layer editing
from pxr import Sdf
layer = Sdf.Layer.FindOrOpen(path)
with Sdf.ChangeBlock():
    # batch edits here

# Sublayer addition
root_layer.subLayerPaths.append("./shot_001.usdz")
```

---

## Warnings & Known Gotchas

- **`stage.Flatten()` destroys point instancing** — large scatter/crowd scenes will explode in memory. The auditor must warn before this step if instance count is high.
- **USDZ spec: no escaping paths** — paths inside a USDZ cannot use `../`. Cache paths must never enter the USDZ. Enforce in `gatherer.py`.
- **`UsdUtils.ComputeAllDependencies` requires a file path** — it cannot work on an in-memory stage. The stage must be written to disk before scanning.
- **Testing runs through the Houdini MCP** — all tests execute inside a live Houdini session. No mocking of `hou` is needed or desired. Claude Code should send test code through the MCP rather than running it in a standalone Python process.
- **`imaketx` is Houdini's own tool, NOT OIIO's `maketx`** — it has a different flag set. Supported output formats: OpenEXR, RAT, TIFF. No `.tx` output — use mipmapped `.exr` instead. See `src/converter.py` section for the full flag reference.
- **Windows path length limit (260 chars)** — shots with deep directory structures can hit this. `platform_utils.py` should warn if any constructed path exceeds 240 characters.
