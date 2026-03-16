# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Also follow the behavioral guidelines in [CLAUDE_GENERIC.md](./CLAUDE_GENERIC.md).

## Project Overview

Houdini Remote Render & Cache — a collection of Houdini HDAs that package scenes for remote execution. Currently includes:

1. **Karma USD Packager** — a LOP HDA that packages USD scenes into self-contained USDZ archives for remote rendering. Pass-through node: doesn't modify the live stage. Flattens the stage, creates a USDZ archive with bundled textures, writes a thin `.usda` wrapper referencing external caches, and generates a manifest.

2. **Remote File Cache** — a SOP HDA that wraps a File Cache SOP with remote packaging. Drop-in replacement for File Cache with identical parameters, plus a "Package for Remote" button that saves a portable `.hip` with rewritten cache paths, an hbatch launch script, and metadata.

3. **Mantra Render Packager** — a ROP HDA that wraps a Mantra ROP with remote packaging. Saves a portable `.hip` with rewritten output paths, generates an hbatch launch script, and writes metadata/manifest.

4. **Redshift ROP** — planned. Remote packaging for Redshift render jobs.

**Environment:** Houdini 21.0+ (Indie license, `.hdalc` extension), Python 3.11+, Linux. HFS at `/opt/hfs21.0.631`.

## Commands

```bash
# Run CI tests (no Houdini required) — 171 tests
pytest -m "not houdini"

# Run all tests including Houdini-dependent ones (requires live Houdini session)
pytest

# Run a single test file
pytest tests/test_validator.py

# Run a single test class or method
pytest tests/test_validator.py::TestValidateShotName::test_valid_name
```

No build step. No linter configured. No `requirements.txt` — all dependencies (`pxr`, `hou`) come from Houdini's bundled Python.

## Architecture

### Karma USD Packager (LOP)

**Two entry points into the same pipeline:**

1. **`src/main.py:run_pipeline()`** — headless entry point. Takes a `Usd.Stage`, shot name, and hip dir. Used for scripted/batch packaging.

2. **`hda_scripts/PythonModule.py`** — HDA callbacks (`on_verify_clicked`, `on_package_clicked`). These replicate the pipeline steps inline (not calling `run_pipeline`) because they need granular control over the UI: per-step log messages, `hou.ui.displayMessage` dialogs, confirmation prompts, and writing to the `log_output` parameter.

Both follow the same sequence: validate → **resolve cache dependencies** → audit → create dirs → **package upstream caches** → inject output paths → flatten & USDZ → write wrapper → write render script → **write orchestration script** → write manifest.

**Module pipeline (in execution order):**

`src/` modules are pure-logic with no `hou` imports at module level (they import `hou` and `pxr` lazily inside functions). This enables CI testing without Houdini.

