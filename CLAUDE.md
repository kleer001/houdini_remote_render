# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Also follow the behavioral guidelines in [CLAUDE_GENERIC.md](./CLAUDE_GENERIC.md).

## Project Overview

Karma USD Packager — a Houdini LOP HDA that packages USD scenes into self-contained USDZ archives for remote rendering. The HDA is a pass-through node: it doesn't modify the live stage. It flattens the stage, creates a USDZ archive with bundled textures, writes a thin `.usda` wrapper referencing external caches, and generates a manifest.

**Environment:** Houdini 21.0+ (Indie license, `.hdalc` extension), Python 3.11+, Linux. HFS at `/opt/hfs21.0.631`.

## Commands

```bash
# Run CI tests (no Houdini required) — 35 tests
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

### Two entry points into the same pipeline

1. **`src/main.py:run_pipeline()`** — headless entry point. Takes a `Usd.Stage`, shot name, and hip dir. Used for scripted/batch packaging.

2. **`hda_scripts/PythonModule.py`** — HDA callbacks (`on_verify_clicked`, `on_package_clicked`). These replicate the pipeline steps inline (not calling `run_pipeline`) because they need granular control over the UI: per-step log messages, `hou.ui.displayMessage` dialogs, confirmation prompts, and writing to the `log_output` parameter.

Both follow the same sequence: validate → audit → create dirs → inject output paths → flatten & USDZ → write wrapper → write manifest.

### Module pipeline (in execution order)

`src/` modules are pure-logic with no `hou` imports at module level (they import `hou` and `pxr` lazily inside functions). This enables CI testing without Houdini.

1. **validator** — shot name regex, HIP file saved check, directory structure check, ROP connection check
2. **auditor** — traverses stage for RenderSettings/Camera/RenderProduct prims, counts PointInstancer instances, authors fallback RenderSettings if missing
3. **classifier** — `UsdUtils.ComputeAllDependencies` to bucket files into textures/caches/sublayers, UDIM pattern detection
4. **converter** — `imaketx` subprocess calls for texture conversion (NOT `maketx` — it doesn't exist in this Houdini build)
5. **gatherer** — copies files to staging dirs, rewrites USD asset paths via `UsdUtils.ModifyAssetPaths`
6. **output_injector** — authors `productName` on RenderProduct prims via `Sdf` layer specs
7. **packager** — `stage.Flatten()` → export `.usda` → `UsdUtils.CreateNewUsdzPackage`
8. **wrapper_writer** — creates thin `.usda` that sublayers the USDZ and overrides cache paths
9. **manifest** — writes human-readable plain-text report
10. **platform_utils** — `imaketx` path resolution, POSIX path normalization, `ensure_dir` with `.placeholder` files (for Google Drive sync)

### HDA scripts (`hda_scripts/`)

- `PythonModule.py` — all logic; `_ensure_src_path()` adds repo root to `sys.path` based on HDA library file location
- `btn_verify.py` / `btn_package.py` — one-liners: `hou.phm().on_verify_clicked(kwargs)`
- `OnCreated.py` — auto-wires node into LOP network, sets teal color, creates network box

### Output structure

Packaging creates `$HIP/{shot_name}/` with subdirs: `Output/`, `Textures/`, `Cache/`, `Scenes/`, `Scripts/`. The manifest goes into the shot root, not `Scripts/`.

## USD API gotchas

- `stage.Flatten()` returns `Sdf.Layer`, not `Usd.Stage`
- `UsdRender.Settings.GetResolutionAttr().Set()` takes `Gf.Vec2i`, not a tuple
- `UsdZip` module does not exist in this Houdini build — use `UsdUtils.CreateNewUsdzPackage`
- `CreateNewUsdzPackage` bundles all referenced assets — they must exist on disk
- Texture tool is `imaketx` (`$HFS/bin/imaketx`), not `maketx`. Output formats: OpenEXR, RAT, TIFF (no `.tx`)

## Testing patterns

- Tests use `pytest.mark.houdini` to separate CI-safe tests from those requiring a live Houdini session
- `conftest.py` is not used; tests import directly from `src.*`
- Some tests in files marked `pytestmark = pytest.mark.houdini` contain non-Houdini test classes that still get skipped in CI
- Dummy textures in `tests/textures/` are gitignored and needed for USDZ packaging tests
