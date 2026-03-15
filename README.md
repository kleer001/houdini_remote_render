# Houdini Remote Render & Cache

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Houdini 21.0+](https://img.shields.io/badge/Houdini-21.0+-orange.svg)](https://www.sidefx.com/products/houdini/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-103%20CI%20%2B%206%20render-brightgreen.svg)](#testing)

Package Houdini USD scenes into self-contained archives that render anywhere — no shared filesystems, no farm managers, no missing textures.

Drop an HDA into your network, click Package, copy the folder to any machine with Houdini, run `./Scripts/run_render.sh`. Done.

## Why this exists

Sending a Karma render to another machine shouldn't require Deadline, a shared NFS mount, or 45 minutes of path debugging. Existing tools either:

- **Collect .hip files** but don't understand USD ([HipCollector](https://github.com/Aeoll/HipCollector))
- **Submit husk jobs** but assume shared filesystems ([HuskSubmitter](https://github.com/Tronotrond/HuskSubmitter))
- **Require pipeline infrastructure** (AYON, ShotGrid, Deadline)

This project packages everything into a portable folder: USDZ with bundled textures, a ready-to-run render script with smart defaults, and a manifest documenting what's inside. Copy it via Google Drive, Dropbox, USB stick, `scp`, or carrier pigeon.

## Quick Start

```bash
# 1. Install (one command)
curl -fsSL https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.sh | bash

# 2. Restart Houdini, drop "Karma USD Packager" into your LOP network

# 3. Set shot name, click Verify, click Package

# 4. Copy the output folder to your render machine and run:
cd SHOT_NAME_P1T1_v001
bash Scripts/run_render.sh
```

## What the packager handles

The HDA audits your scene, warns about potential issues, then bundles everything:

| Problem | What the packager does |
|---|---|
| `.rat` textures not valid in USDZ | Auto-converts to `.exr` |
| `op:` COP textures are runtime-only | Bakes to PNG via render node |
| `op:` SOP geometry paths | Exports to `.usdc` via temp SOP Import |
| `opdef:` VEX shader URIs | Bakes source into USDZ, restores `opdef:` in wrapper |
| `<UDIM>` patterns can't resolve inside USDZ | Extracts tiles as loose files |
| No lights in scene | Warns that render will be black (husk has no default headlight) |
| Missing AOVs | Warns that husk will render black without Beauty AOV |
| Camera mismatch | Warns if RenderSettings camera doesn't exist |

The generated `run_render.sh` includes smart defaults:

- `--restart-delegate 1` auto-added for frame sequences (prevents memory accumulation)
- `--make-output-path` always included
- `--headlight none` always included (prevents phantom headlight)
- Houdini environment auto-sourced from `$HFS`

## Verified render aspects

All features below have been tested end-to-end: build in Houdini, package with the HDA, render with standalone `husk`, verify output. See [Supported Render Aspects](docs/SUPPORTED_RENDER_ASPECTS.md) for details.

**Textures:** file textures, .rat auto-conversion, UDIM sets, COP procedurals, HDRI environment maps
**Materials:** MaterialX (recommended), UsdPreviewSurface, PrincipledShader (VEX, requires Houdini on render machine)
**Geometry:** volumes (VDB/fog), animated deformation, subdivision surfaces, point instances, Alembic references, time-varying topology, nested instancing
**Lighting:** dome/rect/sphere/spot lights, color temperature, per-object visibility, matte/holdout
**Motion blur:** velocity blur, deformation blur, camera motion blur
**Render script:** single-frame, multi-frame sequences, XPU (MaterialX only), all major husk flags

## Installation

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.ps1 | iex
```

The script checks for prerequisites (git, Python 3, Houdini), clones the repo, and registers the HDAs using Houdini's [package system](https://www.sidefx.com/docs/houdini/ref/plugins.html). If anything is missing it tells you exactly what to install and how. No files are copied — HDAs are loaded directly from the repository.

Restart Houdini after installing. The HDAs appear in the Tab menu:
- **Karma USD Packager** — any LOP network
- **Remote File Cache** — any SOP network

### Prerequisites

The bootstrap script handles all of this, but if you're setting things up by hand:

- **Houdini 21.0+** (Indie or Commercial) — must be launched at least once so the preferences directory exists
- **Git** — [git-scm.com](https://git-scm.com/) or your OS package manager
- **Python 3.10+** — your OS package manager, or Houdini's bundled Python (`$HFS/python/bin/python3`)

<details>
<summary>Manual installation (without the bootstrap script)</summary>

#### Step 1 — Clone the repository

```bash
git clone https://github.com/kleer001/houdini_remote_render.git
cd houdini_remote_render
```

#### Step 2 — Register the HDAs

You have two options. Pick one.

**Option A — Run the installer (recommended):**

```bash
python install.py
```

This auto-detects all Houdini versions on your system and creates a package file for each one.

**Option B — Create the package file by hand:**

Create `houdini_remote_render.json` in your Houdini packages directory:

| OS | Packages directory |
|---|---|
| **Linux** | `~/houdini21.0/packages/` |
| **macOS** | `~/Library/Preferences/houdini/21.0/packages/` |
| **Windows** | `%USERPROFILE%\Documents\houdini21.0\packages\` |

Contents:
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

Replace `/path/to/houdini_remote_render` with the actual path where you cloned the repo. Create the `packages/` directory if it doesn't exist.

**Alternative — houdini.env (not recommended):**

Add to `$HOUDINI_USER_PREF_DIR/houdini.env`:

```
HOUDINI_OTLSCAN_PATH = /path/to/houdini_remote_render/hda:&
```

The `:&` appends to the existing scan path. On Windows use `;` instead of `:`.

#### Step 3 — Restart Houdini

The HDAs appear in the Tab menu after restarting.

#### Managing an existing install

If you already have the repository cloned:
```bash
python install.py                   # Install for all Houdini versions
python install.py --version 21.0    # Install for a specific version
python install.py --status          # Check install status
python install.py --uninstall       # Remove
```

</details>

## Updating

HDAs load directly from the cloned repo, so updating is just a `git pull`:

```bash
cd /path/to/houdini_remote_render
git pull
```

Restart Houdini to pick up any changes.

## HDAs

### Karma USD Packager (LOP)

Packages a Solaris/LOP stage into a self-contained USDZ archive for remote rendering with standalone `husk`.

- **Context:** LOPs (Solaris)
- **File:** `hda/karma_usd_packager.hdalc`
- **Node color:** Deep red (X shape)

The HDA is a pass-through node — it doesn't modify your live stage. Drop it between your scene and your Karma ROP, set a shot name, and hit Package.

**Usage:**
1. Wire the node into your LOP network before your Karma ROP
2. Set the **Shot Name** (and pod/team/version)
3. Click **Verify** to dry-run and check for issues
4. Click **Package** to produce the USDZ, wrapper, render script, and manifest
5. Copy the output folder to your render machine
6. Run `bash Scripts/run_render.sh`

**Output structure** (`$HIP/{shot_name}_P{pod}T{team}_v{NNN}/`):
```
Output/              — Rendered frames land here
Textures/            — Converted textures and UDIM tiles
Cache/               — External caches (VDB, bgeo.sc, Alembic)
Scenes/              — USDZ archive + .usda wrapper
Scripts/             — run_render.sh (husk launcher)
render_info.txt      — Frame range and USD filename
{shot}_manifest.txt  — Human-readable packaging report
{shot}.hip.zip       — HIP backup
```

### Remote File Cache (SOP)

Wraps a File Cache SOP with remote packaging. Use it as a drop-in replacement for File Cache — same parameters, same workflow — plus a "Package for Remote" button that bundles everything needed to run the cache on another machine via `hbatch`.

- **Context:** SOPs
- **File:** `hda/remote_file_cache.hdalc`
- **Node color:** Amber

**Usage:**
1. Drop the node into your SOP network (replaces a File Cache SOP)
2. Wire your geometry into it, configure caching as normal
3. Go to the **Remote Package** tab, set **Shot Name** (and pod/team/version)
4. Click **Verify**, then **Package for Remote**
5. Upload the output folder to your remote machine and run `Scripts/run_cache.sh`

**Output structure** (`$HIP/{shot_name}_P{pod}T{team}_v{NNN}/`):
```
Cache/               — Cache output lands here when run remotely
Scenes/              — Portable .hip file
Scripts/             — hbatch launch script (run_cache.sh)
cache_info.txt       — Machine-readable metadata
{shot}_manifest.txt  — Human-readable report
{shot}_original.hip.zip — HIP backup
```

### Mantra / Redshift ROPs (planned)

Remote packaging for Mantra and Redshift render jobs. Coming soon.

## Testing

```bash
# CI tests (no Houdini required) — 103 tests
pytest -m "not houdini"

# Render integration tests (requires $HFS) — 6 tests that invoke husk
export HFS=/opt/hfs21.0.631
pytest tests/test_render_integration.py -v

# All tests
export HFS=/opt/hfs21.0.631
pytest
```

The render integration tests create a minimal USD scene, generate `run_render.sh`, execute it with standalone `husk`, and verify the output EXR. See [Render Integration Tests](docs/render_integration_tests.md) for details.

## Documentation

- [Supported Render Aspects](docs/SUPPORTED_RENDER_ASPECTS.md) — every verified rendering feature with references
- [Pipeline Modules](docs/pipeline_modules.md) — internal module architecture
- [Render Integration Tests](docs/render_integration_tests.md) — automated husk test guide

## License

[MIT](LICENSE)
