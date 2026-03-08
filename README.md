# Karma USD Packager

A Houdini LOP HDA that packages USD scenes into self-contained USDZ archives for remote rendering.

## What It Does

Takes a Solaris/LOP stage and produces:
- A flattened `.usdz` archive with all textures bundled
- A thin `.usda` wrapper that references the USDZ and any external caches
- A human-readable manifest documenting what was packaged

The HDA is a pass-through node — it doesn't modify your live stage. Drop it between your scene and your Karma ROP, set a shot name, and hit Package.

## Requirements

- Houdini 21.0+ (Indie or Commercial)
- Python 3.10+ (Houdini-bundled)

## Installation

1. Copy `hda/karma_usd_packager.hdalc` into your Houdini HDA path (e.g. `$HOUDINI_USER_PREF_DIR/otls/`)
2. The node appears under **Tab > Rendering > Karma USD Packager** in any LOP network

## Usage

1. Wire the node into your LOP network before your Karma ROP
2. Set the **Shot Name**
3. Click **Verify** to dry-run and check for issues
4. Click **Package & Stage** to produce the USDZ, wrapper, and manifest

Output goes into `$HIP/{shot_name}/`:
- `Output/` — rendered frames (e.g. `SHOT.1001.png`)
- `Textures/` — converted textures
- `Cache/` — external caches (VDB, bgeo.sc, Alembic)
- `Scenes/` — USDZ archive + `.usda` wrapper
- `Scripts/` — manifest

### Output Format

The **Output Format** menu (Options tab) controls the rendered image format:

- **PNG** (default) — smaller files, viewable everywhere
- **OpenEXR** — preserves HDR data and multiple AOVs for compositing

If Verify detects extra AOVs beyond the beauty pass, the format auto-switches to EXR since PNG can only store a single image layer.

### Frame Numbering

Rendered filenames use the pattern `{shot_name}.<F4>.{ext}` (e.g. `TNIS0012.1203.exr`). The `<F4>` token is a husk-native frame variable — it gets expanded to the zero-padded frame number at render time. This works with both `husk` (direct) and `hbatch` (farm) workflows.

## Pipeline Modules

| Module | Purpose |
|---|---|
| `validator` | Shot name, HIP file, and directory structure checks |
| `auditor` | USD stage inspection — render settings, camera, products, instances |
| `classifier` | Dependency scanning and UDIM detection |
| `converter` | Texture conversion via `imaketx` |
| `gatherer` | File copying and USD path rewriting |
| `output_injector` | RenderProduct output path authoring (format + frame tokens) |
| `packager` | Stage flatten + USDZ creation |
| `wrapper_writer` | Thin `.usda` wrapper with cache references |
| `manifest` | Human-readable packaging report |

## Testing

```bash
# CI tests (no Houdini required)
pytest -m "not houdini"

# Full tests (requires live Houdini session)
pytest
```

Tests marked `@pytest.mark.houdini` require a running Houdini instance and are skipped in CI.

## License

MIT