1. **validator** — shot name regex, HIP file saved check, directory structure check, ROP connection check
2. **auditor** — traverses stage for RenderSettings/Camera/RenderProduct/Light prims, counts PointInstancer instances, authors fallback RenderSettings if missing
3. **classifier** — `UsdUtils.ComputeAllDependencies` to bucket files into textures/caches/sublayers, UDIM pattern detection
4. **converter** — `imaketx` subprocess calls for texture conversion (NOT `maketx` — it doesn't exist in this Houdini build)
5. **gatherer** — copies files to staging dirs, rewrites USD asset paths via `UsdUtils.ModifyAssetPaths`
6. **output_injector** — authors `productName` on RenderProduct prims via `Sdf` layer specs
7. **packager** — `stage.Flatten()` → export `.usda` → `UsdUtils.CreateNewUsdzPackage`
8. **wrapper_writer** — creates thin `.usda` that sublayers the USDZ and overrides cache paths
9. **render_script_writer** — generates `run_render.sh` husk launcher with smart defaults and HFS environment sourcing
10. **manifest** — writes human-readable plain-text report
11. **platform_utils** — `imaketx` path resolution, POSIX path normalization, `ensure_dir` with `.placeholder` files (for Google Drive sync)
12. **dependency_resolver** — discovers upstream Remote File Cache nodes via wired + virtual wires, topological sort, DAG formatting for verify display
13. **orchestration_writer** — generates `run_all.sh` sequencing cache jobs then render

**HDA scripts (`hda_scripts/`):**

- `PythonModule.py` — all logic; `_ensure_src_path()` adds repo root to `sys.path` based on HDA library file location
- `btn_verify.py` / `btn_package.py` — one-liners: `hou.phm().on_verify_clicked(kwargs)`
- `OnCreated.py` — auto-wires node into LOP network, sets deep red color and X shape, creates network box

**Output structure:** `$HIP/{shot_name}_P{pod}T{team}_v{NNN}/` with subdirs: `Output/`, `Textures/`, `Cache/`, `Scenes/`, `Scripts/`. The manifest goes into the shot root, not `Scripts/`.

### Remote File Cache (SOP)

**HDA structure:** SOP subnet wrapping an internal `filecache::2.0` node. All essential File Cache parameters are bubbled up via `ch("../parm")` / `chs("../parm")` channel references. Remote packaging parameters are in a separate "Remote Package" tab.

**Pipeline:** validate → create dirs → backup .hip → save portable .hip (with rewritten cache paths) → write cache_info.txt → write run_cache.sh → write manifest.

**Modules:**

1. **cache_validator** — File Cache SOP type check (accepts `filecache::2.0`), frame range, output path validation
2. **cache_auditor** — reads File Cache params into a `CacheAuditReport` dataclass
3. **cache_scene_writer** — saves portable `.hip` with rewritten cache output path, handles expression-driven parms (snapshot/restore), unlocks HDA contents temporarily
4. **cache_script_writer** — generates executable `run_cache.sh` with hython command (not hbatch — `render` only works with ROPs, not filecache SOPs)
5. **cache_info_writer** — writes machine-readable `cache_info.txt`
6. **cache_manifest** — human-readable packaging report

**HDA scripts (`hda_scripts_cache/`):**

- `PythonModule.py` — verify and package callbacks; `_ensure_src_path()` pattern same as render packager
- `btn_verify.py` / `btn_package.py` — one-liners: `hou.phm().on_verify_clicked(kwargs)`
- `OnCreated.py` — auto-wires into SOP network, sets amber color, creates network box

**Key implementation details:**
- Internal filecache1 params are linked via expressions, so `cache_scene_writer` must snapshot expressions (not just values) and restore them after saving
- The HDA contents must be unlocked (`allowEditingOfContents()`) before modifying internal parms, then re-locked (`matchCurrentDefinition()`) after
- The portable `.hip` sets `basedir` to `$HIP/../Cache` so cache output lands in the right place relative to `Scenes/`
- `savebackground` is forced OFF and `loadfromdisk` is forced OFF in the portable `.hip`
- File Cache SOP type is versioned as `filecache::2.0` — validator uses `startswith("filecache")`

**Output structure:** `$HIP/{shot_name}_P{pod}T{team}_v{NNN}/` with subdirs: `Cache/`, `Scenes/`, `Scripts/`.

### Dependency Resolver (combined cache + render)

When the Karma USD Packager runs, it discovers upstream Remote File Cache nodes and offers to bundle their cache jobs into the same package. The resolver works in expanding rings:

1. **Walk LOP inputs** — `node.inputs()` recursion through the LOP network
2. **Cross into SOPs** — via `sopimport` (`soppath` parm), `sopcreate`/`sopmodify` (embedded subnet children)
3. **Walk SOP inputs** — `node.inputs()` recursion through SOP networks
4. **Expand via Object Merges** — follow `objpath1..N` parms to discover cross-geo-container references (fixed-point loop)
5. **Detect virtual wires** — file-on-disk coupling (matching write/read paths), `ch()`/`chs()` cross-network expression refs, `op:`/`hou.node()` in VEX/Python code
6. **Find cache nodes** — filter for `remote_file_cache` HDA instances
7. **Topological sort** — Kahn's algorithm, cycle detection, deterministic output

**Key data structures** (`src/dependency_resolver.py`):
- `CacheableUnit` — node path, filecache path, frame range, output path, dependencies
- `VirtualWire` — source, target, wire type, detail
- `DependencyDAG` — cache units dict, execution order, virtual wires, warnings

**Integration points** (`hda_scripts/PythonModule.py`):
- `on_verify_clicked()` — shows the DAG summary (cache labels, virtual wires, execution order)
- `on_package_clicked()` — resolves dependencies, asks user to confirm, packages caches via `save_portable_hip_multi()`, writes per-cache `run_cache_NNN.sh` scripts, generates `run_all.sh`

**Multi-cache hip save** (`cache_scene_writer.save_portable_hip_multi()`): rewrites all cache nodes in a single `hou.hipFile.save()` call. Each per-cache script loads the same hip but cooks a different filecache node.

**Orchestration** (`src/orchestration_writer.py`): generates `run_all.sh` that sequences cache scripts in dependency order then runs the render script. Serial execution, `set -e` for fail-fast.

### Mantra Render Packager (ROP)

**HDA structure:** ROP subnet wrapping an internal Mantra ROP (`ifd`) node. All essential Mantra parameters are bubbled up via channel references. Remote packaging parameters are in a separate "Remote Package" tab.

**Pipeline:** validate → create dirs → backup .hip → save portable .hip (with rewritten `vm_picture`) → write render_info.txt → write run_render.sh → write manifest.

**Modules:**

1. **mantra_validator** — Mantra ROP type check (accepts `ifd` and versioned variants), output picture validation. Reuses `validate_frame_range()` from `cache_validator.py`.
2. **mantra_auditor** — reads Mantra ROP params into a `MantraAuditReport` dataclass (resolution, samples, camera, render engine, AOVs)
3. **mantra_scene_writer** — saves portable `.hip` with rewritten `vm_picture` pointing to `$HIP/../Output/`. Reuses `backup_hip_as_zip()` from `cache_scene_writer.py`.
4. **mantra_script_writer** — generates executable `run_render.sh` using `hbatch -c "render -Va -f start end inc rop_path"`. The script `cd`s into `Scenes/` so `$HIP/../Output/` resolves correctly.
5. **mantra_info_writer** — writes machine-readable `render_info.txt` with renderer=mantra, resolution, samples, camera, etc.
6. **mantra_manifest** — human-readable packaging report with render-specific sections

**HDA scripts (`hda_scripts_mantra/`):**

- `PythonModule.py` — verify and package callbacks; `_ensure_src_path()` pattern same as other packagers
- `btn_verify.py` / `btn_package.py` — one-liners: `hou.phm().on_verify_clicked(kwargs)`
- `OnCreated.py` — auto-wires into ROP network, sets forest green color `(0.2, 0.6, 0.3)`, creates network box

**Key implementation details:**
- Uses `hbatch` (not `hython` or `husk`) because Mantra is a ROP — `hbatch` natively supports `render -f` commands
- Mantra's node type is `ifd` — validator uses `startswith("ifd")`
- Only rewrites `vm_picture` in v1; AOV paths typically derive from `vm_picture` via expressions
- The render script `cd`s into `Scenes/` so `$HIP/../Output/` resolves to the package's `Output/` directory

**Output structure:** `$HIP/{shot_name}_P{pod}T{team}_v{NNN}/` with subdirs: `Output/`, `Scenes/`, `Scripts/`.

## Shared modules

- **`validator.py`** — `validate_shot_name()` and `validate_hip_saved()` are used by all HDAs
- **`platform_utils.py`** — `ensure_dir()`, `normalize_path()`, `check_disk_space()` are used by all HDAs
- **`cache_validator.py`** — `validate_frame_range()` is reused by the Mantra packager
- **`cache_scene_writer.py`** — `backup_hip_as_zip()` is reused by the Mantra packager; `save_portable_hip_multi()` is used by the Karma packager for combined cache+render packaging
- **`dependency_resolver.py`** — DAG discovery and topological sort, used by the Karma packager to find upstream cache nodes
- **`orchestration_writer.py`** — `run_all.sh` generation, used by the Karma packager for combined packaging

## Deliverable = HDA + src/

The `.hdalc` files are the deliverable artifact — they are installed on other people's machines. The HDAs load `src/` modules at runtime via `_ensure_src_path()`, which resolves the repo root relative to the HDA library file. This means **any change to `src/` files is only effective if the updated `src/` directory is delivered alongside the HDA**. Editing `src/` locally without updating the HDA on disk is a local-only fix that won't reach other users. After changing any code (whether in `hda_scripts*/` or `src/`), always save the HDA definition to disk so the `.hdalc` is current.

## USD API gotchas

- `stage.Flatten()` returns `Sdf.Layer`, not `Usd.Stage`
- `UsdRender.Settings.GetResolutionAttr().Set()` takes `Gf.Vec2i`, not a tuple
- `UsdZip` module does not exist in this Houdini build — use `UsdUtils.CreateNewUsdzPackage`
- `CreateNewUsdzPackage` bundles all referenced assets — they must exist on disk
- Texture tool is `imaketx` (`$HFS/bin/imaketx`), not `maketx`. Output formats: OpenEXR, RAT, TIFF (no `.tx`)
- **husk resolves `productName` paths relative to CWD**, not the USD file location. The render script must `cd Scenes/` before calling husk so that `../Output/` resolves correctly to the shot root's `Output/` directory.
- husk frame range flags: `-f START -n COUNT -i INC` (not `-f START END`)

## Testing patterns

- Tests use `pytest.mark.houdini` to separate CI-safe tests from those requiring a live Houdini session
- `conftest.py` is not used; tests import directly from `src.*`
- Some tests in files marked `pytestmark = pytest.mark.houdini` contain non-Houdini test classes that still get skipped in CI
- Dummy textures in `tests/textures/` are gitignored and needed for USDZ packaging tests
