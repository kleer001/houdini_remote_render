# Houdini Remote Render & Cache

A collection of Houdini HDAs that package scenes for remote execution — rendering, simulation caching, and more.

## HDAs

### Karma USD Packager (LOP)

Packages a Solaris/LOP stage into a self-contained USDZ archive for remote rendering.

- **Context:** LOPs (Solaris)
- **File:** `hda/karma_usd_packager.hdalc`
- **Node color:** Teal

Takes a LOP stage and produces:
- A flattened `.usdz` archive with all textures bundled
- A thin `.usda` wrapper that references the USDZ and any external caches
- A human-readable manifest documenting what was packaged
- A `render_info.txt` with frame range and USD filename for farm scripts

The HDA is a pass-through node — it doesn't modify your live stage. Drop it between your scene and your Karma ROP, set a shot name, and hit Package.

**Usage:**
1. Wire the node into your LOP network before your Karma ROP
2. Set the **Shot Name** (and pod/team/version)
3. Click **Verify** to dry-run and check for issues
4. Click **Package** to produce the USDZ, wrapper, and manifest

### Remote File Cache (SOP)

Wraps a File Cache SOP with remote packaging. Use it as a drop-in replacement for File Cache — same parameters, same workflow — plus a "Package for Remote" button that bundles everything needed to run the cache on another machine via `hbatch`.

- **Context:** SOPs
- **File:** `hda/remote_file_cache.hdalc`
- **Node color:** Amber

Produces:
- A portable `.hip` file with cache output paths rewritten for the remote folder structure
- A `run_cache.sh` script that executes the cache via `hbatch`
- A `cache_info.txt` with frame range, node path, and format metadata
- A human-readable manifest
- A zip backup of the original `.hip`

**Usage:**
1. Drop the node into your SOP network (replaces a File Cache SOP)
2. Wire your geometry into it, configure caching as normal
3. Go to the **Remote Package** tab, set **Shot Name** (and pod/team/version)
4. Click **Verify**, then **Package for Remote**
5. Upload the output folder to your remote machine and run `Scripts/run_cache.sh`

### Mantra / Redshift ROPs (planned)

Remote packaging for Mantra and Redshift render jobs. Coming soon.

## Output Structure

Both HDAs produce a self-contained folder at `$HIP/{shot_name}_P{pod}T{team}_v{NNN}/`:

**Karma USD Packager:**
```
Output/              — Rendered frames land here
Textures/            — Converted textures
Cache/               — External caches (VDB, bgeo.sc, Alembic)
Scenes/              — USDZ archive + .usda wrapper + render_info.txt
{shot}_manifest.txt  — Human-readable report
{shot}.hip.zip       — HIP backup
```

**Remote File Cache:**
```
Cache/               — Cache output lands here when run remotely
Scenes/              — Portable .hip file
Scripts/             — hbatch launch script (run_cache.sh)
cache_info.txt       — Machine-readable metadata
{shot}_manifest.txt  — Human-readable report
{shot}_original.hip.zip — HIP backup
```

## Requirements

- Houdini 21.0+ (Indie or Commercial)
- Python 3.10+ (Houdini-bundled)
- Git (for automatic install)

## Installation

### Automatic (recommended)

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.ps1 | iex
```

This clones the repository, detects your Houdini installation(s), and registers the HDAs using Houdini's [package system](https://www.sidefx.com/docs/houdini/ref/plugins.html). No files are copied — HDAs are loaded directly from the repository.

**If you already have the repository cloned:**
```bash
python install.py                   # Install for all Houdini versions
python install.py --version 21.0    # Install for a specific version
python install.py --status          # Check install status
python install.py --uninstall       # Remove
```

### Manual

If you prefer not to use the installer, you have two options:

**Option A — Houdini package file (recommended):**

Create a JSON file at `$HOUDINI_USER_PREF_DIR/packages/houdini_remote_render.json`:

```json
{
    "env": [
        {
            "HOUDINI_OTLSCAN_PATH": {
                "value": "/path/to/houdini_remote_render/hda",
                "method": "append"
            }
        }
    ],
    "path": "/path/to/houdini_remote_render"
}
```

Replace `/path/to/houdini_remote_render` with the actual path to this repository.

`$HOUDINI_USER_PREF_DIR` is:
- **Linux:** `~/houdini21.0/`
- **macOS:** `~/Library/Preferences/houdini/21.0/`
- **Windows:** `%USERPROFILE%\Documents\houdini21.0\`

**Option B — houdini.env:**

Add to `$HOUDINI_USER_PREF_DIR/houdini.env`:

```
HOUDINI_OTLSCAN_PATH = /path/to/houdini_remote_render/hda:&
```

The `:&` appends to the existing scan path rather than replacing it. On Windows use `;` instead of `:`.

### After installation

Restart Houdini. The HDAs appear as:
- **Karma USD Packager** — Tab menu in any LOP network
- **Remote File Cache** — Tab menu in any SOP network

## Pipeline Modules

### Karma USD Packager

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

### Remote File Cache

| Module | Purpose |
|---|---|
| `cache_validator` | File Cache SOP existence and parameter checks |
| `cache_auditor` | Read File Cache params into structured report |
| `cache_scene_writer` | Save portable `.hip` with rewritten cache paths |
| `cache_script_writer` | Generate `run_cache.sh` hbatch launcher |
| `cache_info_writer` | Write machine-readable `cache_info.txt` |
| `cache_manifest` | Human-readable packaging report |

### Shared

| Module | Purpose |
|---|---|
| `validator` | Shot name validation, HIP saved check (shared) |
| `platform_utils` | Path normalization, `ensure_dir`, disk space check (shared) |

## Testing

```bash
# CI tests (no Houdini required) — 83 tests
pytest -m "not houdini"

# Full tests (requires live Houdini session)
pytest
```

Tests marked `@pytest.mark.houdini` require a running Houdini instance and are skipped in CI.

## License

MIT
